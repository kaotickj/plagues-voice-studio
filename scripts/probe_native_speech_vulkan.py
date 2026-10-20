"""Try existing speech checkpoints in an isolated native Vulkan runtime."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plagued_ai import root
from windows_process_memory import wait_with_memory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',action='append')
    parser.add_argument('--case',default='')
    parser.add_argument('--backend',choices=['cpu','vulkan'],default='vulkan')
    parser.add_argument('--low-memory',action='store_true')
    args=parser.parse_args()
    base=ROOT/'artifacts/gpu-model-audit'
    out=base/'native-speech'
    if args.case:out=out/args.case
    out.mkdir(parents=True,exist_ok=True)
    meta=json.loads((base/'native-runtime.json').read_text())
    executable=next(Path(meta['runtime']).rglob('audiocpp_cli.exe'))
    source=Path(meta['source'])
    staged=json.loads((base/'native-checkpoints.json').read_text())
    jobs=[]
    for size in ('0.6B','1.7B'):
        snapshot=Path(staged[f'qwen-tts-{size}']['path'])
        jobs.append((f'qwen-tts-{size}','qwen3_tts',snapshot,
                     ['--request-option','x_vector_only_mode=true']))
    for model in ('english','multilingual-v3'):
        jobs.append(('chatterbox-'+model,'chatterbox',Path(staged['chatterbox-'+model]['path']),
                     ['--session-option','chatterbox.multilingual_t3=v3'] if model=='multilingual-v3' else []))
    index=root()/'models/native-audio/index25'
    if (index/'config.yaml').exists():
        jobs.append(('index25','index_tts2',index,[]))
    results=[]
    env=dict(os.environ,VK_LOADER_LAYERS_DISABLE='VK_LAYER_RENDERDOC_Capture',
             HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    for name,family,model,extra in jobs:
        if args.only and name not in args.only:continue
        folder=out/name;folder.mkdir(exist_ok=True)
        audio=folder/'output.wav'
        if audio.exists():raise RuntimeError('Refusing to overwrite '+str(audio))
        spec=staged.get(name,{}).get('spec',str(source/'model_specs'/(family+'.json')))
        language='es' if name=='chatterbox-multilingual-v3' else 'en'
        text='Buenas noches. Estás escuchando Goodneighbor Blues.' if language=='es' else "Good evening. You're listening to Goodneighbor Blues."
        command=[str(executable),'--task','tts','--family',family,'--model',str(model),
                 '--model-spec-override',spec,
                 '--backend',args.backend,'--device','0','--threads','6','--log','--metrics',
                 '--text',text,
                 '--voice-ref',str(base/'reference.wav'),'--language',language,
                 '--seed','731','--max-tokens','192','--out',str(audio)]+extra
        if args.low_memory:
            prefix='chatterbox' if family=='chatterbox' else 'index_tts2'
            command+=['--session-option',prefix+'.mem_saver=true','--session-option',prefix+'.weight_type=q8_0']
        print('Testing '+name,flush=True)
        (folder/'command.json').write_text(json.dumps(command,indent=2))
        start=time.monotonic()
        result={'model':name,'backend':args.backend,'status':'failed','checkpoint':str(model)}
        try:
            with (folder/'native.log').open('wb') as log:
                proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=executable.parent,
                    env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                try:
                    code,memory=wait_with_memory(proc,300)
                    result['memory']=memory
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait();raise RuntimeError('Native synthesis exceeded five minutes')
            result['exit_code']=code
            if code:raise RuntimeError(f'Native engine exited {code}')
            with wave.open(str(audio),'rb') as f:
                duration=f.getnframes()/f.getframerate()
                assert duration>0.2
            result.update(status='passed',audio=str(audio),audio_seconds=duration)
        except Exception as exc:
            result['error']=str(exc)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        (folder/'result.json').write_text(json.dumps(result,indent=2))
        results.append(result)
        (out/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(result),flush=True)
    return 0 if results and all(r['status']=='passed' for r in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
