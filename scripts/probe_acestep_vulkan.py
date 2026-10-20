"""Exercise all five imported ACE-Step components with both DiT variants."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plagued_ai import root


def main():
    out=ROOT/'artifacts/gpu-model-audit/music'
    out.mkdir(parents=True,exist_ok=True)
    runtime=Path(json.loads((out.parent/'acestep-runtime.json').read_text())['runtime'])
    models=root()/'models/music/ace-step-1.5'
    request=dict(caption='Instrumental slow blues trio, warm electric guitar, upright bass, brushed drums, intimate small-club sound.',
                 lyrics='[Instrumental]',bpm=70,duration=10,keyscale='A minor',timesignature='4',vocal_language='english',
                 seed=731,lm_batch_size=1,synth_batch_size=1,lm_temperature=0.6,lm_cfg_scale=1.0,
                 use_cot_caption=False,output_format='wav16',lm_model='acestep-5Hz-lm-0.6B-Q8_0.gguf')
    input_path=out/'request.json'
    input_path.write_text(json.dumps(request,indent=2))
    env=dict(os.environ,VK_LOADER_LAYERS_DISABLE='VK_LAYER_RENDERDOC_Capture')
    results=[]
    def run(stage,exe,path):
        start=time.monotonic()
        command=[str(runtime/exe),'--models',str(models),'--request',str(path),'--device','Vulkan0']
        with (out/(stage+'.log')).open('wb') as log:
            proc=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            try:code=proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                proc.kill();proc.wait();raise RuntimeError(stage+' exceeded ten minutes')
        record={'stage':stage,'exit':code,'elapsed_seconds':round(time.monotonic()-start,3)}
        results.append(record)
        (out/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(record),flush=True)
        if code:raise RuntimeError(stage+' failed; inspect log')
    run('lm','ace-lm.exe',input_path)
    enriched=out/'request0.json'
    if not enriched.exists():
        candidates=[p for p in out.glob('*.json') if p.name not in ('request.json','results.json')]
        enriched=next(p for p in candidates if json.loads(p.read_text()).get('audio_codes'))
    data=json.loads(enriched.read_text())
    assert data.get('audio_codes'),'ACE LM did not generate conditioning codes'
    for variant,steps in [('turbo',8),('sft',50)]:
        job=dict(data,synth_model=f'acestep-v15-{variant}-Q8_0.gguf',inference_steps=steps,
                 duration=10,output_format='wav16',seed=731)
        path=out/(variant+'.json');path.write_text(json.dumps(job,indent=2))
        before=set(out.glob('*.wav'))
        run(variant,'ace-synth.exe',path)
        audio=next(p for p in out.glob('*.wav') if p not in before)
        with wave.open(str(audio),'rb') as f:
            results[-1].update(audio=str(audio),audio_seconds=f.getnframes()/f.getframerate(),
                               sample_rate=f.getframerate(),channels=f.getnchannels())
            assert f.getnframes()>0 and f.getnchannels()==2
        (out/'results.json').write_text(json.dumps(results,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
