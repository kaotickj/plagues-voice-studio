"""Experimental optional-engine protocol, with no optional ML imports in the host.

Qwen3-TTS and IndexTTS execute under independently chosen Python interpreters.
Neither environment may alter the Chatterbox dependency set. Requests cross the
process boundary through JSON files, with no network listener or shell command.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event, Lock
from datetime import datetime
import time
from uuid import uuid4

ENGINES = {
    'qwen3': {
        'label': 'Qwen3-TTS',
        'models': ('Qwen/Qwen3-TTS-12Hz-0.6B-Base', 'Qwen/Qwen3-TTS-12Hz-1.7B-Base'),
        'languages': ('English', 'Spanish', 'French', 'German', 'Italian', 'Chinese', 'Japanese', 'Korean', 'Russian', 'Portuguese'),
        'link': 'https://github.com/QwenLM/Qwen3-TTS',
    },
    'index25': {
        'label': 'IndexTTS 2.5',
        'models': ('IndexTeam/IndexTTS-2.5',),
        'languages': ('EN', 'ES', 'JA', 'ZH', 'AR'),
        'link': 'https://github.com/index-tts/index-tts',
    },
}


class EngineError(RuntimeError):
    pass


class EngineCancelled(EngineError):
    pass



def native_exit_hint(returncode: int) -> str:
    """Decode Windows native failure codes without mistaking them for Python errors."""
    if (returncode & 0xFFFFFFFF) == 0xC0000005:
        return (
            '\nWindows native access violation (0xC0000005). '
            'A compiled library crashed; this is not the Transformers GenerationMixin warning. '
            'Check the fatal-error traceback above (if present) and Windows Event Viewer > '
            'Windows Logs > Application for the faulting module. '
            'Also retry with other AI applications closed to rule out memory pressure.'
        )
    return ''


def runtime_script_path() -> Path:
    """Runner is a data file, not imported into the host process."""
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return base / 'optional_engine_runner.py'


def is_interpreter(path: str) -> bool:
    p = Path(path).expanduser()
    return p.is_file() and p.name.lower().startswith(('python', 'pypy')) and p.suffix.lower() in ('.exe', '')


def check_configuration(engine: str, python_exe: str, repo: str = '') -> None:
    if engine not in ENGINES:
        raise EngineError('Unknown optional engine')
    if not python_exe or not is_interpreter(python_exe):
        raise EngineError('Select an existing Python executable for this engine (not Chatterbox Python).')
    if engine == 'index25':
        root = Path(repo).expanduser()
        if not (root / 'indextts' / 'infer_v2_5.py').is_file():
            raise EngineError('IndexTTS requires the checked-out index-tts repository directory.')
        if not (root / 'checkpoints' / 'config.yaml').is_file():
            raise EngineError('IndexTTS checkpoint config missing: <repository>/checkpoints/config.yaml')
    if not runtime_script_path().is_file():
        raise EngineError('Optional engine runner missing from the application package.')


def clean_request(request: dict) -> dict:
    engine = str(request.get('engine', ''))
    if engine not in ENGINES:
        raise EngineError('Unknown engine')
    text = str(request.get('text', ''))
    if not 1 <= len(text.strip()) <= 5000:
        raise EngineError('Provide 1–5,000 characters of text per optional-engine generation.')
    model = str(request.get('model', ''))
    if model not in ENGINES[engine]['models']:
        raise EngineError('Unsupported model for selected engine')
    language = str(request.get('language', ''))
    if language not in ENGINES[engine]['languages']:
        raise EngineError('Unsupported language for selected engine')
    ref_path = Path(str(request.get('voice_path', ''))).expanduser()
    if not ref_path.is_file():
        raise EngineError('Choose an existing local voice reference audio file.')
    if ref_path.suffix.lower() not in ('.wav', '.mp3', '.flac', '.ogg'):
        raise EngineError('Voice reference must be WAV, MP3, FLAC, or OGG.')
    out_path = Path(str(request.get('output_path', ''))).expanduser()
    if out_path.suffix.lower() != '.wav' or not out_path.name or out_path.is_dir():
        raise EngineError('Optional engines currently export WAV only.')
    if out_path.exists():
        raise EngineError('Refusing to overwrite an existing recording.')
    speed = float(request.get('speed', 1.0))
    if not 0.5 <= speed <= 2.0:
        raise EngineError('Speed must be from 0.5 to 2.0.')
    device = str(request.get('device', 'cpu'))
    if device not in ('cpu', 'auto', 'cuda'):
        raise EngineError('Invalid processing device.')
    return {
        'engine': engine, 'model': model, 'text': text, 'language': language,
        'voice_path': str(ref_path.resolve()), 'output_path': str(out_path.absolute()),
        'ref_text': str(request.get('ref_text', ''))[:4000],
        'emotion': str(request.get('emotion', 'neutral')),
        'speed': speed, 'device': device,
        'repo': str(request.get('repo', '')),
    }


def new_output_path(folder: Path, stem: str) -> Path:
    import re
    folder = folder.expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', stem).strip('_')[:100] or 'voice'
    from datetime import datetime
    return folder / f'{safe}_{datetime.now():%Y%m%d-%H%M%S}_{uuid4().hex[:7]}.wav'


class EngineRegistry:
    """Separate experimental config, never mutates installed engine environments."""
    def __init__(self, storage: Path):
        self.path = Path(storage) / 'optional_engines.json'

    def read(self) -> dict:
        defaults = {'qwen3': {'python': '', 'repo': ''}, 'index25': {'python': '', 'repo': ''}}
        if not self.path.is_file():
            return defaults
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Malformed engine configuration')
            for engine in defaults:
                e = data.get(engine, {})
                if isinstance(e, dict):
                    defaults[engine] = {'python': str(e.get('python', '')), 'repo': str(e.get('repo', ''))}
            return defaults
        except (OSError, ValueError) as exc:
            raise EngineError(f'Engine configuration could not be read: {exc}') from exc

    def save(self, data: dict) -> None:
        clean = {k: {'python': str(data.get(k, {}).get('python', '')),
                     'repo': str(data.get(k, {}).get('repo', ''))} for k in ENGINES}
        atomic_json_write(self.path, clean)


class CharacterStore:
    """Per-character voice settings, persisted independently from v0.2.x."""
    def __init__(self, storage: Path):
        self.path = Path(storage) / 'character_profiles.json'

    def read(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Expected JSON object')
            return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, dict)}
        except (ValueError, OSError) as exc:
            raise EngineError(f'Character profiles unreadable: {exc}') from exc

    def save_profile(self, name: str, profile: dict) -> None:
        name = name.strip()
        if not 1 <= len(name) <= 80:
            raise EngineError('Character profile name must be 1–80 characters.')
        data = self.read()
        data[name] = dict(profile)
        atomic_json_write(self.path, data)

    def delete_profile(self, name: str) -> None:
        data = self.read()
        data.pop(name, None)
        atomic_json_write(self.path, data)


def atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    try:
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


# Windows PyInstaller's SetDllDirectoryW(bundle/_internal) affects child Python
# interpreters. Starting Python 3.12 with the frozen Python 3.11 DLL directory
# still active can produce:
#   ImportError: Module use of python311.dll conflicts with this version of Python.
# Reset ONLY while creating an optional-engine child and immediately restore.
# The lock serializes simultaneous probes/generations during this short window.
# Python -I additionally prevents importing bundled Python 3.11 native modules:
# when the runner script lives in _internal/, normal script execution places
# _internal/ on sys.path[0] even after DLL paths were sanitized.
_spawn_lock = Lock()


def _isolated_engine_environment() -> dict[str, str]:
    """Do not leak the frozen host's package paths to independent interpreters."""
    env = os.environ.copy()
    for name in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONEXECUTABLE'):
        env.pop(name, None)
    if getattr(sys, 'frozen', False):
        # PyInstaller uses these for its own bootstrap; they do not belong in an
        # unrelated Python 3.12 process.
        for name in tuple(env):
            if name.startswith('_PYI_'):
                env.pop(name, None)
        bundled = getattr(sys, '_MEIPASS', None)
        if bundled and env.get('PATH'):
            root = os.path.normcase(os.path.normpath(str(bundled)))
            def is_host_bundle(folder: str) -> bool:
                folder = os.path.normcase(os.path.normpath(folder.strip('"')))
                return folder == root or folder.startswith(root + os.sep)
            env['PATH'] = os.pathsep.join(x for x in env['PATH'].split(os.pathsep) if not is_host_bundle(x))
        # Linux frozen bootloaders can prepend their own shared-object paths.
        if sys.platform != 'win32' and 'LD_LIBRARY_PATH_ORIG' in env:
            env['LD_LIBRARY_PATH'] = env.pop('LD_LIBRARY_PATH_ORIG')
    return env


