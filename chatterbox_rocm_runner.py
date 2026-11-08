"""Isolated Python3.13 bootstrap; imports only explicitly shipped app sources."""
import json
import faulthandler
import os
from pathlib import Path
import signal
import sys


def arm_parent_death(expected_parent):
    """Linux child-only lifecycle guard, armed before any model import."""
    import ctypes
    if sys.platform != 'linux' or os.getppid() != expected_parent:
        raise RuntimeError('The owning Voice Studio parent exited before ROCm bootstrap')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), 'Could not arm owned ROCm child parent-death signal')
    if os.getppid() != expected_parent:
        raise RuntimeError('The owning Voice Studio parent exited during ROCm bootstrap')
    return dict(signal='SIGTERM', parent_pid=expected_parent, scope='owned Linux ROCm child only')


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    faulthandler.enable()
    sys.dont_write_bytecode = True
    request, response = map(Path, sys.argv[1:])
    data = json.loads(request.read_text(encoding='utf-8'))
    data['parent_death_guard'] = arm_parent_death(int(data['parent_pid']))
    sys.path[:0] = [data['overlay'], data['source_root']]
    from chatterbox_studio.rocm_child import run
    run(data, response)
