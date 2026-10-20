"""Retest every shared writing-model GGUF, including imported Ollama weights."""
import json
import os
from pathlib import Path
import re
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'plugins')]
from plagued_ai import root
from writer_core.runtime import WriterRuntime
from writer_core.settings import default_settings
from writer_core.downloads import MODELS,RUNTIME_VERSION
import writer_core.runtime as runtime_module


def main():
    out=ROOT/'artifacts/gpu-model-audit/text'
    out.mkdir(parents=True,exist_ok=True)
    models=[(key,root()/'models/text'/MODELS[key]['filename']) for key in ('gemma-writer','qwen-small')]
    store=root()/'models/ollama'
    for manifest in sorted((store/'manifests').rglob('*')):
        if not manifest.is_file():continue
        data=json.loads(manifest.read_text(encoding='utf-8'))
        for layer in data.get('layers',[]):
            if layer.get('mediaType')=='application/vnd.ollama.image.model':
                label='ollama-'+manifest.parent.name+'-'+manifest.name
                original=store/'blobs'/layer['digest'].replace(':','-')
                alias=out/(label+'.gguf')
                with original.open('rb') as f:
                    if f.read(4)!=b'GGUF':raise RuntimeError('Ollama model layer is not GGUF: '+str(original))
                if not alias.exists():os.link(original,alias)
                models.append((label,alias))
    results=[]
    messages=[{'role':'system','content':'Write only the requested spoken copy. Do not show reasoning.'},
              {'role':'user','content':'Write a 25-word radio station ID for Goodneighbor Blues. Mention late-night blues music and invite listeners to stay tuned. /no_think'}]
    for label,model in models:
        folder=out/label;folder.mkdir(exist_ok=True)
        settings=default_settings()
        settings.update(model_path=str(model),server_path=str(root()/'runtimes/llama.cpp'/f'{RUNTIME_VERSION}-windows-vulkan/llama-server.exe'),
                        backend='Vulkan',context_size=4096,cpu_threads=6,batch_threads=12,auto_memory_recovery=False)
        runtime=WriterRuntime(settings,folder)
        original=runtime._request
        def request(route,payload=None,timeout=5):
            if payload is not None and route=='/v1/chat/completions':
                payload=dict(payload,seed=731,temperature=0,max_tokens=192,
                             chat_template_kwargs={'enable_thinking':False})
            return original(route,payload,timeout)
        runtime._request=request
        print('Testing '+label,flush=True)
        result={'model':label,'path':str(model),'status':'failed'}
        try:
            spawn=runtime_module.subprocess.Popen
            def verbose_spawn(command,**kwargs):
                return spawn(list(command)+['-lv','5'],**kwargs)
            with patch.object(runtime_module.subprocess,'Popen',verbose_spawn):
                generated=runtime.generate_messages(messages,words=25,status=lambda x:print(x,flush=True))
            logs=Path(generated['log']).read_text(encoding='utf-8',errors='replace')
            evidence=[line for line in logs.splitlines() if re.search('offload|Vulkan0|Radeon|tokens per second',line,re.I)]
            if not any(re.search(r'offloaded [1-9]\d*/',line) for line in evidence):
                raise RuntimeError('No nonzero GPU layer-offload evidence in the native log')
            if not generated['text'].strip():raise RuntimeError('No generated text')
            result.update(status='passed',generation=generated,evidence=evidence)
            (folder/'output.txt').write_text(generated['text'],encoding='utf-8')
        except Exception as exc:
            result['error']=str(exc)
            result['log']=str(runtime.log_path)
        results.append(result)
        (out/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(json.dumps({'model':label,'status':result['status'],'error':result.get('error')}),flush=True)
    return 0 if all(r['status']=='passed' for r in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
