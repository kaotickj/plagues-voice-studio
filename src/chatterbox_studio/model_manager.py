"""Model Manager tab: installed-model visibility and user-initiated downloads."""
from __future__ import annotations

from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QPlainTextEdit, QMessageBox, QProgressBar, QGroupBox,
)

from .model_downloads import (
    CATALOG, MODELS, chatterbox_status, download_chatterbox,
    qwen_python, qwen_task,
)
from .optional_engines import EngineCancelled


class ModelTask(QObject):
    message = pyqtSignal(str)
    completed = pyqtSignal(str, str)  # Model key, result state
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, key: str, operation: str, storage: Path, python_exe: str):
        super().__init__()
        self.key = key
        self.operation = operation
        self.storage = Path(storage)
        self.python_exe = python_exe
        self.cancelled = Event()

    def stop(self):
        self.cancelled.set()

    @pyqtSlot()
    def run(self):
        try:
            model = MODELS[self.key]
            if model.family == 'chatterbox':
                if self.operation != 'download':
                    raise ValueError('Only download is supported for Chatterbox')
                download_chatterbox(model, self.storage, self.cancelled, self.message.emit)
                result = chatterbox_status(self.storage, model)
            else:
                cached = qwen_task(model, self.python_exe, self.operation, self.cancelled,
                                   self.message.emit, self.storage / 'engine_logs')
                result = 'Cached in Qwen environment' if cached else 'No cached snapshot found'
            self.completed.emit(self.key, result)
        except EngineCancelled as exc:
            self.message.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ModelManager(QWidget):
    """No extra menus or changes to the existing Help/About visual design."""
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setObjectName('model_manager')
        self.thread: QThread | None = None
        self.worker: ModelTask | None = None
        self._states: dict[str, str] = {}
        self._build()
        self.refresh()

    @property
    def is_busy(self) -> bool:
        return self.thread is not None

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        header = QLabel('MODEL MANAGER')
        header.setObjectName('sectionTitle')
        outer.addWidget(header)
        intro = QLabel('Download speech models when you need them. Chatterbox models are saved in your user data folder. '
                       'Qwen3-TTS uses its independently configured Python environment and Hugging Face cache. '
                       'IndexTTS 2.5 is supported via Voice Engines; install its separate runtime and checkpoints as described in Help.')
        intro.setWordWrap(True)
        outer.addWidget(intro)

        group = QGroupBox('Model selection and availability')
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.model = QComboBox()
        self.model.setObjectName('model_manager_choice')
        self.model.setAccessibleName('Model to download or check')
        for item in CATALOG:
            self.model.addItem(item.label, item.key)
        self.model.currentIndexChanged.connect(self._show_model)
        row.addWidget(self.model, 1)
        self.refresh_button = QPushButton('Refresh status')
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setObjectName('model_manager_status')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.destination = QLabel()
        self.destination.setObjectName('mutedText')
        self.destination.setWordWrap(True)
        layout.addWidget(self.destination)
        outer.addWidget(group)

        controls = QHBoxLayout()
        self.download = QPushButton('Download selected model')
        self.download.setObjectName('primary')
        self.download.clicked.connect(self.install_selected)
        controls.addWidget(self.download)
        self.check = QPushButton('Check Qwen cache')
        self.check.clicked.connect(self.check_cache)
        controls.addWidget(self.check)
        self.stop_button = QPushButton('Stop')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        outer.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat('Idle')
        outer.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setObjectName('model_manager_log')
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('Download and cache-check diagnostics appear here.')
        outer.addWidget(self.log, 1)
        note = QLabel('Downloads require internet access and free disk space. You control when models are fetched. '
                      'Stopping a Qwen transfer terminates its subprocess. Stopping a Chatterbox transfer takes '
                      'effect after the current Hugging Face transfer. Partially downloaded files may be resumed.')
        note.setObjectName('mutedText')
        note.setWordWrap(True)
        outer.addWidget(note)

    def refresh(self):
        for entry in CATALOG:
            if entry.family == 'chatterbox':
                self._states[entry.key] = chatterbox_status(self.host.storage, entry)
        self._show_model()

    def _show_model(self, *_):
        key = self.model.currentData()
        if not key:
            return
        selected = MODELS[key]
        if selected.family == 'chatterbox':
            state = self._states.get(key, 'Download available')
            from .model_downloads import user_model_directory
            folder = user_model_directory(self.host.storage, key)
            self.destination.setText(f'Per-user model directory: {folder}')
            self.check.setEnabled(False)
        else:
            python = qwen_python(self.host.storage)
            state = self._states.get(key, 'Cache not checked' if python else 'Qwen runtime not configured')
            self.destination.setText('Qwen Python: ' + (python or 'Not found. Configure the runtime under Voice Engines first.'))
            self.check.setEnabled(not self.is_busy and bool(python))
        self.status.setText(f'{selected.label}: {state}')
        self.download.setEnabled(not self.is_busy and (
            (selected.family == 'chatterbox' and state == 'Download available') or
            (selected.family == 'qwen3' and bool(qwen_python(self.host.storage)))))

    def _start(self, operation: str):
        plugins = getattr(self.host, 'plugins', None)
        if plugins is not None and plugins.is_busy:
            QMessageBox.information(self, 'Writer running', 'Finish or cancel the writer before starting model operations.')
            return
        if self.is_busy:
            return
        key = self.model.currentData()
        entry = MODELS[key]
        python = qwen_python(self.host.storage) if entry.family == 'qwen3' else ''
        if entry.family == 'qwen3' and not python:
            QMessageBox.warning(self, 'Qwen runtime missing',
                'Configure the Qwen Python executable in Voice Engines before downloading its models.')
            return
        if operation == 'download':
            answer = QMessageBox.question(self, 'Download model',
                f'Download {entry.label} from {entry.repo}? This requires internet access and may use several GB of disk space.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.thread = QThread(self)
        self.worker = ModelTask(key, operation, self.host.storage, python)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.message.connect(self._message)
        self.worker.completed.connect(self._complete)
        self.worker.failed.connect(self._fail)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.download.setEnabled(False)
        self.check.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.model.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat('Working...')
        self.log.clear()
        self._message(f'Starting {operation} for {entry.label}.')
        self.thread.start()

    def install_selected(self):
        self._start('download')

    def check_cache(self):
        if MODELS[self.model.currentData()].family == 'qwen3':
            self._start('check')

    def _message(self, message: str):
        for line in str(message).splitlines():
            if line.strip():
                self.log.appendPlainText(line[-800:])

    def _complete(self, key: str, result: str):
        self._states[key] = result
        self._message(f'Finished: {result}')
        self._show_model()

    def _fail(self, message: str):
        self._message('Failed: ' + message)
        QMessageBox.warning(self, 'Model Manager', message[-1200:])

    def _finished(self):
        self.thread = None
        self.worker = None
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat('Idle')
        self.refresh_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.model.setEnabled(True)
        self.refresh()

    def stop(self):
        if self.worker is not None:
            self.worker.stop()
            self._message('Stop requested. Waiting for the current operation to finish safely...')
            self.stop_button.setEnabled(False)
