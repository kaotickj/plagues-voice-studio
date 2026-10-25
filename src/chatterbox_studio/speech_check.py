"""Explicit real-inference acceptance check for source and frozen applications.

Invoked only with --speech-self-test request.json report.json. Outputs are
unique siblings of the report; reference audio is read, never modified.
"""
from contextlib import redirect_stderr, redirect_stdout
import faulthandler
import json
from pathlib import Path
import sys
import time
import traceback

from .optional_engines import EngineRegistry, execute_generation, new_output_path
from .paths import user_data_dir


def run(request_path: Path, report_path: Path) -> int:
    report_path=report_path.absolute()
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report={'status':'running','frozen':bool(getattr(sys,'frozen',False)),
            'request':str(request_path),'log':str(report_path.with_suffix('.log'))}
    started=time.monotonic()
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    with report_path.with_suffix('.log').open('w',encoding='utf-8') as log:
        with redirect_stdout(log),redirect_stderr(log):
            faulthandler.enable(file=log)
            try:
                request=json.loads(Path(request_path).read_text(encoding='utf-8'))
                output=new_output_path(report_path.parent,'speech-'+request['engine']+'-'+report_path.stem)
                request['output_path']=str(output)
                report.update(engine=request['engine'],model=request['model'],text=request['text'])
                if request['engine']=='chatterbox':
                    import torch
                    from .engine import Engine
                    from .jobs import NarrationJob
                    torch.set_num_threads(6);torch.manual_seed(731)
                    allowed=('text','model','device','language','voice_path','output_path',
                             'pause_ms','max_chars','exaggeration','cfg_weight','temperature',
                             'profile','voice_id','prepared_text','render_scope')
                    job=NarrationJob.new(**{k:v for k,v in request.items() if k in allowed})
                    audio=Engine().render(job,lambda s:print(s,flush=True),lambda *a:None,lambda:False)
                else:
                    config=EngineRegistry(user_data_dir()).read()[request['engine']]
                    request['repo']=config.get('repo','')
                    if request['engine']=='kokoro':request['model_dir']=config['model_dir']
                    audio=execute_generation(request,config['python'],diagnostic_dir=report_path.parent/'logs')
                import numpy as np
                import soundfile as sf
                samples,rate=sf.read(audio,dtype='float32')
                rms=float(np.sqrt(np.mean(samples.astype(np.float64)**2))) if samples.size else 0
                if not samples.size or not np.isfinite(samples).all() or rms<=1e-5:
                    raise RuntimeError('Speech output is empty, invalid or silent')
                sidecar=audio.with_suffix('.json')
                metadata=json.loads(sidecar.read_text(encoding='utf-8'))
                if metadata.get('text',metadata.get('output_text'))!=request['text']:
                    raise RuntimeError('Saved output transcript does not match the generated script')
                if request['engine']=='chatterbox':
                    if metadata.get('prepared_text',metadata.get('text'))!=job.render_text:
                        raise RuntimeError('Saved render input does not match the requested passage')
                    if metadata.get('effective_settings')!=job.effective_settings():
                        raise RuntimeError('Saved effective settings do not match the requested profile')
                    report.update(profile=job.profile,render_scope=job.render_scope,
                                  prepared_text=job.render_text,effective_settings=job.effective_settings())
                report.update(status='passed',audio=str(audio),sample_rate=rate,seconds=len(samples)/rate,
                              rms=rms,metadata=str(sidecar),runtime=metadata.get('runtime',{}))
            except Exception:
                report.update(status='failed',error=traceback.format_exc())
            finally:
                faulthandler.disable()
    report['elapsed_seconds']=round(time.monotonic()-started,3)
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='passed' else 1
