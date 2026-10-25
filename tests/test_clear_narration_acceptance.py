"""Independent adapter acceptance checks using synthetic audio, never models."""
from contextlib import nullcontext
from dataclasses import replace
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from chatterbox_studio.jobs import NarrationJob


def snapshot(tmp_path, **changes):
    values = dict(text="Read the complete sentence, calmly.", model="english",
                  device="cpu", language="en", voice_path="",
                  output_path=str(tmp_path / "acceptance.wav"))
    values.update(changes)
    return NarrationJob(**values)


@pytest.fixture
def fake_engine(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False), inference_mode=nullcontext))
    from chatterbox_studio.engine import Engine
    return Engine


class RecordingModel:
    sr = 8000

    def __init__(self):
        self.conds = "built-in"
        self.prepared = []
        self.calls = []

    def prepare_conditionals(self, path, exaggeration=.5):
        self.prepared.append((path, exaggeration))
        self.conds = (path, exaggeration)

    def generate(self, text, **options):
        self.calls.append((text, options, self.conds))
        return np.zeros((1, 160), dtype=np.float32)


def render(engine, job):
    return engine.render(job, lambda _: None, lambda *_: None, lambda: False)


@pytest.mark.parametrize("model", ["english", "multilingual-v3", "nano", "turbo"])
def test_actual_adapter_calls_match_declared_capabilities(tmp_path, fake_engine, model):
    reference = tmp_path / "reference.wav"
    reference.touch()
    job = snapshot(tmp_path, model=model, language="fr", voice_path=str(reference),
                   profile="clear_narration", temperature=1.4,
                   exaggeration=.99, cfg_weight=.01)
    model_object = RecordingModel()
    render(fake_engine(model_loader=lambda *_: model_object), job)
    options = model_object.calls[0][1]
    assert options == job.generation_kwargs()
    assert options["temperature"] == .8
    assert model_object.prepared == [(str(reference), .5)]
    if model in ("nano", "turbo"):
        assert "exaggeration" not in options and "cfg_weight" not in options
    else:
        assert options["exaggeration"] == options["cfg_weight"] == .5
    assert ("language_id" in options) == (model == "multilingual-v3")


def test_selected_plan_and_generated_calls_agree_without_manuscript_mutation(tmp_path, fake_engine):
    original = "Opening which should not be generated.\n\nSelected passage.\n\nClosing which should not be generated."
    prepared = "The selected passage.[pause:250ms][volume:0.7]Its quiet ending.[/volume]"
    reference = tmp_path / "authorized-reference.wav"
    reference.touch()
    job = snapshot(tmp_path, text=original, prepared_text=prepared, render_scope="selection",
                   profile="clear_narration", voice_id="authorized-voice-17", voice_path=str(reference))
    model = RecordingModel()
    expected = job.render_steps()
    result = render(fake_engine(model_loader=lambda *_: model), job)
    assert [call[0] for call in model.calls] == [step.text for step in expected if step.kind == "speech"]
    assert all("should not" not in call[0] for call in model.calls)
    metadata = json.loads(result.with_suffix(".json").read_text())
    assert metadata["original_text"] == metadata["text"] == job.text == original
    assert metadata["prepared_text"] == prepared
    assert metadata["voice_id"] == "authorized-voice-17"
    assert metadata["render_scope"] == "selection"
    assert metadata["effective_settings"] == job.effective_settings()


def test_missing_reference_fails_before_any_model_is_loaded(tmp_path, fake_engine):
    loads = []
    engine = fake_engine(model_loader=lambda *args: loads.append(args))
    with pytest.raises(ValueError, match="no longer exists"):
        render(engine, snapshot(tmp_path, voice_path=str(tmp_path / "missing.wav"), voice_id="gone"))
    assert loads == []
    assert not list(tmp_path.glob("*.json"))


def test_clear_profile_preserves_every_word_and_does_not_inject_vocal_events(tmp_path, fake_engine):
    sentences = [f"Sentence {n} contains ordinary narration words and punctuation." for n in range(31)]
    original = "\n\n".join(sentences)
    job = snapshot(tmp_path, text=original, profile="clear_narration", max_chars=2000)
    model = RecordingModel()
    render(fake_engine(model_loader=lambda *_: model), job)
    spoken = " ".join(call[0] for call in model.calls)
    assert spoken.split() == original.split()
    assert "[" not in spoken and "]" not in spoken
    assert all(len(call[0]) <= 220 for call in model.calls)


def test_repeated_reference_preparation_tracks_changed_conditioning(tmp_path, fake_engine):
    reference = tmp_path / "reference.wav"
    reference.touch()
    model = RecordingModel()
    engine = fake_engine(model_loader=lambda *_: model)
    base = snapshot(tmp_path, voice_path=str(reference), exaggeration=.2)
    render(engine, base)
    render(engine, replace(base, exaggeration=.7))
    render(engine, replace(base, profile="clear_narration"))
    render(engine, replace(base, voice_path="", voice_id=""))
    assert model.prepared == [(str(reference), .2), (str(reference), .7), (str(reference), .5)]
    assert [call[2] for call in model.calls] == [
        (str(reference), .2), (str(reference), .7), (str(reference), .5), "built-in"]


@pytest.fixture(scope="session")
def qt_application():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PyQt6.QtWidgets")
    return widgets.QApplication.instance() or widgets.QApplication([])


