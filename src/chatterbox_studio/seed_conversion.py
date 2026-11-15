"""Offline adapter for separately installed Seed-VC V1 F0-auto; no model downloads."""
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import math
import os
import random
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

SEED_REPO = 'Plachta/Seed-VC'
CHECKPOINT = 'DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema_v2.pth'
CONFIG = 'config_dit_mel_seed_uvit_whisper_base_f0_44k.yml'
WHISPER = 'openai/whisper-small'
VOCODER = 'nvidia/bigvgan_v2_44khz_128band_512x'
REQUIRED = {SEED_REPO: (CHECKPOINT, CONFIG),
            'funasr/campplus': ('campplus_cn_common.bin',),
            'lj1995/VoiceConversionWebUI': ('rmvpe.pt',),
            WHISPER: ('config.json', 'model.safetensors', 'preprocessor_config.json'),
            VOCODER: ('config.json', 'bigvgan_generator.pt')}
PROFILE = dict(f0_condition=True, auto_f0_adjust=True, length_adjust=1.0,
               semi_tone_shift=0, diffusion_steps=30, inference_cfg_rate=0.7)


def assets_from_manifest(path):
    """Resolve and hash-check only the V1 assets, never a floating Hub revision."""
    entries = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(entries, list):
        raise ValueError('Seed model manifest must be a list of repositories.')
    assets = {}
    for entry in entries:
        repo = entry.get('repo')
        if repo not in REQUIRED:
            continue
        for item in entry.get('files', []):
            if item.get('name') not in REQUIRED[repo]:
                continue
            key = (repo, item['name'])
            if key in assets:
                raise ValueError('Duplicate Seed model manifest asset: ' + repr(key))
            local = Path(item['path']).expanduser().absolute()
            with local.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != item.get('sha256'):
                raise ValueError('Seed model asset checksum mismatch: ' + item['name'])
            assets[key] = local
    missing = [(repo, name) for repo, names in REQUIRED.items() for name in names
               if (repo, name) not in assets]
    if missing:
        raise ValueError('Seed model assets are missing from the manifest: ' + repr(missing))
    # Directory-based loaders must consume exactly the assets just verified,
    # not unchecked sibling weights selected through a mixed-directory manifest.
    for repo in (WHISPER, VOCODER):
        snapshot = assets[(repo, 'config.json')].parent
        for name in REQUIRED[repo]:
            if assets[(repo, name)] != snapshot / name:
                raise ValueError('Seed directory-loaded assets must share one snapshot with their expected filenames: ' + repo)
    return assets


def validate_profile(req):
    for key, value in PROFILE.items():
        if req.get(key, value) != value:
            raise ValueError('Unsupported Seed V1 profile option: ' + key)
    if req.get('device', 'cpu') not in ('cpu', 'cuda'):
        raise ValueError('Unsupported Seed synthesis device')


