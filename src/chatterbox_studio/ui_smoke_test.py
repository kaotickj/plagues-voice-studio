"""Smoke test actual Qt window construction, without invoking speech synthesis.

Run on Windows via PlaguesVoiceStudio030Experimental.exe --ui-self-test <report.json>.
Use --ui-self-test-no-audio <report.json> for the same widget checks with
diagnostic-only inert media objects. That mode does not initialize real audio.
Exits nonzero and writes exception details if the GUI cannot be initialized.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from . import __version__


def _no_audio_media_types(player_type):
    """Media-only stand-ins for an explicitly requested no-audio diagnostic.

    Keep application widgets and their connections intact. Any attempt to load
    a source or play audio fails, rather than reaching a device or sound server.
    """
    class Signal:
        def __init__(self):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

        def emit(self, value):
            for callback in self.callbacks:
                callback(value)

    class NoAudioPlayer:
        PlaybackState = player_type.PlaybackState

        def __init__(self, parent=None):
            self.playbackStateChanged = Signal()

        def setAudioOutput(self, output):
            self.audio_output = output

        def playbackState(self):
            return self.PlaybackState.StoppedState

        def stop(self):
            self.playbackStateChanged.emit(self.PlaybackState.StoppedState)

        def setSource(self, *args, **kwargs):
            raise RuntimeError('No-audio UI diagnostic forbids loading audio sources.')

        def play(self):
            raise RuntimeError('No-audio UI diagnostic forbids audio playback.')

    class NoAudioOutput:
        def __init__(self, parent=None):
            self._volume = 1.0

        def setVolume(self, volume):
            self._volume = volume

        def volume(self):
            return self._volume

    return NoAudioPlayer, NoAudioOutput


def _check_export_script_preview(browser, sample_dir: Path) -> None:
    """Exercise the real export widgets without synthesis or audio playback."""
    from wave import open as open_wave
    from PyQt6.QtCore import QMimeData, Qt
    from PyQt6.QtWidgets import QApplication
    from .export_metadata import write_export_metadata

    sample_dir.mkdir()
    script = '[narration] The Charles River is quiet.\n\n[whispering] Not for long, sweetheart.'
    audio_path = sample_dir / 'test_story.wav'
    with open_wave(str(audio_path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\x00\x00' * 800)
    write_export_metadata(audio_path, {'engine': 'chatterbox', 'model': 'turbo', 'text': script})
    browser.add_root(sample_dir)
    matches = browser.list.findItems(audio_path.name, Qt.MatchFlag.MatchExactly, 0)
    if len(matches) != 1:
        raise RuntimeError('Generated Chatterbox WAV missing from Export Library.')
    browser.list.setCurrentItem(matches[0])
    if browser.script_preview.toPlainText() != script:
        raise RuntimeError('Export Library failed to display the exact saved script.')
    if not browser.script_preview.isReadOnly() or not browser.copy_script.isEnabled():
        raise RuntimeError('Export script preview must be read-only and copyable.')
    clipboard = QApplication.clipboard()
    saved_clipboard = QMimeData()
    current_clipboard = clipboard.mimeData()
    if current_clipboard is not None:
        for mime_type in current_clipboard.formats():
            saved_clipboard.setData(mime_type, current_clipboard.data(mime_type))
    try:
        browser.copy_script.click()
        if clipboard.text() != script:
            raise RuntimeError('Copy script did not preserve the original tags and whitespace.')
    finally:
        clipboard.setMimeData(saved_clipboard)
    legacy_path = sample_dir / 'older_without_script.wav'
    legacy_path.write_bytes(audio_path.read_bytes())
    browser.refresh()
    matches = browser.list.findItems(legacy_path.name, Qt.MatchFlag.MatchExactly, 0)
    if len(matches) != 1:
        raise RuntimeError('Legacy audio not listed in Export Library.')
    browser.list.setCurrentItem(matches[0])
    if browser.script_preview.toPlainText() or browser.copy_script.isEnabled():
        raise RuntimeError('Legacy recording reused a different audio file script.')


def run(report_path: Path | None = None, *, no_audio: bool = False) -> int:
    report = {"version": __version__,
              "test": "Qt main-window and About dialog lifecycle" + (" (NO AUDIO)" if no_audio else ""),
              "mode": "no_audio" if no_audio else "standard",
              "real_audio": not no_audio,
              "playback": False,
              "audio_note": ("Real audio is disabled. Inert media objects are used; audio source loading and playback are forbidden."
                             if no_audio else "Real Qt multimedia objects are initialized. Audio playback is not tested."),
              "status": "failed", "errors": []}
    try:
        from PyQt6.QtCore import QTimer, QSettings
        from PyQt6.QtWidgets import QApplication, QPushButton, QDialog, QLabel, QLineEdit, QListWidget, QTabWidget, QPlainTextEdit
        from . import app as app_module
        from .app import MainWindow, CSS, _application_icon
        app = QApplication.instance() or QApplication([sys.argv[0]])
        app.setStyle("Fusion")
        app.setStyleSheet(CSS)
        app.setApplicationName("Plague's Voice Studio")
        app.setOrganizationName("KaotickJay")
        with tempfile.TemporaryDirectory(prefix="pvs-ui-smoke-") as tmp:
            # Avoid writing to any real project or v0.1 fallback installation.
            old = os.environ.get('PLAGUES_VOICE_STUDIO_030_HOME')
            os.environ['PLAGUES_VOICE_STUDIO_030_HOME'] = str(Path(tmp) / 'data')
            QSettings.setDefaultFormat(QSettings.Format.IniFormat)
            QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
            # The named QSettings(org, app) overload always uses NativeFormat
            # on Windows, regardless of setDefaultFormat. Supply explicit file
            # settings so this diagnostic cannot read/write the real registry.
            original_settings = app_module.QSettings
            original_player = app_module.QMediaPlayer
            original_audio_output = app_module.QAudioOutput
            def isolated_settings(organization, application):
                settings = QSettings(str(Path(tmp) / (application + '.ini')), QSettings.Format.IniFormat)
                settings.setFallbacksEnabled(False)
                return settings
            app_module.QSettings = isolated_settings
            try:
                if no_audio:
                    app_module.QMediaPlayer, app_module.QAudioOutput = _no_audio_media_types(original_player)
                window = MainWindow()
                if window.windowIcon().isNull():
                    raise RuntimeError('Application icon was not packaged.')
                window.show()
                bethesda_available = sys.platform == 'win32'
                if (window.bethesda_tab is not None) != bethesda_available:
                    raise RuntimeError('Bethesda production export must be available only on Windows.')
                for panel in (window.export_browser, window.engine_lab):
                    handoff = panel.findChild(QPushButton, 'bethesda_export_handoff')
                    if (handoff is not None) != bethesda_available:
                        raise RuntimeError('Bethesda export handoff does not match platform support.')
                # Load the generic plugin through its actual host menu, without a model job.
                writer_action = next((action for action in window.plugins.menu.actions()
                                      if action.data() == 'promotional-writer'), None)
                if writer_action is None:
                    raise RuntimeError('Promotional Writer plugin was not packaged/discovered.')
                writer_action.trigger()
                writer_dialog = window.plugins.dialogs.get('promotional-writer')
                if writer_dialog is None or not writer_dialog.isVisible() or writer_dialog.panel.is_busy:
                    raise RuntimeError('Writer plugin did not open idle from the Plugins menu.')
                if writer_dialog.panel.category.count() != 7:
                    raise RuntimeError('Generic copywriting recipes are missing.')
                writer_dialog.close()
                if writer_dialog.isVisible():
                    raise RuntimeError('Writer plugin did not close.')
                writer_action.trigger()
                if window.plugins.dialogs['promotional-writer'] is not writer_dialog:
                    raise RuntimeError('Writer plugin opened duplicate instances.')
                writer_dialog.close()
                if writer_dialog.isVisible():
                    raise RuntimeError('Writer plugin did not close after reopening.')
                prep_action = next((action for action in window.plugins.menu.actions()
                                    if action.data() == 'script-prep'), None)
                if prep_action is None:
                    raise RuntimeError('Script Prep plugin was not packaged/discovered.')
                prep_action.trigger()
                prep_dialog = window.plugins.dialogs.get('script-prep')
                if prep_dialog is None or not prep_dialog.isVisible():
                    raise RuntimeError('Script Prep did not open from the Plugins menu.')
                prep_dialog.panel.source.setPlainText('Dr. Jones paid $12.50.')
                prep_dialog.panel.preview()
                if prep_dialog.panel.output.toPlainText() != 'Doctor Jones paid twelve dollars and fifty cents.':
                    raise RuntimeError('Script Prep speech preparation failed.')
                if prep_dialog.panel.send_button.isEnabled():
                    raise RuntimeError('Script Prep handoff bypassed review.')
                prep_dialog.close()
                # Regression: exercise the actual About action twice, including
                # closing the dialog between attempts, in the frozen EXE.
                about_button = window.findChild(QPushButton, 'about_button')
                if about_button is None:
                    raise RuntimeError('About button missing from main window.')
                about_button.click()
                about_dialog = window.findChild(QDialog, 'plagues_about_dialog')
                if about_dialog is None or not about_dialog.isVisible():
                    raise RuntimeError('About button failed to open its dialog.')
                if about_dialog.findChild(QLabel, 'about_logo').pixmap().isNull():
                    raise RuntimeError('About dialog logo did not load.')
                about_dialog.close()
                about_button.click()
                if not about_dialog.isVisible():
                    raise RuntimeError('About dialog did not reopen.')
                about_dialog.close()
                # Regression: the update-check dialog opens without networking
                # or creating a thread. Auto-checks must be off by default.
                update_button = window.findChild(QPushButton, 'updates_button')
                if update_button is None:
                    raise RuntimeError('Check for updates button missing.')
                update_button.click()
                update_dialog = window.findChild(QDialog, 'pvs_updates_dialog')
                if update_dialog is None or not update_dialog.isVisible():
                    raise RuntimeError('Updates dialog failed to open.')
                if update_dialog.auto.isChecked() or update_dialog.is_checking:
                    raise RuntimeError('Updates should be opt-in and idle by default.')
                if not update_dialog.findChild(QPushButton, 'updates_check_now'):
                    raise RuntimeError('Manual update button missing.')
                update_dialog.close()
                # Regression: help is searchable, can render a topic, and the
                # About dialog includes diagnostics without importing torch.
                model_manager = window.model_manager
                if model_manager.model.count() != 6:
                    raise RuntimeError('Model Manager model catalogue missing.')
                if model_manager.is_busy:
                    raise RuntimeError('Model Manager started a download during initialization.')
                lab = window.engine_lab
                if lab is None or lab.engine.count() != 3:
                    raise RuntimeError('Voice Engines tab missing or incomplete.')
                if lab.registry.read()['qwen3']['python']:
                    raise RuntimeError('Smoke test should have isolated optional-engine settings.')
                if lab.model.count() != 2:
                    raise RuntimeError('Qwen model selector did not populate.')
                if lab.findChild(QPlainTextEdit, 'engine_diagnostics') is None:
                    raise RuntimeError('Voice-engine live diagnostics pane missing.')
                if not lab.elapsed_timer.isSingleShot() and lab.elapsed_timer.isActive():
                    raise RuntimeError('Optional engine timer started during initialization.')
                lab.engine.setCurrentIndex(1)
                if lab.model.count() != 1 or lab.language.count() != 5:
                    raise RuntimeError('IndexTTS settings failed to switch.')
                lab.engine.setCurrentIndex(lab.engine.findData('kokoro'))
                if lab.preset_voice.count() != 6 or lab.preset_voice.isHidden() or not lab.voice.isHidden():
                    raise RuntimeError('Kokoro preset/reference controls failed to switch.')
                lab.preset_voice.setCurrentIndex(lab.preset_voice.findData('bf_emma'))
                if lab.language.currentData() != 'English (UK)' or lab.device.currentData() != 'auto':
                    raise RuntimeError('Kokoro voice accent or compute configuration is incorrect.')
                if (lab.device.findData('directml') >= 0) != (sys.platform == 'win32') or lab.device.findData('cuda') >= 0:
                    raise RuntimeError('Kokoro compute choices do not match this platform.')
                if not lab.ref_text.isHidden() or lab.compare.isEnabled():
                    raise RuntimeError('Kokoro must not offer reference cloning or cloned-voice comparison.')
                lab.engine.setCurrentIndex(0)
                if lab.voice.isHidden() or not lab.preset_voice.isHidden():
                    raise RuntimeError('Cloning reference controls failed to return after Kokoro.')
                lab.character.setEditText('Smoke Test Character')
                lab.save_profile()
                if 'Smoke Test Character' not in lab.profiles.read():
                    raise RuntimeError('Voice character profile was not saved.')
                if not (Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'optional_engine_runner.py').is_file():
                    raise RuntimeError('Optional subprocess runner missing from frozen package.')
                help_center = window.findChild(type(window.help_center), 'help_center')
                if help_center is None:
                    raise RuntimeError('New Help center missing.')
                help_logo = help_center.findChild(QLabel, 'help_logo')
                if help_logo is None or help_logo.pixmap().isNull():
                    raise RuntimeError('Help logo missing from frozen package.')
                help_search = help_center.findChild(QLineEdit)
                if help_search is None:
                    raise RuntimeError('Help search field missing.')
                help_search.setText('Bethesda')
                if help_center.topic_list.count() < 1:
                    raise RuntimeError('Help topic filtering failed.')
                help_search.clear()
                if help_center.topic_list.count() < 6:
                    raise RuntimeError('Help topic list incomplete.')
                # Run this in the frozen application as well as the source GUI:
                # controls existing alone do not establish exact preview/copy.
                _check_export_script_preview(window.export_browser,
                                             Path(tmp) / 'script-preview-acceptance')
                about_button.click()
                if about_dialog.findChild(QTabWidget, 'about_tabs') is None:
                    raise RuntimeError('About credits and diagnostics tabs missing.')
                if not about_dialog.isVisible():
                    raise RuntimeError('About dialog failed its third open.')
                about_dialog.close()
                QTimer.singleShot(400, app.quit)
                if app.exec() != 0:
                    raise RuntimeError('Qt application event loop failed.')
                window.player.stop()
                window.deleteLater()
            finally:
                app_module.QSettings = original_settings
                app_module.QMediaPlayer = original_player
                app_module.QAudioOutput = original_audio_output
                if old is None: os.environ.pop('PLAGUES_VOICE_STUDIO_030_HOME', None)
                else: os.environ['PLAGUES_VOICE_STUDIO_030_HOME'] = old
        report["status"] = "passed"
    except BaseException:
        report["errors"].append(traceback.format_exc())
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1
