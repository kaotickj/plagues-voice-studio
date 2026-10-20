"""Out-of-process optional TTS backends. Run with an isolated Python environment.

No optional packages are needed by Plague's Voice Studio itself. Only stdlib
imports take place until the user explicitly requests a probe or generation.
"""
from __future__ import annotations
import json
import hashlib
import os
import shutil
from pathlib import Path
import sys
import traceback
from uuid import uuid4


def stage(text: str) -> None:
    print('[PVS] ' + text, flush=True)

def kokoro_files(directory: str) -> tuple[Path, Path]:
    folder = Path(directory).expanduser()
    model, voices = folder / 'kokoro-v1.0.int8.onnx', folder / 'voices-v1.0.bin'
    if not model.is_file() or not voices.is_file():
        raise RuntimeError('Kokoro model folder must contain kokoro-v1.0.int8.onnx and voices-v1.0.bin.')
    return model, voices


def kokoro_directml_model(source: Path) -> Path:
    """Cache an equivalent padding expression supported by DirectML.

    ConvTranspose output_padding extends the right output boundary. When right
    padding covers that extension, reducing it is algebraically equivalent.
    DirectML rejects the grouped 1-D output_padding used by the official export.
    Learned tensors and the original ONNX file are never modified.
    """
    import onnx
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    cache = source.parent / 'directml'
    destination = cache / f'kokoro-padding-v1-{source_hash[:16]}.onnx'
    manifest = destination.with_suffix('.json')
    if destination.is_file() and manifest.is_file():
        try:
            info = json.loads(manifest.read_text(encoding='utf-8'))
            if (info.get('source_sha256') == source_hash and
                    info.get('graph_sha256') == hashlib.sha256(destination.read_bytes()).hexdigest()):
                return destination
        except (OSError, ValueError):
            pass
    stage('Preparing cached DirectML-compatible padding graph; original weights are preserved')
    model = onnx.load(str(source))
    converted = []
    for node in model.graph.node:
        if node.op_type != 'ConvTranspose':
            continue
        attrs = {a.name: onnx.helper.get_attribute_value(a) for a in node.attribute}
        extra = attrs.get('output_padding', [])
        if not any(extra):
            continue
        rank = len(extra)
        pads = list(attrs.get('pads', [0] * (rank * 2)))
        if attrs.get('auto_pad', b'NOTSET') != b'NOTSET' or 'output_shape' in attrs:
            raise RuntimeError('This Kokoro export has unsupported automatic ConvTranspose padding.')
        if len(pads) != 2 * rank or any(pads[rank+i] < value for i, value in enumerate(extra)):
            raise RuntimeError('This Kokoro export cannot express output_padding as nonnegative right padding.')
        for i, value in enumerate(extra):
            pads[rank+i] -= value
        for attr in list(node.attribute):
            if attr.name in ('pads', 'output_padding'):
                node.attribute.remove(attr)
        node.attribute.append(onnx.helper.make_attribute('pads', pads))
        converted.append(node.name)
    if not converted:
        raise RuntimeError('Kokoro export differs from the tested DirectML graph. Use CPU or the pinned model release.')
    graph = model.SerializeToString(deterministic=True)
    info = {'source_sha256': source_hash, 'graph_sha256': hashlib.sha256(graph).hexdigest(),
            'transform': 'ConvTranspose output_padding to right pads v1', 'converted_nodes': converted}
    cache.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.' + uuid4().hex + '.tmp')
    temp_manifest = temporary.with_suffix('.json')
    try:
        temporary.write_bytes(graph)
        temp_manifest.write_text(json.dumps(info, indent=2), encoding='utf-8')
        os.replace(temporary, destination)
        os.replace(temp_manifest, manifest)
    finally:
        temporary.unlink(missing_ok=True)
        temp_manifest.unlink(missing_ok=True)
    return destination


