"""Keep the local narration guide aligned with controls users can inspect."""
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6.QtWidgets')


@pytest.fixture
def help_widget(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QApplication
    from chatterbox_studio.help_center import HelpCenter

    for name in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME'):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    monkeypatch.setenv('PLAGUED_AI_HOME', str(tmp_path / 'shared'))
    monkeypatch.setenv('PLAGUES_VOICE_STUDIO_030_HOME', str(tmp_path / 'studio'))
    app = QApplication.instance() or QApplication([])
    guide = HelpCenter()
    yield guide
    guide.close()
    app.processEvents()


def article(guide, query, title):
    guide.search.setText(query)
    for row in range(guide.topic_list.count()):
        if guide.topic_list.item(row).text() == title:
            guide.topic_list.setCurrentRow(row)
            return guide.browser.toPlainText()
    raise AssertionError(f'{title!r} not found for {query!r}')


def test_profile_help_matches_canonical_settings_and_capabilities(help_widget):
    from chatterbox_studio.jobs import NarrationJob

    text = article(help_widget, 'clear narration', 'Clear Narration and passage previews')
    job = NarrationJob(text='An ordinary narration.', model='english', device='cpu',
                       language='en', voice_path='', output_path='unused.wav',
                       profile='clear_narration')
    values = job.effective_settings()
    assert 'Current settings is the default profile' in text
    assert 'Clear Narration is optional' in text
    assert f'temperature {values["temperature"]:g}' in text
    assert f'{values["max_chars"]} characters' in text
    assert f'{values["pause_ms"]} ms' in text
    assert f'expressiveness {values["exaggeration"]:g}' in text
    assert f'CFG {values["cfg_weight"]:g}' in text
    assert 'Original English and Multilingual V3' in text
    assert 'Turbo and Nano do not support those two generation controls' in text
    assert 'restore and edit your custom values' in text
    assert 'adds no vocal effects' in text
    assert 'Explicit manuscript tags are preserved' in text


def test_passage_and_preview_help_explains_actual_scope(help_widget):
    text = article(help_widget, 'selected passage', 'Clear Narration and passage previews')
    for phrase in (
            'Full document', 'Selected passage', 'Generate and Batch Queue use this scope',
            'separate export', 'does not splice into or replace an existing recording',
            'Preview render plan', 'Ctrl+Shift+P', 'no audio',
            'preview again after changing them', 'original manuscript and prepared render input',
            'full original manuscript', 'complete opening and closing app directives'):
        assert phrase in text
    tags = article(help_widget, 'script tags', 'Script tags')
    assert 'Preview render plan' in tags and 'Ctrl+Shift+P' in tags
    assert 'without generating audio' in tags


def test_natural_profile_help_is_opt_in_and_limits_the_listening_evidence(help_widget):
    from chatterbox_studio.jobs import NarrationJob

    text = article(help_widget, 'natural narration', 'Clear Narration and passage previews')
    values = NarrationJob(text='An ordinary narration.', model='english', device='cpu',
                          language='en', voice_path='', output_path='unused.wav',
                          profile='natural_narration').effective_settings()
    assert 'Current settings is the default profile' in text
    assert 'Natural Narration (Original English)' in text
    assert f'CFG {values["cfg_weight"]:g}' in text
    for phrase in ('built-in voice and imported references',
                   'not established as better for every passage or voice',
                   'restores your custom controls',
                   'does not apply to Turbo, Nano, Multilingual V3, Qwen3-TTS or IndexTTS'):
        assert phrase in text


def test_export_help_uses_current_widget_labels(help_widget, monkeypatch, tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QWidget
    from chatterbox_studio import export_browser

    host = QWidget()
    host.storage = tmp_path
    host.settings = QSettings(str(tmp_path / 'exports.ini'), QSettings.Format.IniFormat)
    host.settings.setFallbacksEnabled(False)
    host.player = SimpleNamespace(stop=lambda: None)
    monkeypatch.setattr(export_browser, 'new_export_directory', lambda _: tmp_path / 'exports')
    monkeypatch.setattr(export_browser, 'old_export_directories', lambda: [])
    browser = export_browser.ExportBrowser(host)
    try:
        text = article(help_widget, 'export library', 'Export Library')
        for label in (browser.text_views.tabText(0), browser.text_views.tabText(1),
                      browser.copy_script.text()):
            assert label in text
        assert 'Render input' in text and 'Original manuscript' in text
        assert 'Copy render input' in text
        assert 'selected passage' in text and 'full document' in text
        assert 'only one script show that script in both tabs' in text
        assert 'Script preview' not in text and 'Copy script' not in text
    finally:
        browser.close()
        host.close()
