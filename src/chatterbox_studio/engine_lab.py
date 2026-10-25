"""Local multi-engine voice studio. Chatterbox narration remains independent."""
from __future__ import annotations

from pathlib import Path
from threading import Event
import sys

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox,
    QComboBox, QLineEdit, QPushButton, QFileDialog, QPlainTextEdit, QMessageBox,
    QDoubleSpinBox, QScrollArea, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QSplitter, QDialog, QTabWidget,
)

from .optional_engines import (
    ENGINES, KOKORO_VOICES, EngineRegistry, CharacterStore, EngineError, EngineCancelled,
    clean_request, new_output_path, execute_generation, execute_probe,
)


class OptionalEngineWorker(QObject):
    message = pyqtSignal(str)
    result = pyqtSignal(str, str, float)  # engine, output, elapsed seconds
    failure = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, jobs: list[tuple[dict, str]] | None = None,
                 probe: tuple[str, str, str, str] | None = None,
                 diagnostic_dir: Path | None = None):
        super().__init__()
        self.jobs = jobs or []
        self.probe = probe
        self.diagnostic_dir = diagnostic_dir
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    @pyqtSlot()
    def run(self):
        from time import monotonic
        try:
            if self.probe:
                engine, exe, repo, model_dir, *native = self.probe
                options = native[0] if native else {}
                result = execute_probe(engine, exe, repo, cancelled=self.cancel_event,
                                       log=self.message.emit, diagnostic_dir=self.diagnostic_dir,
                                       model_dir=model_dir, **options)
                detail = (result['status'] if result.get('backend') == 'native_vulkan' else
                          result['runtime'] + '; available providers: ' + ', '.join(result['providers']) if engine == 'kokoro' else
                          f'PyTorch {result["torch"]}, CUDA: {result["cuda_available"]}')
                self.message.emit(f'{ENGINES[engine]["label"]}: {detail}')
            for request, exe in self.jobs:
                if self.cancel_event.is_set():
                    break
                start = monotonic()
                output = execute_generation(request, exe, self.cancel_event, self.message.emit,
                                            diagnostic_dir=self.diagnostic_dir)
                self.result.emit(request['engine'], str(output), monotonic() - start)
        except EngineCancelled:
            self.message.emit('Voice engine generation cancelled.')
        except Exception as exc:
            self.failure.emit(str(exc))
        finally:
            self.finished.emit()


