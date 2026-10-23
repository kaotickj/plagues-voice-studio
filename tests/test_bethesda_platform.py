"""Platform capability gates; no external tools, audio playback or inference."""
import builtins
import os
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6.QtWidgets')
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget
from chatterbox_studio import app, engine_lab, export_browser, plugin_manager


@pytest.fixture(scope='module')
def qt_app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.mark.parametrize('platform', ['win32', 'linux', 'darwin'])
def test_full_production_tab_is_created_only_on_windows(monkeypatch, platform):
    factory = Mock(return_value=object())
    module = ModuleType('chatterbox_studio.bethesda_widget')
    module.BethesdaExportTab = factory
    host = SimpleNamespace(tabs=SimpleNamespace(addTab=Mock()))
    # Avoid imposing a fake OS on unrelated pytest/Qt lifecycle code.
    with monkeypatch.context() as context:
        context.setattr(app.sys, 'platform', platform)
        context.setitem(sys.modules, module.__name__, module if platform == 'win32' else None)
        app.MainWindow._build_bethesda_tab(host)
    if platform == 'win32':
        factory.assert_called_once_with(host)
        host.tabs.addTab.assert_called_once_with(factory.return_value, 'Bethesda Voice Export')
    else:
        assert host.bethesda_tab is None
        factory.assert_not_called()
        host.tabs.addTab.assert_not_called()


@pytest.mark.parametrize('available', [False, True])
def test_audio_views_offer_handoff_only_when_host_has_production_tab(
        qt_app, monkeypatch, tmp_path, available):
    host = QWidget()
    host.storage = tmp_path / 'data'
    host.storage.mkdir()
    host.settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    host.player = SimpleNamespace(stop=Mock())
    host.voices = SimpleNamespace(list_voices=lambda: [])
    host.bethesda_tab = QWidget(host) if available else None
    monkeypatch.setattr(export_browser, 'new_export_directory', lambda _: tmp_path / 'exports')
    monkeypatch.setattr(export_browser, 'old_export_directories', lambda: [])
    browser = export_browser.ExportBrowser(host)
    lab = engine_lab.EngineLab(host)
    try:
        for panel in (browser, lab):
            assert (panel.findChild(QPushButton, 'bethesda_export_handoff') is not None) == available
        # Ordinary audio import/export browsing remains available on Linux.
        audio_dir = tmp_path / 'exports'
        audio_dir.mkdir()
        for name in ('ordinary.wav', 'ordinary.mp3'):
            (audio_dir / name).write_bytes(b'existing audio sentinel')
        browser.add_root(audio_dir)
        assert {browser.list.topLevelItem(i).text(0)
                for i in range(browser.list.topLevelItemCount())} == {'ordinary.wav', 'ordinary.mp3'}
        assert all(p.read_bytes() == b'existing audio sentinel' for p in audio_dir.iterdir())
    finally:
        host.close()
        host.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize('handoff', [engine_lab.EngineLab.send_to_bethesda,
                                     export_browser.ExportBrowser.send_selected])
def test_direct_handoff_is_safe_without_production_capability(handoff):
    selected = Mock(side_effect=AssertionError('Unsupported action inspected a recording'))
    handoff(SimpleNamespace(host=SimpleNamespace(bethesda_tab=None), selected_path=selected))
    selected.assert_not_called()


@pytest.mark.parametrize('active', [False, True])
def test_plugin_guard_handles_absent_production_tab(active):
    host = SimpleNamespace(thread=None, bethesda_tab=None,
                           engine_lab=SimpleNamespace(is_busy=active),
                           model_manager=SimpleNamespace(is_busy=False))
    manager = SimpleNamespace(host=host, is_busy=False)
    assert bool(plugin_manager.PluginManager.can_generate(manager)) == active


@pytest.mark.parametrize('model_busy', [False, True])
def test_close_without_production_tab_preserves_saved_tool_settings(
        qt_app, monkeypatch, tmp_path, model_busy):
    window = app.MainWindow.__new__(app.MainWindow)
    QMainWindow.__init__(window)
    window.plugins = SimpleNamespace(is_busy=False, close_all=Mock())
    window._update_dialog = None
    window.thread = None
    window.bethesda_tab = None
    window.engine_lab = SimpleNamespace(is_busy=False)
    window.model_manager = SimpleNamespace(is_busy=model_busy)
    window.settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    window.settings.setValue('bethesda/facefx', 'preserved Windows tool path')
    window.model = window.format = SimpleNamespace(currentData=lambda: 'saved setting')
    window.pause = window.chunk = SimpleNamespace(value=lambda: 100)
    window.player = SimpleNamespace(stop=Mock())
    before = {key: window.settings.value(key) for key in window.settings.allKeys()}
    notice = Mock()
    monkeypatch.setattr(app.QMessageBox, 'information', notice)
    event = QCloseEvent()
    window.closeEvent(event)
    if model_busy:
        assert not event.isAccepted()
        assert {key: window.settings.value(key) for key in window.settings.allKeys()} == before
        window.player.stop.assert_not_called()
        window.plugins.close_all.assert_not_called()
        notice.assert_called_once()
    else:
        assert event.isAccepted()
        assert window.settings.value('bethesda/facefx') == 'preserved Windows tool path'
        window.player.stop.assert_called_once()
        window.plugins.close_all.assert_called_once()
        notice.assert_not_called()
    window.deleteLater()
    qt_app.processEvents()


@pytest.mark.parametrize('platform', ['linux', 'win32'])
def test_package_excludes_only_windows_ui_and_keeps_portable_helpers(monkeypatch, platform):
    root = Path(__file__).resolve().parents[1]
    captured = {}
    hooks = SimpleNamespace(collect_all=lambda *_args, **_kwargs: ([], [], []),
                            collect_submodules=lambda *_args: [], copy_metadata=lambda *_args: [])
    original_import = builtins.__import__

    def imports(name, *args, **kwargs):
        return hooks if name == 'PyInstaller.utils.hooks' else original_import(name, *args, **kwargs)

    def analysis(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

    with monkeypatch.context() as context:
        context.setattr(sys, 'platform', platform)
        context.setattr(builtins, '__import__', imports)
        context.setenv('PVS_SLIM_BUILD', '1')
        runpy.run_path(str(root / 'ChatterboxStudio.spec'), init_globals={
            'SPECPATH': str(root), 'Analysis': analysis,
            'PYZ': lambda *_args, **_kwargs: None,
            'EXE': lambda *_args, **_kwargs: None,
            'COLLECT': lambda *_args, **_kwargs: None,
        })
    assert ('chatterbox_studio.bethesda_widget' in captured['excludes']) == (platform != 'win32')
    for module in ('chatterbox_studio.bethesda_export', 'chatterbox_studio.mod_profiles'):
        assert module in captured['hiddenimports']
        assert module not in captured['excludes']
