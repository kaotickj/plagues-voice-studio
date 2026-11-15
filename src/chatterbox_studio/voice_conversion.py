"""Offline, one-shot Chatterbox conversion subprocess (no model downloads)."""
from pathlib import Path
import argparse
import os
import time


def convert(source, reference, weights, output, device='cpu', model=None):
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.vc import ChatterboxVC
    for path in (source, reference, Path(weights) / 's3gen.safetensors'):
        if not Path(path).is_file():
            raise ValueError(f'Missing local audio or model file: {path}')
    data, rate = sf.read(source, always_2d=True)
    duration = len(data) / rate
    if not 0.25 <= duration <= 20.1 or not np.isfinite(data).all():
        raise ValueError('Record between 0.25 and 20 seconds of valid audio.')
    if np.max(np.abs(data)) < 0.0001:
        raise ValueError('The recording is silent. Check the microphone input.')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('The selected GPU is unavailable. Choose CPU.')
    start = time.monotonic()
    if model is None:
        model = ChatterboxVC.from_local(Path(weights), device=device)
    loaded = time.monotonic()
    audio = model.generate(str(source), target_voice_path=str(reference))
    audio = np.asarray(audio.detach().cpu()).reshape(-1)
    if not audio.size or not np.isfinite(audio).all():
        raise RuntimeError('Conversion returned invalid audio.')
    sf.write(output, audio, model.sr, subtype='PCM_16')
    print(f'Input {duration:.2f}s; model load {loaded-start:.2f}s; conversion {time.monotonic()-loaded:.2f}s', flush=True)
    return model


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('source', 'reference', 'weights', 'output'):
        parser.add_argument(name)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    args = parser.parse_args()
    convert(**vars(args))
