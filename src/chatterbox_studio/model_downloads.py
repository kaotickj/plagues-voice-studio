"""Model catalogue and explicit on-demand downloads (no ML imports at startup).

Chatterbox models are stored in writable per-user data, never in the
PyInstaller read-only bundle. Qwen models use the configured Qwen interpreter's
normal Hugging Face cache, preserving existing downloads and environments.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from fnmatch import fnmatch
import os
import subprocess
import time

from .paths import bundled_models_dir, canonical_data_dir, legacy_v030_dir
from plagued_ai import root as shared_root, previous_studio_dir
from .optional_engines import (
    EngineCancelled, EngineError, EngineRegistry, _spawn_optional_interpreter,
    _stop_process, _watch_engine_process,
)


@dataclass(frozen=True)
class ModelChoice:
    key: str
    label: str
    family: str
    repo: str
    required: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()


CATALOG: tuple[ModelChoice, ...] = (
    ModelChoice('nano', 'Chatterbox Nano', 'chatterbox', 'ResembleAI/chatterbox-nano',
                ('ve.safetensors', 't3_nano_v1.safetensors', 's3gen_meanflow.safetensors', 'tokenizer_config.json'),
                ('ve.safetensors', 't3_nano_v1.safetensors', 's3gen_meanflow.safetensors',
                 '*.json', '*.txt', '*.pt', '*.model')),
    ModelChoice('turbo', 'Chatterbox Turbo', 'chatterbox', 'ResembleAI/chatterbox-turbo',
                ('ve.safetensors', 't3_turbo_v1.safetensors', 's3gen_meanflow.safetensors', 'tokenizer_config.json'),
                ('ve.safetensors', 't3_turbo_v1.safetensors', 's3gen_meanflow.safetensors',
                 '*.json', '*.txt', '*.pt', '*.model')),
    ModelChoice('english', 'Chatterbox Original English', 'chatterbox', 'ResembleAI/chatterbox',
                ('ve.safetensors', 't3_cfg.safetensors', 's3gen.safetensors', 'tokenizer.json', 'conds.pt'),
                ('ve.safetensors', 't3_cfg.safetensors', 's3gen.safetensors', 'tokenizer.json', 'conds.pt')),
    ModelChoice('multilingual-v3', 'Chatterbox Multilingual V3', 'chatterbox', 'ResembleAI/chatterbox',
                ('ve.pt', 's3gen.pt', 'conds.pt', 't3_mtl23ls_v3.safetensors',
                 'grapheme_mtl_merged_expanded_v1.json', 'Cangjie5_TC.json'),
                ('ve.pt', 's3gen.pt', 'conds.pt', 't3_mtl23ls_v3.safetensors',
                 'grapheme_mtl_merged_expanded_v1.json', 'Cangjie5_TC.json')),
    ModelChoice('qwen-0.6b', 'Qwen3-TTS Base 0.6B', 'qwen3', 'Qwen/Qwen3-TTS-12Hz-0.6B-Base'),
    ModelChoice('qwen-1.7b', 'Qwen3-TTS Base 1.7B', 'qwen3', 'Qwen/Qwen3-TTS-12Hz-1.7B-Base'),
)
MODELS = {model.key: model for model in CATALOG}


def user_model_directory(storage: Path, key: str) -> Path:
    if Path(storage) == canonical_data_dir():
        return shared_root()/'models'/'chatterbox'/key
    return Path(storage) / 'models' / key


def legacy_model_directory(storage: Path, key: str, *, errors: list[str] | None = None) -> Path | None:
    """Old model weights are reused read-only when running from canonical storage."""
    if Path(storage) != canonical_data_dir():
        return None
    path = legacy_v030_dir() / "models" / key
    try:
        return path if path.is_dir() else None
    except OSError as exc:
        _record_access_error(path, exc, errors)
        return None


def installed_model_directory(storage: Path, model: ModelChoice, *, errors: list[str] | None = None) -> Path | None:
    """Choose complete current or legacy weights; never use partial downloads."""
    current = user_model_directory(storage, model.key)
    if has_required_files(current, model, errors=errors):
        return current
    for previous in (Path(storage)/'models'/model.key, previous_studio_dir()/'models'/model.key):
        if Path(storage) == canonical_data_dir() and has_required_files(previous, model, errors=errors):
            return previous
    legacy = legacy_model_directory(storage, model.key, errors=errors)
    if legacy is not None and has_required_files(legacy, model, errors=errors):
        return legacy
    return None


def _record_access_error(path: Path, exc: OSError, errors: list[str] | None) -> None:
    # Never resolve, repair or traverse around an OS-denied mount/reparse point.
    if errors is not None:
        message = f'{path}: {exc}'
        if message not in errors:
            errors.append(message)


def _nonempty_file(path: Path, *, errors: list[str] | None = None) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError as exc:
        _record_access_error(path, exc, errors)
        return False


def _has_gpt2_tokenizer(folder: Path, *, errors: list[str] | None = None) -> bool:
    # The pinned backend supports both self-contained fast JSON and GPT-2's
    # vocabulary/merges representation. Config alone cannot tokenize speech.
    return (_nonempty_file(folder / 'tokenizer.json', errors=errors) or
            (_nonempty_file(folder / 'vocab.json', errors=errors) and _nonempty_file(folder / 'merges.txt', errors=errors)))


def has_required_files(folder: Path, model: ModelChoice, *, errors: list[str] | None = None) -> bool:
    return (bool(model.required) and all(_nonempty_file(folder / name, errors=errors) for name in model.required)
            and (model.key not in ('nano', 'turbo') or _has_gpt2_tokenizer(folder, errors=errors)))


def chatterbox_status(storage: Path, model: ModelChoice) -> str:
    if model.family != 'chatterbox':
        raise ValueError('Chatterbox status requires a Chatterbox model')
    errors: list[str] = []
    selected = installed_model_directory(storage, model, errors=errors)
    if model.key == 'multilingual-v3' and (selected is not None or has_required_files(bundled_models_dir()/model.key, model, errors=errors)):
        from .tokenizer_assets import installed_pkuseg
        try:
            tokenizer = installed_pkuseg(storage)
        except OSError as exc:
            return f'Tokenizer location unavailable: {exc}'
        if tokenizer is None:
            return 'Tokenizer download required (select Download to repair)'
    if selected is not None:
        return ('Installed (previous v0.3 data)' if
                Path(storage) == canonical_data_dir() and selected == legacy_v030_dir() / 'models' / model.key
                else 'Installed (user data)')
    if has_required_files(bundled_models_dir() / model.key, model, errors=errors):
        return 'Included with application'
    if errors:
        return 'Model location unavailable: ' + '; '.join(errors)
    return 'Download available'


def qwen_python(storage: Path) -> str:
    from .optional_engines import is_interpreter
    try:
        saved = EngineRegistry(storage).read()['qwen3']['python']
    except (EngineError, OSError):
        saved = ''
    def available(candidate):
        try:
            return is_interpreter(candidate)
        except OSError:
            return False
    if available(saved):
        return saved
    py_path = ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    folders = [Path(storage) / 'engines' / 'qwen3']
    if Path(storage) == canonical_data_dir():
        folders.append(legacy_v030_dir() / 'engines' / 'qwen3')
    for folder in folders:
        candidate = folder / py_path
        if available(str(candidate)):
            return str(candidate)
    return ''


def download_chatterbox(model: ModelChoice, storage: Path, cancelled: Event, log) -> Path:
    """Download into writable storage; incomplete models are never selected for inference.

    Cancellation is cooperative after an in-progress Hub transfer; unlike Qwen
    subprocess cancellation, a Hugging Face thread cannot be safely killed.
    """
    if model.family != 'chatterbox':
        raise ValueError('Not a Chatterbox model')
    target = user_model_directory(storage, model.key)
    if cancelled.is_set():
        raise EngineCancelled('Cancelled')
    errors: list[str] = []
    installed = installed_model_directory(storage, model, errors=errors)
    if model.key == 'multilingual-v3' and installed is None and has_required_files(bundled_models_dir()/model.key, model, errors=errors):
        installed = bundled_models_dir()/model.key
    if installed is not None:
        if model.key == 'multilingual-v3':
            from .tokenizer_assets import ensure_multilingual_assets
            ensure_multilingual_assets(storage, cancelled, log)
        log(f'This Chatterbox model is already available at {installed}. No download needed.')
        return installed
    if errors:
        raise EngineError('Model location unavailable; no download started: ' + '; '.join(errors))
    if has_required_files(target, model):
        log('This Chatterbox model is already downloaded.')
        return target
    log(f'Downloading {model.label} from {model.repo}...')
    log(f'Destination: {target}')
    log('Stop takes effect between individual file downloads.')
    target.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import hf_hub_download, list_repo_files  # Lazy import.
    available = list_repo_files(model.repo)
    wanted = [name for name in available if any(fnmatch(name, pattern) for pattern in model.patterns)]
    if not wanted:
        raise EngineError(f'No downloadable files matched {model.label}. Check the upstream repository.')
    for number, filename in enumerate(wanted, 1):
        if cancelled.is_set():
            raise EngineCancelled('Cancelled. Already-downloaded files can be reused on retry.')
        log(f'File {number}/{len(wanted)}: {filename}')
        hf_hub_download(repo_id=model.repo, filename=filename, local_dir=target)
    if cancelled.is_set():
        raise EngineCancelled('Cancelled after the current transfer. Partial files may be reused on retry.')
    if not has_required_files(target, model):
        missing = [f for f in model.required if not _nonempty_file(target / f)]
        if model.key in ('nano', 'turbo') and not _has_gpt2_tokenizer(target):
            missing.append('tokenizer.json or both vocab.json and merges.txt')
        raise EngineError(f'{model.label}: download incomplete, missing/empty {missing}')
    if model.key == 'multilingual-v3':
        from .tokenizer_assets import ensure_multilingual_assets
        ensure_multilingual_assets(storage, cancelled, log)
    log(f'Installed {model.label} in {target}')
    return target


# Runs only inside a separately installed Qwen Python interpreter.
# No model weights or packages are installed into the Chatterbox application.
_QWEN_SCRIPT = '''import sys
from pathlib import Path
from huggingface_hub import snapshot_download
from huggingface_hub.constants import HF_HUB_CACHE
import shutil

repo, operation = sys.argv[1], sys.argv[2]
# A cached Hub revision is NOT evidence that multi-GB model weights are complete.
# Verify both speech-tokenizer and primary weight files before claiming readiness.
required = ("config.json", "model.safetensors", "tokenizer_config.json",
            "vocab.json", "merges.txt", "generation_config.json",
            "preprocessor_config.json", "speech_tokenizer/config.json",
            "speech_tokenizer/model.safetensors", "speech_tokenizer/preprocessor_config.json")

def verify(path):
    root = Path(path)
    missing = []
    for filename in required:
        item = root / filename
        minimum = 1024 if filename.endswith(".safetensors") else 1
        if not item.is_file() or item.stat().st_size < minimum:
            missing.append(filename)
    if missing:
        raise RuntimeError("Incomplete Qwen model snapshot; missing/empty files: " + ", ".join(missing))
    print("PVS_MODEL_VERIFIED " + str(root), flush=True)
    return root

if operation == 'check':
    try:
        path = snapshot_download(repo_id=repo, local_files_only=True)
        verify(path)
        print('PVS_CACHE_FOUND', flush=True)
    except Exception as exc:
        print("PVS_CACHE_INCOMPLETE " + str(exc), flush=True)
        print('PVS_CACHE_MISSING', flush=True)
elif operation == 'download':
    cache = Path(HF_HUB_CACHE)
    disk = next((p for p in (cache, cache.parent, Path.home()) if p.exists()), Path.home())
    free_gib = shutil.disk_usage(disk).free / (1024 ** 3)
    print("PVS_CACHE_VOLUME_FREE_GIB " + format(free_gib, '.2f'), flush=True)
    print("PVS_DOWNLOADING " + repo, flush=True)
    # Resume files already in the cache; never delete user models automatically.
    path = snapshot_download(repo_id=repo, max_workers=1)
    verify(path)
    print('PVS_DOWNLOAD_COMPLETE ' + str(path), flush=True)
else:
    raise ValueError('Invalid model operation')
'''


def qwen_command(python_exe: str, model: ModelChoice, operation: str) -> list[str]:
    if model.family != 'qwen3' or operation not in ('check', 'download'):
        raise ValueError('Invalid Qwen model operation')
    try:
        available = Path(python_exe).is_file()
    except OSError as exc:
        raise EngineError(f'Qwen Python is unavailable at {python_exe}: {exc}') from exc
    if not available:
        raise EngineError('Qwen Python is not configured. Set it under Voice Engines first.')
    return [python_exe, '-I', '-u', '-c', _QWEN_SCRIPT, model.repo, operation]


def qwen_task(model: ModelChoice, python_exe: str, operation: str, cancelled: Event,
              log, diagnostic_dir: Path) -> bool:
    """Download/cache-check with the same isolated subprocess protection as synthesis.

    Returns whether Qwen has a cached snapshot for the model. A cached snapshot
    is not a substitute for successful model initialization or a test render.
    """
    command = qwen_command(python_exe, model, operation)
    logfile = Path(diagnostic_dir) / f'{model.key}-{operation}-{time.time_ns()}.log'
    logfile.parent.mkdir(parents=True, exist_ok=True)
    log(f'Checking Qwen cache' if operation == 'check' else f'Downloading {model.label} to the Qwen environment cache')
    log(f'Diagnostic file: {logfile}')
    with logfile.open('wb') as sink:
        proc = _spawn_optional_interpreter(command, stdout=sink, stderr=subprocess.STDOUT)
        try:
            _watch_engine_process(proc, logfile, time.monotonic(), 7200, cancelled, log)
        finally:
            if proc.poll() is None:
                _stop_process(proc)
    output = logfile.read_text(encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        raise EngineError(f'Qwen model operation failed (exit {proc.returncode}). See {logfile}:\n{output[-1200:]}')
    if operation == 'download':
        if 'PVS_DOWNLOAD_COMPLETE ' not in output:
            raise EngineError('Qwen download finished without a confirmation marker')
        log('Qwen model files downloaded. Run a generation to validate inference.')
        return True
    return 'PVS_CACHE_FOUND' in output
