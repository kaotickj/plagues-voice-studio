"""Chatterbox adapter and streaming audio export.

Heavy ML dependencies are intentionally imported only inside a background worker.
"""
from __future__ import annotations
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import numpy as np

from .jobs import NarrationJob
from .paths import bundled_models_dir, user_data_dir
from .model_downloads import MODELS, has_required_files, installed_model_directory
from .narration_markup import plan_script
from .export_metadata import write_export_metadata


class GenerationCancelled(Exception):
    pass


def resolve_device(requested: str) -> str:
    import torch
    available = torch.cuda.is_available()
    if requested == "cuda" and not available:
        raise RuntimeError("CUDA selected, but the installed PyTorch build cannot access CUDA. Choose CPU or Auto.")
    return "cuda" if available and requested in ("auto", "cuda") else "cpu"


def unique_output_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists() and not path.with_suffix(".json").exists():
        return path
    for n in range(2, 10001):
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        if not candidate.exists() and not candidate.with_suffix(".json").exists():
            return candidate
    raise RuntimeError("Too many exports use this filename")


def load_model(model_id: str, device: str):
    """Load included offline weights when present, otherwise Hugging Face cache/download."""
    # Prefer validated per-user downloads; frozen app files remain read-only.
    spec = MODELS[model_id]
    user_path = installed_model_directory(user_data_dir(), spec)
    bundled_path = bundled_models_dir() / model_id
    path = user_path if user_path is not None else bundled_path
    if not has_required_files(path, spec):
        path = None
    if model_id in ("nano", "turbo"):
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        if path is not None:
            return ChatterboxTurboTTS.from_local(path, device=device, nano=(model_id == "nano"))
        return ChatterboxTurboTTS.from_pretrained(device=device, nano=(model_id == "nano"))
    if model_id == "english":
        from chatterbox.tts import ChatterboxTTS
        if path is not None:
            return ChatterboxTTS.from_local(path, device=device)
        return ChatterboxTTS.from_pretrained(device=device)
    if model_id == "multilingual-v3":
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        if path is not None:
            return ChatterboxMultilingualTTS.from_local(path, device=device, t3_model="v3")
        return ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
    raise ValueError(f"Unknown model: {model_id}")