def probe(engine: str, model_dir: str = '') -> dict:
    try:
        stage(f'Checking optional engine {engine} imports')
        if engine == 'qwen3':
            from qwen_tts import Qwen3TTSModel  # noqa: F401
            import torch
            import soundfile  # noqa: F401
        elif engine == 'index25':
            from indextts.infer_v2_5 import IndexTTS2  # noqa: F401
            import torch
        elif engine == 'kokoro':
            from kokoro_onnx import Kokoro  # noqa: F401
            import onnxruntime as ort
            import numpy as np
            import soundfile  # noqa: F401
            if 'DmlExecutionProvider' in ort.get_available_providers():
                import onnx  # noqa: F401; needed to prepare the compatible GPU graph
            _, voices = kokoro_files(model_dir)
            with np.load(str(voices), allow_pickle=False) as pack:
                available = sorted(pack.files)
            required = {'am_michael', 'am_fenrir', 'bm_george', 'af_heart', 'af_bella', 'bf_emma'}
            if not required.issubset(available):
                raise RuntimeError('Kokoro voice pack is missing required preset voices.')
            stage('Kokoro imports and model files checked; synthesis is tested by Generate')
            return {'ready': True, 'runtime': 'ONNX Runtime ' + ort.__version__,
                    'providers': ort.get_available_providers(), 'voices': available}
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


def windows_cpu_tensor_reader() -> None:
    """Use bounded reads instead of Windows copy-on-write checkpoint mappings.

    This process is owned by one optional-engine job. No installed package or
    host process is patched. Install before importing the engine/Transformers so
    their imported safe_open aliases use the same reader.
    """
    if sys.platform != 'win32':
        return
    import inspect
    import safetensors
    import safetensors.torch
    original = safetensors.safe_open
    if getattr(original, '_pvs_pread', False):
        return
    if 'backend' not in inspect.signature(original).parameters:
        raise RuntimeError('Windows CPU loading requires safetensors 0.8.0 or newer in this '
                           'optional engine environment. Rerun the engine setup script; '
                           'the Studio/Chatterbox environment does not need changing.')
    def read_open(*args, **kwargs):
        kwargs['backend'] = 'pread'
        return original(*args, **kwargs)
    read_open._pvs_pread = True
    safetensors.safe_open = read_open
    safetensors.torch.safe_open = read_open
    # Some Torch distributions import Transformers helpers early.
    module = sys.modules.get('transformers.modeling_utils')
    if module is not None and getattr(module, 'safe_open', None) is original:
        module.safe_open = read_open
    stage('Windows CPU checkpoint reader: pread (no whole-file copy-on-write mapping)')


def qwen_model_source(model: str) -> str:
    """Prefer a complete cached snapshot, including processor/tokenizer assets.

    Qwen's processor loader does not forward local_files_only and its tokenizer
    fix otherwise looks up remote model metadata even for cached weights.
    Passing the snapshot directory keeps a complete installation offline.
    """
    if Path(model).is_dir():
        return model
    from huggingface_hub import snapshot_download
    try:
        folder = Path(snapshot_download(repo_id=model, local_files_only=True))
    except (OSError, ValueError):
        return model
    required = ('config.json', 'tokenizer_config.json', 'vocab.json', 'merges.txt',
                'generation_config.json', 'preprocessor_config.json',
                'speech_tokenizer/config.json', 'speech_tokenizer/model.safetensors',
                'speech_tokenizer/preprocessor_config.json')
    if (all((folder/name).is_file() and (folder/name).stat().st_size for name in required)
            and any(p.stat().st_size for p in folder.glob('*.safetensors'))):
        stage('Using cached Qwen model and tokenizer: ' + str(folder))
        return str(folder)
    return model


def qwen_run(req: dict) -> None:
    stage('Importing Qwen3-TTS and PyTorch; this may take some time on CPU')
    import torch
    import soundfile as sf
    device = _device(req.get('device', 'cpu'), torch)
    if device == 'cpu':
        windows_cpu_tensor_reader()
    from qwen_tts import Qwen3TTSModel
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
        qwen_model_source(req['model']), device_map=device,
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
    device = _device(req.get('device', 'cpu'), torch)
    if device == 'cpu':
        windows_cpu_tensor_reader()
    from indextts.infer_v2_5 import IndexTTS2
    root = Path(req['repo']).resolve()
    checkpoints = root / 'checkpoints'
    if not (checkpoints/'config.yaml').is_file() and os.environ.get('PLAGUED_INDEX_CHECKPOINTS'):
        checkpoints = Path(os.environ['PLAGUED_INDEX_CHECKPOINTS'])
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


