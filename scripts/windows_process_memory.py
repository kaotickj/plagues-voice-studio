"""Sample an owned process and Windows commit headroom without changing settings."""
import ctypes
from ctypes import wintypes
import subprocess
import sys
import time


def wait_with_memory(proc,timeout):
    if sys.platform!='win32':return proc.wait(timeout=timeout),{}
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[
            (name,ctypes.c_size_t) for name in ['peak_working','working','peak_paged_pool','paged_pool',
                'peak_nonpaged_pool','nonpaged_pool','pagefile','peak_pagefile','private']]
    class Status(ctypes.Structure):
        _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[
            (name,ctypes.c_ulonglong) for name in ['total_phys','avail_phys','total_pagefile',
                'avail_pagefile','total_virtual','avail_virtual','extended']]
    get_process=ctypes.WinDLL('psapi').GetProcessMemoryInfo
    get_process.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    get_system=ctypes.WinDLL('kernel32').GlobalMemoryStatusEx
    get_system.argtypes=[ctypes.POINTER(Status)]
    peak=0;minimum=None;start=time.monotonic()
    while proc.poll() is None:
        process=Counters();process.cb=ctypes.sizeof(process)
        if get_process(int(proc._handle),ctypes.byref(process),ctypes.sizeof(process)):
            peak=max(peak,process.private)
        system=Status();system.length=ctypes.sizeof(system)
        if get_system(ctypes.byref(system)):
            minimum=system.avail_pagefile if minimum is None else min(minimum,system.avail_pagefile)
        if time.monotonic()-start>timeout:
            raise subprocess.TimeoutExpired(proc.args,timeout)
        time.sleep(0.05)
    return proc.returncode,{'peak_private_mib':round(peak/(1024**2),1),
                           'minimum_available_commit_mib':round(minimum/(1024**2),1) if minimum is not None else None}
