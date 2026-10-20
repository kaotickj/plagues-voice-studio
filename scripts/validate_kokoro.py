"""Render real Kokoro preset samples through Studio's isolated engine protocol."""
import argparse
from array import array
import json
import math
from pathlib import Path
import sys
import time
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from plagued_ai import root
from chatterbox_studio import optional_engines as oe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/kokoro-validation'))
    parser.add_argument('--python', default='')
    parser.add_argument('--runner', type=Path)
    parser.add_argument('--voice', action='append', choices=oe.KOKORO_VOICES)
    parser.add_argument('--speed', type=float, default=1.0)
    parser.add_argument('--device', choices=['cpu','auto','directml'], default='auto')
    parser.add_argument('--profile', action='store_true', help='Record actual ONNX execution providers for each sample.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.runner:
        runner = args.runner.resolve()
        if not runner.is_file():
            parser.error('Runner file is missing.')
        oe.runtime_script_path = lambda: runner
    python = args.python or oe.EngineRegistry(root()/'apps/voice-studio').read()['kokoro']['python']
    models = str(root() / 'models/speech/kokoro')
    report = {'status':'running','model_dir':models,'python':python,'samples':[]}
    report['probe'] = oe.execute_probe('kokoro', python, model_dir=models,
                                      diagnostic_dir=args.output/'logs', log=print)
    text = ("You're listening to Goodneighbor Blues. The lights are on, the coffee is fresh, "
            "and there's another good record waiting on the turntable. Stay with us. "
            "We'll keep the music coming while you make your way home.")
    for voice in args.voice or oe.KOKORO_VOICES:
        name, accent = oe.KOKORO_VOICES[voice]
        output = oe.new_output_path(args.output, name)
        request = dict(engine='kokoro',model=oe.ENGINES['kokoro']['models'][0],
                       preset_voice=voice,model_dir=models,language=accent,
                       speed=args.speed,device=args.device,text=text,output_path=str(output),profile=args.profile)
        start = time.monotonic()
        audio = oe.execute_generation(request, python, diagnostic_dir=args.output/'logs', log=print)
        elapsed = time.monotonic()-start
        metadata = json.loads(audio.with_suffix('.json').read_text(encoding='utf-8'))
        with wave.open(str(audio),'rb') as f:
            assert f.getnchannels()==1 and f.getsampwidth()==2 and f.getframerate()==24000
            duration = f.getnframes()/f.getframerate()
            samples = array('h',f.readframes(f.getnframes()))
        rms = math.sqrt(sum(x*x for x in samples)/len(samples))/32768
        assert duration > 1 and rms > 0.001, 'Missing or silent synthesis'
        entry = dict(voice=voice,name=name,accent=accent,speed=args.speed,device=args.device,
                     runtime=metadata.get('runtime',{}),audio=str(audio.resolve()),text=text,
                     elapsed_seconds=round(elapsed,3),audio_seconds=round(duration,3),
                     real_time_factor=round(elapsed/duration,3),rms=round(rms,5))
        report['samples'].append(entry)
        (args.output/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(entry),flush=True)
    report['status']='passed'
    (args.output/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('All Kokoro samples passed.',flush=True)


if __name__=='__main__':
    main()
