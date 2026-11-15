"""Isolated recovered Python bootstrap; only explicit local script execution."""
import json
import os
from pathlib import Path
import runpy
import sys

base = Path(__file__).resolve().parent
config = json.loads((base/'dependencies.json').read_text())
engine, script, *arguments = sys.argv[1:]
if engine not in ('index25', 'chatterbox'):
    raise SystemExit('Unknown Speak as runtime')
script = Path(script).resolve()
if not script.is_file():
    raise SystemExit('The requested local worker script is missing: ' + str(script))
cache = base/'cache'/engine
for folder in ('numba','mpl','miopen-db','miopen'):
    (cache/folder).mkdir(parents=True, exist_ok=True)
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
    XDG_CACHE_HOME=str(cache), NUMBA_CACHE_DIR=str(cache/'numba'), MPLCONFIGDIR=str(cache/'mpl'),
    MIOPEN_USER_DB_PATH=str(cache/'miopen-db'), MIOPEN_CUSTOM_CACHE_DIR=str(cache/'miopen'),
    OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
# No global library search path, Python environment modification, or package install.
for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONEXECUTABLE', 'LD_LIBRARY_PATH'):
    os.environ.pop(key, None)
sys.path.insert(0, config['index_site'] if engine == 'index25' else config['chatterbox_overlay'])
sys.path.insert(0, str(script.parent))
sys.argv = [str(script), *arguments]
runpy.run_path(str(script), run_name='__main__')
