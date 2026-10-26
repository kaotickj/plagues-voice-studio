"""Profile/adapter behavior with synthetic audio; no model or GPU inference."""
from contextlib import nullcontext
from dataclasses import replace
import json
import sys
from types import SimpleNamespace

import pytest

from chatterbox_studio.jobs import MODEL_CHOICES, NarrationJob, is_narration_profile_supported
from chatterbox_studio.narration_markup import MarkupError, plan_script


def job(**values):
    source = dict(text="Hello, reader. Welcome to the next chapter.", model="english",
                  device="cpu", language="en", voice_path="", output_path="story.wav")
    source.update(values)
    return NarrationJob(**source)


def test_custom_profile_preserves_legacy_controls_and_plan():
    legacy = job(max_chars=100, pause_ms=300, exaggeration=.72, cfg_weight=.31, temperature=.65)
    legacy.validate()
    assert legacy.profile == "custom"
    assert legacy.render_text == legacy.text
    assert legacy.render_steps() == plan_script(legacy.text, 100, 300)
    assert legacy.generation_kwargs() == {"temperature": .65, "exaggeration": .72, "cfg_weight": .31}
    assert legacy.effective_settings()["conditioning_exaggeration"] == .72


def test_clear_narration_roundtrip_is_explicit_and_adds_no_effects(tmp_path):
    reference = tmp_path / "reference.wav"
    reference.touch()
    clear = job(profile="clear_narration", voice_id="stable-voice-id", max_chars=100,
                voice_path=str(reference), pause_ms=750, exaggeration=.9, cfg_weight=.1, temperature=1.2)
    restored = NarrationJob(**json.loads(json.dumps(clear.as_json())))
    restored.validate()
    assert restored == clear
    assert restored.text == clear.text
    assert restored.render_text == clear.text
    assert restored.generation_kwargs() == {"temperature": .8, "exaggeration": .5, "cfg_weight": .5}
    assert restored.effective_settings()["max_chars"] == 220
    assert restored.effective_settings()["pause_ms"] == 180
    assert " ".join(step.text for step in restored.render_steps() if step.kind == "speech") == clear.text
    assert all(step.rate == 1 and step.volume == 1 and not step.emphasis
               for step in restored.render_steps() if step.kind == "speech")


@pytest.mark.parametrize("model", ["nano", "turbo"])
def test_unsupported_generation_controls_are_not_sent(model, tmp_path):
    reference = tmp_path / "reference.wav"
    reference.touch()
    candidate = job(model=model, profile="clear_narration", voice_path=str(reference))
    candidate.validate()
    assert candidate.effective_settings()["exaggeration"] is None
    assert candidate.effective_settings()["cfg_weight"] is None
    assert candidate.generation_kwargs() == {"temperature": .8}


def test_multilingual_retains_language_control():
    assert job(model="multilingual-v3", language="fr", profile="clear_narration").generation_kwargs() == {
        "temperature": .8, "exaggeration": .5, "cfg_weight": .5, "language_id": "fr"}


def test_natural_profile_roundtrip_and_only_generation_cfg_changes():
    original = "Opening.\nThe selected passage.\nEnding."
    natural = job(text=original, prepared_text="The selected passage.", render_scope="selection",
                  profile="natural_narration", max_chars=80, pause_ms=700,
                  exaggeration=.9, cfg_weight=.8, temperature=1.2)
    restored = NarrationJob(**json.loads(json.dumps(natural.as_json())))
    restored.validate()
    clear = replace(restored, profile="clear_narration")
    assert restored == natural
    assert restored.text == original
    assert restored.render_text == "The selected passage."
    assert restored.effective_settings() == {**clear.effective_settings(), "cfg_weight": .3}
    assert restored.generation_kwargs() == {"temperature": .8, "exaggeration": .5, "cfg_weight": .3}
    steps = restored.render_steps()
    assert steps == clear.render_steps()
    assert len(steps) == 1 and steps[0].text == restored.render_text
    assert steps[0].rate == steps[0].volume == 1 and not steps[0].emphasis


@pytest.mark.parametrize("model", MODEL_CHOICES)
def test_profile_support_helper_preserves_existing_capabilities(model):
    assert is_narration_profile_supported("custom", model)
    assert is_narration_profile_supported("clear_narration", model)
    assert is_narration_profile_supported("natural_narration", model) == (model == "english")
    assert not is_narration_profile_supported("unknown", model)
    assert not is_narration_profile_supported("natural_narration", "unknown")


