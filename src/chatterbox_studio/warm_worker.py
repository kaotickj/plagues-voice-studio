"""JSON-lines inference service; one model, one request at a time, no UI imports."""
import contextlib
import gc
import json
import os
from pathlib import Path
import socket
import sys
import time


def offline():
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    connect = socket.socket.connect
    def guarded(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise OSError('Speak as is offline; install required assets explicitly.')
        return connect(sock, address)
    socket.socket.connect = guarded
    socket.socket.connect_ex = guarded


def validate_audio(path):
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(path) as audio:
        if audio.frames == 0 or audio.samplerate < 8000 or audio.frames / audio.samplerate > 120:
            raise ValueError('Model returned empty or excessively long audio.')
        audible = False
        for block in audio.blocks(blocksize=65536):
            if not np.isfinite(block).all():
                raise ValueError('Model returned non-finite audio.')
            audible = audible or bool(np.any(block))
        if not audible:
            raise ValueError('Model returned silent audio.')


def load_index_runner():
    """Load our pure Python adapter without exposing the frozen library tree.

    Adding _internal to sys.path lets the external Python load the application's
    bundled Torch/native extensions, which may target a different Python ABI.
    Execute only this owned file; imports keep using the selected engine runtime.
    """
    import importlib.util
    here = Path(__file__).resolve()
    root = here.parents[2] if (here.parents[2] / 'optional_engine_runner.py').is_file() else here.parents[1]
    spec = importlib.util.spec_from_file_location('_pvs_speak_as_index_runner', root / 'optional_engine_runner.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.index_run


class Session:
    def __init__(self, validator=validate_audio):
        self.validator = validator
        self.model = None
        self.key = None
        self.lock = None
        self.index_runner = None

    def release(self):
        self.model = None
        self.key = None
        gc.collect()
        if self.lock:
            self.lock.close()
            self.lock = None

    def __call__(self, req):
        engine = req['engine']
        if engine not in ('chatterbox', 'index25', 'seed_v1'):
            raise ValueError('Unsupported Speak as engine')
        key = (engine, req.get('device', 'cpu'), req.get('weights'), req.get('repo'), req.get('cache'), req.get('manifest'))
        if self.key is not None and self.key != key:
            raise ValueError('Runtime configuration changed; restart the worker.')
        if key[1] == 'cuda' and self.lock is None:
            if sys.platform != 'linux':
                raise RuntimeError('Warm GPU worker currently requires Linux GPU locking.')
            import fcntl
            path = os.environ.get('PVS_GPU_LOCK', '/run/lock/gnb-ai-gpu.lock')
            lock = open(path, 'r+')  # Existing shared lock only; no private substitute.
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except Exception:
                lock.close()
                raise RuntimeError('The GPU is reserved by another application. Try later or choose CPU.')
            self.lock = lock
        was_warm = self.model is not None
        started = time.monotonic()
        details = {}
        if engine == 'seed_v1':
            from seed_conversion import convert
            self.model, details = convert(req, model=self.model)
        elif engine == 'chatterbox':
            from voice_conversion import convert
            self.model = convert(req['source'], req['reference'], req['weights'], req['output_path'],
                                 req.get('device', 'cpu'), model=self.model)
        else:
            repo = Path(req['repo']).resolve()
            sys.path.insert(0, str(repo))
            os.chdir(repo)
            if self.index_runner is None:
                self.index_runner = load_index_runner()
            self.model = self.index_runner(req, synthesizer=self.model)
        self.validator(req['output_path'])
        self.key = key
        result = {'output_path': req['output_path'], 'seconds': time.monotonic()-started, 'warm': was_warm}
        if engine == 'index25':
            result.update(reference_seconds=getattr(self.model, '_pvs_reference_seconds', 0),
                          reference_note=getattr(self.model, '_pvs_reference_note', ''))
        result.update(details)
        return result


def serve(handler, source, destination):
    for line in source:
        request_id = None
        try:
            if len(line) > 65536:
                raise ValueError('Request too large')
            req = json.loads(line)
            request_id = req['id']
            # ML libraries print progress; never mix it with protocol stdout.
            with contextlib.redirect_stdout(sys.stderr):
                result = handler(req)
            response = dict(result, id=request_id, ok=True)
        except Exception as exc:
            response = dict(id=request_id, ok=False, error=str(exc))
        destination.write(json.dumps(response) + '\n')
        destination.flush()
        if not response['ok']:
            # Do not reuse partially initialized model state after an error.
            break


if __name__ == '__main__':
    offline()
    session = Session()
    try:
        serve(session, sys.stdin, sys.stdout)
    finally:
        session.release()
