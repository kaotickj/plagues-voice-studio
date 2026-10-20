"""Matched, sequential CPU/Vulkan text generation using shared writing models."""
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'plugins')]
from plagued_ai import root
from writer_core.settings import default_settings
from writer_core.downloads import MODELS,RUNTIME_VERSION
from writer_core.runtime import WriterRuntime

OUT=ROOT/'artifacts/vulkan-benchmark'
PROMPT=[{'role':'system','content':'Write only the requested spoken advertisement. Use only the supplied facts.'},
        {'role':'user','content':'Write a 45 to 55 word advertisement for Harbor Radio Repair. Facts: independent workshop; repairs tabletop radios and record players; provides a written estimate before repairs; customers decide whether to approve the work. End by inviting listeners to bring their equipment for assessment. Do not invent prices, hours, warranties, expertise claims or discounts.'}]


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    (OUT/'protocol.json').write_text(json.dumps({'messages':PROMPT,'seed':731,'temperature':0,'max_tokens':256,'context':8192,'threads':6,'prompt_threads':12,'order':['gemma-writer/CPU','gemma-writer/Vulkan','qwen-small/CPU','qwen-small/Vulkan'],'note':'One cold load and one draft per configuration; exploratory measurement, not a broad quality benchmark.'},indent=2),encoding='utf-8')
    for preset in ('gemma-writer','qwen-small'):
        for backend in ('CPU','Vulkan'):
            folder=OUT/(preset+'-'+backend.lower());folder.mkdir(exist_ok=True)
            variant='windows-cpu' if backend=='CPU' else 'windows-vulkan'
            settings=default_settings()
            settings.update(server_path=str(root()/'runtimes/llama.cpp'/f'{RUNTIME_VERSION}-{variant}'/'llama-server.exe'),
                            model_path=str(root()/'models/text'/MODELS[preset]['filename']),model_preset=preset,
                            backend=backend,cpu_threads=6,batch_threads=12,context_size=8192,auto_memory_recovery=False)
            runtime=WriterRuntime(settings,folder)
            original=runtime._request
            def request(route,payload=None,timeout=5):
                if payload is not None and route=='/v1/chat/completions':
                    payload=dict(payload,seed=731,temperature=0,max_tokens=256)
                return original(route,payload,timeout)
            runtime._request=request
            print(f'Starting {preset} on {backend}',flush=True)
            try:
                result=runtime.generate_messages(PROMPT,words=50,status=lambda message:print(message,flush=True))
                log=Path(result['log']).read_text(encoding='utf-8',errors='replace')
                result.update(preset=preset,backend=backend,evidence=[line for line in log.splitlines() if re.search(r'offload|Vulkan0|Radeon|tokens per second',line,re.I)])
                (folder/'output.txt').write_text(result['text'],encoding='utf-8')
            except Exception as exc:
                result={'preset':preset,'backend':backend,'error':str(exc),'log':str(runtime.log_path)}
            (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            results.append(result)
            (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
            print(json.dumps({k:result.get(k) for k in ('preset','backend','elapsed_seconds','load_seconds','first_text_seconds','error')}),flush=True)
    return 0 if all('error' not in r for r in results) else 1


if __name__=='__main__':
    raise SystemExit(run())
