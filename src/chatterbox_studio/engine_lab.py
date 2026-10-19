"""Local multi-engine voice studio. Chatterbox narration remains independent."""
from __future__ import annotations

from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox,
    QComboBox, QLineEdit, QPushButton, QFileDialog, QPlainTextEdit, QMessageBox,
    QDoubleSpinBox, QScrollArea, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QSplitter,
)

from .optional_engines import (
    ENGINES, EngineRegistry, CharacterStore, EngineError, EngineCancelled,
    clean_request, new_output_path, execute_generation, execute_probe,
)


class OptionalEngineWorker(QObject):
    message = pyqtSignal(str)
    result = pyqtSignal(str, str, float)  # engine, output, elapsed seconds
    failure = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, jobs: list[tuple[dict, str]] | None = None,
                 probe: tuple[str, str, str] | None = None,
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
                engine, exe, repo = self.probe
                result = execute_probe(engine, exe, repo, cancelled=self.cancel_event,
                                       log=self.message.emit, diagnostic_dir=self.diagnostic_dir)
                self.message.emit(f'{ENGINES[engine]["label"]} ready. PyTorch {result["torch"]}, CUDA: {result["cuda_available"]}')
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
    """Qwen3-TTS and IndexTTS runtimes, profiles, and comparison."""
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
        note = QLabel('Chatterbox, Qwen3-TTS and IndexTTS 2.5 are supported speech engines. Qwen3 and IndexTTS use independent Python runtimes and separately downloaded model weights. Run memory-intensive AI jobs one at a time if system memory is limited.')
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
        self.index_py = QLineEdit(self.config['index25']['python'])
        self.index_py.setPlaceholderText('...\\index-tts\\.venv\\Scripts\\python.exe')
        self.index_repo = QLineEdit(self.config['index25']['repo'])
        self.index_repo.setPlaceholderText('Directory containing indextts and checkpoints')
        for title, field, directory in [
            ('Qwen3 Python', self.qwen_py, False),
            ('IndexTTS Python', self.index_py, False),
            ('IndexTTS repository', self.index_repo, True),
        ]:
            r = QHBoxLayout(); r.addWidget(field, 1)
            b = QPushButton('Browse...')
            b.clicked.connect(lambda checked=False, e=field, d=directory: self._browse(e, d))
            r.addWidget(b)
            rform.addRow(title, r)
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
        form = QFormLayout(settings)
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
        self.text.setPlaceholderText('Enter narration for Qwen3-TTS or IndexTTS 2.5. Compare Engines sends the same passage to each engine in sequence.')
        self.text.setMinimumHeight(110)
        self.text.setMaximumHeight(195)
        slayout.addWidget(self.text)
        actions = QHBoxLayout()
        from_narration = QPushButton('Copy text from Narration Studio')
        from_narration.clicked.connect(lambda: self.text.setPlainText(self.host.editor.toPlainText()))
        actions.addWidget(from_narration)
        self.generate = QPushButton('Generate with selected engine')
        self.generate.setObjectName('primary')
        self.generate.clicked.connect(self.generate_selected)
        actions.addWidget(self.generate)
        self.compare = QPushButton('Compare Engines')
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
        for label, function in [
            ('Play selected', self.play_selected),
            ('Stop playback', self.host.player.stop),
            ('Send selected to Bethesda Export', self.send_to_bethesda),
            ('Open exports folder', self.open_folder),
        ]:
            button = QPushButton(label)
            button.clicked.connect(function)
            buttons.addWidget(button)
        result_layout.addLayout(buttons)
        layout.addWidget(results)
        self.status = QLabel('Configure the Python runtime for Qwen3-TTS or IndexTTS 2.5, select Test selected engine, then generate speech.')
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
            path = QFileDialog.getExistingDirectory(self, 'Select IndexTTS repository directory')
        else:
            path, _ = QFileDialog.getOpenFileName(self, 'Select isolated Python interpreter', '', 'Executables (*.exe);;All files (*)')
        if path: field.setText(path)

    def save_runtimes(self):
        self.config = {
            'qwen3': {'python': self.qwen_py.text().strip(), 'repo': ''},
            'index25': {'python': self.index_py.text().strip(), 'repo': self.index_repo.text().strip()},
        }
        try:
            self.registry.save(self.config)
            self.status.setText('Engine runtime paths saved. No installation was performed.')
        except Exception as exc:
            QMessageBox.warning(self, 'Unable to save runtime settings', str(exc))

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
        self.emotion.setEnabled(eng == 'index25')
        self.speed.setEnabled(eng == 'index25')
        self.ref_text.setEnabled(eng == 'qwen3')
        name = self.character.currentText().strip() if hasattr(self, 'character') else ''
        profile = self.profiles.read().get(name, {})
        chosen = profile.get('engines', {}).get(eng, {})
        self._apply_engine_settings(chosen)

    def _apply_engine_settings(self, chosen: dict):
        for combo, value in [
            (self.model, chosen.get('model')),
            (self.language, chosen.get('language')),
            (self.device, chosen.get('device')),
            (self.emotion, chosen.get('emotion')),
        ]:
            index = combo.findData(value)
            if index >= 0: combo.setCurrentIndex(index)
        if 'speed' in chosen:
            self.speed.setValue(float(chosen['speed']))

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
            engines[self.engine.currentData()] = {
                'model': self.model.currentData(), 'language': self.language.currentData(),
                'device': self.device.currentData(), 'emotion': self.emotion.currentData(),
                'speed': self.speed.value(),
            }
            profile = {'preferred_engine': self.engine.currentData(),
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
        voice = self.host.voices.resolve(self.voice.currentData() or '')
        name = character or self.voice.currentText() or 'speaker'
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
        }
        return clean_request(result)

    def _start(self, jobs=None, probe=None):
        plugins = getattr(self.host, 'plugins', None)
        if plugins is not None and plugins.is_busy:
            QMessageBox.information(self, 'Writer running', 'Finish or cancel the writer before starting a voice-engine operation.')
            return
        if self.thread is not None:
            QMessageBox.information(self, 'Engine already running', 'Finish or cancel the current generation first.')
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
        self._start(probe=(engine, entry['python'], entry['repo']))

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
            for engine in ENGINES:
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
        for col, val in enumerate((ENGINES[engine]['label'], model.rsplit('/', 1)[-1], f'{elapsed:.1f}s', str(output))):
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
        self.generate.setEnabled(True); self.compare.setEnabled(True); self.test.setEnabled(True)
        self.cancel.setEnabled(False)

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
        file = self.selected_path()
        if file and file.is_file():
            self.host.bethesda_tab.audio.setText(str(file))
            self.host.tabs.setCurrentWidget(self.host.bethesda_tab)
        else:
            QMessageBox.information(self, 'Select audio', 'Choose a generated recording first.')

    def open_folder(self):
        file = self.selected_path()
        if file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file.parent)))

    def open_docs(self):
        QDesktopServices.openUrl(QUrl(ENGINES[self.engine.currentData()]['link']))
