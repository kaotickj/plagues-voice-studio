"""Smoke test actual Qt window construction, without invoking speech synthesis.

Run on Windows via PlaguesVoiceStudio030Experimental.exe --ui-self-test <report.json>.
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


def run(report_path: Path | None = None) -> int:
    report = {"version": __version__, "test": "Qt main-window and About dialog lifecycle", "status": "failed", "errors": []}
    try:
        from PyQt6.QtCore import QTimer, QSettings, Qt
        from PyQt6.QtWidgets import QApplication, QPushButton, QDialog, QLabel, QLineEdit, QListWidget, QTabWidget, QPlainTextEdit
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
            try:
                window = MainWindow()
                if window.windowIcon().isNull():
                    raise RuntimeError('Application icon was not packaged.')
                window.show()
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
                # Regression: help is searchable, can render a topic, and the
                # About dialog includes diagnostics without importing torch.
                model_manager = window.model_manager
                if model_manager.model.count() != 6:
                    raise RuntimeError('Model Manager model catalogue missing.')
                if model_manager.is_busy:
                    raise RuntimeError('Model Manager started a download during initialization.')
                lab = window.engine_lab
                if lab is None or lab.engine.count() != 2:
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
                lab.engine.setCurrentIndex(0)
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
                # Release-candidate regression: exercise JSON transcript export
                # and the ACTUAL packaged Export Library preview/copy widgets.
                # This uses tiny synthetic WAV files, without loading TTS weights
                # or touching the user's existing recordings.
                from .export_metadata import write_export_metadata
                from wave import open as open_wave
                sample_dir = Path(tmp) / 'script-preview-acceptance'
                sample_dir.mkdir()
                script = '[narration] The Charles River is quiet.\n\n[whispering] Not for long, sweetheart.'
                audio_path = sample_dir / 'test_story.wav'
                with open_wave(str(audio_path), 'wb') as output_wave:
                    output_wave.setnchannels(1)
                    output_wave.setsampwidth(2)
                    output_wave.setframerate(8000)
                    output_wave.writeframes(b'\x00\x00' * 800)
                write_export_metadata(audio_path, {
                    'engine': 'chatterbox', 'model': 'turbo', 'text': script,
                })
                browser = window.export_browser
                browser.add_root(sample_dir)
                matches = browser.list.findItems(audio_path.name, Qt.MatchFlag.MatchExactly, 0)
                if len(matches) != 1:
                    raise RuntimeError('Generated Chatterbox WAV missing from Export Library.')
                browser.list.setCurrentItem(matches[0])
                if browser.script_preview.toPlainText() != script:
                    raise RuntimeError('Export Library failed to display the exact saved script.')
                if not browser.script_preview.isReadOnly() or not browser.copy_script.isEnabled():
                    raise RuntimeError('Export script preview must be read-only and copyable.')
                browser.copy_script.click()
                if QApplication.clipboard().text() != script:
                    raise RuntimeError('Copy script did not preserve the original tags and whitespace.')
                legacy_path = sample_dir / 'older_without_script.wav'
                legacy_path.write_bytes(b'not a playable recording; metadata-missing regression only')
                browser.refresh()
                matches = browser.list.findItems(legacy_path.name, Qt.MatchFlag.MatchExactly, 0)
                if len(matches) != 1:
                    raise RuntimeError('Legacy audio not listed in Export Library.')
                browser.list.setCurrentItem(matches[0])
                if browser.script_preview.toPlainText() or browser.copy_script.isEnabled():
                    raise RuntimeError('Legacy recording reused a different audio file script.')
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
                if old is None: os.environ.pop('PLAGUES_VOICE_STUDIO_030_HOME', None)
                else: os.environ['PLAGUES_VOICE_STUDIO_030_HOME'] = old
        report["status"] = "passed"
    except BaseException:
        report["errors"].append(traceback.format_exc())
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1
