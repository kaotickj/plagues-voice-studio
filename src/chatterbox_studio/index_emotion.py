"""Offline IndexTTS emotion stage. ASR has already exited before this starts."""
import json
import os
from pathlib import Path
import socket
import sys
import time


def run(request):
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    original_connect = socket.socket.connect
    def offline(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise OSError('Speak as is offline; required assets must already be installed.')
        return original_connect(sock, address)
    socket.socket.connect = offline
    sys.path.insert(0, str(Path(request['repo']).resolve()))
    here = Path(__file__).resolve()
    runner_root = here.parents[2] if (here.parents[2] / 'optional_engine_runner.py').is_file() else here.parents[1]
    import importlib.util
    spec = importlib.util.spec_from_file_location('_pvs_index_emotion_runner', runner_root / 'optional_engine_runner.py')
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    index_run = adapter.index_run
    start = time.monotonic()
    index_run(request)
    print(f'IndexTTS emotion synthesis: {time.monotonic()-start:.2f}s', flush=True)


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
