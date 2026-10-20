"""Offline reference checks for every installed Studio speech-model choice."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plagued_ai import root,app_dir


def chatterbox(model,output):
    import torch
    torch.set_num_threads(6);torch.manual_seed(731)
    from chatterbox_studio.engine import Engine
    from chatterbox_studio.jobs import NarrationJob
    job=NarrationJob.new(text="Good evening. You're listening to Goodneighbor Blues.",model=model,device='cpu',
        language='en',voice_path=str(ROOT/'artifacts/gpu-model-audit/reference.wav'),output_path=output,
        max_chars=180,pause_ms=100,temperature=0.7)
    Engine().render(job,lambda x:print(x,flush=True),lambda a,b:print(a,b,flush=True),lambda:False)


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',action='append',default=[])
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/gpu-model-audit/speech-cpu')
    args=parser.parse_args()
    from chatterbox_studio.optional_engines import ENGINES,EngineRegistry,execute_generation
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='6',MKL_NUM_THREADS='6')
    config=EngineRegistry(app_dir('voice-studio')).read()
    jobs=[(name,'chatterbox',name) for name in ('nano','turbo','english','multilingual-v3')]
    jobs += [('qwen-tts-'+size,'qwen3',model) for size,model in zip(('0.6b','1.7b'),ENGINES['qwen3']['models'])]
    jobs += [('index25','index25',ENGINES['index25']['models'][0])]
    if args.only:
        jobs=[job for job in jobs if job[0] in args.only]
        if not jobs:parser.error('No matching speech models')
    results=[]
    for name,engine,model in jobs:
        print('CPU reference test:',name,flush=True)
        folder=out/name;folder.mkdir(exist_ok=True)
        audio=folder/'output.wav'
        result={'model':name,'backend':'cpu','status':'failed'}
        start=time.monotonic()
        try:
            if engine=='chatterbox':
                with (folder/'native.log').open('wb') as log:
                    p=subprocess.run([sys.executable,'-u',str(Path(__file__).resolve()),'--chatterbox',model,str(audio)],
                        stdout=log,stderr=subprocess.STDOUT,env=os.environ.copy(),timeout=600)
                if p.returncode:raise RuntimeError('Chatterbox exited '+str(p.returncode))
            else:
                request=dict(engine=engine,model=model,language='English' if engine=='qwen3' else 'EN',
                    text="Good evening. You're listening to Goodneighbor Blues.",device='cpu',
                    voice_path=str(ROOT/'artifacts/gpu-model-audit/reference.wav'),output_path=str(audio),repo=config[engine].get('repo',''))
                execute_generation(request,config[engine]['python'],timeout_seconds=600,diagnostic_dir=folder/'logs',log=lambda x:print(x,flush=True))
            with wave.open(str(audio),'rb') as f:
                assert f.getnframes()>0
                result.update(audio_seconds=f.getnframes()/f.getframerate(),sample_rate=f.getframerate())
            result.update(status='passed',audio=str(audio))
        except Exception as exc:result['error']=str(exc)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        results.append(result)
        (out/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(result),flush=True)
    return 0 if all(r['status']=='passed' for r in results) else 1


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--chatterbox':
        chatterbox(sys.argv[2],sys.argv[3])
    else:raise SystemExit(main())
