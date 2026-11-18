"""Offline, CPU-only preset speech; shares the validated Studio adapter."""
import json
import sys
import time
from pathlib import Path
from warm_worker import offline, load_index_runner, validate_audio

offline()
# Locate the sibling adapter without importing the Studio GUI or frozen libraries.
import importlib.util
spec = importlib.util.spec_from_file_location('adapter', Path(__file__).resolve().parents[2] / 'optional_engine_runner.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
req = json.loads(Path(sys.argv[1]).read_text())
started = time.monotonic()
try:
    adapter.kokoro_run(req)
    validate_audio(req['output_path'])
    print(json.dumps({'ok': True, 'seconds': time.monotonic()-started, 'output_path': req['output_path']}), flush=True)
except Exception as exc:
    print(json.dumps({'ok': False, 'error': str(exc)}), flush=True)
    sys.exit(1)
