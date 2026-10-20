"""Explicit local Kokoro inference check, also callable from the frozen EXE."""
import json
from pathlib import Path
import traceback
import wave

from .optional_engines import ENGINES, EngineRegistry, execute_generation, new_output_path
from plagued_ai import app_dir


def run(report_path: Path) -> int:
    report_path = report_path.absolute()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {'status':'failed','test':'Kokoro isolated inference from application process'}
    try:
        config = EngineRegistry(app_dir('voice-studio')).read()['kokoro']
        output = new_output_path(report_path.parent, 'Kokoro_Michael_frozen_check')
        request = dict(engine='kokoro', model=ENGINES['kokoro']['models'][0],
            model_dir=config['model_dir'], preset_voice='am_michael',
            language='English (US)',device='auto',speed=1.0,profile=True,
            text='This is a local voice check. The music will be back in a moment.',
            output_path=str(output))
        audio = execute_generation(request, config['python'], diagnostic_dir=report_path.parent/'logs')
        with wave.open(str(audio),'rb') as f:
            if f.getnchannels()!=1 or f.getsampwidth()!=2 or f.getframerate()!=24000 or f.getnframes()<2400:
                raise RuntimeError('Kokoro returned an unexpected WAV format or empty recording.')
        metadata = json.loads(audio.with_suffix('.json').read_text(encoding='utf-8'))
        report.update(status='passed',audio=str(audio),runtime=metadata['runtime'])
    except Exception:
        report['error']=traceback.format_exc()
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='passed' else 1