def apply_local_effects(audio: np.ndarray, sample_rate: int, rate: float = 1.0,
                        volume: float = 1.0, emphasis: bool = False) -> np.ndarray:
    """Apply post-synthesis effects. Rate uses FFmpeg atempo to preserve pitch.

    Emphasis is a modest gain lift, not a promise of natural TTS prosody.
    """
    result = np.asarray(audio, dtype=np.float32).reshape(-1)
    if abs(rate - 1.0) > 1e-6:
        import imageio_ffmpeg
        executable = imageio_ffmpeg.get_ffmpeg_exe()
        proc = subprocess.run([
            executable, '-hide_banner', '-loglevel', 'error', '-nostdin',
            '-f', 'f32le', '-ar', str(sample_rate), '-ac', '1', '-i', 'pipe:0',
            '-af', f'atempo={rate:.6f}', '-f', 'f32le', 'pipe:1'
        ], input=result.astype('<f4').tobytes(), capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError('Could not apply speaking rate: ' + proc.stderr.decode(errors='replace')[-600:])
        result = np.frombuffer(proc.stdout, dtype='<f4').copy()
        if not result.size:
            raise RuntimeError('Speaking-rate processor produced empty audio')
    gain = volume * (1.15 if emphasis else 1.0)
    if gain != 1.0:
        result = result * gain
    return np.clip(result, -1.0, 1.0)


class Engine:
    """Caches one model at a time to avoid accumulating VRAM use."""
    def __init__(self, model_loader=load_model):
        self.model_loader = model_loader
        self.model = None
        self.model_key: tuple[str, str] | None = None
        self.builtin_voice = None

    def _get_model(self, model_id: str, device: str, report: Callable[[str], None]):
        key = (model_id, device)
        if self.model_key != key:
            self.model = None
            self.builtin_voice = None
            if device == "cuda":
                import torch
                torch.cuda.empty_cache()
            report(f"Loading {model_id} on {device} (first use may download weights)...")
            self.model = self.model_loader(model_id, device)
            self.model_key = key
            self.builtin_voice = getattr(self.model, "conds", None)
        return self.model

    def render(self, job: NarrationJob, report: Callable[[str], None],
               progress: Callable[[int, int], None], cancelled: Callable[[], bool]) -> Path:
        job.validate()
        import soundfile as sf
        import torch
        device = resolve_device(job.device)
        if cancelled():
            raise GenerationCancelled()
        model = self._get_model(job.model, device, report)
        if cancelled():
            raise GenerationCancelled()
        # Prepare once, not per chunk. Do not let the previous job's voice leak into this one.
        if job.voice_path:
            report(f"Preparing voice: {Path(job.voice_path).name}")
            model.prepare_conditionals(job.voice_path, exaggeration=job.exaggeration)
        else:
            model.conds = self.builtin_voice
            if model.conds is None:
                raise RuntimeError("This model has no built-in voice. Import a reference recording.")
        steps = plan_script(job.text, job.max_chars, job.pause_ms)
        speech_total = sum(step.kind == "speech" for step in steps)
        speech_index = 0
        target = unique_output_path(Path(job.output_path).expanduser())
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.partial.wav')
        mp3_temp = target.with_name(target.name + '.partial.mp3')
        temporary.unlink(missing_ok=True)
        mp3_temp.unlink(missing_ok=True)
        try:
            with sf.SoundFile(str(temporary), mode="w", samplerate=int(model.sr),
                              channels=1, subtype="PCM_16", format="WAV") as file:
                for step in steps:
                    if cancelled():
                        raise GenerationCancelled()
                    if step.kind == 'pause':
                        if step.pause_ms:
                            file.write(np.zeros(round(model.sr * step.pause_ms / 1000), dtype=np.float32))
                        continue
                    speech_index += 1
                    chunk = step.text
                    report(f"Generating segment {speech_index}/{speech_total} ({len(chunk)} characters)")
                    args = {"temperature": job.temperature}
                    if job.model == "multilingual-v3":
                        args.update(language_id=job.language, exaggeration=job.exaggeration,
                                    cfg_weight=job.cfg_weight)
                    elif job.model == "english":
                        args.update(exaggeration=job.exaggeration, cfg_weight=job.cfg_weight)
                    # Turbo and Nano do not support cfg or exaggeration during generation.
                    with torch.inference_mode():
                        audio = model.generate(chunk, **args)
                    if hasattr(audio, "detach"):
                        audio = audio.detach().cpu().numpy()
                    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
                    if audio.size == 0 or not np.all(np.isfinite(audio)):
                        raise RuntimeError(f"Model returned invalid audio for segment {speech_index}")
                    audio = apply_local_effects(audio, int(model.sr), step.rate,
                                                step.volume, step.emphasis)
                    file.write(audio)
                    progress(speech_index, speech_total)
                    if cancelled():
                        raise GenerationCancelled()
            if job.format == "mp3":
                report("Encoding MP3...")
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                proc = subprocess.run([
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(temporary),
                    "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_temp)
                ], capture_output=True, text=True, check=False)
                if proc.returncode:
                    raise RuntimeError(f"MP3 conversion failed: {proc.stderr[-1200:]}")
                if cancelled():
                    raise GenerationCancelled()
                os.replace(mp3_temp, target)
            else:
                os.replace(temporary, target)
            # Preserve the immutable job snapshot used for this specific render.
            # Scripts include exactly the original tags, newlines, and punctuation.
            # Use target, not job.output_path, because target can be numbered.
            metadata = {
                **job.as_json(),
                "engine": "chatterbox",
                "output_path": str(target),
                "device_used": device,
                "sample_rate": int(model.sr),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            sidecar = write_export_metadata(target, metadata)
            report(f"Saved script metadata: {sidecar}")
            report(f"Saved: {target}")
            return target
        finally:
            temporary.unlink(missing_ok=True)
            mp3_temp.unlink(missing_ok=True)