class EngineLab(QWidget):
    """Isolated speech runtimes, preset/cloned voices, profiles and comparison."""
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setObjectName('engine_lab')
        self.registry = EngineRegistry(host.storage)
        self.profiles = CharacterStore(host.storage)
        self.config = self.registry.read()
        self.worker: OptionalEngineWorker | None = None
        self.thread: QThread | None = None
        self._started_at = 0.0
        self._last_status = 'Engine idle'
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._refresh_elapsed)
        self._build()
        self.refresh_voices()
        self.refresh_profiles()
        self._engine_changed()

    def _build(self):
        outer = QVBoxLayout(self)
        headline = QLabel('VOICE ENGINES')
        headline.setObjectName('sectionTitle')
        outer.addWidget(headline)
        note = QLabel('Qwen3-TTS, IndexTTS 2.5 and Kokoro use independent runtimes and shared model storage. '
                      'Python remains the default. Native Vulkan is an explicit Linux option for reviewed local runtimes; '
                      'Index native generation remains unavailable until placement verification is qualified.')
        note.setWordWrap(True)
        outer.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)
        panel = QWidget()
        scroll.setWidget(panel)
        layout = QVBoxLayout(panel)

        runtimes = QGroupBox('1. Engine environments')
        rform = QFormLayout(runtimes)
        self.qwen_py = QLineEdit(self.config['qwen3']['python'])
        self.qwen_py.setPlaceholderText('...\\qwen3\\.venv\\Scripts\\python.exe')
        if sys.platform != 'win32':
            self.qwen_py.setPlaceholderText('.../qwen3/.venv/bin/python')
        self.index_py = QLineEdit(self.config['index25']['python'])
        self.index_py.setPlaceholderText('...\\index-tts\\.venv\\Scripts\\python.exe')
        if sys.platform != 'win32':
            self.index_py.setPlaceholderText('.../index-tts/.venv/bin/python')
        self.index_repo = QLineEdit(self.config['index25']['repo'])
        self.index_repo.setPlaceholderText('Directory containing indextts and checkpoints')
        self.kokoro_py = QLineEdit(self.config['kokoro']['python'])
        self.kokoro_py.setPlaceholderText('PlaguedAI\\runtimes\\python\\kokoro-directml\\Scripts\\python.exe')
        if sys.platform != 'win32':
            self.kokoro_py.setPlaceholderText('.../PlaguedAI/runtimes/python/kokoro-onnx/bin/python')
        self.kokoro_models = QLineEdit(self.config['kokoro']['model_dir'])
        self.kokoro_models.setToolTip('Folder containing kokoro-v1.0.int8.onnx and voices-v1.0.bin; shared by all tools.')
        for title, field, directory in [
            ('Qwen3 Python', self.qwen_py, False),
            ('IndexTTS Python', self.index_py, False),
            ('IndexTTS repository', self.index_repo, True),
            ('Kokoro Python', self.kokoro_py, False),
            ('Kokoro model folder', self.kokoro_models, True),
        ]:
            r = QHBoxLayout(); r.addWidget(field, 1)
            b = QPushButton('Browse...')
            b.clicked.connect(lambda checked=False, e=field, d=directory: self._browse(e, d))
            r.addWidget(b)
            rform.addRow(title, r)
        native = self.config['native']
        self.native_fields = {}
        for key, title, directory in (
            ('native_executable', 'Native speech executable', False),
            ('native_sha256', 'Reviewed executable SHA256', None),
            ('qwen_06_model_dir', 'Native Qwen Base 0.6B folder', True),
            ('qwen_17_model_dir', 'Native Qwen Base 1.7B folder', True),
            ('index_model_dir', 'Native IndexTTS 2.5 folder', True),
            ('native_gpu_lock', 'Existing shared GPU lock', False),
        ):
            field = QLineEdit(native.get(key, ''))
            field.setObjectName(key)
            self.native_fields[key] = field
            row = QHBoxLayout(); row.addWidget(field, 1)
            if directory is not None:
                browse = QPushButton('Browse...')
                browse.clicked.connect(lambda checked=False, e=field, d=directory: self._browse(e, d))
                row.addWidget(browse)
            rform.addRow(title, row)
        discover = QPushButton('Find retained native preset paths')
        discover.clicked.connect(self._discover_native_paths)
        rform.addRow(discover)
        note = QLabel('Native Vulkan is a separate Linux backend. Select a reviewed audio.cpp runtime and complete local model folders. '
                      'Finding paths does not save settings, install anything or test the GPU. Python remains the default.')
        note.setWordWrap(True); rform.addRow(note)
        controls = QHBoxLayout()
        save = QPushButton('Save runtime paths')
        save.clicked.connect(self.save_runtimes)
        controls.addWidget(save)
        self.test = QPushButton('Test selected engine')
        test = self.test
        test.clicked.connect(self.test_engine)
        controls.addWidget(test)
        controls.addStretch()
        docs = QPushButton('Official engine documentation')
        docs.clicked.connect(self.open_docs)
        controls.addWidget(docs)
        rform.addRow(controls)
        layout.addWidget(runtimes)

        settings = QGroupBox('2. Character and generation settings')
        form = self.settings_form = QFormLayout(settings)
        self.character = QComboBox()
        self.character.setEditable(True)
        self.character.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.character.setPlaceholderText('Choose or type a character name')
        self.character.currentIndexChanged.connect(self._profile_selected)
        r = QHBoxLayout(); r.addWidget(self.character, 1)
        save = QPushButton('Save profile'); save.clicked.connect(self.save_profile); r.addWidget(save)
        delete = QPushButton('Delete'); delete.clicked.connect(self.delete_profile); r.addWidget(delete)
        form.addRow('Character', r)
        self.engine = QComboBox()
        for identifier, data in ENGINES.items():
            self.engine.addItem(data['label'], identifier)
        self.engine.currentIndexChanged.connect(self._engine_changed)
        form.addRow('Engine', self.engine)
        self.backend = QComboBox()
        self.backend.setObjectName('optional_engine_backend')
        self.backend.addItem('Python (existing runtime; compatible default)', 'python')
        self.backend.addItem('Native Vulkan (Linux, explicit GPU)', 'native_vulkan')
        self.backend.currentIndexChanged.connect(self._backend_changed)
        form.addRow('Backend', self.backend)
        self.backend_note = QLabel('')
        self.backend_note.setWordWrap(True)
        self.backend_note.setObjectName('native_backend_status')
        form.addRow(self.backend_note)
        self.model = QComboBox()
        form.addRow('Model', self.model)
        self.language = QComboBox()
        form.addRow('Language', self.language)
        self.device = QComboBox()
        for name, value in [('CPU (compatible default)', 'cpu'), ('Auto', 'auto'), ('NVIDIA CUDA', 'cuda')]:
            self.device.addItem(name, value)
        form.addRow('Compute', self.device)
        self.voice = QComboBox()
        form.addRow('Reference voice', self.voice)
        self.preset_voice = QComboBox()
        self.preset_voice.setObjectName('kokoro_preset_voice')
        for identifier, (name, accent) in KOKORO_VOICES.items():
            self.preset_voice.addItem(f'{name} — {accent}', identifier)
        self.preset_voice.currentIndexChanged.connect(self._kokoro_voice_changed)
        form.addRow('Kokoro voice', self.preset_voice)
        self.preset_note = QLabel('Kokoro uses ready-made voices and cannot clone reference recordings. Use Chatterbox, Qwen3 or IndexTTS for your saved voices.')
        self.preset_note.setWordWrap(True)
        form.addRow(self.preset_note)
        self.ref_text = QPlainTextEdit()
        self.ref_text.setFixedHeight(75)
        self.ref_text.setPlaceholderText('Exact words spoken in the reference audio; optional for Qwen voice cloning, helps speaker fidelity.')
        form.addRow('Reference transcript', self.ref_text)
        self.emotion = QComboBox()
        for name in ('neutral','happy','angry','sad','afraid','disgusted','melancholic','surprised','calm'):
            self.emotion.addItem(name.capitalize(), name)
        form.addRow('IndexTTS emotion', self.emotion)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.5, 2.0); self.speed.setSingleStep(0.05)
        self.speed.setDecimals(2); self.speed.setValue(1.0)
        self.speed.setToolTip('IndexTTS duration factor; >1.0 slows the speech. Qwen Base ignores this field.')
        form.addRow('IndexTTS duration factor', self.speed)
        layout.addWidget(settings)

        script = QGroupBox('3. Script and generation')
        slayout = QVBoxLayout(script)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText('Enter the words to speak. Kokoro uses your selected preset voice; Qwen3 and IndexTTS clone a reference voice.')
        self.text.setMinimumHeight(110)
        self.text.setMaximumHeight(195)
        slayout.addWidget(self.text)
        actions = QHBoxLayout()
        from_narration = QPushButton('Copy text from Narration Studio')
        from_narration.clicked.connect(lambda: self.text.setPlainText(self.host.editor.toPlainText()))
        actions.addWidget(from_narration)
        self.preview_text = QPushButton('Preview render text')
        self.preview_text.setToolTip('Review the selected engine’s prepared text without generating audio. English AM/PM clocks are expanded; the original text stays unchanged.')
        self.preview_text.clicked.connect(self._preview_render_text)
        actions.addWidget(self.preview_text)
        actions.addStretch()
        slayout.addLayout(actions)
        actions = QHBoxLayout()
        self.generate = QPushButton('Generate with selected engine')
        self.generate.setObjectName('primary')
        self.generate.clicked.connect(self.generate_selected)
        actions.addWidget(self.generate)
        self.compare = QPushButton('Compare cloning engines')
        self.compare.setToolTip('Compare Qwen3-TTS and IndexTTS 2.5 using their separately configured local runtimes. Each generation runs sequentially.')
        self.compare.clicked.connect(self.compare_engines)
        actions.addWidget(self.compare)
        self.cancel = QPushButton('Cancel')
        self.cancel.clicked.connect(self.cancel_work)
        self.cancel.setEnabled(False)
        actions.addWidget(self.cancel)
        slayout.addLayout(actions)
        layout.addWidget(script)

        results = QGroupBox('4. Recordings and comparison')
        result_layout = QVBoxLayout(results)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Engine', 'Model', 'Render time', 'WAV recording'])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda *_: self.play_selected())
        self.table.setMinimumHeight(145)
        result_layout.addWidget(self.table)
        buttons = QHBoxLayout()
        recording_actions = [
            ('Play selected', self.play_selected),
            ('Stop playback', self.host.player.stop),
            ('Open exports folder', self.open_folder),
        ]
        if getattr(self.host, 'bethesda_tab', None) is not None:
            recording_actions.insert(2, ('Send selected to Bethesda Export', self.send_to_bethesda))
        for label, function in recording_actions:
            button = QPushButton(label)
            if function == self.send_to_bethesda:
                button.setObjectName('bethesda_export_handoff')
            button.clicked.connect(function)
            buttons.addWidget(button)
        result_layout.addLayout(buttons)
        layout.addWidget(results)
        setup = 'scripts/setup_kokoro_windows.ps1' if sys.platform == 'win32' else 'LINUX.md (optional runtimes)'
        self.status = QLabel(f'Choose an engine, verify its runtime with Test selected engine, then generate speech. Kokoro setup: {setup}.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        diagnostics = QGroupBox('5. Live engine diagnostics')
        dlayout = QVBoxLayout(diagnostics)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setObjectName('engine_diagnostics')
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumBlockCount(300)
        self.diagnostics.setMinimumHeight(155)
        self.diagnostics.setPlaceholderText('Engine loading, model downloads, and speech-generation details appear here. Logs are saved in the current application data folder.')
        dlayout.addWidget(self.diagnostics)
        row = QHBoxLayout()
        folder = QPushButton('Open diagnostic logs')
        folder.clicked.connect(self.open_diagnostic_logs)
        row.addWidget(folder)
        row.addStretch()
        dlayout.addLayout(row)
        layout.addWidget(diagnostics)

    def _browse(self, field: QLineEdit, directory: bool):
        if directory:
            path = QFileDialog.getExistingDirectory(self, 'Select engine folder')
        else:
            filters = 'Executables (*.exe);;All files (*)' if sys.platform == 'win32' else 'All files (*)'
            path, _ = QFileDialog.getOpenFileName(self, 'Select isolated Python interpreter', '', filters)
        if path: field.setText(path)

    def save_runtimes(self):
        self.config['qwen3'].update(python=self.qwen_py.text().strip())
        self.config['index25'].update(python=self.index_py.text().strip(), repo=self.index_repo.text().strip())
        self.config['kokoro'].update(python=self.kokoro_py.text().strip(), model_dir=self.kokoro_models.text().strip())
        self.config['native'].update({key: field.text().strip() for key, field in self.native_fields.items()})
        if self.engine.currentData() in ('qwen3', 'index25'):
            self.config[self.engine.currentData()]['backend'] = self.backend.currentData()
        try:
            self.registry.save(self.config)
            self.status.setText('Engine runtime paths saved. No installation was performed.')
        except Exception as exc:
            QMessageBox.warning(self, 'Unable to save runtime settings', str(exc))

    def _discover_native_paths(self):
        from .native_vulkan import discover_native_settings
        found = discover_native_settings(self.host.storage)
        if not found:
            self.status.setText('No retained native preset paths were found here. Choose existing paths manually; check mounted drives.')
            return
        for key, value in found.items():
            if key in self.native_fields and not self.native_fields[key].text().strip():
                self.native_fields[key].setText(value)
        self.status.setText('Retained paths suggested in empty fields. Review them, save explicitly, then test paths. GPU generation has not run.')

    def _backend_changed(self, *_):
        if not hasattr(self, 'device') or not hasattr(self, 'compare'):
            return
        eng = self.engine.currentData()
        if eng == 'kokoro':
            self.backend.blockSignals(True)
            self.backend.setCurrentIndex(self.backend.findData('python'))
            self.backend.blockSignals(False)
        native = eng in ('qwen3', 'index25') and self.backend.currentData() == 'native_vulkan'
        self.backend.setEnabled(eng != 'kokoro')
        same_engine = getattr(self, '_backend_engine', None) == eng
        was_native = getattr(self, '_native_active', False)
        if not hasattr(self, '_python_controls'):
            self._python_controls = {}
        if native and same_engine and not was_native:
            self._python_controls[eng] = (self.device.currentData(), self.emotion.currentData(), self.speed.value())
        current = self.device.currentData()
        self.device.clear()
        if native:
            self.device.addItem('Vulkan GPU 0 (no fallback)', 'vulkan')
            self.emotion.setCurrentIndex(self.emotion.findData('neutral'))
            self.speed.setValue(1.0)
        elif eng == 'kokoro':
            choices = [('Auto (prefer DirectML GPU)', 'auto'), ('DirectML GPU (Radeon / Intel / NVIDIA)', 'directml'), ('CPU', 'cpu')] if sys.platform == 'win32' else [('Auto (CPU)', 'auto'), ('CPU', 'cpu')]
            for label, value in choices: self.device.addItem(label, value)
        else:
            for label, value in [('CPU (compatible default)', 'cpu'), ('Auto', 'auto'), ('GPU via PyTorch (CUDA / ROCm runtime)', 'cuda')]:
                self.device.addItem(label, value)
        selected = self.device.findData(current)
        if selected >= 0: self.device.setCurrentIndex(selected)
        if not native and same_engine and was_native and eng in self._python_controls:
            device, emotion, speed = self._python_controls[eng]
            for combo, value in ((self.device, device), (self.emotion, emotion)):
                index = combo.findData(value)
                if index >= 0: combo.setCurrentIndex(index)
            self.speed.setValue(speed)
        self.device.setEnabled(not native)
        self.emotion.setEnabled(eng == 'index25' and not native)
        self.speed.setEnabled(eng in ('index25', 'kokoro') and not native)
        if native:
            self.emotion.setToolTip('Native emotion controls have not been qualified; Neutral is required.')
            self.speed.setToolTip('Native duration controls have not been qualified; 1.0 is required.')
        else:
            self.emotion.setToolTip('Select the emotion supported by the Python Index adapter.')
            self.speed.setToolTip('Kokoro speaking speed: >1.0 speaks faster.' if eng == 'kokoro' else
                                  'IndexTTS duration factor: >1.0 slows the speech.')
        from .native_vulkan import native_generation_blocker
        blocker = native_generation_blocker(eng) if native else ''
        if native and sys.platform != 'linux':
            blocker = 'Native Vulkan currently supports Linux only. Choose Python on this platform.'
        self.backend_note.setText(blocker or ('Native Vulkan0: at most 1,000 prepared characters; reference at most 30 seconds. '
                                            'Exact Qwen transcript or explicitly embedding-only conditioning; no CPU fallback. '
                                            'GPU generation still requires runtime qualification.' if native else
                                            'Python uses the separately configured runtime and selected compute device.'))
        if hasattr(self, 'generate'):
            self.generate.setEnabled(self.thread is None and not blocker)
            self.compare.setEnabled(self.thread is None and eng != 'kokoro' and not blocker)
        self._backend_engine, self._native_active = eng, native

    def _native_request_settings(self, engine, model):
        values = {key: field.text().strip() for key, field in self.native_fields.items()}
        key = ('qwen_06_model_dir' if '0.6B' in model else 'qwen_17_model_dir') if engine == 'qwen3' else 'index_model_dir'
        return {key: values[key] for key in ('native_executable', 'native_sha256', 'native_gpu_lock')} | {'native_model_dir': values[key]}

    def _restore_native_settings(self, engine, model, values):
        folder_key = ('qwen_06_model_dir' if '0.6B' in model else 'qwen_17_model_dir') if engine == 'qwen3' else 'index_model_dir'
        for key in ('native_executable', 'native_sha256', 'native_gpu_lock'):
            if key in values:
                self.native_fields[key].setText(str(values[key]))
        if 'native_model_dir' in values:
            self.native_fields[folder_key].setText(str(values['native_model_dir']))

    def _engine_changed(self, *_):
        eng = self.engine.currentData()
        if not eng: return
        self.model.blockSignals(True)
        self.language.blockSignals(True)
        try:
            self.model.clear(); self.language.clear()
            for model in ENGINES[eng]['models']: self.model.addItem(model.rsplit('/', 1)[-1], model)
            for lang in ENGINES[eng]['languages']: self.language.addItem(lang, lang)
        finally:
            self.model.blockSignals(False)
            self.language.blockSignals(False)
        is_kokoro = eng == 'kokoro'
        for field, visible in ((self.voice, not is_kokoro), (self.ref_text, not is_kokoro),
                               (self.preset_voice, is_kokoro), (self.emotion, eng == 'index25'),
                               (self.speed, eng in ('index25', 'kokoro'))):
            field.setVisible(visible)
            self.settings_form.labelForField(field).setVisible(visible)
        self.preset_note.setVisible(is_kokoro)
        self.emotion.setEnabled(eng == 'index25')
        self.speed.setEnabled(eng in ('index25', 'kokoro'))
        self.settings_form.labelForField(self.speed).setText('Speaking speed' if is_kokoro else 'IndexTTS duration factor')
        self.speed.setToolTip('Kokoro speaking speed: >1.0 speaks faster.' if is_kokoro else
                              'IndexTTS duration factor: >1.0 slows the speech.')
        self.ref_text.setEnabled(eng == 'qwen3')
        if is_kokoro:
            if getattr(self, '_last_engine', None) != 'kokoro':
                self._clone_device = self.device.currentData()
            self.device.clear()
            choices = [('Auto (prefer DirectML GPU)', 'auto'), ('DirectML GPU (Radeon / Intel / NVIDIA)', 'directml'), ('CPU', 'cpu')] if sys.platform == 'win32' else [('Auto (CPU)', 'auto'), ('CPU', 'cpu')]
            for label, value in choices:
                self.device.addItem(label, value)
        elif getattr(self, '_last_engine', None) == 'kokoro':
            self.device.clear()
            for label, value in [('CPU (compatible default)', 'cpu'), ('Auto', 'auto'), ('NVIDIA CUDA', 'cuda')]:
                self.device.addItem(label, value)
            self.device.setCurrentIndex(self.device.findData(getattr(self, '_clone_device', 'cpu')))
        self.device.setEnabled(True)
        self.language.setEnabled(not is_kokoro)
        self.compare.setEnabled(not is_kokoro and self.thread is None)
        self._last_engine = eng
        self.backend.blockSignals(True)
        self.backend.setCurrentIndex(self.backend.findData(self.config.get(eng, {}).get('backend', 'python')))
        self.backend.blockSignals(False)
        self._backend_changed()
        self.speed.setValue(1.0)
        name = self.character.currentText().strip() if hasattr(self, 'character') else ''
        profile = self.profiles.read().get(name, {})
        chosen = profile.get('engines', {}).get(eng, {})
        self._apply_engine_settings(chosen)

    def _kokoro_voice_changed(self, *_):
        if self.engine.currentData() == 'kokoro':
            accent = KOKORO_VOICES[self.preset_voice.currentData()][1]
            self.language.setCurrentIndex(self.language.findData(accent))

    def _apply_engine_settings(self, chosen: dict):
        engine = self.engine.currentData()
        backend = chosen.get('backend', self.config.get(engine, {}).get('backend', 'python'))
        self.backend.setCurrentIndex(self.backend.findData(backend))
        for combo, value in [
            (self.model, chosen.get('model')),
            (self.language, chosen.get('language')),
            (self.device, chosen.get('device')),
            (self.emotion, chosen.get('emotion')),
            (self.preset_voice, chosen.get('preset_voice')),
        ]:
            index = combo.findData(value)
            if index >= 0: combo.setCurrentIndex(index)
        if 'speed' in chosen:
            self.speed.setValue(float(chosen['speed']))
        if self.backend.currentData() == 'native_vulkan':
            self._restore_native_settings(engine, self.model.currentData(), chosen.get('native_settings', {}))
            self._backend_changed()
        if self.engine.currentData() == 'kokoro':
            self._kokoro_voice_changed()

    def refresh_voices(self):
        selected = self.voice.currentData()
        self.voice.clear()
        for item in self.host.voices.list_voices():
            self.voice.addItem(item['name'], item['id'])
        index = self.voice.findData(selected)
        if index >= 0: self.voice.setCurrentIndex(index)

    def refresh_profiles(self, selected: str = ''):
        profiles = self.profiles.read()
        current = selected or self.character.currentText()
        self.character.blockSignals(True)
        self.character.clear()
        self.character.addItem('')
        self.character.addItems(sorted(profiles))
        index = self.character.findText(current)
        if index >= 0: self.character.setCurrentIndex(index)
        else: self.character.setEditText(current)
        self.character.blockSignals(False)

    def _profile_selected(self, *_):
        name = self.character.currentText().strip()
        profile = self.profiles.read().get(name)
        if not profile: return
        self.refresh_voices()
        voice_index = self.voice.findData(profile.get('voice_id'))
        if voice_index >= 0: self.voice.setCurrentIndex(voice_index)
        self.ref_text.setPlainText(profile.get('ref_text', ''))
        preferred = profile.get('preferred_engine', 'qwen3')
        index = self.engine.findData(preferred)
        if index >= 0: self.engine.setCurrentIndex(index)
        self._apply_engine_settings(profile.get('engines', {}).get(self.engine.currentData(), {}))

    def save_profile(self):
        try:
            name = self.character.currentText().strip()
            current = self.profiles.read().get(name, {})
            engines = dict(current.get('engines', {}))
            engines[self.engine.currentData()] = {**engines.get(self.engine.currentData(), {}),
                'model': self.model.currentData(), 'language': self.language.currentData(),
                'device': self.device.currentData(), 'emotion': self.emotion.currentData(),
                'speed': self.speed.value(),
                'backend': self.backend.currentData(),
                'preset_voice': self.preset_voice.currentData() if self.engine.currentData() == 'kokoro' else '',
            }
            if self.backend.currentData() == 'native_vulkan':
                engines[self.engine.currentData()]['native_settings'] = self._native_request_settings(self.engine.currentData(), self.model.currentData())
            profile = {**current, 'preferred_engine': self.engine.currentData(),
                       'voice_id': self.voice.currentData(),
                       'ref_text': self.ref_text.toPlainText(), 'engines': engines}
            self.profiles.save_profile(name, profile)
            self.refresh_profiles(name)
            self.status.setText(f'Character settings saved: {name}. Engine-specific presets are retained.')
        except EngineError as exc:
            QMessageBox.warning(self, 'Unable to save character', str(exc))

    def delete_profile(self):
        name = self.character.currentText().strip()
        if name not in self.profiles.read(): return
        if QMessageBox.question(self, 'Delete character profile', f'Delete settings for {name}? No source audio will be deleted.') != QMessageBox.StandardButton.Yes:
            return
        self.profiles.delete_profile(name)
        self.character.setEditText('')
        self.refresh_profiles()

    def _preview_render_text(self):
        from .text_preparation import prepare_render_text
        original = self.text.toPlainText()
        prepared = prepare_render_text(original, self.language.currentData() or '')
        previous = getattr(self, '_text_preview_dialog', None)
        if previous is not None:
            previous.close()
            previous.deleteLater()
        dialog = QDialog(self)
        dialog.setObjectName('engine_render_preview')
        dialog.setWindowTitle('Preview render text — no audio generated')
        dialog.resize(740, 520)
        layout = QVBoxLayout(dialog)
        summary = QLabel('Selected engine: ' + self.engine.currentText()
                         + '. Generate uses the current text and language. English AM/PM clocks are expanded for speech.')
        summary.setWordWrap(True)
        layout.addWidget(summary)
        tabs = QTabWidget()
        for title, name, text in (
            ('Render text', 'engine_preview_prepared', prepared),
            ('Original manuscript', 'engine_preview_original', original),
        ):
            field = QPlainTextEdit()
            field.setObjectName(name)
            field.setReadOnly(True)
            field.setPlainText(text)
            tabs.addTab(field, title)
        layout.addWidget(tabs)
        close = QPushButton('Close')
        close.clicked.connect(dialog.close)
        layout.addWidget(close)
        self._text_preview_dialog = dialog
        dialog.show()

    def _make_request(self, engine: str) -> dict:
        # For comparisons, use saved per-engine settings when available.
        character = self.character.currentText().strip()
        profile = self.profiles.read().get(character, {})
        saved = profile.get('engines', {}).get(engine, {})
        if engine == self.engine.currentData():
            model = self.model.currentData()
            lang = self.language.currentData()
            device = self.device.currentData()
            emotion = self.emotion.currentData()
            speed = self.speed.value()
        else:
            model = saved.get('model', ENGINES[engine]['models'][0])
            lang = saved.get('language', 'English' if engine == 'qwen3' else 'EN')
            device = saved.get('device', self.device.currentData())
            emotion = saved.get('emotion', 'neutral')
            speed = saved.get('speed', 1.0)
        preset = self.preset_voice.currentData() if engine == self.engine.currentData() else saved.get('preset_voice', 'am_michael')
        if engine == 'kokoro':
            voice = ''
            lang = KOKORO_VOICES[preset][1]
        else:
            voice = self.host.voices.resolve(self.voice.currentData() or '')
        name = character or (KOKORO_VOICES[preset][0] if engine == 'kokoro' else self.voice.currentText()) or 'speaker'
        from .pvs_library import new_export_directory
        root = new_export_directory(self.host.storage)
        output = new_output_path(root, f'{name}_{engine}')
        result = {
            'engine': engine, 'model': model, 'language': lang,
            'device': device, 'text': self.text.toPlainText(),
            'voice_path': voice, 'ref_text': self.ref_text.toPlainText(),
            'emotion': emotion, 'speed': speed,
            'repo': self.index_repo.text().strip() if engine == 'index25' else '',
            'output_path': str(output),
            'preset_voice': preset if engine == 'kokoro' else '',
            'model_dir': self.kokoro_models.text().strip() if engine == 'kokoro' else '',
        }
        backend = self.backend.currentData() if engine == self.engine.currentData() else saved.get('backend', self.config.get(engine, {}).get('backend', 'python'))
        result['backend'] = backend
        if backend == 'native_vulkan':
            native_settings = self._native_request_settings(engine, model) if engine == self.engine.currentData() else saved.get('native_settings', self._native_request_settings(engine, model))
            result.update(native_settings, device='vulkan')
        return clean_request(result)

    def _start(self, jobs=None, probe=None):
        from .native_vulkan import native_generation_blocker
        for request, _ in jobs or []:
            if request.get('backend') == 'native_vulkan' and native_generation_blocker(request['engine']):
                QMessageBox.information(self, 'Native engine unavailable', native_generation_blocker(request['engine']))
                return
        plugins = getattr(self.host, 'plugins', None)
        if plugins is not None and plugins.is_busy:
            QMessageBox.information(self, 'Writer running', 'Finish or cancel the writer before starting a voice-engine operation.')
            return
        if self.thread is not None:
            QMessageBox.information(self, 'Engine already running', 'Finish or cancel the current generation first.')
            return
        if getattr(self.host, 'thread', None) is not None or any(
                getattr(getattr(self.host, name, None), 'is_busy', False)
                for name in ('model_manager', 'bethesda_tab')):
            QMessageBox.information(self, 'Operation running',
                'Finish or cancel the active narration, model, or export operation before starting a voice-engine operation.')
            return
        self.thread = QThread(self)
        self.worker = OptionalEngineWorker(jobs=jobs, probe=probe,
                                           diagnostic_dir=self.host.storage / 'engine_logs')
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.message.connect(self._diagnostic_message)
        self.worker.result.connect(self._generation_result)
        self.worker.failure.connect(self._failure)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.generate.setEnabled(False); self.compare.setEnabled(False); self.test.setEnabled(False)
        self.cancel.setEnabled(True)
        from time import monotonic
        self._started_at = monotonic()
        self._last_status = 'Isolated engine process starting...'
        self.diagnostics.clear()
        self._diagnostic_message('Launching isolated engine. Use Cancel to stop.')
        self.elapsed_timer.start()
        self.thread.start()

    def test_engine(self):
        self.save_runtimes()
        engine = self.engine.currentData()
        entry = self.config[engine]
        options = {}
        if self.backend.currentData() == 'native_vulkan':
            options = {'backend': 'native_vulkan', 'model': self.model.currentData(),
                       'native_settings': self._native_request_settings(engine, self.model.currentData())}
        self._start(probe=(engine, entry['python'], entry.get('repo', ''), entry.get('model_dir', ''), options))

    def generate_selected(self):
        self.save_runtimes()
        try:
            engine = self.engine.currentData()
            job = self._make_request(engine)
            self._start(jobs=[(job, self.config[engine]['python'])])
        except EngineError as exc:
            QMessageBox.warning(self, 'Check voice engine', str(exc))

    def compare_engines(self):
        self.save_runtimes()
        try:
            # Compare in the SAME language; IndexTTS supports fewer languages.
            #  Neither model is sent a language code it does not support.
            common = {'English': 'EN', 'Spanish': 'ES', 'Japanese': 'JA', 'Chinese': 'ZH'}
            chosen = self.language.currentData()
            if self.engine.currentData() == 'index25':
                reverse = {value: key for key, value in common.items()}
                chosen = reverse.get(chosen, '')
            if chosen not in common:
                raise EngineError('A/B comparison supports English, Spanish, Japanese or Chinese. Choose a shared language first.')
            jobs = []
            for engine in ('qwen3', 'index25'):
                req = self._make_request(engine)
                req['language'] = chosen if engine == 'qwen3' else common[chosen]
                jobs.append((req, self.config[engine]['python']))
            self._start(jobs=jobs)
        except EngineError as exc:
            QMessageBox.warning(self, 'Check comparison settings', str(exc))

    def _diagnostic_message(self, message: str):
        from datetime import datetime
        for line in str(message).splitlines():
            if not line.strip():
                continue
            self.diagnostics.appendPlainText(f'{datetime.now():%H:%M:%S}  {line}')
            self._last_status = line[-350:]
        self._refresh_elapsed()

    def _refresh_elapsed(self):
        if self.thread is not None:
            from time import monotonic
            seconds = max(0, int(monotonic() - self._started_at))
            self.status.setText(f'Elapsed {seconds // 60:02d}:{seconds % 60:02d}  |  {self._last_status}')
        else:
            self.status.setText(self._last_status)

    def open_diagnostic_logs(self):
        folder = self.host.storage / 'engine_logs'
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _generation_result(self, engine: str, output: str, elapsed: float):
        row = self.table.rowCount(); self.table.insertRow(row)
        from json import loads
        sidecar = Path(output).with_suffix('.json')
        model = loads(sidecar.read_text(encoding='utf-8')).get('model', '') if sidecar.is_file() else ''
        metadata = loads(sidecar.read_text(encoding='utf-8')) if sidecar.is_file() else {}
        model_label = model.rsplit('/', 1)[-1]
        if engine == 'kokoro':
            model_label += ' / ' + KOKORO_VOICES[metadata['preset_voice']][0]
            backend = metadata.get('runtime', {}).get('backend')
            if backend:
                model_label += ' / ' + ('DirectML' if backend == 'directml' else 'CPU')
        elif metadata.get('backend') == 'native_vulkan':
            model_label += ' / Native Vulkan0'
        for col, val in enumerate((ENGINES[engine]['label'], model_label, f'{elapsed:.1f}s', str(output))):
            item = QTableWidgetItem(val)
            if col == 3: item.setData(Qt.ItemDataRole.UserRole, str(output))
            self.table.setItem(row, col, item)
        self.table.selectRow(row)
        self.host.export_browser.add_root(Path(output).parent)
        self._diagnostic_message(f'Generated {Path(output).name} with {ENGINES[engine]["label"]}')

    def _failure(self, error: str):
        self._diagnostic_message('Voice engine failed. See the diagnostic log; other engines remain unaffected.')
        self._diagnostic_message(error[-3000:])
        QMessageBox.warning(self, 'Voice engine failed', error[-8000:])

    def _finished(self):
        self.elapsed_timer.stop()
        self.thread = None
        self.worker = None
        self.generate.setEnabled(True); self.compare.setEnabled(self.engine.currentData() != 'kokoro'); self.test.setEnabled(True)
        self.cancel.setEnabled(False)
        self._backend_changed()

    def cancel_work(self):
        if self.worker is not None:
            self.worker.cancel()
            self._diagnostic_message('Cancel requested. Stopping the isolated engine process...')

    @property
    def is_busy(self):
        return self.thread is not None

    def selected_path(self) -> Path | None:
        row = self.table.currentRow()
        item = self.table.item(row, 3) if row >= 0 else None
        return Path(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def play_selected(self):
        file = self.selected_path()
        if file and file.is_file(): self.host._play_file(str(file))
        else: QMessageBox.information(self, 'Select audio', 'Select a generated recording first.')

    def send_to_bethesda(self):
        tab = getattr(self.host, 'bethesda_tab', None)
        if tab is None:
            return
        file = self.selected_path()
        if file and file.is_file():
            tab.audio.setText(str(file))
            self.host.tabs.setCurrentWidget(tab)
        else:
            QMessageBox.information(self, 'Select audio', 'Choose a generated recording first.')

    def open_folder(self):
        file = self.selected_path()
        if file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file.parent)))

    def open_docs(self):
        QDesktopServices.openUrl(QUrl(ENGINES[self.engine.currentData()]['link']))
