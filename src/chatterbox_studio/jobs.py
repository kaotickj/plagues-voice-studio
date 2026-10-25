"""Serializable narration job snapshots."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from uuid import uuid4

MODEL_CHOICES = {
    "nano": "Nano, efficient English (CPU friendly)",
    "turbo": "Turbo, expressive English",
    "english": "Original English, creative controls",
    "multilingual-v3": "Multilingual V3, 23 languages",
}
LANGUAGES = {
    "ar": "Arabic", "da": "Danish", "de": "German", "el": "Greek",
    "en": "English", "es": "Spanish", "fi": "Finnish", "fr": "French",
    "he": "Hebrew", "hi": "Hindi", "it": "Italian", "ja": "Japanese",
    "ko": "Korean", "ms": "Malay", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "sv": "Swedish",
    "sw": "Swahili", "tr": "Turkish", "zh": "Chinese",
}

NARRATION_PROFILES = {
    "custom": "Current settings",
    "clear_narration": "Clear Narration",
    "natural_narration": "Natural Narration (Original English)",
}

# A reproducible general-use starting point, not a claim of better audio.
# Explicit manuscript tags are retained; this profile never adds vocal events.
_CLEAR_NARRATION = {
    "max_chars": 220, "pause_ms": 180,
    "exaggeration": 0.5, "cfg_weight": 0.5, "temperature": 0.8,
}

# An opt-in setting preferred in a bounded two-voice listening comparison.
# It changes generation CFG only; reference conditioning remains at 0.5.
_NATURAL_NARRATION = {**_CLEAR_NARRATION, "cfg_weight": 0.3}


def is_narration_profile_supported(profile: str, model: str) -> bool:
    return (profile in NARRATION_PROFILES and model in MODEL_CHOICES
            and (profile != "natural_narration" or model == "english"))


def _validate_profile_model(profile: str, model: str) -> None:
    if profile not in NARRATION_PROFILES:
        raise ValueError("Unknown narration profile")
    if model not in MODEL_CHOICES:
        raise ValueError("Unknown Chatterbox model")
    if not is_narration_profile_supported(profile, model):
        raise ValueError("Natural Narration is available only for Original English")

@dataclass(frozen=True)
class NarrationJob:
    text: str
    model: str
    device: str
    language: str
    voice_path: str
    output_path: str
    format: str = "wav"
    max_chars: int = 220
    pause_ms: int = 180
    exaggeration: float = 0.5
    cfg_weight: float = 0.5
    temperature: float = 0.8
    job_id: str = ""
    profile: str = "custom"
    voice_id: str = ""
    prepared_text: str | None = None
    render_scope: str = "full_document"

    @property
    def render_text(self) -> str:
        """Reviewed render input, kept separate from the original manuscript."""
        from .text_preparation import prepare_render_text
        source = self.text if self.prepared_text is None else self.prepared_text
        language = self.language if self.model == 'multilingual-v3' else 'en'
        return prepare_render_text(source, language)

    def effective_settings(self) -> dict:
        """Describe controls the adapter actually uses for this model and profile.

        Turbo/Nano have no generation CFG or exaggeration controls. Reference
        preparation retains its separate exaggeration argument for compatibility.
        """
        _validate_profile_model(self.profile, self.model)
        values = {key: getattr(self, key) for key in _CLEAR_NARRATION}
        if self.profile == "clear_narration":
            values.update(_CLEAR_NARRATION)
        elif self.profile == "natural_narration":
            values.update(_NATURAL_NARRATION)
        values["conditioning_exaggeration"] = values["exaggeration"]
        if self.model in ("nano", "turbo"):
            values["exaggeration"] = None
            values["cfg_weight"] = None
        return values

    def generation_kwargs(self) -> dict:
        """Exact keyword arguments passed to model.generate, without metadata."""
        values = self.effective_settings()
        args = {"temperature": values["temperature"]}
        if self.model in ("english", "multilingual-v3"):
            args.update(exaggeration=values["exaggeration"], cfg_weight=values["cfg_weight"])
        if self.model == "multilingual-v3":
            args["language_id"] = self.language
        return args

    def render_steps(self):
        """Use one deterministic plan for preview and synthesis."""
        from .narration_markup import plan_script
        values = self.effective_settings()
        return plan_script(self.render_text, values["max_chars"], values["pause_ms"])

    def validate(self) -> None:
        from .narration_markup import parse_script
        if not self.text.strip():
            raise ValueError("Enter some narration text")
        _validate_profile_model(self.profile, self.model)
        if self.render_scope not in ("full_document", "selection"):
            raise ValueError("Unknown narration render scope")
        if self.prepared_text is not None and not isinstance(self.prepared_text, str):
            raise ValueError("Prepared narration must be text")
        if not self.render_text.strip():
            raise ValueError("Enter some narration text to render")
        if self.render_scope == "selection" and self.prepared_text is None:
            raise ValueError("A selection render needs its reviewed passage")
        if self.device not in ("auto", "cpu", "cuda"):
            raise ValueError("Unknown processing device")
        if self.model == "multilingual-v3" and self.language not in LANGUAGES:
            raise ValueError("Unsupported language")
        if self.model == "turbo" and not self.voice_path:
            raise ValueError("Turbo requires an imported reference voice")
        if self.voice_id and not self.voice_path:
            raise ValueError("The selected voice reference is unavailable; choose another voice or the built-in voice")
        if self.voice_path and not Path(self.voice_path).is_file():
            raise ValueError("The selected voice file no longer exists")
        if self.format not in ("wav", "mp3"):
            raise ValueError("Only WAV and MP3 exports are supported")
        if Path(self.output_path).suffix.lower() != f".{self.format}":
            raise ValueError("Output filename does not match the selected format")
        if not 60 <= self.max_chars <= 2000:
            raise ValueError("Chunk length must be 60–2000 characters")
        if not 0 <= self.pause_ms <= 2500:
            raise ValueError("Pause must be between 0 and 2500 ms")
        if not 0 <= self.exaggeration <= 1 or not 0 <= self.cfg_weight <= 1:
            raise ValueError("Expressiveness controls must be between 0 and 1")
        if not 0.1 <= self.temperature <= 1.5:
            raise ValueError("Temperature must be 0.1–1.5")
        # A reviewed selection can come from a larger manuscript. Validate the
        # actual render input, including rejecting incomplete markup scopes.
        parse_script(self.render_text)

    def as_json(self) -> dict:
        return asdict(self)

    @classmethod
    def new(cls, **kwargs):
        return cls(job_id=uuid4().hex, **kwargs)