@pytest.mark.parametrize("model", ["nano", "turbo", "multilingual-v3"])
@pytest.mark.parametrize("method", ["validate", "effective_settings", "generation_kwargs", "render_steps"])
def test_natural_profile_fails_clearly_for_unsupported_model(model, method):
    candidate = job(profile="natural_narration", model=model)
    with pytest.raises(ValueError, match="only for Original English"):
        getattr(candidate, method)()


def test_selection_keeps_original_manuscript_and_uses_reviewed_text():
    source = "The opening.\n\nThe selected passage.\n\nThe ending."
    selected = job(text=source, prepared_text="The selected passage.", render_scope="selection")
    selected.validate()
    assert selected.text == source
    assert [step.text for step in selected.render_steps() if step.kind == "speech"] == ["The selected passage."]
    with pytest.raises(MarkupError, match="Unclosed"):
        replace(selected, prepared_text="[rate:0.9]The selected passage.").validate()


@pytest.mark.parametrize("values, message", [
    ({"profile": "pretend"}, "profile"),
    ({"render_scope": "pretend"}, "scope"),
    ({"render_scope": "selection"}, "reviewed passage"),
    ({"prepared_text": "  "}, "text to render"),
    ({"prepared_text": 42}, "must be text"),
    ({"voice_id": "missing-voice-id"}, "reference is unavailable"),
    ({"voice_path": "/not/a/real/reference.wav"}, "no longer exists"),
])
def test_invalid_snapshot(values, message):
    with pytest.raises(ValueError, match=message):
        job(**values).validate()


@pytest.fixture
def software_engine(monkeypatch):
    # Importing or exercising a real backend is outside these software tests.
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False), inference_mode=nullcontext))
    from chatterbox_studio.engine import Engine
    return Engine


class ConditioningModel:
    sr = 8000

    def __init__(self):
        self.conds = "built-in"
        self.prepared = []
        self.calls = []
        self.fail_preparation = False

    def prepare_conditionals(self, path, exaggeration=.5):
        self.conds = (path, exaggeration)
        self.prepared.append((path, exaggeration))
        if self.fail_preparation:
            raise ValueError("Synthetic preparation failure")

    def generate(self, text, **options):
        import numpy as np
        self.calls.append((text, options, self.conds))
        return np.zeros((1, 800), dtype=np.float32)


def render(engine, candidate, **callbacks):
    return engine.render(candidate, callbacks.get("report", lambda _: None),
                         callbacks.get("progress", lambda *_: None),
                         callbacks.get("cancelled", lambda: False))


def test_reference_a_b_builtin_and_failed_preparation_are_isolated(tmp_path, software_engine):
    first = tmp_path / "first.wav"; first.touch()
    second = tmp_path / "second.wav"; second.touch()
    model = ConditioningModel()
    engine = software_engine(model_loader=lambda *_: model)
    base = job(text="A full sentence. " * 25, max_chars=75, voice_path=str(first),
               output_path=str(tmp_path / "output.wav"))
    render(engine, base)
    first_count = len(model.calls)
    assert len(model.prepared) == 1  # once per job, never per segment
    assert all(call[2] == (str(first), .5) for call in model.calls)
    render(engine, replace(base, voice_path=str(second)))
    second_count = len(model.calls)
    assert len(model.prepared) == 2
    assert all(call[2] == (str(second), .5) for call in model.calls[first_count:])
    render(engine, replace(base, voice_path=""))
    assert all(call[2] == "built-in" for call in model.calls[second_count:])
    model.fail_preparation = True
    with pytest.raises(ValueError, match="Synthetic"):
        render(engine, base)
    assert model.conds == "built-in"


