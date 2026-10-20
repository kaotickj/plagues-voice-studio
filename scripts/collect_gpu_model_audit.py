"""Collect recorded model probes and validate their decoded audio without re-running inference."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT/'artifacts/gpu-model-audit'


def main():
    import numpy as np
    import soundfile as sf
    sources = [
        'text/results.json', 'vision/result.json', 'kokoro-retest/results.json',
        'native-speech/results.json', 'native-speech/index-raw/results.json',
        'native-speech/low-memory/results.json', 'native-speech/cpu-control/results.json',
        'speech-cpu/results.json', 'music/results.json',
        'cached-nlp/bart/result.json', 'cached-nlp/mpnet/result.json', 'cached-nlp/minilm/result.json',
    ]
    report = dict(date='2026-10-20', gpu='AMD Radeon RX 7600 XT, 16 GB', results={}, audio=[])
    paths = set()

    def audio_paths(value):
        if isinstance(value, dict):
            if value.get('audio'): paths.add(Path(value['audio']))
            for child in value.values(): audio_paths(child)
        elif isinstance(value, list):
            for child in value: audio_paths(child)

    for name in sources:
        value = json.loads((AUDIT/name).read_text(encoding='utf-8'))
        report['results'][name] = value
        audio_paths(value)
    for path in sorted(paths):
        data, rate = sf.read(path, dtype='float32', always_2d=True)
        finite = bool(np.isfinite(data).all())
        rms = float(np.sqrt(np.mean(np.square(data, dtype=np.float64)))) if len(data) else 0
        report['audio'].append(dict(path=str(path), frames=len(data), sample_rate=rate,
            channels=data.shape[1], seconds=len(data)/rate, finite=finite, rms=rms,
            peak=float(np.max(np.abs(data))) if len(data) else 0,
            status='passed' if finite and len(data)>0 and rms>1e-5 else 'failed'))
    report['audio_status'] = 'passed' if report['audio'] and all(x['status']=='passed' for x in report['audio']) else 'failed'
    report['scope'] = ('Actual generation/inference for installed model families; failed and unsupported GPU paths remain explicit. '
        'MiniLM ONNX export variants are formats of one model, not independently validated here. '
        'Nonempty finite non-silent WAV checks do not establish transcript accuracy, clone fidelity or music quality. '
        'Kokoro and writer GPU adapters are integrated; native Qwen, Index, ACE and cached NLP probes are experimental tests outside Studio menus.')
    (AUDIT/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(audio_status=report['audio_status'], audio_files=len(report['audio']),
        result_sets=len(sources), report=str(AUDIT/'summary.json'))))
    return 0 if report['audio_status']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
