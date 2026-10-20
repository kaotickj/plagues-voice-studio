"""CPU topology and separate llama.cpp decoding/prompt-processing thread budgets."""
import os
import sys
from functools import lru_cache

@lru_cache(maxsize=1)
def cpu_topology():
    logical=max(1,os.cpu_count() or 1)
    physical=None
    if sys.platform=='win32':
        try:
            import ctypes
            from ctypes import wintypes
            api=ctypes.WinDLL('kernel32',use_last_error=True).GetLogicalProcessorInformationEx
            api.argtypes=[wintypes.DWORD,ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD)]
            api.restype=wintypes.BOOL
            size=wintypes.DWORD(0)
            api(0,None,ctypes.byref(size))  # RelationProcessorCore
            if 0<size.value<1024*1024:
                buffer=ctypes.create_string_buffer(size.value)
                if api(0,buffer,ctypes.byref(size)):
                    offset=0;count=0
                    while offset+8<=size.value:
                        relationship=int.from_bytes(buffer.raw[offset:offset+4],'little')
                        length=int.from_bytes(buffer.raw[offset+4:offset+8],'little')
                        if length<8 or offset+length>size.value:break
                        count+=relationship==0;offset+=length
                    if count:physical=count
        except (OSError,AttributeError,ValueError):pass
    if physical is None:physical=max(1,logical//2) if logical>2 else logical
    return min(physical,logical),logical

def recommended_threads():
    physical,logical=cpu_topology()
    return min(32,physical),min(64,logical)

def thread_budgets(settings):
    decode,batch=recommended_threads()
    decode=max(1,min(32,int(settings.get('cpu_threads',decode))))
    batch_setting=int(settings.get('batch_threads',0))
    batch=max(1,min(64,batch_setting or batch))
    return decode,batch
