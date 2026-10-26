"""Bounded external Chatterbox ROCm transport; no host Torch imports."""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from uuid import uuid4

RAM_LIMIT = 12 * 1024**3
TIME_LIMIT = 300


def known_runtime_defaults():
    python = Path('/opt/gnb-reading-voice/bin/python')
    overlay = Path('/home/kaotickj/Documents/Codex/2026-10-25/task/voice-studio-rocm-probe/overlay')
    if sys.platform == 'linux' and python.is_file() and (overlay / 'chatterbox').is_dir():
        return {'python': str(python), 'overlay': str(overlay)}
    return {'python': '', 'overlay': ''}


def runtime_paths(job):
    if sys.platform != 'linux':
        raise RuntimeError('External AMD ROCm is supported on Linux only. Choose CPU explicitly on this platform.')
    python = Path(job.rocm_python).expanduser().absolute()  # Preserve venv symlink invocation.
    overlay = Path(job.rocm_overlay).expanduser().resolve()
    if not python.is_file() or not os.access(python, os.X_OK) or not python.name.startswith('python'):
        raise RuntimeError('External ROCm Python is unavailable; choose an existing approved Python runtime')
    if not (overlay / 'chatterbox' / '__init__.py').is_file():
        raise RuntimeError('The approved Chatterbox overlay is unavailable; no runtime installation was attempted')
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    runner = base / 'chatterbox_rocm_runner.py'
    source = base / 'rocm_source' if getattr(sys, 'frozen', False) else base / 'src'
    if not runner.is_file() or not (source / 'chatterbox_studio' / 'engine.py').is_file():
        raise RuntimeError('External Chatterbox runner/plain Python sources are missing from this build')
    lock = Path(job.rocm_gpu_lock)
    if not lock.is_file() or lock.resolve() != Path('/run/lock/gnb-ai-gpu.lock').resolve():
        raise RuntimeError('The existing shared GPU lock is required; no competing lock is created')
    return python, overlay, runner, source


def group_rss(group, active=None):
    total = 0
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(') ', 1)[1].split()
            if int(fields[2]) == group:
                total += int(fields[21]) * os.sysconf('SC_PAGE_SIZE')
                if active is not None and fields[0] != 'Z':
                    active.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return total


def stop_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Owned ROCm child did not exit after signals; its inherited shared GPU lock remains held. '
                               'Inspect the recorded process group before starting another GPU job.') from exc
        return
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Owned ROCm child did not exit after signals; its inherited shared GPU lock remains held. '
                               'Inspect the recorded process group before starting another GPU job.') from exc
        end = time.monotonic() + 1
        while True:
            active = []
            group_rss(proc.pid, active)
            if not active:
                break
            if time.monotonic() >= end:
                raise RuntimeError('Owned ROCm process group still has active PIDs ' + str(active)
                                   + '; inspect cleanup before starting another GPU job')
            time.sleep(.02)


@contextmanager
def gpu_lock(path, cancelled, report, deadline):
    import fcntl
    # The child inherits this same open-file description. Closing the parent's
    # descriptor never unlocks a still-running child after uncertain cleanup.
    with Path(path).open('r') as lock:
        notified = False
        while True:
            if cancelled():
                from .engine import GenerationCancelled
                raise GenerationCancelled()
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not notified: report('Waiting for the shared GPU lock; existing jobs remain running.')
                notified = True
                if time.monotonic() >= deadline - 5:
                    raise RuntimeError('Shared GPU remained busy; no external render started')
                time.sleep(.1)
        yield lock


def validate_proof(runtime):
    if (runtime.get('actual_backend') != 'rocm' or not runtime.get('hip_version')
        or runtime.get('actual_device') != 'cuda:0' or runtime.get('cpu_fallback') is not False):
        raise RuntimeError('Child did not prove AMD ROCm execution; no CPU fallback/output was accepted')
    modules = runtime.get('module_parameters', {})
    forwards = runtime.get('forward_evidence', {})
    for name in ('t3', 's3gen', 've'):
        data = modules.get(name, {})
        if not data.get('gpu_parameters') or data.get('non_gpu_parameters'):
            raise RuntimeError('Chatterbox GPU parameter placement was not proved for ' + name)
    for name in ('t3', 's3gen'):
        if not forwards.get(name, {}).get('gpu_tensor_seen'):
            raise RuntimeError('Actual GPU forward tensor evidence was not proved for ' + name)
    for name in ('_stft', '_istft'):
        data = runtime.get('dsp_evidence', {}).get(name, {})
        if data.get('device') != 'cuda:0' or not data.get('gpu_outputs'):
            raise RuntimeError('Actual GPU vocoder DSP evidence was not proved for ' + name)


