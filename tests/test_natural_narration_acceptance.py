"""Independent opt-in profile acceptance; synthetic models and isolated Qt only."""
from dataclasses import replace
import json

import pytest

from chatterbox_studio.jobs import NarrationJob
from test_clear_narration_acceptance import (
    RecordingModel, fake_engine, isolated_window, qt_application, render, snapshot,
)


def choose(window, profile):
    window.generation_profile.setCurrentIndex(window.generation_profile.findData(profile))


def custom_values(window):
    window.exaggeration.slider.setValue(73)
    window.cfg.slider.setValue(62)
    window.temperature.slider.setValue(91)
    window.chunk.setValue(340)
    window.pause.setValue(70)
    return window._snapshot().effective_settings()


@pytest.mark.parametrize("model", ["nano", "turbo", "multilingual-v3"])
def test_unsupported_natural_fails_before_loader(tmp_path, fake_engine, model):
    loaded = []
    candidate = snapshot(tmp_path, model=model, profile="natural_narration")
    engine = fake_engine(model_loader=lambda *args: loaded.append(args))
    with pytest.raises(ValueError, match="only for Original English"):
        render(engine, candidate)
    assert loaded == []
    assert not list(tmp_path.glob("*.json"))


def test_actual_natural_arguments_and_selection_sidecar(tmp_path, fake_engine):
    original = "Opening.\nThe selected passage.\nClosing."
    prepared = "Selected words.[pause:100ms]A quiet ending."
    candidate = snapshot(tmp_path, text=original, prepared_text=prepared,
                         render_scope="selection", profile="natural_narration",
                         exaggeration=.9, cfg_weight=.7, temperature=1.2,
                         max_chars=400, pause_ms=500)
    model = RecordingModel()
    result = render(fake_engine(model_loader=lambda *_: model), candidate)
    assert [call[0] for call in model.calls] == ["Selected words.", "A quiet ending."]
    assert all(call[1] == dict(temperature=.8, exaggeration=.5, cfg_weight=.3)
               and call[2] == "built-in" for call in model.calls)
    metadata = json.loads(result.with_suffix(".json").read_text())
    assert metadata["profile"] == "natural_narration"
    assert metadata["text"] == metadata["original_text"] == original
    assert metadata["prepared_text"] == prepared
    assert metadata["render_scope"] == "selection"
    assert metadata["effective_settings"] == candidate.effective_settings()
    assert metadata["generation_kwargs"] == model.calls[0][1]
    assert [step["pause_ms"] for step in metadata["render_plan"] if step["kind"] == "pause"] == [100]
    assert NarrationJob(**json.loads(json.dumps(candidate.as_json()))) == candidate
    clear = replace(candidate, profile="clear_narration").effective_settings()
    assert clear == {**candidate.effective_settings(), "cfg_weight": .5}
    assert replace(candidate, profile="custom").generation_kwargs() == {
        "temperature": 1.2, "exaggeration": .9, "cfg_weight": .7}


def test_switching_fixed_profiles_preserves_custom_and_queued_snapshot(isolated_window):
    window, warnings = isolated_window
    window.editor.setPlainText("An ordinary narration passage.")
    assert window.generation_profile.currentData() == "custom"
    expected = custom_values(window)
    for profile in ("clear_narration", "natural_narration", "clear_narration", "natural_narration"):
        choose(window, profile)
        job = window._snapshot()
        assert job.effective_settings()["cfg_weight"] == (.3 if profile == "natural_narration" else .5)
        assert not window.cfg.isEnabled() and not window.temperature.isEnabled()
    natural = window._snapshot()
    window._append_job(natural)
    choose(window, "custom")
    assert window._snapshot().effective_settings() == expected
    window.model.setCurrentIndex(window.model.findData("nano"))
    assert window.queue[0] is natural
    assert natural.model == "english" and natural.profile == "natural_narration"
    assert natural.generation_kwargs()["cfg_weight"] == .3
    assert not warnings


@pytest.mark.parametrize("model", ["nano", "turbo", "multilingual-v3"])
def test_model_change_and_disabled_profile_restore_custom(isolated_window, model):
    window, warnings = isolated_window
    window.editor.setPlainText("A narration for profile restoration.")
    expected = custom_values(window)
    choose(window, "natural_narration")
    window.model.setCurrentIndex(window.model.findData(model))
    assert window.generation_profile.currentData() == "custom"
    assert window.cfg.value() == expected["cfg_weight"]
    assert window.exaggeration.value() == expected["conditioning_exaggeration"]
    assert window.temperature.value() == expected["temperature"]
    assert window.chunk.value() == expected["max_chars"] and window.pause.value() == expected["pause_ms"]
    index = window.generation_profile.findData("natural_narration")
    assert not window.generation_profile.model().item(index).isEnabled()
    assert "requires Original English" in window.generation_summary.text()
    # Disabled entries are still selectable by code/settings restoration.
    choose(window, "natural_narration")
    assert window.generation_profile.currentData() == "custom"
    window.model.setCurrentIndex(window.model.findData("english"))
    assert window.generation_profile.model().item(index).isEnabled()
    assert window._snapshot().effective_settings() == expected
    assert not warnings


def test_natural_restart_and_inconsistent_saved_model_are_safe(isolated_window):
    from chatterbox_studio.app import MainWindow
    window, warnings = isolated_window
    window.editor.setPlainText("The unchanged manuscript.")
    expected = custom_values(window)
    choose(window, "natural_narration")
    window.close()
    window.settings.sync()
    restored = MainWindow()
    try:
        restored.editor.setPlainText("The unchanged manuscript.")
        assert restored.generation_profile.currentData() == "natural_narration"
        assert restored._snapshot().generation_kwargs()["cfg_weight"] == .3
        choose(restored, "clear_narration")
        choose(restored, "natural_narration")
        choose(restored, "custom")
        assert restored._snapshot().effective_settings() == expected
        restored.close()
        restored.settings.setValue("model", "multilingual-v3")
        restored.settings.setValue("narration/profile", "natural_narration")
        restored.settings.sync()
        inconsistent = MainWindow()
        try:
            inconsistent.editor.setPlainText("A restored passage.")
            assert inconsistent.generation_profile.currentData() == "custom"
            assert "requires Original English" in inconsistent.generation_summary.text()
            assert inconsistent.cfg.value() == expected["cfg_weight"]
        finally:
            inconsistent.close()
    finally:
        restored.close()
    assert not warnings


def test_natural_preview_uses_effective_cfg_without_generation(isolated_window):
    from PyQt6.QtWidgets import QPlainTextEdit
    window, warnings = isolated_window
    source = "A plain manuscript with no surprise effects."
    window.editor.setPlainText(source)
    choose(window, "natural_narration")
    window._preview_render_plan()
    preview = window._render_preview_dialog
    settings = preview.findChild(QPlainTextEdit, "render_preview_settings").toPlainText()
    assert "natural_narration" in settings and "cfg_weight: 0.3" in settings
    assert preview.findChild(QPlainTextEdit, "render_preview_original").toPlainText() == source
    assert preview.findChild(QPlainTextEdit, "render_preview_text").toPlainText() == source
    assert window.thread is None and not window.queue
    assert not warnings
