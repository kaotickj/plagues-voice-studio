"""Fetch developer-published ACE-Step Windows tools without installing a service."""
import hashlib
import json
from pathlib import Path
from setup_gpu_probe_runtimes import fetch,root,ROOT


def main():
    base='https://www.serveurperso.com/temp/acestep.cpp-win64/build/Release/'
    runtime=root()/'runtimes/acestep.cpp/windows-vulkan-probe'
    files=['ace-lm.exe','ace-synth.exe','ace-server.exe','ggml.dll','ggml-base.dll',
           'ggml-vulkan.dll','ggml-cpu-x64.dll','ggml-cpu-haswell.dll']
    records=[]
    for name in files:
        path=runtime/name
        fetch(base+name,path)
        with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
        records.append({'file':name,'url':base+name,'sha256':sha,'bytes':path.stat().st_size})
        print(name,path.stat().st_size,flush=True)
    folder=ROOT/'artifacts/gpu-model-audit'
    (folder/'acestep-runtime.json').write_text(json.dumps({'runtime':str(runtime),'files':records,
        'note':'Developer-published HTTPS binaries; hashes recorded locally, no publisher checksums supplied.'},indent=2))


if __name__=='__main__':main()
