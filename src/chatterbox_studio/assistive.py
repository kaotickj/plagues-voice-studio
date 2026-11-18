"""Phrase-based assistive speech, with explicit sending to a temporary microphone."""
import json
import time
from pathlib import Path
from types import SimpleNamespace
from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, QUrl
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QFormLayout,
    QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QComboBox, QCheckBox)
from .speak_as import SpeakAsDialog
from . import assistive_route as route


class AssistiveDialog(SpeakAsDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Plague’s Voice Studio — Assistive speech')
        self.setMinimumWidth(600)
        self.started_at = None
        self.session_route = QProcess(self)
        self.sender = QProcess(self)
        self.preset_process = QProcess(self)
        self.preset_process.finished.connect(self._preset_finished)
        self.preset_process.errorOccurred.connect(self._preset_error)
        self.session_route.finished.connect(self._route_ended)
        self.session_route.errorOccurred.connect(lambda _: self.route_status.setText('Microphone could not start. Check PipeWire.'))
        self.sender.finished.connect(self._sent)
        self.sender.errorOccurred.connect(lambda _: self.status.setText('Sending failed. Check the virtual microphone.'))
        self.route_timer = QTimer(self)
        self.route_timer.setSingleShot(True)
        self.route_timer.timeout.connect(self._route_check)
        self.preset_watchdog = QTimer(self)
        self.preset_watchdog.setSingleShot(True)
        self.preset_watchdog.timeout.connect(self.stop)
        self._preset_stdout = bytearray()
        self.preset_process.readyReadStandardOutput.connect(self._preset_read)
        self.preset_process.readyReadStandardError.connect(lambda: self.preset_process.readAllStandardError())
        # Keep existing runtime controls behind one disclosure. No settings writes.
        old = self.layout()
        old.itemAt(0).widget().hide()
        advanced = QWidget(self)
        advanced.setLayout(old)
        layout = QVBoxLayout(self)
        intro = QLabel('Type a phrase or record up to 20 seconds. Prepare, review, then send.\nProcessing stays on this computer. Speech conversion is phrase-based, not live.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = self.main_form = QFormLayout()
        layout.addLayout(form)
        self.input_kind = QComboBox()
        self.input_kind.addItems(['Type a phrase', 'Record a phrase'])
        form.addRow('Input', self.input_kind)
        self.tts_kind = QComboBox()
        self.tts_kind.addItems(['Quick preset voice — CPU', 'Saved voice — IndexTTS'])
        form.addRow('Typed / corrected speech', self.tts_kind)
        self.preset = QComboBox()
        for name, code in [('Heart (US)', 'af_heart'), ('Michael (US)', 'am_michael'), ('Bella (US)', 'af_bella'), ('Fenrir (US)', 'am_fenrir'), ('Emma (UK)', 'bf_emma'), ('George (UK)', 'bm_george')]:
            self.preset.addItem(name, code)
        form.addRow('Quick voice', self.preset)
        for label, widget in [('Saved voice', self.voices), ('Recording method', self.mode), ('Saved voice / conversion device', self.device)]:
            self._remove(old, widget)
            form.addRow(label, widget)
            widget.show()
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText('Type what you want to say, or review and correct recognized words here.')
        self.text.setAccessibleName('Words to speak')
        self.text.setMaximumHeight(150)
        layout.addWidget(self.text)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.prepare = QPushButton('Prepare speech')
        self.prepare.clicked.connect(self.prepare_text)
        row.addWidget(self.prepare)
        self._remove(old, self.record)
        self.record.pressed.disconnect()
        self.record.released.disconnect()
        self.record.setText('Start recording')
        self.record.clicked.connect(self.toggle_recording)
        row.addWidget(self.record)
        self.record.show()
        self._remove(old, self.recording_countdown)
        layout.addWidget(self.recording_countdown)
        self.recording_countdown.show()
        action = QHBoxLayout()
        layout.addLayout(action)
        self.replay.clicked.disconnect()
        self.replay.setText('Preview on speakers')
        self.replay.clicked.connect(self.preview)
        for widget in (self.replay, self.save, self.cancel):
            self._remove(old, widget)
            action.addWidget(widget)
            widget.show()
        self.cancel.setText('Stop / cancel')
        self.route_button = QPushButton('Enable virtual microphone')
        self.route_button.clicked.connect(self.toggle_route)
        layout.addWidget(self.route_button)
        self.route_status = QLabel('Microphone off. Enable it, then select “Plague’s Voice Microphone” in the receiving app.')
        self.route_status.setWordWrap(True)
        layout.addWidget(self.route_status)
        self.send = QPushButton('Send to microphone')
        self.send.setEnabled(False)
        self.send.clicked.connect(self.send_audio)
        layout.addWidget(self.send)
        self.details = QCheckBox('Show runtime options')
        self.details.toggled.connect(advanced.setVisible)
        layout.addWidget(self.details)
        layout.addWidget(advanced)
        advanced.hide()
        self._remove(old, self.status)
        layout.addWidget(self.status)
        self.status.show()
        self.status.setText('Ready. Nothing is recorded or sent automatically.')
        self.input_kind.currentIndexChanged.connect(self._input_changed)
        self.tts_kind.currentIndexChanged.connect(self._input_changed)
        self._input_changed()
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.prepare_text)
        QShortcut(QKeySequence('Escape'), self, activated=self.stop)

    @staticmethod
    def _remove(layout, widget):
        if isinstance(layout, QFormLayout):
            label = layout.labelForField(widget)
            if label:
                label.hide()
        layout.removeWidget(widget)
        for i in range(layout.count()):
            child = layout.itemAt(i).layout()
            if child:
                AssistiveDialog._remove(child, widget)

    def _input_changed(self):
        spoken = self.input_kind.currentIndex() == 1
        self.record.setVisible(spoken)
        self.recording_countdown.setVisible(spoken)
        self.mode.setEnabled(spoken)
        quick = self.tts_kind.currentIndex() == 0
        self.preset.setEnabled(quick)
        self.main_form.setRowVisible(self.mode, spoken)
        self.main_form.setRowVisible(self.voices, spoken or not quick)
        self.main_form.setRowVisible(self.device, spoken or not quick)

    def _busy(self):
        return bool(self.source or self.warm.busy or self.process.state() != QProcess.ProcessState.NotRunning or self.preset_process.state() != QProcess.ProcessState.NotRunning)

    def _allow_discard(self):
        # Assistive phrases are intentionally temporary; Save WAV remains available.
        return True

    def _idle(self):
        super()._idle()
        if hasattr(self, 'prepare'):
            self.prepare.setEnabled(True)
            self.record.setText('Start recording')
            self.input_kind.setEnabled(True)
            self.tts_kind.setEnabled(True)
            self._input_changed()

    def _clear_result(self):
        self.player.stop()
        self.sender.kill()
        self.last_result = None
        self.replay.setEnabled(False)
        self.save.setEnabled(False)
        self.send.setEnabled(False)
        (Path(self.temp.name) / 'output.wav').unlink(missing_ok=True)
        self.cancelled = False
        self.started_at = time.monotonic()

    def toggle_recording(self):
        if self.source:
            self.finish_recording()
            return
        if self._busy():
            return
        self._clear_result()
        self.start_recording()
        if self.source:
            self.record.setText('Finish recording')
            self.prepare.setEnabled(False)
            self.input_kind.setEnabled(False)
            self.tts_kind.setEnabled(False)

    def _start_index(self):
        # Review before synthesis/send: ASR can change the intended words.
        try:
            words = (Path(self.temp.name) / 'transcript.txt').read_text().strip()
            if not words or len(words) > 2000:
                raise ValueError('No usable words recognized. Type or record again.')
            self.text.setPlainText(words)
            self._idle()
            self.status.setText('Review and correct the recognized words, then choose Prepare speech. Nothing has been sent.')
        except (OSError, ValueError) as exc:
            self._conversion_error(str(exc))

    def prepare_text(self):
        try:
            self._prepare_text()
        except Exception as exc:
            self._conversion_error(str(exc))

    def _prepare_text(self):
        if self._busy():
            return
        words = self.text.toPlainText().strip()
        if not words or len(words) > 2000:
            self.status.setText('Enter between 1 and 2,000 characters.')
            return
        self._clear_result()
        self.prepare.setEnabled(False)
        self.record.setEnabled(False)
        self.input_kind.setEnabled(False)
        self.tts_kind.setEnabled(False)
        from .optional_engines import _isolated_engine_environment, EngineRegistry
        env = QProcessEnvironment()
        for key, value in _isolated_engine_environment().items():
            env.insert(key, value)
        env.insert('HF_HUB_OFFLINE', '1')
        env.insert('TRANSFORMERS_OFFLINE', '1')
        env.insert('PYTHONDONTWRITEBYTECODE', '1')
        if self.launchers.get('gpu_lock'):
            env.insert('PVS_GPU_LOCK', self.launchers['gpu_lock'])
        output = str(Path(self.temp.name) / 'output.wav')
        for control in (self.voices, self.device, self.reference_mode, self.asr_mode, self.preset, *self.index_fields):
            control.setEnabled(False)
        self.status.setText('Preparing speech locally…')
        if self.tts_kind.currentIndex() == 0:
            self.warm.stop()
            config = EngineRegistry(self.parent().storage).read()['kokoro']
            request = dict(engine='kokoro', model_dir=config['model_dir'], text=words,
                           preset_voice=self.preset.currentData(), device='cpu', speed=1.0, output_path=output)
            path = Path(self.temp.name) / 'typed.json'
            path.write_text(json.dumps(request))
            self.pending_metadata = dict(engine='kokoro', workflow='assistive', text=words, voice=self.preset.currentText())
            self._preset_stdout.clear()
            self.preset_process.setProcessEnvironment(env)
            self.preset_process.start(config['python'], ['-B', str(Path(__file__).with_name('assistive_worker.py')), str(path)])
            self.preset_watchdog.start(120000)
        else:
            python, repo, _, _ = [f.text().strip() for f in self.index_fields]
            if not self.voices.currentData():
                self._conversion_error('Choose a saved voice first.')
                return
            req = dict(engine='index25', repo=repo, text=words, voice_path=self.voices.currentData(),
                       output_path=output, device=self.device.currentData(), language='auto', speed=1.0,
                       reference_seconds=self.reference_mode.currentData())
            self._submit_conversion(python, req, env, 300000)

    def _preset_read(self):
        self._preset_stdout.extend(bytes(self.preset_process.readAllStandardOutput()))
        self._preset_stdout = self._preset_stdout[-16384:]

    def _preset_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.preset_watchdog.stop()
            self._conversion_error('Could not start the configured local Kokoro runtime.')

    def _preset_finished(self, code, status):
        self.preset_watchdog.stop()
        self._preset_read()
        if self.cancelled:
            self._idle()
            return
        try:
            result = json.loads(self._preset_stdout.decode().splitlines()[-1])
            if code or not result.get('ok'):
                raise ValueError(result.get('error', 'Speech preparation failed.'))
            self._converted(result)
        except (ValueError, IndexError) as exc:
            self._conversion_error(str(exc))

    def _converted(self, result):
        self.watchdog.stop()
        self._idle()
        if self.cancelled:
            return
        path = Path(result['output_path'])
        if not path.is_file():
            self._conversion_error('Prepared audio is missing.')
            return
        self.last_result = dict(path=path, metadata=dict(self.pending_metadata or {}), saved=False)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.replay.setEnabled(True)
        self.save.setEnabled(True)
        self.send.setEnabled(self.session_route.state() == QProcess.ProcessState.Running)
        elapsed = time.monotonic() - self.started_at if self.started_at else result['seconds']
        self.status.setText(f'Ready in {elapsed:.1f} seconds. Preview or send when ready. Nothing sent yet.')

    def preview(self):
        if self.last_result:
            self.sender.kill()
            self.player.play()

    def toggle_route(self):
        if self.session_route.state() != QProcess.ProcessState.NotRunning:
            self.sender.kill()
            self.session_route.kill()
            return
        try:
            if route.SINK in route.available() or route.SOURCE in route.available():
                self.route_status.setText('A Voice Microphone session already exists. Close that session first.')
                return
        except Exception as exc:
            self.route_status.setText('PipeWire unavailable: ' + str(exc))
            return
        args = route.command()
        self.session_route.start(args[0], args[1:])
        self.route_status.setText('Starting microphone…')
        self.route_timer.start(700)

    def _route_check(self):
        try:
            if self.session_route.state() != QProcess.ProcessState.Running or not route.ready():
                raise RuntimeError('The virtual microphone did not appear.')
            self.route_button.setText('Disable virtual microphone')
            self.route_status.setText('Select “Plague’s Voice Microphone” as the input in your call, game or recording app. Only Send transmits audio.')
            self.send.setEnabled(bool(self.last_result))
        except Exception as exc:
            self.session_route.kill()
            self.route_status.setText(str(exc))

    def _route_ended(self, *_):
        self.sender.kill()
        self.send.setEnabled(False)
        self.route_button.setText('Enable virtual microphone')
        self.route_status.setText('Microphone off. Your default audio devices are unchanged.')

    def send_audio(self):
        if not self.last_result or self.sender.state() != QProcess.ProcessState.NotRunning:
            return
        try:
            if self.session_route.state() != QProcess.ProcessState.Running or not route.ready():
                raise RuntimeError('Enable the virtual microphone first.')
            self.player.stop()
            self.sender.start('pw-play', ['--target', route.SINK, '--properties', '{ node.dont-fallback = true node.dont-reconnect = true }', str(self.last_result['path'])])
            self.status.setText('Sending to Plague’s Voice Microphone…')
        except Exception as exc:
            self.status.setText(str(exc))

    def _sent(self, code, *_):
        if not self.cancelled:
            self.status.setText('Phrase sent.' if code == 0 else 'Sending stopped or failed.')

    def stop(self):
        if hasattr(self, 'sender'):
            self.sender.kill()
            self.preset_process.kill()
            self.preset_watchdog.stop()
        super().stop()
        self.status.setText('Stopped. Nothing is being recorded, prepared or sent.')

    def done(self, result):
        self.stop()
        self.session_route.kill()
        self.session_route.waitForFinished(1500)
        self.sender.waitForFinished(1500)
        self.preset_process.waitForFinished(1500)
        super().done(result)


def main():
    from plagued_ai import root
    from .paths import canonical_data_dir
    from .voices import VoiceLibrary
    app = QApplication([])
    parent = QWidget()
    parent.storage = canonical_data_dir()
    parent.voices = VoiceLibrary(root(), read_only=True)
    parent.voice = SimpleNamespace(currentData=lambda: '')
    parent.settings = SimpleNamespace(value=lambda key, default='': default)
    dialog = AssistiveDialog(parent)
    dialog.exec()


if __name__ == '__main__':
    main()
