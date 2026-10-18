"""Out-of-process optional TTS backends. Run with an isolated Python environment.

No optional packages are needed by Plague's Voice Studio itself. Only stdlib
imports take place until the user explicitly requests a probe or generation.
"""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
import sys
import traceback


def stage(text: str) -> None:
    print('[PVS] ' + text, flush=True)

def probe(engine: str) -> dict:
    try:
        stage(f'Checking optional engine {engine} imports')
        if engine == 'qwen3':
            from qwen_tts import Qwen3TTSModel  # noqa: F401
            import torch
            import soundfile  # noqa: F401
        elif engine == 'index25':
            from indextts.infer_v2_5 import IndexTTS2  # noqa: F401
            import torch
        else:
            raise RuntimeError('Unknown optional engine')
        stage('Import check finished')
        return {'ready': True, 'torch': torch.__version__,
                'cuda_available': bool(torch.cuda.is_available())}
    except Exception as exc:
        return {'ready': False, 'error': f'{type(exc).__name__}: {exc}'}


def _device(mode: str, torch):
    if mode == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable in this isolated engine.')
    return 'cuda:0' if (mode == 'cuda' or (mode == 'auto' and torch.cuda.is_available())) else 'cpu'


def qwen_run(req: dict) -> None:
    stage('Importing Qwen3-TTS and PyTorch; this may take some time on CPU')
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel
    device = _device(req.get('device', 'cpu'), torch)
    stage(f'Compute device: {device}; PyTorch: {torch.__version__}')
    cache = Path(os.environ.get('HF_HOME', str(Path.home() / '.cache' / 'huggingface')))
    try:
        free_gb = shutil.disk_usage(cache if cache.exists() else Path.home()).free / (1024 ** 3)
        stage(f'Available disk space on model-cache volume: {free_gb:.1f} GiB')
        if free_gb < 2:
            stage('WARNING: Low disk space may prevent model downloads or caching.')
    except OSError:
        pass
    stage('Loading model. First use may download gigabytes of weights from Hugging Face.')
    # Avoid hard-depending on FlashAttention/CUDA in a Windows/AMD installation.
    # Eager attention and fp32 are deliberate compatibility-first defaults on CPU.
    model = Qwen3TTSModel.from_pretrained(
        req['model'], device_map=device,
        dtype=torch.bfloat16 if device.startswith('cuda') else torch.float32,
        attn_implementation='eager',
    )
    stage('Model loaded successfully; preparing speaker reference')
    ref_text = req.get('ref_text', '').strip()
    options = {
        'text': req['text'], 'language': req['language'],
        'ref_audio': req['voice_path'],
    }
    if ref_text:
        options['ref_text'] = ref_text
    else:
        # Supported upstream alternative when no exact reference transcript exists.
        options['x_vector_only_mode'] = True
    stage('Generating speech; CPU inference may take several minutes')
    waves, sr = model.generate_voice_clone(**options)
    stage('Generation finished; writing WAV file')
    sf.write(req['output_path'], waves[0], sr, subtype='PCM_16')
    stage('WAV saved successfully')


def index_run(req: dict) -> None:
    stage('Importing IndexTTS and PyTorch')
    import torch
    from indextts.infer_v2_5 import IndexTTS2
    device = _device(req.get('device', 'cpu'), torch)
    root = Path(req['repo']).resolve()
    checkpoints = root / 'checkpoints'
    # Keep diagnostic output ahead of the memory-intensive constructor: native
    # extensions can abort Python without raising a catchable exception.
    stage(f'IndexTTS runtime: Python {sys.version.split()[0]}, '
          f'PyTorch {torch.__version__}, device {device}, '
          f'CPU inference threads {torch.get_num_threads()}')
    stage('Loading IndexTTS model and checkpoints (conservative backend)')
    synthesizer = IndexTTS2(
        cfg_path=str(checkpoints / 'config.yaml'),
        model_dir=str(checkpoints),
        device=device,
        use_bf16=device.startswith('cuda'),
        use_cuda_kernel=False,
        use_deepspeed=False,
        use_accel=False,
        use_torch_compile=False,
        use_qwen_emo=False,
    )
    stage('IndexTTS model initialization finished')
    options = {
        'spk_audio_prompt': req['voice_path'], 'text': req['text'],
        'lang': req['language'], 'output_path': req['output_path'],
        'duration_factor': float(req.get('speed', 1.0)), 'verbose': False,
    }
    emotion = req.get('emotion', 'neutral')
    emotions = ['happy', 'angry', 'sad', 'afraid', 'disgusted', 'melancholic', 'surprised', 'calm']
    if emotion in emotions:
        options['emo_vector'] = [0.8 if item == emotion else 0.0 for item in emotions]
    stage('Generating IndexTTS speech')
    synthesizer.infer(**options)
    stage('IndexTTS WAV saved successfully')


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == '--probe':
        print(json.dumps(probe(argv[2])))
        return 0
    if len(argv) != 4 or argv[1] != '--run':
        print('Usage: optional_engine_runner.py --probe <qwen3|index25> OR --run request.json result.json', file=sys.stderr)
        return 2
    request_path, response_path = Path(argv[2]), Path(argv[3])
    try:
        req = json.loads(request_path.read_text(encoding='utf-8'))
        if req['engine'] == 'qwen3':
            qwen_run(req)
        elif req['engine'] == 'index25':
            index_run(req)
        else:
            raise ValueError('Unknown engine')
        result = {'ok': True}
        code = 0
    except BaseException:
        result = {'ok': False, 'error': traceback.format_exc()}
        stage('Generation failed; traceback follows')
        print(result['error'], flush=True)
        code = 1
    response_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv))
