"""Exercise actual Qt handoffs and project switching without model inference."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6.QtWidgets')
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QWidget, QComboBox, QPlainTextEdit, QTabWidget
from chatterbox_studio.bethesda_widget import BethesdaExportTab
from chatterbox_studio.engine_lab import EngineLab
from chatterbox_studio.export_browser import ExportBrowser


@pytest.fixture(scope='module')
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def host(tmp_path, qt_app):
    window = QWidget()
    window.storage = tmp_path / 'data'
    window.storage.mkdir()
    window.settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    window.thread = None
    window.queue = []
    window.results = {}
    window._log = lambda *_: None
    window.voice = QComboBox(window)
    window.voice.addItem('Default', '')
    window.voice.addItem('Saved voice', 'saved-id')
    window.model = QComboBox(window)
    window.model.addItem('Nano', 'nano')
    window.editor = QPlainTextEdit(window)
    window.tabs = QTabWidget(window)
    window.bethesda_tab = BethesdaExportTab(window)
    window.tabs.addTab(window.bethesda_tab, 'Bethesda')
    yield window
    window.close()
    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.parametrize('sender', [EngineLab.send_to_bethesda, ExportBrowser.send_selected])
def test_audio_handoff_loads_its_own_script(host, tmp_path, sender):
    recording = tmp_path / 'new recording.wav'
    recording.write_bytes(b'audio placeholder')
    recording.with_suffix('.json').write_text(json.dumps({
        'text': 'This is the generated dialogue.', 'ref_text': 'Entirely different speaker reference.'}))
    host.bethesda_tab.transcript.setPlainText('Previous recording, wrong dialogue.')
    sender(SimpleNamespace(host=host, selected_path=lambda: recording))
    assert host.bethesda_tab.audio.text() == str(recording)
    assert host.bethesda_tab.transcript.toPlainText() == 'This is the generated dialogue.'


@pytest.mark.parametrize('metadata', [None, b'broken JSON', b'[]', b'{"ref_text":"reference only"}', b'\xff'])
def test_old_or_unreadable_metadata_clears_stale_script(host, tmp_path, metadata):
    recording = tmp_path / 'old recording.wav'
    recording.write_bytes(b'audio placeholder')
    if metadata is not None:
        recording.with_suffix('.json').write_bytes(metadata)
    host.bethesda_tab.transcript.setPlainText('Stale dialogue must not survive an audio change.')
    host.bethesda_tab.audio.setText(str(recording))
    assert host.bethesda_tab.transcript.toPlainText() == ''


def test_chatterbox_handoff_uses_completed_job_snapshot(host, tmp_path):
    recording = tmp_path / 'narration.wav'
    recording.write_bytes(b'audio placeholder')
    host.queue = [SimpleNamespace(job_id='job1', text='Actual [chuckle] recorded words.')]
    host.results = {'job1': str(recording)}
    host.editor.setPlainText('An edited script that was never recorded.')
    host.bethesda_tab.audio.setText(str(recording))
    assert host.bethesda_tab.transcript.toPlainText() == 'Actual recorded words.'


def test_project_switch_does_not_reuse_other_projects_voicetype(host):
    tab = host.bethesda_tab
    first = tab.store.new_project('First mod', plugin='First.esp')
    voice = tab.store.new_voice('Actor', 'FirstVoice', 'saved-id', 'nano')
    first['voices'].append(voice)
    second = tab.store.new_project('Second mod', plugin='Second.esp')
    tab.projects = [first, second]
    tab._refresh_project_select(first['id'])
    tab._refresh_voice_select(voice['id'])
    assert tab.voice_type.text() == 'FirstVoice'
    tab.project_select.setCurrentIndex(tab.project_select.findData(second['id']))
    assert tab.plugin.text() == 'Second.esp'
    assert tab.voice_type.text() == ''


def test_saving_project_preserves_voicetype_being_entered(host):
    tab = host.bethesda_tab
    tab.project_name.setText('New mod')
    tab.plugin.setText('New.esp')
    tab.voice_type.setText('NewVoice')
    tab._save_project()
    assert tab.voice_type.text() == 'NewVoice'


def test_deleting_voice_assignment_clears_voicetype(host):
    tab = host.bethesda_tab
    project = tab.store.new_project('Mod')
    voice = tab.store.new_voice('Actor', 'ActorVoice', '', 'nano')
    project['voices'].append(voice)
    tab.projects = [project]
    tab._refresh_project_select(project['id'])
    tab._refresh_voice_select(voice['id'])
    tab._delete_voice_profile()
    assert tab.voice_type.text() == ''


def test_destination_preview_does_not_write_project_files(host):
    host.bethesda_tab._update_preview()
    assert not (host.storage / 'bethesda_source').exists()
    assert 'Incomplete destination' in host.bethesda_tab.preview.text()


@pytest.mark.parametrize('platform,runner', [('linux', 'wine'), ('win32', 'native')])
def test_platform_defaults_preserve_windows(host, monkeypatch, platform, runner):
    import chatterbox_studio.bethesda_widget as gui
    monkeypatch.setattr(gui.sys, 'platform', platform)
    tab = BethesdaExportTab(host)
    assert tab.tool_runner.currentData() == runner
    assert tab.lip_backend.currentData() == ('lipgenerator' if platform == 'linux' else 'facefxwrapper')
    assert tab.encoder_type.currentData() == ('xwmaencode' if platform == 'linux' else 'wmaencoders')
    assert tab.timeout.value() == 240
    assert tab.timeout.minimum() == 1
    assert tab.timeout.maximum() == 3600
    assert tab.wine_fields.isHidden() == (runner == 'native')


def test_tool_settings_roundtrip_and_runner_visibility(host):
    tab = host.bethesda_tab
    tab._select_combo(tab.tool_runner, 'wine')
    tab._select_combo(tab.lip_backend, 'lipgenerator')
    tab._select_combo(tab.encoder_type, 'xwmaencode')
    tab.wine_path.setText('/opt/Proton/files/bin/wine')
    tab.wine_prefix.setText('/home/user/pvs prefix')
    tab.facefx.setText('/games/CK/LipGenerator.exe')
    tab.timeout.setValue(600)
    tab._save_tools()
    loaded = BethesdaExportTab(host)
    config = loaded._config()
    assert config.lip_backend == 'lipgenerator'
    assert config.tool_runner == 'wine'
    assert config.wine_path == '/opt/Proton/files/bin/wine'
    assert config.wine_prefix == '/home/user/pvs prefix'
    assert config.facefx_path == '/games/CK/LipGenerator.exe'
    assert config.encoder_type == 'xwmaencode'
    assert config.tool_timeout_seconds == 600
    assert not loaded.wine_fields.isHidden()
    loaded._select_combo(loaded.tool_runner, 'native')
    assert loaded.wine_fields.isHidden()
    assert loaded.wine_prefix.text() == '/home/user/pvs prefix'
    loaded._select_combo(loaded.game, 'skyrimse')
    assert 'Incompatible' in loaded.compatibility.text()
    loaded._select_combo(loaded.lip_backend, 'facefxwrapper')
    assert 'Incompatible' not in loaded.compatibility.text()


def test_diagnostics_saves_without_audio_or_project(host, monkeypatch):
    import chatterbox_studio.bethesda_widget as gui
    seen = []
    monkeypatch.setattr(gui, 'diagnose_tools', lambda config: seen.append(config) or ['Select a valid Wine executable.'])
    tab = host.bethesda_tab
    tab.wine_path.setText('/missing/wine')
    tab._diagnose()
    assert seen[0].source_audio == ''
    assert tab.diagnostics.toPlainText() == 'Select a valid Wine executable.'
    assert host.settings.value('bethesda/tools/wine_path') == '/missing/wine'
    assert not (host.storage / 'bethesda_source').exists()


def test_worker_cancellation_callback_and_friendly_completion(host, monkeypatch):
    import threading
    import chatterbox_studio.bethesda_widget as gui
    event = threading.Event()
    event.set()
    def cancelled_export(config, report, cancelled):
        assert cancelled()
        raise gui.BethesdaExportCancelled('Cancelled')
    monkeypatch.setattr(gui, 'export_dialogue', cancelled_export)
    worker = gui.ExportTask(object(), event)
    results = []
    worker.complete.connect(lambda path, error: results.append((path, error)))
    worker.run()
    assert results == [('', '')]
    monkeypatch.setattr(gui.QMessageBox, 'warning', lambda *_: pytest.fail('Cancellation should not display an error dialog'))
    host.bethesda_tab._finished(*results[0])
    assert 'cancelled' in host.bethesda_tab.status.text()


def test_export_ignores_gpu_job_rejects_repeat_and_cancels(host, tmp_path, qt_app, monkeypatch):
    import threading
    import time
    import chatterbox_studio.bethesda_widget as gui
    entered = threading.Event()
    started = []
    def fake_export(config, report, cancelled):
        started.append(config)
        entered.set()
        deadline = time.monotonic() + 4
        while not cancelled() and time.monotonic() < deadline:
            time.sleep(.005)
        if cancelled():
            raise gui.BethesdaExportCancelled('Cancelled')
        raise RuntimeError('Test cancellation timed out')
    monkeypatch.setattr(gui, 'export_dialogue', fake_export)
    monkeypatch.setattr(gui.BethesdaExportSettings, 'validate', lambda _: None)
    monkeypatch.setattr(gui, 'expected_fuz_path', lambda _: tmp_path / 'destination.fuz')
    notices = []
    monkeypatch.setattr(gui.QMessageBox, 'information', lambda *args: notices.append(args[1]))
    monkeypatch.setattr(gui.QMessageBox, 'warning', lambda *args: notices.append(args[1]))
    tab = host.bethesda_tab
    host.thread = object()  # A narration/GPU job must not block independent conversion.
    tab._start()
    try:
        assert entered.wait(2)
        assert tab.is_busy
        assert not tab.run_button.isEnabled()
        assert tab.cancel_button.isEnabled()
        tab._start()
        assert notices == ['Busy']
        assert len(started) == 1
        tab._cancel()
        assert tab.cancel_event.is_set()
        assert tab.is_busy  # Keep close protection until QThread actually finishes.
        assert not tab.cancel_button.isEnabled()
        tab._progress('Late worker progress')
        assert 'Cancelling' in tab.status.text()
        deadline = time.monotonic() + 3
        while tab.is_busy and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(.005)
        assert not tab.is_busy
        assert tab.run_button.isEnabled()
        assert tab.diagnose_button.isEnabled()
        assert 'cancelled' in tab.status.text()
        assert notices == ['Busy']
    finally:
        tab.cancel_event.set()
        if tab.thread is not None:
            tab.thread.quit()
            tab.thread.wait(5000)
            qt_app.processEvents()
        host.thread = None


def test_legacy_linux_facefx_settings_keep_backend_assumption(host, monkeypatch):
    import chatterbox_studio.bethesda_widget as gui
    monkeypatch.setattr(gui.sys, 'platform', 'linux')
    host.settings.setValue('bethesda/tools/facefx', '/old/tools/FaceFXWrapper.exe')
    tab = BethesdaExportTab(host)
    assert tab.lip_backend.currentData() == 'facefxwrapper'
    assert tab.encoder_type.currentData() == 'wmaencoders'
    assert tab.facefx.text() == '/old/tools/FaceFXWrapper.exe'
    assert 'In-game validation is required' in tab.compatibility.text()
    assert 'runtime-dependent' in tab.compatibility.text()
    assert 'BETHESDA_LINUX.md' in tab.setup_help.text()


@pytest.mark.parametrize('platform', ['linux', 'win32'])
@pytest.mark.parametrize('backend,encoder', [('facefxwrapper', 'wmaencoders'), ('lipgenerator', 'xwmaencode')])
def test_explicit_tool_choices_override_platform_defaults(host, monkeypatch, platform, backend, encoder):
    import chatterbox_studio.bethesda_widget as gui
    monkeypatch.setattr(gui.sys, 'platform', platform)
    host.settings.setValue('bethesda/tools/lip_backend', backend)
    host.settings.setValue('bethesda/tools/encoder_type', encoder)
    tab = BethesdaExportTab(host)
    assert tab.lip_backend.currentData() == backend
    assert tab.encoder_type.currentData() == encoder


def test_linux_guide_paths_source_and_frozen(host, monkeypatch, tmp_path):
    import chatterbox_studio.bethesda_widget as gui
    monkeypatch.setattr(gui.sys, 'frozen', False, raising=False)
    assert host.bethesda_tab._linux_guide_path() == Path(gui.__file__).resolve().parents[2] / 'BETHESDA_LINUX.md'
    monkeypatch.setattr(gui.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(gui.sys, '_MEIPASS', str(tmp_path), raising=False)
    assert host.bethesda_tab._linux_guide_path() == tmp_path / 'BETHESDA_LINUX.md'


@pytest.mark.parametrize('platform,hidden', [('linux', False), ('win32', True)])
def test_linux_guide_button_platform_visibility(host, monkeypatch, platform, hidden):
    import chatterbox_studio.bethesda_widget as gui
    monkeypatch.setattr(gui.sys, 'platform', platform)
    tab = BethesdaExportTab(host)
    assert tab.guide_button.isHidden() == hidden


def test_linux_guide_missing_reports_actionable_warning(host, monkeypatch, tmp_path):
    import chatterbox_studio.bethesda_widget as gui
    monkeypatch.setattr(gui.BethesdaExportTab, '_linux_guide_path', staticmethod(lambda: tmp_path / 'missing.md'))
    notices = []
    monkeypatch.setattr(gui.QMessageBox, 'warning', lambda *args: notices.append(args[2]))
    host.bethesda_tab._open_linux_guide()
    assert len(notices) == 1
    assert 'BETHESDA_LINUX.md' in notices[0]
    assert 'release documentation' in notices[0]


def test_linux_guide_renders_in_readonly_dialog(host, monkeypatch, tmp_path):
    import chatterbox_studio.bethesda_widget as gui
    guide = tmp_path / 'BETHESDA_LINUX.md'
    guide.write_text('# Linux setup\nInstall your own tools.', encoding='utf-8')
    opened = []
    monkeypatch.setattr(gui.QDesktopServices, 'openUrl', lambda url: opened.append(url.toString()))
    monkeypatch.setattr(gui.BethesdaExportTab, '_linux_guide_path', staticmethod(lambda: guide))
    rendered = []
    def inspect_dialog(dialog):
        browser = dialog.findChild(gui.QTextBrowser)
        assert browser.isReadOnly()
        assert not browser.openExternalLinks()
        assert not browser.openLinks()
        rendered.append(browser.toPlainText())
        assert opened == []  # Rendering a guide must not launch the browser.
        from PyQt6.QtCore import QUrl
        browser.anchorClicked.emit(QUrl('https://example.com/dependencies'))
        assert opened == ['https://example.com/dependencies']
        return 0
    monkeypatch.setattr(gui.QDialog, 'exec', inspect_dialog)
    host.bethesda_tab._open_linux_guide()
    assert rendered == ['Linux setup\nInstall your own tools.']


@pytest.mark.parametrize('url,allowed', [
    ('https://example.com/tools', True),
    ('http://example.com/tools', False),
    ('file:///tmp/tool.exe', False),
    ('javascript:alert(1)', False),
    ('BETHESDA_VOICE_EXPORT.md', False),
    ('https:relative', False),
])
def test_guide_links_only_dispatch_https_on_click(host, monkeypatch, url, allowed):
    import chatterbox_studio.bethesda_widget as gui
    from PyQt6.QtCore import QUrl
    opened = []
    monkeypatch.setattr(gui.QDesktopServices, 'openUrl', lambda target: opened.append(target.toString()))
    host.bethesda_tab._open_guide_link(QUrl(url))
    assert opened == ([url] if allowed else [])
