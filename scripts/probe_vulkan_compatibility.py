"""Isolated native Vulkan probes; never edits driver or application settings."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from plagued_ai import root

OUT=Path(__file__).resolve().parents[1]/'artifacts/vulkan-compatibility'
OUT.mkdir(parents=True,exist_ok=True)
runtime=root()/'runtimes/llama.cpp/b11703-windows-vulkan'
model=root()/'models/text/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
profiles={
    'no-host-visible':{'GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM':'1'},
    'conservative-shaders':{'GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM':'1','GGML_VK_DISABLE_COOPMAT':'1','GGML_VK_DISABLE_COOPMAT2':'1','GGML_VK_DISABLE_DOT2':'1','GGML_VK_DISABLE_ASYNC':'1'},
    'fp32-fallback':{'GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM':'1','GGML_VK_DISABLE_COOPMAT':'1','GGML_VK_DISABLE_COOPMAT2':'1','GGML_VK_DISABLE_DOT2':'1','GGML_VK_DISABLE_ASYNC':'1','GGML_VK_DISABLE_F16':'1'},
}
results=[]
for name,changes in profiles.items():
    env=dict(os.environ,**changes);env['PATH']=str(runtime)+os.pathsep+env.get('PATH','')
    args=[str(runtime/'llama-completion.exe'),'--model',str(model),'--device','Vulkan0','--n-gpu-layers','99','--ctx-size','2048','--threads','6','--predict','32','--prompt','Write one short sentence about a radio repair shop.','--fit','off','--load-mode','mmap','--no-host','--log-verbosity','5']
    print('Testing '+name,flush=True)
    with (OUT/(name+'.log')).open('wb') as log:
        proc=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    record={'profile':name,'environment':changes,'returncode':proc.returncode}
    results.append(record);print(json.dumps(record),flush=True)
    (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    if proc.returncode==0:break