def _is_frozen_windows() -> bool:
    return sys.platform == 'win32' and bool(getattr(sys, 'frozen', False))


def _set_windows_dll_directory(path: str | None) -> None:
    import ctypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = kernel32.SetDllDirectoryW
    fn.argtypes = [ctypes.c_wchar_p]
    fn.restype = ctypes.c_bool
    if not fn(path):
        raise OSError(ctypes.get_last_error(), 'SetDllDirectoryW failed')


def _spawn_optional_interpreter(command: list[str], **kwargs) -> subprocess.Popen:
    """Start an external Python interpreter without PyInstaller's DLL search path.

    DLL search directories are process-wide on Windows; restore the bundled
    application's directory immediately after CreateProcess returns.
    """
    kwargs['env'] = _isolated_engine_environment()
    # The frozen GUI must never show an unsolicited console window. This is
    # also necessary when launched by a windowed PyInstaller executable.
    if sys.platform == 'win32':
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | subprocess.CREATE_NO_WINDOW
    if not _is_frozen_windows():
        return subprocess.Popen(command, **kwargs)
    bundle = getattr(sys, '_MEIPASS', None)
    if not bundle:
        raise EngineError('Frozen application is missing its bundle path.')
    with _spawn_lock:
        _set_windows_dll_directory(None)
        try:
            return subprocess.Popen(command, **kwargs)
        finally:
            _set_windows_dll_directory(str(bundle))