def publish(audio, metadata, target):
    """Promote both new files exclusively, preserving competing exports."""
    os.link(audio, target)
    try:
        os.link(metadata, target.with_suffix('.json'))
    except OSError:
        if target.lstat().st_ino == audio.stat().st_ino:
            target.unlink()
        raise


def render_external(job, report, progress, cancelled):
    from .engine import GenerationCancelled, local_model_path, unique_output_path
    if cancelled():
        raise GenerationCancelled()
    python, overlay, runner, source = runtime_paths(job)
    model = local_model_path(job.model)
    if model is None:
        raise RuntimeError('Complete existing local weights are required; external ROCm never downloads models')
    target = unique_output_path(Path(job.output_path).expanduser())
    target.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = target.parent / '.pvs-rocm-diagnostics' / uuid4().hex
    diagnostics.mkdir(mode=0o700, parents=True)
    report('Private ROCm diagnostics: ' + str(diagnostics))
    deadline = time.monotonic() + TIME_LIMIT
    with tempfile.TemporaryDirectory(prefix='.pvs-rocm-', dir=target.parent) as directory:
        work = Path(directory)
        request = work / 'request.json'
        response = work / 'response.json'
        log = diagnostics / 'process.log'
        child_job = job.as_json()
        reference_sha = None
        if job.voice_path:
            reference = Path(job.voice_path)
            if reference.stat().st_size > 128 * 1024**2:
                raise RuntimeError('Choose a reference file smaller than 128 MiB for the bounded ROCm job')
            snapshot = work / ('reference' + reference.suffix)
            with reference.open('rb') as source_file:
                reference_sha = hashlib.file_digest(source_file, 'sha256').hexdigest()
            shutil.copyfile(reference, snapshot)
            with reference.open('rb') as source_file, snapshot.open('rb') as copied:
                if (hashlib.file_digest(source_file, 'sha256').hexdigest() != reference_sha
                    or hashlib.file_digest(copied, 'sha256').hexdigest() != reference_sha):
                    raise RuntimeError('Voice reference changed during snapshot; no render was started')
            child_job['voice_path'] = str(snapshot)
        request.write_text(json.dumps({'job': job.as_json(), 'overlay': str(overlay),
            'source_root': str(source), 'model_dir': str(model), 'work': str(work),
            'parent_pid': os.getpid(),
            'child_voice_path': child_job['voice_path'], 'ffmpeg': '/usr/bin/ffmpeg',
            'proof_path': str(diagnostics / 'gpu-evidence.json')}, ensure_ascii=False), encoding='utf-8')
        env = os.environ.copy()
        for key in tuple(env):
            if key.startswith('_PYI_') or key in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONEXECUTABLE',
                'LD_LIBRARY_PATH', 'HSA_OVERRIDE_GFX_VERSION'):
                env.pop(key, None)
        env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
            HF_HOME=str(work / 'hf'), XDG_CACHE_HOME=str(work / 'cache'),
            NUMBA_CACHE_DIR=str(work / 'numba'), OMP_NUM_THREADS='6', MKL_NUM_THREADS='6',
            OPENBLAS_NUM_THREADS='6', TOKENIZERS_PARALLELISM='false',
            MIOPEN_USER_DB_PATH=str(work / 'miopen-db'), MIOPEN_CUSTOM_CACHE_DIR=str(work / 'miopen-cache'),
            PYTORCH_KERNEL_CACHE_PATH=str(work / 'kernels'), TRITON_CACHE_DIR=str(work / 'triton'),
            TORCHINDUCTOR_CACHE_DIR=str(work / 'inductor'), TORCH_HOME=str(work / 'torch'))
        report('External Chatterbox ROCm: existing local weights; no silent CPU fallback. Waiting for shared GPU if busy.')
        peak = 0
        with gpu_lock(job.rocm_gpu_lock, cancelled, report, deadline) as lock:
                if cancelled():
                    raise GenerationCancelled()
                with log.open('wb') as sink:
                    proc = subprocess.Popen([str(python), '-I', '-B', '-u', '-X', 'faulthandler', str(runner), str(request), str(response)],
                        stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT,
                        env=env, start_new_session=True, pass_fds=(lock.fileno(),))
                    try:
                        (diagnostics / 'process.json').write_text(json.dumps(dict(pid=proc.pid, process_group=proc.pid,
                            requested_backend='rocm', timeout_seconds=TIME_LIMIT, ram_budget_bytes=RAM_LIMIT)), encoding='utf-8')
                        log_offset = 0
                        while proc.poll() is None:
                            if cancelled():
                                raise GenerationCancelled()
                            if time.monotonic() >= deadline - 5:
                                raise RuntimeError('External ROCm reached the 300-second bound; no output was accepted')
                            peak = max(peak, group_rss(proc.pid))
                            if peak > RAM_LIMIT:
                                raise RuntimeError('External ROCm exceeded the 12 GiB sampled process-group RAM budget')
                            if log.stat().st_size > 8 * 1024**2:
                                raise RuntimeError('External ROCm diagnostics exceeded the bounded log size')
                            with log.open(encoding='utf-8', errors='replace') as stream:
                                stream.seek(log_offset)
                                for line in stream.read(8192).splitlines():
                                    if line.strip(): report(line[-500:])
                                log_offset = stream.tell()
                            time.sleep(.1)
                    finally:
                        stop_group(proc)
        if proc.returncode or not response.is_file():
            detail = log.read_text(encoding='utf-8', errors='replace')[-3000:]
            (diagnostics / 'failure.json').write_text(json.dumps(dict(returncode=proc.returncode,
                sampled_group_peak_rss_bytes=peak, audio_accepted=False)), encoding='utf-8')
            raise RuntimeError('External Chatterbox ROCm failed; choose CPU explicitly if needed. '
                               + 'Diagnostics: ' + str(diagnostics) + '\n' + detail)
        result = json.loads(response.read_text(encoding='utf-8'))
        if not result.get('ok'):
            raise RuntimeError('External Chatterbox ROCm failed: ' + str(result.get('error')))
        runtime = result['runtime']; validate_proof(runtime)
        expected_engine = hashlib.sha256((source / 'chatterbox_studio' / 'engine.py').read_bytes()).hexdigest()
        if runtime.get('engine_source_sha256') != expected_engine:
            raise RuntimeError('External child did not use this build\'s exact shared Chatterbox engine source')
        audio = work / ('render.' + job.format)
        metadata = audio.with_suffix('.json')
        if not audio.is_file() or audio.stat().st_size < 44 or not metadata.is_file():
            raise RuntimeError('External ROCm produced no valid-sized recording and matching metadata')
        if job.format == 'wav':
            with wave.open(str(audio), 'rb') as recording:
                if recording.getnframes() <= 0:
                    raise RuntimeError('External ROCm produced empty audio')
        saved = json.loads(metadata.read_text(encoding='utf-8'))
        if (saved.get('text') != job.text or saved.get('prepared_text') != job.render_text
            or saved.get('generation_kwargs') != job.generation_kwargs()
            or saved.get('effective_settings') != job.effective_settings()
            or saved.get('render_plan') != [asdict(step) for step in job.render_steps()]):
            raise RuntimeError('Child render settings/text differ from the original narration snapshot')
        saved.update(job.as_json(), original_text=job.text, prepared_text=job.render_text,
            output_path=str(target), device_used='rocm', runtime={**runtime,
                'sampled_group_peak_rss_bytes': peak, 'ram_budget_bytes': RAM_LIMIT,
                'timeout_seconds': TIME_LIMIT, 'cpu_fallback': False, 'diagnostics': str(diagnostics),
                'reference_sha256': reference_sha})
        metadata.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding='utf-8')
        if cancelled():
            raise GenerationCancelled()
        publish(audio, metadata, target)
        steps = sum(s.kind == 'speech' for s in job.render_steps())
        progress(steps, steps)
        report('Saved external Chatterbox ROCm recording: ' + str(target))
        return target