def test_export_records_exact_prepared_plan_and_effective_settings(tmp_path, software_engine):
    model = ConditioningModel()
    engine = software_engine(model_loader=lambda *_: model)
    reference = tmp_path / "reference.wav"
    reference.touch()
    candidate = job(text="Opening.\nSelected words.\nEnding.", prepared_text="Selected words.",
                    render_scope="selection", profile="clear_narration", voice_id="voice-123",
                    voice_path=str(reference),
                    output_path=str(tmp_path / "selected.wav"), exaggeration=.9, cfg_weight=.1)
    result = render(engine, candidate)
    metadata = json.loads(result.with_suffix(".json").read_text())
    assert metadata["original_text"] == metadata["text"] == candidate.text
    assert metadata["prepared_text"] == candidate.render_text
    assert metadata["render_scope"] == "selection"
    assert metadata["voice_id"] == "voice-123"
    assert metadata["profile"] == "clear_narration"
    assert metadata["effective_settings"] == candidate.effective_settings()
    assert metadata["generation_kwargs"] == candidate.generation_kwargs() == model.calls[0][1]
    assert [step["text"] for step in metadata["render_plan"] if step["kind"] == "speech"] == [call[0] for call in model.calls]


def test_clock_export_and_adapter_preserve_manuscript(tmp_path, software_engine):
    model = ConditioningModel()
    engine = software_engine(model_loader=lambda *_: model)
    candidate = job(text='Meet at 9:05 a.m.', output_path=str(tmp_path / 'clock.wav'))
    result = render(engine, candidate)
    metadata = json.loads(result.with_suffix('.json').read_text())
    assert metadata['original_text'] == metadata['text'] == candidate.text == 'Meet at 9:05 a.m.'
    assert metadata['prepared_text'] == candidate.render_text == 'Meet at nine oh five a.m.'
    assert [call[0] for call in model.calls] == [candidate.render_text]


@pytest.mark.parametrize("use_reference", [False, True], ids=["built-in", "authorized-reference"])
def test_natural_profile_adapter_and_sidecar_preserve_conditioning_and_text(tmp_path, software_engine, use_reference):
    model = ConditioningModel()
    engine = software_engine(model_loader=lambda *_: model)
    reference = tmp_path / "synthetic-reference.wav"
    reference.touch()
    original = "Opening.\nThe reviewed passage.\nEnding."
    candidate = job(text=original, prepared_text="The reviewed passage.", render_scope="selection",
                    profile="natural_narration", exaggeration=.9, cfg_weight=.8, temperature=1.2,
                    voice_id="authorized-synthetic-id" if use_reference else "",
                    voice_path=str(reference) if use_reference else "",
                    output_path=str(tmp_path / "natural.wav"))
    result = render(engine, candidate)
    expected_args = {"temperature": .8, "exaggeration": .5, "cfg_weight": .3}
    assert model.calls == [(candidate.render_text, expected_args,
                            (str(reference), .5) if use_reference else "built-in")]
    assert model.prepared == ([(str(reference), .5)] if use_reference else [])
    metadata = json.loads(result.with_suffix(".json").read_text())
    assert metadata["profile"] == "natural_narration"
    assert metadata["voice_id"] == candidate.voice_id
    assert metadata["original_text"] == metadata["text"] == original
    assert metadata["prepared_text"] == candidate.render_text
    assert metadata["generation_kwargs"] == expected_args
    assert metadata["effective_settings"] == {
        "max_chars": 220, "pause_ms": 180, "exaggeration": .5, "cfg_weight": .3,
        "temperature": .8, "conditioning_exaggeration": .5}
    assert metadata["render_plan"] == [{"kind": "speech", "text": candidate.render_text,
        "pause_ms": 0, "rate": 1., "volume": 1., "emphasis": False}]


def test_cancelled_preview_cleans_up_then_repeated_preview_uses_current_reference(tmp_path, software_engine):
    from chatterbox_studio.engine import GenerationCancelled
    first = tmp_path / "first.wav"; first.touch()
    second = tmp_path / "second.wav"; second.touch()
    model = ConditioningModel()
    engine = software_engine(model_loader=lambda *_: model)
    candidate = job(text="First sentence. Next sentence. " * 20, voice_path=str(first),
                    output_path=str(tmp_path / "preview.wav"), max_chars=60)
    with pytest.raises(GenerationCancelled):
        render(engine, candidate, cancelled=lambda: bool(model.calls))
    assert not list(tmp_path.glob("*.partial.wav"))
    assert not (tmp_path / "preview.json").exists()
    assert not (tmp_path / "preview.wav").exists()
    result = render(engine, replace(candidate, voice_path=str(second)))
    assert result.is_file()
    assert model.calls[-1][2] == (str(second), .5)