def _diagnostic_path(engine: str, diagnostic_dir: Path | None) -> Path:
    if diagnostic_dir is None:
        raise ValueError('A persistent diagnostic directory was not supplied.')
    folder = Path(diagnostic_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return folder / f'{engine}-{stamp}-{uuid4().hex[:8]}.log'


def _watch_engine_process(proc: subprocess.Popen, logfile: Path,
                          start: float, timeout_seconds: int,
                          cancelled: Event | None = None, log=None) -> None:
    """Observe redirected text without blocking on pipe buffers or GUI events.

    Poll the file while the child runs, so output is visible during lengthy
    Hugging Face downloads. The file is retained when diagnostic_dir is set.
    """
    offset = 0
    pending = ''
    last_activity = start
    warned_at = start
    def drain() -> None:
        nonlocal offset, pending, last_activity
        if not logfile.exists():
            return
        with logfile.open('rb') as source:
            source.seek(offset)
            data = source.read(128 * 1024)
            offset = source.tell()
        if not data:
            return
        last_activity = time.monotonic()
        pending += data.decode('utf-8', errors='replace').replace('\r', '\n')
        fragments = pending.split('\n')
        pending = fragments.pop()
        if log:
            # Limit signals from fast tqdm progress bars; full details remain in log.
            for line in fragments[-12:]:
                line = line.strip()
                if line:
                    log(line[-650:])
        if len(pending) > 8192:
            pending = pending[-4096:]

    while proc.poll() is None:
        drain()
        elapsed = time.monotonic() - start
        if cancelled is not None and cancelled.is_set():
            _stop_process(proc)
            drain()
            raise EngineCancelled('Cancelled by user')
        if elapsed >= timeout_seconds:
            _stop_process(proc)
            drain()
            raise EngineError(f'Optional engine exceeded the {timeout_seconds // 60}-minute limit. '
                              f'Diagnostic log: {logfile}')
        if log and time.monotonic() - max(last_activity, warned_at) >= 120:
            warned_at = time.monotonic()
            log(f'No new engine output for 2 minutes (elapsed {int(elapsed)}s). '
                'CPU loading or a download may still be running; Cancel is available.')
        time.sleep(0.35)
    drain()
    if pending.strip() and log:
        log(pending.strip()[-650:])


def _stop_process(proc: subprocess.Popen) -> None:
    """Cooperatively stop the optional engine, escalating after a short wait."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def execute_probe(engine: str, python_exe: str, repo: str = '', timeout: int = 120,
                  cancelled: Event | None = None, log=None,
                  diagnostic_dir: Path | None = None) -> dict:
    check_configuration(engine, python_exe, repo)
    if cancelled is not None and cancelled.is_set():
        raise EngineCancelled('Cancelled')
    kwargs = {'cwd': str(Path(repo).resolve())} if engine == 'index25' else {}
    command = [python_exe, '-I', '-u', '-X', 'faulthandler', str(runtime_script_path()), '--probe', engine]
    with tempfile.TemporaryDirectory(prefix='pvs-probe-') as temp:
        logfile = (_diagnostic_path(engine + '-probe', diagnostic_dir)
                   if diagnostic_dir is not None else Path(temp) / 'probe.log')
        if log:
            log(f'Checking {ENGINES[engine]["label"]} imports (timeout {timeout}s).')
            if diagnostic_dir is not None:
                log(f'Diagnostic file: {logfile}')
        start = time.monotonic()
        with logfile.open('wb') as sink:
            proc = _spawn_optional_interpreter(command, stdout=sink,
                                               stderr=subprocess.STDOUT, **kwargs)
            try:
                _watch_engine_process(proc, logfile, start, timeout, cancelled, log)
            finally:
                if proc.poll() is None:
                    _stop_process(proc)
        output = logfile.read_text(encoding='utf-8', errors='replace')
        if proc.returncode != 0:
            raise EngineError(f'Engine probe exited {proc.returncode}'
                              f'{native_exit_hint(proc.returncode)}:\n{output[-4000:]}\nLog: {logfile}')
        try:
            # The runner writes a JSON result on its final line. Upstream
            # packages may print warnings before that result.
            result = next(json.loads(line) for line in reversed(output.splitlines())
                          if line.strip().startswith('{'))
        except (ValueError, StopIteration) as exc:
            raise EngineError(f'Unexpected engine probe response: {output[-1500:]}') from exc
        if not result.get('ready'):
            raise EngineError(str(result.get('error', 'Engine is not ready')))
        return result


def execute_generation(request: dict, python_exe: str, cancelled: Event | None = None,
                       log=None, timeout_seconds: int = 2700,
                       diagnostic_dir: Path | None = None) -> Path:
    """Single-shot optional engine, live diagnostics and controlled cancellation."""
    request = clean_request(request)
    engine = request['engine']
    check_configuration(engine, python_exe, request.get('repo', ''))
    output = Path(request['output_path'])
    output.parent.mkdir(parents=True, exist_ok=True)
    if cancelled is not None and cancelled.is_set():
        raise EngineCancelled('Cancelled')
    with tempfile.TemporaryDirectory(prefix='pvs-engine-') as temporary:
        root = Path(temporary)
        source, response = root / 'request.json', root / 'result.json'
        logfile = (_diagnostic_path(engine + '-generate', diagnostic_dir)
                   if diagnostic_dir is not None else root / 'process.log')
        source.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
        command = [python_exe, '-I', '-u', '-X', 'faulthandler', str(runtime_script_path()), '--run', str(source), str(response)]
        kwargs = {'cwd': str(Path(request['repo']).resolve())} if engine == 'index25' else {}
        start = time.monotonic()
        if log:
            log(f'Starting {ENGINES[engine]["label"]}. Generation limit: {timeout_seconds // 60} minutes.')
            if diagnostic_dir is not None:
                log(f'Diagnostic file: {logfile}')
        with logfile.open('wb') as sink:
            proc = _spawn_optional_interpreter(command, stdout=sink,
                                               stderr=subprocess.STDOUT, **kwargs)
            try:
                _watch_engine_process(proc, logfile, start, timeout_seconds, cancelled, log)
            finally:
                if proc.poll() is None:
                    _stop_process(proc)
        detail = logfile.read_text(encoding='utf-8', errors='replace')[-7000:]
        if proc.returncode != 0:
            raise EngineError(f'{ENGINES[engine]["label"]} exited {proc.returncode}'
                              f'{native_exit_hint(proc.returncode)}:\n{detail}\nLog: {logfile}')
        if not response.is_file():
            raise EngineError(f'Engine produced no response.\n{detail}\nLog: {logfile}')
        try:
            result = json.loads(response.read_text(encoding='utf-8'))
        except ValueError as exc:
            raise EngineError(f'Invalid engine response file. Log: {logfile}') from exc
        if not result.get('ok'):
            raise EngineError(str(result.get('error', 'Unknown engine error')) +
                              '\n' + detail[-1000:] + f'\nLog: {logfile}')
        if not output.is_file() or output.stat().st_size < 44:
            raise EngineError('Engine returned success but did not create a valid-sized WAV file.')
        atomic_json_write(output.with_suffix('.json'), {
            'engine': engine, 'model': request['model'], 'language': request['language'],
            'text': request['text'],
            'voice_path': request['voice_path'], 'ref_text': request['ref_text'],
            'emotion': request['emotion'], 'speed': request['speed'], 'device': request['device'],
            'duration_seconds': round(time.monotonic() - start, 2),
            'diagnostic_log': str(logfile) if diagnostic_dir is not None else '',
        })
        return output
