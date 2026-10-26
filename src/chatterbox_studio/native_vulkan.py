"""Explicit, offline audio.cpp transport for retained Linux speech runtimes.

No ML imports or preset code is executed. The fixed protocol follows the existing
native voice plugins; it does not apply their persona, pronunciation or effects.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import wave


class NativeVulkanError(RuntimeError):
    pass


class NativeVulkanCancelled(NativeVulkanError):
    pass


MAX_REFERENCE_SECONDS = 30
QWEN_MODELS = {'Qwen/Qwen3-TTS-12Hz-0.6B-Base': '0b6',
               'Qwen/Qwen3-TTS-12Hz-1.7B-Base': '1b7'}
INDEX_FILES = ('config.yaml', 'gpt.safetensors', 's2mel.safetensors',
               'semantic_codec_model.safetensors', 'campplus.safetensors',
               'feat1.safetensors', 'feat2.safetensors', 'wav2vec2bert_stats.safetensors',
               'multilingual_zh_ja_yue_char_del.tiktoken', 'bigvgan/config.json',
               'bigvgan/model.safetensors', 'w2v-bert-2.0/config.json',
               'w2v-bert-2.0/preprocessor_config.json', 'w2v-bert-2.0/model.safetensors')
PLACEMENT_COMPONENTS = {'qwen3': ('talker', 'speech_tokenizer_decoder')}
LANGUAGES = {'English': 'en', 'Spanish': 'es', 'French': 'fr', 'German': 'de',
             'Italian': 'it', 'Chinese': 'zh', 'Japanese': 'ja', 'Korean': 'ko',
             'Russian': 'ru', 'Portuguese': 'pt', 'EN': 'en', 'ES': 'es',
             'JA': 'ja', 'ZH': 'zh', 'AR': 'ar'}


def digest(path: Path) -> str:
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def native_generation_blocker(engine: str) -> str:
    if engine == 'index25':
        return ('Index native Vulkan generation is unavailable until its actual GPU placement '
                'markers are qualified. Checking paths does not qualify GPU synthesis.')
    if engine not in PLACEMENT_COMPONENTS:
        return 'This engine has no qualified native Vulkan adapter.'
    return ''


def _existing(value, label: str, directory=False) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise NativeVulkanError(f'Choose the existing native {label}.')
    path = Path(value).expanduser()
    if not path.is_absolute() or not (path.is_dir() if directory else path.is_file()):
        raise NativeVulkanError(f'Native {label} is unavailable. Check its path and mounted drive.')
    return path.resolve()


def validate_native_configuration(engine: str, model: str, settings: dict) -> dict:
    """Read metadata and verify executable identity, without starting it."""
    if sys.platform != 'linux':
        raise NativeVulkanError('The coordinated native Vulkan adapter currently supports Linux only; choose Python on this platform.')
    if engine not in ('qwen3', 'index25'):
        raise NativeVulkanError('Native Vulkan is available for Qwen Base and IndexTTS 2.5 only.')
    binary = _existing(settings.get('native_executable'), 'executable')
    expected = str(settings.get('native_sha256', '')).lower()
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise NativeVulkanError('Provide the reviewed native executable SHA256; unknown binaries are not launched.')
    if not os.access(binary, os.X_OK) or digest(binary) != expected:
        raise NativeVulkanError('Native executable is not executable or its SHA256 changed. Review the runtime before using it.')
    folder = _existing(settings.get('native_model_dir'), 'model folder', directory=True)
    lock = _existing(settings.get('native_gpu_lock'), 'shared GPU lock')
    if engine == 'qwen3':
        if model not in QWEN_MODELS:
            raise NativeVulkanError('Select a supported Qwen Base model, not CustomVoice or VoiceDesign.')
        required = ('config.json', 'model.safetensors', 'tokenizer_config.json', 'vocab.json',
                    'merges.txt', 'preprocessor_config.json', 'generation_config.json',
                    'speech_tokenizer/config.json', 'speech_tokenizer/model.safetensors',
                    'speech_tokenizer/preprocessor_config.json')
        config_file = folder / 'config.json'
        try:
            if config_file.stat().st_size > 65536:
                raise ValueError('oversized config')
            config = json.loads(config_file.read_text(encoding='utf-8'))
            if config.get('tts_model_type') != 'base' or config.get('tts_model_size') != QWEN_MODELS[model]:
                raise ValueError('different model variant')
        except (OSError, ValueError, AttributeError) as exc:
            raise NativeVulkanError('Qwen folder must match the selected Base model and size.') from exc
        family = 'qwen3_tts'
    else:
        if model != 'IndexTeam/IndexTTS-2.5':
            raise NativeVulkanError('Select IndexTTS 2.5.')
        required, config_file, family = INDEX_FILES, folder / 'config.yaml', 'index_tts2'
    missing = [name for name in required if not (folder / name).is_file() or not (folder / name).stat().st_size]
    if missing:
        raise NativeVulkanError('Native model folder is incomplete: ' + ', '.join(missing))
    return {'executable': str(binary), 'sha256': expected, 'model_dir': str(folder),
            'model_config_sha256': digest(config_file), 'gpu_lock': str(lock), 'family': family,
            'model_files': {name: {'bytes': (folder / name).stat().st_size,
                                   'mtime_ns': (folder / name).stat().st_mtime_ns} for name in required}}


def validate_native_controls(request: dict) -> None:
    if not isinstance(request.get('text'), str) or not request['text'].strip():
        raise NativeVulkanError('Provide plain spoken text for the native passage.')
    if not isinstance(request.get('ref_text', ''), str):
        raise NativeVulkanError('The reference transcript must be text.')
    if request.get('device', 'vulkan') != 'vulkan':
        raise NativeVulkanError('Native Vulkan requires explicit Vulkan device 0; no CPU fallback is provided.')
    if float(request.get('speed', 1.0)) != 1.0 or request.get('emotion', 'neutral') != 'neutral':
        raise NativeVulkanError('Native emotion and duration controls are unavailable; use Neutral and 1.0.')
    if len(request.get('text', '')) > 1000:
        raise NativeVulkanError('Use at most 1,000 prepared characters per native passage; split longer text for review.')
    if len(request.get('ref_text', '')) > 4000:
        raise NativeVulkanError('Reference transcript exceeds 4,000 characters; choose a matching shorter excerpt. It is never silently truncated.')
    if request.get('language') not in LANGUAGES:
        raise NativeVulkanError('This language is not available in the native adapter.')
    for name in ('text', 'ref_text'):
        value = request.get(name, '')
        if '\x00' in value or any(ord(c) < 32 and c not in '\r\n\t' for c in value):
            raise NativeVulkanError('Use plain text without control characters.')


def build_native_command(request: dict, config: dict, reference: Path, output: Path) -> list[str]:
    validate_native_controls(request)
    command = [config['executable'], '--task', 'tts', '--family', config['family'],
               '--model', config['model_dir'], '--backend', 'vulkan', '--device', '0',
               '--threads', '4', '--log', '--metrics', '--text', request['text'],
               '--voice-ref', str(reference), '--language', LANGUAGES[request['language']],
               '--seed', '731', '--max-tokens', '1200', '--out', str(output)]
    if request['engine'] == 'qwen3':
        transcript = request.get('ref_text', '')
        command += ['--request-option', 'x_vector_only_mode=' + ('false' if transcript.strip() else 'true'),
                    '--text-chunk-size', '480', '--session-option', 'qwen3_tts.stitch_decode=true']
        if transcript.strip():
            command += ['--reference-text', transcript]
    return command


def _cancelled(cancelled):
    if cancelled is not None and cancelled.is_set():
        raise NativeVulkanCancelled('Native generation cancelled.')


@contextmanager
def gpu_reservation(path: Path, cancelled=None, log=None, timeout=300):
    import fcntl
    # Open only an existing lock. Never create a competing lock or bypass it.
    with Path(path).open('r') as lock:
        start = time.monotonic()
        notified = False
        while True:
            _cancelled(cancelled)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not notified and log:
                    log('Waiting for the shared GPU; other work stays running. Cancel is available.')
                notified = True
                if time.monotonic() - start >= timeout:
                    raise NativeVulkanError('Shared GPU stayed busy. Try again after the active job finishes.')
                time.sleep(.1)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _stop_owned(proc):
    # A launcher can exit while its own descendants still hold GPU resources.
    # Address its private process group even after the leader has exited.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=3)


def _environment():
    env = os.environ.copy()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONEXECUTABLE', 'LD_LIBRARY_PATH'):
        env.pop(key, None)
    env.pop('HSA_OVERRIDE_GFX_VERSION', None)
    for key in tuple(env):
        if key.startswith('_PYI_'):
            env.pop(key, None)
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', OMP_NUM_THREADS='4',
               TOKENIZERS_PARALLELISM='false')
    return env


def _run_owned(command, logfile, cancelled, timeout, output_path=None):
    _cancelled(cancelled)
    with Path(logfile).open('ab') as sink:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=sink,
                                stderr=subprocess.STDOUT, env=_environment(), start_new_session=True)
        start = time.monotonic()
        try:
            while proc.poll() is None:
                _cancelled(cancelled)
                if time.monotonic() - start >= timeout:
                    raise NativeVulkanError('Native process exceeded its time limit; no output was accepted.')
                if Path(logfile).stat().st_size > 8 * 1024 ** 2:
                    raise NativeVulkanError('Native diagnostic output exceeded its bounded size.')
                if output_path is not None and Path(output_path).exists() and Path(output_path).stat().st_size > 64 * 1024 ** 2:
                    raise NativeVulkanError('Native audio output exceeded its bounded size.')
                time.sleep(.1)
            if proc.returncode:
                raise NativeVulkanError(f'Native process exited {proc.returncode}; no fallback was attempted. Log: {logfile}')
        finally:
            _stop_owned(proc)


def _wav_info(path):
    try:
        with wave.open(str(path), 'rb') as audio:
            duration = audio.getnframes() / audio.getframerate()
            if audio.getnframes() <= 0 or audio.getcomptype() != 'NONE':
                raise ValueError('empty or compressed WAV')
            remaining = audio.getnframes()
            frame_bytes = audio.getnchannels() * audio.getsampwidth()
            while remaining:
                count = min(remaining, 16384)
                if len(audio.readframes(count)) != count * frame_bytes:
                    raise ValueError('truncated PCM payload')
                remaining -= count
            return duration, audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
    except (OSError, ValueError, wave.Error, EOFError, ZeroDivisionError) as exc:
        raise NativeVulkanError('Native audio must be a nonempty PCM WAV.') from exc


def _prepare_reference(source, work, logfile, cancelled, timeout=60):
    source = Path(source)
    try:
        info = _wav_info(source)
    except NativeVulkanError:
        info = None
    if info is not None and info[0] > MAX_REFERENCE_SECONDS:
        raise NativeVulkanError('Choose a reference excerpt of at most 30 seconds and its exact matching transcript; audio is never silently trimmed.')
    if info is not None and info[1:] == (24000, 1, 2):
        target = work / 'conditioning.wav'
        shutil.copyfile(source, target)
        return target, {'preparation': 'private byte-identical mono 24kHz PCM snapshot', 'seconds': info[0]}
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise NativeVulkanError('The packaged FFmpeg tool is required to prepare this reference.') from exc
    target = work / 'conditioning.wav'
    # Decode one second beyond the accepted bound to detect long input. Such a
    # result is rejected, never used with the full transcript or silently cut.
    _run_owned([ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', str(source),
                '-t', str(MAX_REFERENCE_SECONDS + 1), '-map_metadata', '-1',
                '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', str(target)],
               logfile, cancelled, timeout)
    info = _wav_info(target)
    if info[0] > MAX_REFERENCE_SECONDS:
        raise NativeVulkanError('Choose a reference excerpt of at most 30 seconds with its exact transcript; no truncated reference was used.')
    if info[1:] != (24000, 1, 2):
        raise NativeVulkanError('Reference preparation did not produce mono 24kHz 16-bit PCM; no output was accepted.')
    return target, {'preparation': 'derived mono 24kHz PCM; no accepted trimming', 'seconds': info[0]}


def _placement(logfile, engine):
    blocker = native_generation_blocker(engine)
    if blocker:
        raise NativeVulkanError(blocker)
    family = 'qwen3_tts' if engine == 'qwen3' else 'index_tts2'
    found, cpu, devices, identities = set(), set(), [], {}
    uncertain_device = False
    declaration = re.compile(r'\bggml_vulkan:\s*(?:(\d+)\s*=|Device\s+(\d+)\s*[:=])\s*([^|\r\n]*)', re.IGNORECASE)
    software = re.compile(r'llvmpipe|lavapipe|swiftshader|softpipe|\b(?:software|cpu|unknown|generic|virtual|emulated)\b', re.IGNORECASE)
    physical = re.compile(r'\b(?:Radeon|Instinct)\s+\S+|\bAMD\s+Custom\s+GPU\s+\S+|'
                          r'\bNVIDIA\s+\S+|\b(?:GeForce|Quadro|Tesla)\s+\S+|'
                          r'\bIntel\b[^|\r\n]*\b(?:Arc|Iris|UHD|HD\s+Graphics|Xe)\b', re.IGNORECASE)
    with Path(logfile).open(encoding='utf-8', errors='replace') as source:
        for line in source:
            match = re.search(r'(' + family + r'\.([\w.]+)\.weights\.buffer_name)\s+(Vulkan0|CPU\w*)\b', line)
            if match:
                (found if match[3] == 'Vulkan0' else cpu).add(match[2])
            device = declaration.search(line)
            if device and int(device[1] or device[2]) == 0:
                name = ' '.join(device[3].strip().split())
                devices.append(line.strip()[:500])
                # A nominal hardware name cannot override a software ICD/type
                # declared in the same selected-device line's properties.
                if not name or software.search(line) or not physical.search(name):
                    uncertain_device = True
                identities[name.casefold()] = name
    missing = set(PLACEMENT_COMPONENTS[engine]) - found
    uncertain = set(PLACEMENT_COMPONENTS[engine]) & cpu
    if missing or uncertain:
        raise NativeVulkanError('Actual Vulkan model-buffer placement was not confirmed for '
                                + ', '.join(sorted(missing | uncertain)) + '; no output was accepted.')
    if uncertain_device or len(identities) != 1:
        raise NativeVulkanError('A single physical GPU identity for Vulkan device 0 was not confirmed. '
                                'Missing, software or conflicting device evidence cannot qualify GPU generation; no output was accepted.')
    return {'actual_backend': 'vulkan', 'actual_device': 'Vulkan0',
            'physical_device_name': next(iter(identities.values())),
            'gpu_weight_buffers': sorted(found), 'cpu_weight_buffers': sorted(cpu),
            'device_evidence': devices[:8],
            'device_identity_scope': 'Runtime declaration for selected Vulkan device 0; no separate hardware probe performed.',
            'placement_scope': 'Verified model weight buffers; CPU preprocessing and other operations may remain.'}


def execute_native_generation(request, cancelled=None, log=None, timeout_seconds=300, diagnostic_dir=None):
    _cancelled(cancelled)
    blocker = native_generation_blocker(request.get('engine', ''))
    if blocker:
        raise NativeVulkanError(blocker)
    validate_native_controls(request)
    deadline = time.monotonic() + min(timeout_seconds, 300)
    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise NativeVulkanError('Native process exceeded its time limit; no output was accepted.')
        return seconds
    config = validate_native_configuration(request['engine'], request['model'], request)
    output = Path(request['output_path'])
    if output.exists() or output.is_symlink() or output.with_suffix('.json').exists():
        raise NativeVulkanError('Refusing to overwrite existing output or provenance.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pvs-native-', dir=output.parent) as temporary:
        work = Path(temporary)
        if diagnostic_dir is not None:
            Path(diagnostic_dir).mkdir(parents=True, exist_ok=True)
            logfile = Path(diagnostic_dir) / (work.name + '.log')
            logfile.touch(exist_ok=False)
            if log:
                log(f'Diagnostic file: {logfile}')
        else:
            logfile = work / 'native.log'
        reference = Path(request['voice_path'])
        if reference.stat().st_size > 128 * 1024 ** 2:
            raise NativeVulkanError('Choose a bounded reference excerpt (at most 128 MiB and 30 seconds).')
        reference_sha = digest(reference)
        prepared, conditioning = _prepare_reference(reference, work, logfile, cancelled, min(60, remaining()))
        if digest(reference) != reference_sha:
            raise NativeVulkanError('Reference changed during preparation. Retry with a stable excerpt and matching transcript.')
        conditioning.update(source_sha256=reference_sha, prepared_sha256=digest(prepared),
                            mode=('reference_transcript' if request.get('ref_text', '').strip() else 'embedding_only')
                            if request['engine'] == 'qwen3' else 'reference_audio',
                            exact_transcript_used=bool(request.get('ref_text', '').strip()) if request['engine'] == 'qwen3' else False)
        raw = work / 'raw.wav'
        command = build_native_command(request, config, prepared, raw)
        if log:
            log('Native Vulkan selected explicitly. Verifying actual placement; no CPU/Python fallback.')
        with gpu_reservation(Path(config['gpu_lock']), cancelled, log, timeout=remaining()):
            # Recheck the reviewed executable immediately before launch.
            if digest(Path(config['executable'])) != config['sha256']:
                raise NativeVulkanError('Native executable changed while waiting for the GPU.')
            current = validate_native_configuration(request['engine'], request['model'], request)
            if current['model_files'] != config['model_files'] or current['model_config_sha256'] != config['model_config_sha256']:
                raise NativeVulkanError('Native model metadata changed while waiting for the GPU.')
            _run_owned(command, logfile, cancelled, remaining(), output_path=raw)
        _cancelled(cancelled)
        placement = _placement(logfile, request['engine'])
        info = _wav_info(raw)
        if info[0] > 300:
            raise NativeVulkanError('Native output exceeded the bounded passage duration.')
        runtime = {**placement, 'requested_backend': 'native_vulkan',
                   'executable': config['executable'], 'executable_sha256': config['sha256'],
                   'model_dir': config['model_dir'], 'model_config_sha256': config['model_config_sha256'],
                   'model_files': config['model_files'], 'conditioning': conditioning,
                   'model_identity_scope': 'Configuration SHA256 and file size/mtime metadata; weight contents were not rehashed.',
                   'sample_rate': info[1], 'audio_seconds': info[0],
                   'diagnostic_log': str(logfile) if diagnostic_dir is not None else '',
                   'audio_acceptance': 'Generated file requires listening review.'}
        metadata = {**request, 'text': request.get('original_text', request['text']),
                    'original_text': request.get('original_text', request['text']),
                    'prepared_text': request.get('prepared_text', request['text']),
                    'runtime': runtime, 'duration_seconds': round(min(timeout_seconds, 300) - remaining(), 2),
                    'diagnostic_log': runtime['diagnostic_log']}
        sidecar = work / 'provenance.json'
        sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        _cancelled(cancelled)
        os.link(raw, output)  # Exclusive same-filesystem promotion, never replace.
        try:
            os.link(sidecar, output.with_suffix('.json'))
        except OSError:
            # Remove only this newly promoted inode if provenance publication
            # loses a race. Never replace a recording or sidecar owned by others.
            if output.lstat().st_ino == raw.stat().st_ino:
                output.unlink()
            raise
        return output, runtime


def discover_native_settings(storage: Path) -> dict:
    """Suggest retained paths on explicit user action; never save or run presets."""
    for name in ('mister-plague-vulkan', 'mama-mire-vulkan'):
        directory = Path(storage) / 'plugins' / name
        preset = directory / 'preset.json'
        try:
            if preset.stat().st_size > 50000:
                continue
            data = json.loads(preset.read_text(encoding='utf-8'))
            engine = data['engine']
            if data.get('version') != 1 or engine.get('family') != 'qwen3_tts' or engine.get('backend') != 'vulkan':
                continue
            relative = Path(engine['binary'])
            if relative.is_absolute() or not (directory / relative).resolve().is_relative_to(directory.resolve()):
                continue
            binary = directory / relative
            if not binary.is_file() or not re.fullmatch(r'[0-9a-fA-F]{64}', engine.get('binary_sha256', '')):
                continue
            parent = Path(engine['model']).parent
            return {'native_executable': str(binary), 'native_sha256': engine['binary_sha256'],
                    'native_gpu_lock': str(engine.get('shared_gpu_lock', '')),
                    'qwen_06_model_dir': str(parent / 'qwen-tts-0.6B'),
                    'qwen_17_model_dir': str(parent / 'qwen-tts-1.7B'),
                    'index_model_dir': str(parent / 'index25')}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return {}
