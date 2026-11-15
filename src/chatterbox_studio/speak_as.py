"""Explicit push-to-talk conversion, playback, and user-directed permanent export."""
from pathlib import Path
import sys
import os
import json
import math
import tempfile
import wave
from PyQt6.QtCore import QBuffer, QEvent, QIODevice, QProcess, QProcessEnvironment, QTimer, Qt, QUrl
from PyQt6.QtMultimedia import QAudioFormat, QAudioSource, QAudioOutput, QMediaDevices, QMediaPlayer
from PyQt6.QtWidgets import QComboBox, QDialog, QFileDialog, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout
from .model_downloads import MODELS, installed_model_directory
from .paths import bundled_models_dir


_CONVERSION_METADATA_KEYS = frozenset({
    'f0_condition', 'auto_f0_adjust', 'length_adjust', 'semi_tone_shift',
    'seed_diffusion_steps', 'seed_random_seed', 'inference_cfg_rate', 'reference_duration',
    'output_sample_rate', 'output_peak', 'output_gain_db',
})


class SpeakAsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Speak as… — local voice conversion')
        self.setMinimumWidth(520)
        from .warm_client import WarmClient
        self.warm = WarmClient(self)
        self.warm.completed.connect(self._converted)
        self.warm.failed.connect(self._conversion_error)
        self.warm.released.connect(self._released)
        self.warm.progress.connect(self._progress)
        config = os.environ.get('PVS_SPEAK_AS_CONFIG')
        if not config:
            saved_config = Path(parent.storage) / 'speak_as.json'
            config = str(saved_config) if saved_config.is_file() else None
        self.config_error = ''
        try:
            self.launchers = json.loads(Path(config).read_text()) if config else {}
            if not isinstance(self.launchers, dict) or any(not isinstance(v, str) for v in self.launchers.values()):
                raise ValueError('Launcher paths must be strings.')
        except (OSError, ValueError) as exc:
            self.launchers = {}
            self.config_error = str(exc)
        self.temp = tempfile.TemporaryDirectory(prefix='studio-speak-as-')
        self.last_result = None
        self.pending_metadata = None
        self.source = None
        self.buffer = None
        self.cancelled = False
        self.model_ready = False
        self.stage_timeout_ms = 120000
        self.process = QProcess(self)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.finish_recording)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(100)
        self.countdown_timer.timeout.connect(self._update_recording_countdown)
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self._timeout)
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.player.errorOccurred.connect(lambda *args: self.status.setText('Playback failed: ' + self.player.errorString()))
        layout = QVBoxLayout(self)
        intro = QLabel('Hold to record, then release to convert and play. Maximum 20 seconds.\nSave WAV keeps the converted recording permanently; headphones recommended.\nSeed-VC V1 aims to keep relative inflection while moving your register toward the target voice; a perfect match is not guaranteed.\nChatterbox converts your audio directly, but cadence and inflections may change.\nIndexTTS is alternate transcription + re-synthesis and may change words and timing.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        controls = QFormLayout()
        layout.addLayout(controls)
        self.voices = QComboBox()
        for voice in parent.voices.list_voices():
            path = parent.voices.resolve(voice['id'])
            if path and Path(path).is_file():
                self.voices.addItem(voice['name'], str(path))
        selected = parent.voices.resolve(parent.voice.currentData() or '')
        if selected:
            self.voices.setCurrentIndex(max(0, self.voices.findData(str(selected))))
        controls.addRow('Reference voice', self.voices)
        self.mode = QComboBox()
        self.mode.addItem('Chatterbox — direct conversion', 'chatterbox')
        self.mode.addItem('IndexTTS — alternate transcription + re-synthesis', 'index25')
        self.mode.addItem('Seed-VC V1 — target register (44.1 kHz)', 'seed_v1')
        controls.addRow('Engine', self.mode)
        self.asr_mode = QComboBox()
        self.asr_mode.addItem('Transcription: configured Whisper (multilingual)', 'configured')
        if self.launchers.get('fast_asr_executable') and self.launchers.get('fast_asr_model'):
            self.asr_mode.addItem('Transcription: fast English (small.en; may change words)', 'fast_en')
        self.asr_label = QLabel('Transcription')
        controls.addRow(self.asr_label, self.asr_mode)
        self.reference_mode = QComboBox()
        self.reference_mode.addItem('Fast reference (5 seconds)', 5)
        self.reference_mode.addItem('Full reference (original)', 0)
        self.reference_mode.setToolTip('Uses up to 5 seconds of the speaker reference for diffusion conditioning. Full speaker identity and style embeddings, source recording and emotion guidance remain unchanged.')
        self.reference_label = QLabel('Voice reference detail')
        controls.addRow(self.reference_label, self.reference_mode)
        from .optional_engines import EngineRegistry
        index = EngineRegistry(parent.storage).read()['index25']
        self.index_fields = []
        self.index_labels = []
        for label, value in [('IndexTTS Python', self.launchers.get('index_python', index['python'])),
                             ('IndexTTS repository', self.launchers.get('index_repo', index['repo'])),
                             ('whisper-cli executable', self.launchers.get('whisper_executable', '')),
                             ('Whisper GGML model', self.launchers.get('whisper_model', ''))]:
            field = QLineEdit(value)
            field.setPlaceholderText(label)
            field.setToolTip(label)
            field.textEdited.connect(lambda: self.warm.stop())
            field_label = QLabel(label)
            controls.addRow(field_label, field)
            self.index_labels.append(field_label)
            self.index_fields.append(field)
        self.normal_asr = tuple(field.text() for field in self.index_fields[2:])
        self.asr_mode.currentIndexChanged.connect(self._asr_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.mode.currentIndexChanged.connect(lambda: self.warm.stop())
        self.phase = 'conversion'
        self.device = QComboBox()
        self.device.addItem('CPU (slower)', 'cpu')
        self.device.addItem('GPU (CUDA / ROCm)', 'cuda')
        controls.addRow('Synthesis device', self.device)
        self.device.currentIndexChanged.connect(lambda: self.warm.stop())
        self.runtime_label = QLabel('Chatterbox runtime')
        self.runtime_path = QLineEdit()
        self.runtime_path.setReadOnly(True)
        controls.addRow(self.runtime_label, self.runtime_path)
        self.index_fields[0].textChanged.connect(lambda value: self.runtime_path.setText(value)
            if self.mode.currentData() == 'index25' else None)
        self.runtime_note = QLabel()
        self.runtime_note.setWordWrap(True)
        layout.addWidget(self.runtime_note)
        self.transcript = QLineEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText('Appears after local transcription')
        self.transcript_label = QLabel('Recognized words')
        controls.addRow(self.transcript_label, self.transcript)
        self.replay = QPushButton('Replay last result')
        self.replay.setAutoDefault(False)
        self.replay.setEnabled(False)
        self.replay.clicked.connect(self.player.play)
        layout.addWidget(self.replay)
        self.save = QPushButton('Save WAV…')
        self.save.setAutoDefault(False)
        self.save.setEnabled(False)
        self.save.clicked.connect(self.save_recording)
        layout.addWidget(self.save)
        self.record = QPushButton('Hold to speak')
        self.record.setAutoDefault(False)
        self.record.pressed.connect(self.start_recording)
        self.record.released.connect(self.finish_recording)
        layout.addWidget(self.record)
        self.recording_countdown = QLabel('Recording time remaining: 20.0 s')
        self.recording_countdown.setObjectName('recordingCountdown')
        self.recording_countdown.setStyleSheet('font-size: 14pt; font-weight: bold;')
        self.recording_countdown.setAccessibleName('Recording time remaining')
        layout.addWidget(self.recording_countdown)
        self.cancel = QPushButton('Cancel / release model / stop playback')
        self.cancel.setAutoDefault(False)
        self.cancel.clicked.connect(self.stop)
        layout.addWidget(self.cancel)
        self.status = QLabel('Ready. The microphone starts only while you hold the button.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.weights = installed_model_directory(parent.storage, MODELS['english']) or bundled_models_dir() / 'english'
        self.python = str(self.launchers.get('chatterbox_python') or parent.settings.value('rocm/python', '') or sys.executable)
        self.overlay = str(parent.settings.value('rocm/overlay', '') or '')
        self.runtime_path.setText(self.python)
        # Prefer configured Seed direct conversion without changing existing item indices.
        if self.asr_mode.findData('fast_en') >= 0:
            fast_exe = self.launchers['fast_asr_executable']
            fast_model = self.launchers['fast_asr_model']
            if Path(fast_exe).is_file() and Path(fast_model).is_dir():
                self.asr_mode.setCurrentIndex(self.asr_mode.findData('fast_en'))
        if self._seed_configured():
            self.mode.setCurrentIndex(self.mode.findData('seed_v1'))
        elif not self._chatterbox_configured() and self._index_configured():
            self.mode.setCurrentIndex(self.mode.findData('index25'))
        self._mode_changed()
        if not self.voices.count():
            self.status.setText('Import a reference voice first. No downloads are started here.')
        elif not self.record.isEnabled():
            self.status.setText('Configure a local Seed-VC V1 runtime, install English Chatterbox weights and its external Python runtime, or select a configured IndexTTS engine. No downloads are started here.')

        if self.config_error:
            self.status.setText('Could not read Speak As runtime configuration: ' + self.config_error)

    def _chatterbox_configured(self):
        return ((self.weights / 's3gen.safetensors').is_file()
                and Path(self.python).is_file() and os.access(self.python, os.X_OK)
                and not (getattr(sys, 'frozen', False) and self.python == sys.executable))

    def _index_configured(self):
        python, repo, whisper, model = [f.text().strip() for f in self.index_fields]
        return (Path(python).is_file() and Path(repo, 'indextts/infer_v2_5.py').is_file()
                and Path(repo, 'checkpoints/config.yaml').is_file()
                and Path(whisper).is_file()
                and (Path(model).is_dir() if self.asr_mode.currentData() == 'fast_en' else Path(model).is_file()))

    def _seed_config_errors(self):
        errors = []
        python = self.launchers.get('seed_python', '').strip()
        repo = self.launchers.get('seed_repo', '').strip()
        cache = self.launchers.get('seed_cache', '').strip()
        manifest = self.launchers.get('seed_manifest', '').strip()
        if not python or not Path(python).is_file() or not os.access(python, os.X_OK):
            errors.append('seed_python must be an executable Python runtime')
        if not repo or not Path(repo, 'inference.py').is_file():
            errors.append('seed_repo must contain inference.py')
        if not cache or not Path(cache).is_dir():
            errors.append('seed_cache must be an existing local model directory')
        try:
            if not manifest or not isinstance(json.loads(Path(manifest).read_text(encoding='utf-8')), list):
                raise ValueError('Expected a JSON repository list')
        except (OSError, UnicodeError, ValueError):
            errors.append('seed_manifest must be an existing readable JSON manifest')
        return errors

    def _seed_configured(self):
        return not self._seed_config_errors()

    def _mode_changed(self):
        engine = self.mode.currentData()
        is_index = engine == 'index25'
        for widget in (self.asr_mode, self.asr_label, self.reference_mode, self.reference_label,
                       self.transcript, self.transcript_label, *self.index_labels):
            widget.setVisible(is_index)
        fast = self.asr_mode.currentData() == 'fast_en'
        self.index_labels[2].setText('Fast English executable' if fast else 'whisper-cli executable')
        self.index_labels[3].setText('Fast English model folder' if fast else 'Whisper GGML model')
        for field in self.index_fields:
            field.setVisible(is_index)
        for field in self.index_fields[2:]:
            field.setEnabled(self.asr_mode.currentData() != 'fast_en')
        if hasattr(self, 'weights'):
            self.runtime_label.setText({'chatterbox': 'Chatterbox runtime',
                'index25': 'IndexTTS runtime', 'seed_v1': 'Seed-VC V1 runtime'}[engine])
            self.runtime_path.setText(self.launchers.get('seed_python', '') if engine == 'seed_v1'
                else self.index_fields[0].text() if is_index else self.python)
            self.runtime_path.setPlaceholderText('Not configured')
            note = ('Local runtimes only. Cold model loading and the first use of a new audio length '
                    'can take several minutes, even with a warm model.')
            seed_errors = self._seed_config_errors() if engine == 'seed_v1' else []
            if engine == 'seed_v1':
                note += ('\nFixed target-register profile: F0 conditioning and automatic F0 adjustment on; '
                         'length 1.0, semitone shift 0, 30 diffusion steps, CFG 0.7.')
                if seed_errors:
                    note += '\nSeed-VC V1 unavailable: ' + '; '.join(seed_errors) + '. No microphone opened.'
            self.runtime_note.setText(note)
            self.record.setEnabled(bool(self.voices.count()) and
                (is_index or (engine == 'seed_v1' and not seed_errors)
                 or (engine == 'chatterbox' and self._chatterbox_configured())))

    def _asr_changed(self):
        self.warm.stop()
        if self.asr_mode.currentData() == 'fast_en':
            self.normal_asr = tuple(field.text() for field in self.index_fields[2:])
            values = (self.launchers['fast_asr_executable'], self.launchers['fast_asr_model'])
        else:
            values = self.normal_asr
        for field, value in zip(self.index_fields[2:], values):
            field.setText(value)
        self._mode_changed()

    def start_recording(self):
        if self.source or self.warm.busy or self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self.recording_countdown.setText('Recording time remaining: 20.0 s')
        if self.mode.currentData() == 'seed_v1':
            errors = self._seed_config_errors()
            if errors:
                self._mode_changed()
                self.status.setText('Seed-VC V1 unavailable: ' + '; '.join(errors) + '. No microphone opened.')
                return
        if self.mode.currentData() == 'chatterbox' and not self._chatterbox_configured():
            self.status.setText('Direct conversion needs an executable Chatterbox Python runtime and English S3Gen weights. No microphone opened.')
            return
        if self.mode.currentData() == 'index25' and not self._index_configured():
            self.status.setText('IndexTTS needs its working Python runtime, repository/checkpoints, and selected local transcription executable/model. No microphone opened.')
            return
        if self.last_result and not self.last_result['saved']:
            if self._allow_discard():
                # The physical press may have ended inside the modal prompt.
                # Never start capture until the user makes a fresh press.
                self.last_result = None
                self.save.setEnabled(False)
                self.replay.setEnabled(False)
                self.player.stop()
                self.player.setSource(QUrl())
                self.status.setText('Ready. Hold to speak again to start a new recording.')
            return
        self.last_result = None
        self.save.setEnabled(False)
        self.player.stop()
        self.player.setSource(QUrl())
        self.replay.setEnabled(False)
        self.transcript.clear()
        self.cancelled = False
        self.model_ready = False
        device = QMediaDevices.defaultAudioInput()
        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if device.isNull() or not device.isFormatSupported(fmt):
            self.status.setText('No microphone supporting 16 kHz mono PCM is available. Check system input and permissions.')
            return
        self.buffer = QBuffer(self)
        if not self.buffer.open(QIODevice.OpenModeFlag.ReadWrite):
            self._end_capture()
            self.status.setText('Could not create the microphone recording buffer.')
            return
        try:
            self.source = QAudioSource(device, fmt, self)
        except Exception as exc:
            self._end_capture()
            self.status.setText('Could not initialize microphone: ' + str(exc))
            return
        self.source.stateChanged.connect(self._audio_state)
        self.warm.hold_idle()
        self.mode.setEnabled(False)
        self.reference_mode.setEnabled(False)
        self.asr_mode.setEnabled(False)
        for field in self.index_fields:
            field.setEnabled(False)
        self.voices.setEnabled(False)
        self.device.setEnabled(False)
        self.status.setText('Recording… release to convert (20-second limit).')
        try:
            self.source.start(self.buffer)
        except Exception as exc:
            self.stop()
            self.status.setText('Could not start microphone: ' + str(exc))
            return
        if self.source:
            self.timer.start(20000)
            self._update_recording_countdown()
            self.countdown_timer.start()

    def _update_recording_countdown(self):
        # Read the capture deadline, rather than counting refresh callbacks.
        # Round up so zero is shown only when the recording limit is reached.
        remaining_ms = max(0, self.timer.remainingTime())
        remaining = math.ceil(remaining_ms / 100) / 10
        self.recording_countdown.setText(f'Recording time remaining: {remaining:.1f} s')

    def _audio_state(self, state):
        from PyQt6.QtMultimedia import QAudio
        if self.source and self.source.error() != QAudio.Error.NoError:
            self.stop()
            self.status.setText('Microphone failed. Check input device and system permissions.')

    def _end_capture(self):
        if self.source:
            self._update_recording_countdown()
        self.countdown_timer.stop()
        self.timer.stop()
        source, self.source = self.source, None
        if source:
            source.stop()
            source.deleteLater()
        if self.buffer:
            data = bytes(self.buffer.data())[:16000 * 2 * 20]
            data = data[:len(data) - len(data) % 2]  # Discard an incomplete PCM frame.
            self.buffer.close()
            self.buffer.deleteLater()
            self.buffer = None
            return data
        return b''

    def finish_recording(self):
        if not self.source:
            return
        data = self._end_capture()
        if len(data) < 8000:
            self.status.setText('Recording too short. Hold for at least a quarter second.')
            self._idle()
            return
        from array import array
        if max(abs(v) for v in array('h', data)) < 4:
            self.status.setText('Recording is silent. Check the microphone input.')
            self._idle()
            return
        root = Path(self.temp.name)
        try:
            (root / 'output.wav').unlink(missing_ok=True)
            (root / 'transcript.txt').unlink(missing_ok=True)
            with wave.open(str(root / 'input.wav'), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(data)
        except (OSError, wave.Error) as exc:
            self.status.setText('Could not save the recording: ' + str(exc))
            self._idle()
            return
        self.record.setEnabled(False)
        self.status.setText('Converting locally… Cancel stops the conversion process.')
        from .optional_engines import _isolated_engine_environment
        env = QProcessEnvironment()
        for key, value in _isolated_engine_environment().items():
            env.insert(key, value)
        env.insert('HF_HUB_OFFLINE', '1')
        env.insert('TRANSFORMERS_OFFLINE', '1')
        if self.mode.currentData() == 'chatterbox':
            env.insert('PYTHONPATH', self.overlay)
        env.insert('OMP_NUM_THREADS', '2')
        env.insert('NUMBA_CACHE_DIR', str(root / 'numba'))
        if self.launchers.get('gpu_lock'):
            env.insert('PVS_GPU_LOCK', self.launchers['gpu_lock'])
        self.process.setProcessEnvironment(env)
        if self.mode.currentData() == 'index25':
            self.phase = 'transcription'
            python, repo, whisper, model = [f.text().strip() for f in self.index_fields]
            self.status.setText('Transcribing locally on CPU…')
            self.process.start(whisper, ['-m', model, '-f', str(root / 'input.wav'),
                '-otxt', '-of', str(root / 'transcript'), '-l', 'auto', '-ng', '-t', '4'])
            self._arm_timeout(120000)
            return
        self.phase = 'conversion'
        if self.mode.currentData() == 'seed_v1':
            request = dict(engine='seed_v1', source=str(root / 'input.wav'),
                reference=self.voices.currentData(), repo=self.launchers['seed_repo'].strip(),
                cache=self.launchers['seed_cache'].strip(), manifest=self.launchers['seed_manifest'].strip(),
                output_path=str(root / 'output.wav'), device=self.device.currentData(),
                f0_condition=True, auto_f0_adjust=True, length_adjust=1.0, semi_tone_shift=0,
                diffusion_steps=30, inference_cfg_rate=0.7)
            self.status.setText('Seed-VC V1 target-register conversion… Cold loading can take several minutes. Cancel stops conversion.')
            self._submit_conversion(self.launchers['seed_python'].strip(), request, env, 600000)
            return
        request = dict(engine='chatterbox', source=str(root / 'input.wav'),
            reference=self.voices.currentData(), weights=str(self.weights),
            output_path=str(root / 'output.wav'), device=self.device.currentData())
        self._submit_conversion(self.python, request, env, 120000)

    def _idle(self):
        self.warm.resume_idle()
        self.mode.setEnabled(True)
        self.reference_mode.setEnabled(True)
        self.asr_mode.setEnabled(True)
        for field in self.index_fields:
            field.setEnabled(True)
        self._mode_changed()
        self.voices.setEnabled(True)
        self.device.setEnabled(True)

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.watchdog.stop()
            if self.cancelled:
                self._idle()
                return
            self.status.setText('Could not start local transcription: ' + self.process.errorString())
            self._idle()

    def _finished(self, code, status):
        self.watchdog.stop()
        details = bytes(self.process.readAllStandardError()).decode(errors='replace')
        timing = bytes(self.process.readAllStandardOutput()).decode(errors='replace')
        if self.cancelled:
            self._idle()
            return
        if self.phase == "transcription" and code == 0 and status == QProcess.ExitStatus.NormalExit:
            self._start_index()
            return
        self._idle()
        if self.cancelled:
            return
        output = Path(self.temp.name) / 'output.wav'
        if code or status != QProcess.ExitStatus.NormalExit or not output.is_file():
            self.status.setText('Conversion failed: ' + details[-1000:])
            return
        self.status.setText(timing[-500:] or 'Conversion complete.')
        self.player.setSource(QUrl.fromLocalFile(str(output)))
        self.player.play()

    def _start_index(self):
        root = Path(self.temp.name)
        transcript_path = root / 'transcript.txt'
        try:
            text = transcript_path.read_text(encoding='utf-8').strip() if transcript_path.is_file() else ''
        except (OSError, UnicodeError) as exc:
            self.status.setText('Could not read local transcription: ' + str(exc))
            self._idle()
            return
        self.transcript.setText(text)
        if not text or len(text) > 2000:
            self.status.setText('Transcription was empty or too long; no speech generated.')
            self._idle()
            return
        python, repo, _, _ = [f.text().strip() for f in self.index_fields]
        request = dict(repo=repo, text=text, voice_path=self.voices.currentData(),
            emotion_audio_path=str(root / 'input.wav'), output_path=str(root / 'output.wav'),
            device=self.device.currentData(), language='auto', speed=1.0,
            reference_seconds=self.reference_mode.currentData())
        try:
            (root / 'index.json').write_text(json.dumps(request), encoding='utf-8')
        except OSError as exc:
            self._conversion_error('Could not prepare IndexTTS request: ' + str(exc))
            return
        self.phase = 'conversion'
        self.status.setText('IndexTTS emotion synthesis… Transcript: ' + text)
        request['engine'] = 'index25'
        self._submit_conversion(python, request, self.process.processEnvironment(), 300000)

    def _submit_conversion(self, python, request, environment, timeout):
        self.pending_metadata = dict(engine=request['engine'], workflow='speak_as',
            voice=self.voices.currentText(),
            device=request.get('device'), text=request.get('text', ''),
            transcription=request.get('text'),
            conversion='direct_audio' if request['engine'] in ('chatterbox', 'seed_v1') else 'transcription_resynthesis')
        try:
            self.warm.submit(python, request, environment)
            self._arm_timeout(timeout)
        except Exception as exc:
            self._conversion_error(str(exc))

    def _converted(self, result):
        self.watchdog.stop()
        self._idle()
        if self.cancelled:
            return
        output = Path(result['output_path'])
        if not output.is_file():
            self._conversion_error('Converted WAV is missing.')
            return
        metadata = dict(self.pending_metadata or dict(engine=self.mode.currentData(),
            workflow='speak_as', voice=self.voices.currentText(), text='', transcription=None))
        conversion_metadata = result.get('conversion_metadata')
        if isinstance(conversion_metadata, dict):
            for key in _CONVERSION_METADATA_KEYS:
                value = conversion_metadata.get(key)
                if isinstance(value, (bool, int)) or isinstance(value, float) and math.isfinite(value):
                    metadata[key] = value
        self.last_result = dict(path=output, metadata=metadata, saved=False)
        self.save.setEnabled(True)
        self.model_ready = True
        state = 'Warm model' if result.get('warm') else 'Model loaded'
        self.status.setText(f"{state}; {result['seconds']:.2f}s. Model stays ready for 60 seconds; Cancel releases it.")
        if result.get('reference_note'):
            self.status.setText(self.status.text() + '\n' + result['reference_note'])
        if isinstance(result.get('conversion_note'), str) and result['conversion_note'].strip():
            self.status.setText(self.status.text() + '\n' + result['conversion_note'].strip()[:500])
        self.status.setText(self.status.text() + '\nUnsaved recording. Use Save WAV to keep it.')
        self.player.setSource(QUrl.fromLocalFile(result['output_path']))
        self.player.play()
        self.replay.setEnabled(True)

    def save_recording(self):
        if not self.last_result:
            return False
        from datetime import datetime
        from .pvs_library import new_export_directory, safe_voice_name
        from .speak_as_export import save_recording
        result = self.last_result
        folder = new_export_directory(self.parent().storage)
        name = safe_voice_name(result['metadata'].get('voice', 'voice'))
        suggested = folder / f'{name}_speak_as_{datetime.now():%Y%m%d-%H%M%S}.wav'
        filename, _ = QFileDialog.getSaveFileName(self, 'Save converted recording', str(suggested),
            'WAV (*.wav)', options=QFileDialog.Option.DontConfirmOverwrite)
        if not filename:
            return False
        target = Path(filename)
        if target.suffix.lower() != '.wav':
            target = Path(str(target) + '.wav')
        try:
            if target.resolve().is_relative_to(Path(self.temp.name).resolve()):
                raise ValueError('Choose a permanent folder outside this recording session')
            save_recording(result['path'], target, result['metadata'])
        except (OSError, ValueError) as exc:
            self.status.setText('Recording not saved: ' + str(exc) + '\nChoose a new filename; the last result is still available.')
            return False
        result['saved'] = True
        self.status.setText('Saved converted recording: ' + str(target))
        browser = getattr(self.parent(), 'export_browser', None)
        if browser is not None:
            try:
                browser.add_root(target.parent)
            except Exception as exc:
                self.status.setText(self.status.text() + '\nSaved successfully, but Export Library could not refresh: ' + str(exc))
        return True

    def _allow_discard(self):
        if not self.last_result or self.last_result['saved']:
            return True
        answer = QMessageBox.question(self, 'Keep converted recording?',
            'The last converted recording has not been saved. Save it before continuing?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_recording()
        return answer == QMessageBox.StandardButton.Discard

    def _conversion_error(self, message):
        self.model_ready = False
        self.watchdog.stop()
        self._idle()
        if not self.cancelled:
            self.status.setText('Conversion failed: ' + message)

    def _progress(self, message):
        if not self.cancelled and self.warm.busy:
            self.status.setText(message + '… Cancel remains available.')

    def _released(self):
        ready, self.model_ready = self.model_ready, False
        if ready and hasattr(self, 'status') and not self.source and not self.warm.busy and self.process.state() == QProcess.ProcessState.NotRunning:
            self.status.setText('Model released. Hold to record another line.')

    def _arm_timeout(self, milliseconds):
        self.stage_timeout_ms = milliseconds
        self.watchdog.start(milliseconds)

    def _timeout(self):
        self.stop()
        self.status.setText(f'This stage exceeded the {self.stage_timeout_ms // 1000}-second limit and was stopped.')

    def stop(self):
        self.cancelled = True
        self.model_ready = False
        self._end_capture()
        self.player.stop()
        self.watchdog.stop()
        self.warm.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        else:
            self._idle()
        self.status.setText('Stopped. Hold to record a new line.')

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow() and self.source:
            self.stop()
            self.status.setText('Recording cancelled because the window lost focus.')
        super().changeEvent(event)

    def done(self, result):
        if not self._allow_discard():
            return
        self.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.waitForFinished(3000)
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.status.setText('Waiting for conversion to stop. Try closing again shortly.')
            return
        if not self.warm.stop(wait=True):
            self.status.setText('Waiting for the model worker to exit. Try closing again.')
            return
        self.player.setSource(QUrl())
        self.temp.cleanup()
        super().done(result)