def write_pcm_output(path, audio, rate):
    """Avoid hard clipping during PCM conversion, using one transparent gain only."""
    import numpy as np
    import soundfile as sf
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if rate != 44100 or not audio.size or not np.isfinite(audio).all():
        raise ValueError('Seed returned invalid 44.1 kHz audio.')
    peak = float(np.max(np.abs(audio)))
    if peak < 1e-8:
        raise ValueError('Seed returned silent audio.')
    # Single attenuation retains the generated take's relative dynamics. It is
    # neither a compressor nor pitch correction; values <= .999 are unchanged.
    gain = min(1.0, .999 / peak)
    path = Path(path)
    with tempfile.NamedTemporaryFile(prefix='seed-pcm-', suffix='.wav', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        sf.write(temporary, audio * gain, rate, subtype='PCM_16')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(output_peak=peak, output_gain_db=20 * math.log10(gain),
                output_sample_rate=rate)


def prepare_reference(source, target):
    """Use the reviewed 10-second mono PCM reference profile; original untouched."""
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(source) as stream:
        rate = stream.samplerate
        audio = stream.read(min(len(stream), 10 * rate), dtype='float32', always_2d=True)
    if len(audio) < rate // 4 or not np.isfinite(audio).all():
        raise ValueError('The selected reference must contain valid speech for at least 0.25 seconds.')
    audio = audio.mean(axis=1)
    if np.max(np.abs(audio)) < .0001:
        raise ValueError('The opening of the selected reference is silent. Choose a reference starting with clear speech.')
    if rate != 44100:
        import librosa
        audio = librosa.resample(audio, orig_sr=rate, target_sr=44100)
    sf.write(target, audio, 44100, subtype='PCM_16')
    return len(audio) / 44100


class _AudioProxy:
    def __init__(self, module, writer):
        self.module, self.writer = module, writer
    def __getattr__(self, name):
        return self.writer if name == 'save' else getattr(self.module, name)


class SeedV1:
    def __init__(self, req):
        validate_profile(req)
        self.repo = Path(req['repo']).expanduser().resolve(strict=True)
        self.cache = Path(req['cache']).expanduser().resolve(strict=True)
        if not (self.repo / 'inference.py').is_file() or not self.cache.is_dir():
            raise ValueError('Seed repository or cache directory is unavailable.')
        os.environ.update(HF_HOME=str(self.cache / 'hf'), HF_HUB_CACHE=str(self.repo / 'checkpoints'),
            HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
            HF_HUB_DISABLE_IMPLICIT_TOKEN='1', XDG_CACHE_HOME=str(self.cache),
            NUMBA_CACHE_DIR=str(self.cache / 'numba'), MPLCONFIGDIR=str(self.cache / 'matplotlib'),
            MIOPEN_USER_DB_PATH=str(self.cache / 'miopen-db'), MIOPEN_CUSTOM_CACHE_DIR=str(self.cache / 'miopen'))
        for name in ('numba', 'matplotlib', 'miopen-db', 'miopen'):
            (self.cache / name).mkdir(exist_ok=True)
        print('[PVS] Checking local Seed V1 model assets…', flush=True)
        self.assets = assets_from_manifest(req['manifest'])
        import torch
        if req.get('device', 'cpu') == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('The selected GPU is unavailable. Choose CPU explicitly.')
        self.device = req.get('device', 'cpu')
        os.chdir(self.repo)
        sys.path.insert(0, str(self.repo))
        spec = importlib.util.spec_from_file_location('_pvs_seed_v1_inference', self.repo / 'inference.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.device = torch.device(self.device)
        os.environ['HF_HUB_CACHE'] = str(self.repo / 'checkpoints')
        def local_asset(repo_id, model_filename='pytorch_model.bin', config_filename=None):
            try:
                model = str(self.assets[(repo_id, model_filename)])
                return (model, str(self.assets[(repo_id, config_filename)])) if config_filename else model
            except KeyError as exc:
                raise ValueError('Seed requested an unconfigured local model asset') from exc
        self.module.load_custom_model_from_hf = local_asset
        self.args = SimpleNamespace(**PROFILE, checkpoint=str(self.assets[(SEED_REPO, CHECKPOINT)]),
            config=str(self.assets[(SEED_REPO, CONFIG)]), fp16=self.device == 'cuda')
        from modules.bigvgan.bigvgan import BigVGAN
        from transformers import WhisperModel, AutoFeatureExtractor
        print('[PVS] Loading Seed V1 F0-auto on ' + self.device + '…', flush=True)
        with ExitStack() as stack:
            for cls, identifier in ((BigVGAN, VOCODER), (WhisperModel, WHISPER), (AutoFeatureExtractor, WHISPER)):
                original = cls.from_pretrained
                snapshot = str(self.assets[(identifier, 'config.json')].parent)
                def local_pretrained(name, *args, _original=original, _identifier=identifier, _snapshot=snapshot, _model_class=cls, **kwargs):
                    if name != _identifier:
                        raise ValueError('Unexpected Seed model identifier: ' + str(name))
                    kwargs['local_files_only'] = True
                    if _model_class is WhisperModel:
                        kwargs['use_safetensors'] = True
                    if self.device == 'cpu' and _identifier == WHISPER and 'torch_dtype' in kwargs:
                        kwargs['torch_dtype'] = torch.float32
                    return _original(_snapshot, *args, **kwargs)
                stack.enter_context(patch.object(cls, 'from_pretrained', local_pretrained))
            self.models = list(self.module.load_models(self.args))
        original_f0 = self.models[2]
        def voiced_f0(audio, *args, **kwargs):
            import numpy as np
            values = original_f0(audio, *args, **kwargs)
            voiced = np.asarray(values)[np.asarray(values) > 1]
            if len(voiced) < 3 or not np.isfinite(values).all():
                raise ValueError('Seed needs clearly voiced speech in both the recording and reference. No reliable pitch was found.')
            return values
        self.models[2] = voiced_f0
        self.module.load_models = lambda args: self.models

    def convert(self, req):
        validate_profile(req)
        import numpy as np
        import soundfile as sf
        import torch
        source, reference, output = (Path(req[k]).expanduser().resolve() for k in ('source', 'reference', 'output_path'))
        if output in (source, reference):
            raise ValueError('Converted output must not overwrite a source or reference.')
        data, rate = sf.read(source, always_2d=True)
        duration = len(data) / rate
        if not .25 <= duration <= 20.1 or not np.isfinite(data).all() or np.max(np.abs(data)) < .0001:
            raise ValueError('Record between 0.25 and 20 seconds of valid, audible speech.')
        if not reference.is_file():
            raise ValueError('The selected reference is unavailable.')
        info = sf.info(reference)
        if info.duration < .25:
            raise ValueError('The selected reference is too short.')
        output.parent.mkdir(parents=True, exist_ok=True)
        metadata = dict(f0_condition=True, auto_f0_adjust=True, length_adjust=1.0,
            semi_tone_shift=0, seed_diffusion_steps=30, inference_cfg_rate=.7, seed_random_seed=1709,
            reference_duration=min(10.0, info.duration))
        writes = []
        def writer(unused_path, audio, sample_rate, **kwargs):
            writes.append(True)
            if len(writes) != 1:
                raise RuntimeError('Seed produced unexpected multiple outputs.')
            metadata.update(write_pcm_output(output, audio.detach().cpu().numpy(), sample_rate))
        args = SimpleNamespace(**vars(self.args), source=str(source), target=str(reference))
        random.seed(1709)
        np.random.seed(1709)
        torch.manual_seed(1709)
        if self.device == 'cuda':
            torch.cuda.manual_seed_all(1709)
        print('[PVS] Converting with Seed V1; matching reference register…', flush=True)
        with tempfile.TemporaryDirectory(prefix='seed-output-', dir=output.parent) as tmp:
            args.output = tmp
            target = Path(tmp) / 'reference-10s.wav'
            metadata['reference_duration'] = prepare_reference(reference, target)
            args.target = str(target)
            original = self.module.torchaudio
            self.module.torchaudio = _AudioProxy(original, writer)
            try:
                self.module.main(args)
            finally:
                self.module.torchaudio = original
        if len(writes) != 1:
            raise RuntimeError('Seed produced no output.')
        note = 'Seed V1: source inflection shifted toward reference register (first 10 seconds); saved at 44.1 kHz.'
        if metadata['output_gain_db'] < -.001:
            note += f" Output attenuated {abs(metadata['output_gain_db']):.1f} dB to avoid PCM clipping."
        return dict(conversion_metadata=metadata, conversion_note=note)


def convert(req, model=None):
    validate_profile(req)
    model = model or SeedV1(req)
    return model, model.convert(req)