def kokoro_run(req: dict) -> dict:
    stage('Importing Kokoro and ONNX Runtime')
    import numpy as np
    import onnxruntime as ort
    import soundfile as sf
    from kokoro_onnx import Kokoro
    model, voices = kokoro_files(req['model_dir'])
    mode = req.get('device', 'auto')
    if mode not in ('cpu', 'auto', 'directml'):
        raise ValueError('Choose Kokoro CPU, Auto or DirectML.')
    available = ort.get_available_providers()
    use_gpu = mode == 'directml' or (mode == 'auto' and 'DmlExecutionProvider' in available)
    if use_gpu and 'DmlExecutionProvider' not in available:
        raise RuntimeError('DirectML is not installed in this Kokoro runtime. Run setup_kokoro_windows.ps1 -Backend DirectML or choose CPU.')
    options = ort.SessionOptions()
    options.intra_op_num_threads = min(6, os.cpu_count() or 1)
    options.inter_op_num_threads = 1
    if req.get('profile'):
        options.enable_profiling = True
        options.profile_file_prefix = req['output_path'] + '.profile'
    providers = ['CPUExecutionProvider']
    if use_gpu:
        model = kokoro_directml_model(model)
        # Required by DirectML; graph optimizers also crash on this export.
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        providers = [('DmlExecutionProvider', {'device_id': '0'}), 'CPUExecutionProvider']
    stage(f'Loading Kokoro INT8; ONNX Runtime {ort.__version__}; '
          f'backend {"DirectML GPU" if use_gpu else "CPU"}; CPU threads {options.intra_op_num_threads}')
    session = ort.InferenceSession(str(model), sess_options=options, providers=providers)
    active = session.get_providers()
    if use_gpu and 'DmlExecutionProvider' not in active:
        raise RuntimeError('DirectML session fell back to CPU. Choose CPU explicitly or inspect the runtime diagnostics.')
    stage('Active execution providers: ' + ', '.join(active))
    synthesizer = Kokoro.from_session(session, str(voices))
    preset = req['preset_voice']
    accents = {'am_michael': 'en-us', 'am_fenrir': 'en-us', 'bm_george': 'en-gb',
               'af_heart': 'en-us', 'af_bella': 'en-us', 'bf_emma': 'en-gb'}
    if preset not in accents:
        raise ValueError('Unsupported Kokoro preset voice.')
    stage(f'Generating speech with {preset}, speed {req.get("speed", 1.0):.2f}')
    samples, sample_rate = synthesizer.create(req['text'], voice=preset,
                                             speed=float(req.get('speed', 1.0)), lang=accents[preset])
    samples = np.asarray(samples).reshape(-1)
    if not samples.size or not np.isfinite(samples).all():
        raise RuntimeError('Kokoro returned empty or non-finite audio.')
    profile = {}
    if req.get('profile'):
        path = session.end_profiling()
        counts = {}
        for event in json.loads(Path(path).read_text(encoding='utf-8')):
            provider = event.get('args', {}).get('provider')
            if provider:
                counts[provider] = counts.get(provider, 0) + 1
        profile = {'path': path, 'provider_events': counts}
        if use_gpu and not counts.get('DmlExecutionProvider'):
            raise RuntimeError('Profiling detected no DirectML GPU operations.')
    # Exclusive creation also protects against a file appearing after validation.
    with open(req['output_path'], 'xb') as output:
        sf.write(output, samples, sample_rate, format='WAV', subtype='PCM_16')
    stage(f'Kokoro WAV saved: {len(samples) / sample_rate:.2f}s, {sample_rate} Hz')
    return {'backend': 'directml' if use_gpu else 'cpu', 'providers': active,
            'onnxruntime': ort.__version__, 'model_path': str(model), 'profile': profile}


def main(argv: list[str]) -> int:
    if len(argv) in (3, 4) and argv[1] == '--probe':
        result = probe(argv[2], argv[3] if len(argv) == 4 else '')
        print(json.dumps(result))
        return 0 if result.get('ready') else 1
    if len(argv) != 4 or argv[1] != '--run':
        print('Usage: optional_engine_runner.py --probe <qwen3|index25|kokoro> [model-folder] OR --run request.json result.json', file=sys.stderr)
        return 2
    request_path, response_path = Path(argv[2]), Path(argv[3])
    try:
        req = json.loads(request_path.read_text(encoding='utf-8'))
        runtime = {}
        if req['engine'] == 'qwen3':
            qwen_run(req)
        elif req['engine'] == 'index25':
            index_run(req)
        elif req['engine'] == 'kokoro':
            runtime = kokoro_run(req)
        else:
            raise ValueError('Unknown engine')
        result = {'ok': True, 'runtime': runtime}
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