@pytest.fixture
def isolated_window(tmp_path, monkeypatch, qt_application):
    from PyQt6.QtCore import QSettings
    from chatterbox_studio import app as app_module, export_browser

    for name, folder in (("PLAGUED_AI_HOME", "shared"),
                         ("PLAGUES_VOICE_STUDIO_HOME", "studio"),
                         ("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"),
                         ("XDG_CACHE_HOME", "cache")):
        monkeypatch.setenv(name, str(tmp_path / folder))

    def temporary_settings(organization, application):
        settings = QSettings(str(tmp_path / (application + ".ini")), QSettings.Format.IniFormat)
        settings.setFallbacksEnabled(False)
        return settings

    monkeypatch.setattr(app_module, "QSettings", temporary_settings)
    # The sandbox cannot connect to the desktop sound server. Keep these
    # widget/selection checks independent of pre-existing audio startup.
    class SilentPlayer:
        PlaybackState = SimpleNamespace(PlayingState=1)

        def __init__(self, *_):
            self.playbackStateChanged = SimpleNamespace(connect=lambda _: None)

        def setAudioOutput(self, *_):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(app_module, "QMediaPlayer", SilentPlayer)
    monkeypatch.setattr(app_module, "QAudioOutput", lambda *_: SimpleNamespace(setVolume=lambda _: None))
    monkeypatch.setattr(app_module, "new_export_directory", lambda _: tmp_path / "exports")
    monkeypatch.setattr(export_browser, "new_export_directory", lambda _: tmp_path / "exports")
    monkeypatch.setattr(export_browser, "old_export_directories", lambda: [])
    monkeypatch.setattr(app_module, "CompatibleVoiceLibrary", lambda _: SimpleNamespace(
        list_voices=lambda: [], resolve=lambda _: ""))
    warnings = []
    monkeypatch.setattr(app_module.QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    qt_application.setStyle("Fusion")
    qt_application.setStyleSheet(app_module.CSS)
    window = app_module.MainWindow()
    window.device.setCurrentIndex(window.device.findData("cpu"))
    window.model.setCurrentIndex(window.model.findData("english"))
    window.output.setText(str(tmp_path / "render.wav"))
    yield window, warnings
    if window._render_preview_dialog is not None:
        window._render_preview_dialog.close()
    window.close()
    qt_application.processEvents()


def test_ui_preview_repetition_and_scope_snapshot_are_exact(isolated_window):
    from PyQt6.QtWidgets import QPlainTextEdit
    from PyQt6.QtGui import QTextCursor
    window, warnings = isolated_window
    original = "Opening 😀 paragraph.\n\nA selected passage.\n\nClosing."
    window.editor.setPlainText(original)
    passage = "A selected passage."
    start = len(original[:original.index(passage)].encode("utf-16-le")) // 2
    cursor = window.editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + len(passage), QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    window.render_scope.setCurrentIndex(window.render_scope.findData("selection"))
    expected = window._snapshot()
    assert expected is not None and expected.render_text == passage
    window._preview_render_plan()
    first = window._render_preview_dialog
    assert first.findChild(QPlainTextEdit, "render_preview_text").toPlainText() == passage
    assert first.findChild(QPlainTextEdit, "render_preview_original").toPlainText() == original
    window._preview_render_plan()
    second = window._render_preview_dialog
    assert second is not first
    assert second.findChild(QPlainTextEdit, "render_preview_text").toPlainText() == expected.render_text
    assert window.thread is None and not window.queue
    assert window.editor.toPlainText() == original
    assert not warnings


def test_ui_selected_passage_requires_complete_directions_and_reference(isolated_window):
    from PyQt6.QtGui import QTextCursor
    window, warnings = isolated_window
    window.editor.setPlainText("Before. [volume:0.7]Quiet words.[/volume] After.")
    start = window.editor.toPlainText().index("Quiet")
    cursor = window.editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(start + len("Quiet words."), QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    window.render_scope.setCurrentIndex(window.render_scope.findData("selection"))
    assert window._snapshot() is None
    assert "complete opening and closing" in warnings[-1]
    window.render_scope.setCurrentIndex(window.render_scope.findData("full_document"))
    window.voice.addItem("Missing saved voice", "missing-id")
    window.voice.setCurrentIndex(window.voice.findData("missing-id"))
    assert window._snapshot() is None
    assert "no longer available" in warnings[-1]


def test_export_browser_separates_selected_input_from_complete_manuscript(isolated_window, tmp_path):
    from PyQt6.QtCore import QMimeData, Qt
    from PyQt6.QtWidgets import QApplication
    from chatterbox_studio.export_metadata import write_export_metadata
    import soundfile as sf

    window, _ = isolated_window
    audio = tmp_path / "selected-recording.wav"
    sf.write(audio, np.zeros(80, dtype=np.float32), 8000)
    source = "The opening.\nThe selected passage.\nThe closing."
    selected = "The selected passage."
    write_export_metadata(audio, dict(text=source, prepared_text=selected,
        render_scope="selection", engine="chatterbox", model="english"))
    browser = window.export_browser
    browser.add_root(tmp_path)
    item = browser.list.findItems(audio.name, Qt.MatchFlag.MatchExactly, 0)[0]
    browser.list.setCurrentItem(item)
    assert browser.script_preview.toPlainText() == selected
    assert browser.original_preview.toPlainText() == source
    assert browser.script_preview.isReadOnly() and browser.original_preview.isReadOnly()
    assert "Selected passage" in browser.preview_status.text()
    clipboard = QApplication.clipboard()
    preserved = QMimeData()
    current = clipboard.mimeData()
    if current is not None:
        for mime_type in current.formats():
            preserved.setData(mime_type, current.data(mime_type))
    try:
        browser.text_views.setCurrentIndex(1)
        assert browser.copy_script.text() == "Copy render input"
        browser.copy_script.click()
        assert clipboard.text() == selected
    finally:
        clipboard.setMimeData(preserved)
