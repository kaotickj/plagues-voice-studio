"""Exercise narration profiles and passage review with isolated Qt settings."""
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6.QtWidgets')


@pytest.fixture
def windows(monkeypatch, tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    from chatterbox_studio import app, export_browser

    monkeypatch.setenv('PLAGUED_AI_HOME', str(tmp_path / 'shared'))
    monkeypatch.setenv('PLAGUES_VOICE_STUDIO_030_HOME', str(tmp_path / 'studio'))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    qt = QApplication.instance() or QApplication([])
    settings_class = QSettings

    def settings(_organization, name):
        value = settings_class(str(tmp_path / (name + '.ini')), settings_class.Format.IniFormat)
        value.setFallbacksEnabled(False)
        return value

    class Voices:
        def __init__(self, *_):
            pass

        def list_voices(self):
            return []

        def resolve(self, _):
            return ''

    class Player:
        # Real Qt widgets remain under test; the sandbox cannot open desktop
        # PipeWire/PulseAudio sockets. Text preview never needs audio hardware.
        PlaybackState = app.QMediaPlayer.PlaybackState

        def __init__(self, *_):
            self.playbackStateChanged = SimpleNamespace(connect=lambda _: None)

        def setAudioOutput(self, _):
            pass

        def stop(self):
            pass

    class AudioOutput:
        def __init__(self, *_):
            pass

        def setVolume(self, _):
            pass

    monkeypatch.setattr(app, 'QSettings', settings)
    monkeypatch.setattr(app, 'CompatibleVoiceLibrary', Voices)
    monkeypatch.setattr(app, 'QMediaPlayer', Player)
    monkeypatch.setattr(app, 'QAudioOutput', AudioOutput)
    monkeypatch.setattr(app, 'user_data_dir', lambda: tmp_path / 'studio')
    monkeypatch.setattr(app, 'new_export_directory', lambda _: tmp_path / 'exports')
    monkeypatch.setattr(export_browser, 'new_export_directory', lambda _: tmp_path / 'exports')
    monkeypatch.setattr(export_browser, 'old_export_directories', lambda: [])
    made = []

    def create():
        window = app.MainWindow()
        window.model.setCurrentIndex(window.model.findData('english'))
        window.editor.setPlainText('First sentence. Second sentence.')
        window.output.setText(str(tmp_path / 'candidate.wav'))
        made.append(window)
        return window

    yield create
    for window in made:
        window.close()
    qt.processEvents()


def select(window, start, end):
    from PyQt6.QtGui import QTextCursor
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(len(text[:start].encode('utf-16-le')) // 2)
    cursor.setPosition(len(text[:end].encode('utf-16-le')) // 2, QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    window.render_scope.setCurrentIndex(window.render_scope.findData('selection'))


def test_profile_keeps_custom_settings_and_model_capabilities(windows):
    window = windows()
    assert window.generation_profile.currentData() == 'custom'
    window.exaggeration.slider.setValue(91)
    window.cfg.slider.setValue(24)
    window.temperature.slider.setValue(112)
    window.chunk.setValue(340)
    window.pause.setValue(70)
    custom = window._snapshot().effective_settings()
    window.generation_profile.setCurrentIndex(window.generation_profile.findData('clear_narration'))
    clear = window._snapshot().effective_settings()
    assert clear['temperature'] == .8 and clear['max_chars'] == 220
    assert clear['exaggeration'] == clear['cfg_weight'] == .5
    assert not window.chunk.isEnabled() and not window.temperature.isEnabled()
    window.generation_profile.setCurrentIndex(0)
    assert window._snapshot().effective_settings() == custom
    assert window.chunk.isEnabled() and window.exaggeration.isEnabled()
    window.model.setCurrentIndex(window.model.findData('nano'))
    assert not window.cfg.isHidden() and not window.exaggeration.isHidden()
    assert not window.cfg.isEnabled() and not window.exaggeration.isEnabled()
    assert 'unavailable' in window.generation_summary.text()
    assert window._snapshot().generation_kwargs() == {'temperature': 1.12}


def test_profile_roundtrip_keeps_custom_values(windows):
    window = windows()
    window.temperature.slider.setValue(109)
    window.exaggeration.slider.setValue(66)
    window.cfg.slider.setValue(32)
    window.chunk.setValue(380)
    window.pause.setValue(85)
    expected = window._snapshot().effective_settings()
    window.generation_profile.setCurrentIndex(1)
    window.close()
    restored = windows()
    assert restored.generation_profile.currentData() == 'clear_narration'
    restored.generation_profile.setCurrentIndex(0)
    assert restored._snapshot().effective_settings() == expected


def test_selection_and_repeated_preview_preserve_manuscript(windows, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QPlainTextEdit
    window = windows()
    original = 'Intro 😀.\nSecond [pause:100ms] passage.\nLast sentence.'
    window.editor.setPlainText(original)
    start, end = original.index('Second'), original.index('\nLast')
    select(window, start, end)
    job = window._snapshot()
    assert job.text == original
    assert job.render_text == original[start:end]
    assert job.render_scope == 'selection'
    assert job.voice_id == ''
    assert window._snapshot().render_steps() == job.render_steps()
    window._preview_render_plan()
    first = window._render_preview_dialog
    assert first.findChild(QPlainTextEdit, 'render_preview_text').toPlainText() == job.render_text
    assert first.findChild(QPlainTextEdit, 'render_preview_original').toPlainText() == original
    assert 'PAUSE 100 ms' in first.findChild(QPlainTextEdit, 'render_preview_steps').toPlainText()
    window._preview_render_plan()
    assert window._render_preview_dialog is not first
    assert not window.queue and window.thread is None
    assert window.editor.toPlainText() == original
    assert not (tmp_path / 'candidate.wav').exists()
    assert not (tmp_path / 'candidate.json').exists()
    scheduled = []
    monkeypatch.setattr(window, '_start_jobs', lambda jobs: scheduled.extend(jobs))
    window.generate.click()
    assert scheduled == window.queue
    assert scheduled[0].text == original and scheduled[0].render_text == job.render_text
    window.editor.setPlainText('A later manuscript edit.')
    assert scheduled[0].text == original


def test_selection_requires_complete_directions_and_existing_voice(windows, monkeypatch):
    from chatterbox_studio import app
    window = windows()
    warnings = []
    monkeypatch.setattr(app.QMessageBox, 'warning', lambda *_: warnings.append(_[2]))
    window.render_scope.setCurrentIndex(1)
    assert window._snapshot() is None
    assert 'Select the passage' in warnings[-1]
    original = 'Before. [rate:0.8]Slower sentence.[/rate] After.'
    window.editor.setPlainText(original)
    select(window, original.index('Slower'), original.index('[/rate]'))
    assert window._snapshot() is None
    assert 'complete opening and closing' in warnings[-1]
    select(window, original.index('[rate:'), original.index(' After.'))
    assert window._snapshot().render_text == '[rate:0.8]Slower sentence.[/rate]'
    window.render_scope.setCurrentIndex(0)
    window.voice.addItem('Removed reference', 'missing-voice')
    window.voice.setCurrentIndex(window.voice.count() - 1)
    assert window._snapshot() is None
    assert 'no longer available' in warnings[-1]
    window._refresh_voices()
    assert window.voice.currentData() == 'missing-voice'
    assert 'Unavailable reference' in window.voice.currentText()
    assert window._snapshot() is None
    assert not window.preview_voice.isEnabled()


@pytest.mark.parametrize('size', [(1330, 880), (940, 650)])
def test_settings_remain_usable_at_supported_window_sizes(windows, size):
    from PyQt6.QtWidgets import QApplication, QScrollArea
    from chatterbox_studio.ui_theme import CSS
    window = windows()
    window.setStyleSheet(CSS)
    window.generation_profile.setCurrentIndex(1)
    window.resize(*size)
    window.show()
    QApplication.processEvents()
    scroll = window.findChild(QScrollArea, 'narration_settings_scroll')
    assert scroll is not None and scroll.widgetResizable()
    assert window.model.height() >= window.model.minimumSizeHint().height()
    assert window.generation_profile.height() >= window.generation_profile.minimumSizeHint().height()
    assert window.generation_profile.isVisible()
    assert window.preview_render.isVisible()
    manuscript_scroll = window.findChild(QScrollArea, 'narration_manuscript_scroll')
    assert manuscript_scroll is not None and manuscript_scroll.widgetResizable()
    assert window.editor.height() >= 160
    assert window.output.height() >= window.output.minimumSizeHint().height()
    assert window.format.height() >= window.format.minimumSizeHint().height()
    assert window.pause.height() >= window.pause.minimumSizeHint().height()
    assert window.generate.isVisible()


def test_preview_is_available_from_keyboard(windows):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    window = windows()
    window.show()
    window.activateWindow()
    window.editor.setFocus()
    QApplication.processEvents()
    QTest.keyClick(window.editor, Qt.Key.Key_P,
                   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    QApplication.processEvents()
    assert window._render_preview_dialog is not None
    assert window._render_preview_dialog.isVisible()
    assert window.thread is None and not window.queue
