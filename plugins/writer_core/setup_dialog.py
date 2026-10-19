"""Shared model setup UI, independent of either writing product."""
from copy import deepcopy
from pathlib import Path
import os
import platform
import threading
import time
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget)
from .downloads import Cancelled, MODELS, install_runtime, install_model
from .settings import save_settings

class DownloadWorker(QObject):
    progress = pyqtSignal(int, int, str)
    success = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, data_dir, operation, selection):
        super().__init__()
        self.data_dir, self.operation, self.selection = data_dir, operation, selection
        self.cancelled = threading.Event()
        self._last_progress = 0

    def report(self, done, total, message):
        now = time.monotonic()
        # Qt signals use signed 32-bit ints. Report MiB for the 5.64 GB model.
        if now - self._last_progress > .15 or done == total or total == 0:
            self.progress.emit(done // (1024 * 1024), total // (1024 * 1024), message)
            self._last_progress = now

    @pyqtSlot()
    def run(self):
        try:
            if self.operation == 'runtime':
                result = install_runtime(self.data_dir, self.selection, self.cancelled, self.report)
            else:
                result = install_model(self.data_dir, self.cancelled, self.report, self.selection)
            self.success.emit(result)
        except Cancelled:
            self.error.emit('Download cancelled. Partial downloads are kept for Resume.')
        except Exception as exc:
            if self.cancelled.is_set():
                self.error.emit('Download cancelled. Partial downloads are kept for Resume.')
            else:
                self.error.emit(f'{exc}\nRetry resumes an interrupted download. Check internet access and free disk space.')
        finally:
            self.finished.emit()


class SetupDialog(QDialog):
    def __init__(self, settings, data_dir, parent=None, save_callback=save_settings):
        super().__init__(parent)
        self.setWindowTitle('AI Setup | Separate local script writer')
        self.resize(830, 590)
        self.settings = deepcopy(settings)
        self.save_callback = save_callback
        self.data_dir = Path(data_dir)
        self.thread = self.worker = None
        self._operation = None
        layout = QVBoxLayout(self)
        introduction = QLabel(
            'Writing uses its own llama.cpp runtime and a text-generation GGUF. '
            'Voice Studio’s Qwen3-TTS speech weights cannot write scripts. '
            'After setup, writing runs locally without internet.')
        introduction.setWordWrap(True); layout.addWidget(introduction)
        form = QFormLayout()
        self.preset = QComboBox()
        for key, model in MODELS.items():
            self.preset.addItem(model['label'], key)
        self.preset.addItem('Other compatible GGUF (choose existing file)', 'custom')
        self.preset.setCurrentIndex(max(0, self.preset.findData(settings.get('model_preset', 'gemma-writer'))))
        form.addRow('Writing model', self.preset)
        self.model_note = QLabel(); self.model_note.setWordWrap(True)
        form.addRow('', self.model_note)
        self.backend = QComboBox(); self.backend.addItems(['CPU', 'Vulkan'])
        self.backend.setCurrentText(settings['backend'])
        form.addRow('Hardware', self.backend)
        backend_note = QLabel('CPU is the baseline. Vulkan is optional for AMD GPUs and still needs testing on your machine.')
        backend_note.setWordWrap(True); form.addRow('', backend_note)
        self.server = QLineEdit(settings['server_path'])
        form.addRow('llama-server', self.path_row(self.server, False))
        self.model = QLineEdit(settings['model_path'])
        form.addRow('GGUF model', self.path_row(self.model, True))
        self.context = QSpinBox(); self.context.setRange(1024, 32768); self.context.setSingleStep(1024)
        self.context.setValue(settings.get('context_size', 8192))
        form.addRow('Context tokens', self.context)
        self.cpu_threads = QSpinBox(); self.cpu_threads.setRange(1, 32)
        self.cpu_threads.setValue(settings.get('cpu_threads', min(12, max(1, os.cpu_count() or 4))))
        self.cpu_threads.setToolTip('llama.cpp CPU inference threads. Start near physical core count; higher can be slower. Applies to one script, not parallel drafts.')
        form.addRow('CPU inference threads', self.cpu_threads)
        self.disable_repack = QCheckBox('Disable weight repacking (--no-repack, recommended for 9B)')
        self.disable_repack.setChecked(settings.get('disable_repack', True))
        self.disable_repack.setToolTip(
            'Avoids large extra CPU_REPACK allocations during model loading. '
            'Usually improves startup reliability; enabling repacking can be faster if you have enough memory.')
        form.addRow('Memory compatibility', self.disable_repack)
        self.cache_mode = QComboBox()
        self.cache_mode.addItem('Balanced: Q8 keys, F16 values (recommended)', 'balanced')
        self.cache_mode.addItem('Standard: F16 keys and values (more memory)', 'standard')
        self.cache_mode.addItem('Compact: Q8 keys and values (requires flash attention)', 'compact')
        self.cache_mode.setCurrentIndex(max(0, self.cache_mode.findData(settings.get('kv_cache_mode', 'balanced'))))
        self.cache_mode.setToolTip('Balanced reduces KV-cache memory without requiring quantized V support. Compact can save more memory but may fail on some backends.')
        form.addRow('KV-cache memory', self.cache_mode)
        self.auto_recover = QCheckBox('Retry with smaller context after KV-cache allocation failure')
        self.auto_recover.setChecked(settings.get('auto_memory_recovery', True))
        self.auto_recover.setToolTip('Restarts only this writer server using successively smaller contexts; the configured value is never overwritten. Very long scripts may no longer fit.')
        form.addRow('Automatic recovery', self.auto_recover)
        self.context.setToolTip('Context length is a major memory cost. For troubleshooting, use 4,096 or 2,048. Long drafts need more tokens. Gemma is trained for 8,192.')
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.install_button = QPushButton('Install writing runtime'); self.install_button.clicked.connect(self.download_runtime)
        self.download_button = QPushButton('Download / resume model'); self.download_button.clicked.connect(self.download_model)
        buttons.addWidget(self.install_button); buttons.addWidget(self.download_button); layout.addLayout(buttons)
        self.state = QLabel('Choose an existing compatible GGUF to reuse it, or download a model above.')
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); layout.addWidget(self.progress)
        self.cancel_button = QPushButton('Cancel download'); self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_download); layout.addWidget(self.cancel_button)
        sources = QLabel('Models: <a style="color:#badb8a" href="https://huggingface.co/DavidAU/Gemma-The-Writer-Mighty-Sword-9B-GGUF">Gemma The Writer</a> '
                         ' · <a style="color:#badb8a" href="https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF">Qwen3 Instruct</a>'
                         ' · Runtime: <a style="color:#badb8a" href="https://github.com/ggml-org/llama.cpp">llama.cpp</a>')
        sources.setOpenExternalLinks(True); layout.addWidget(sources)
        footer = QHBoxLayout(); footer.addStretch()
        self.save_button = QPushButton('Save setup'); self.save_button.clicked.connect(self.commit)
        self.close_button = QPushButton('Close'); self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.save_button); footer.addWidget(self.close_button); layout.addLayout(footer)
        self.preset.currentIndexChanged.connect(self.preset_changed)
        self.backend.currentTextChanged.connect(self.update_controls)
        self.update_controls()

    def path_row(self, field, model):
        row = QWidget(); line = QHBoxLayout(row); line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(field, 1)
        button = QPushButton('Browse')
        button.clicked.connect(lambda: self.browse(field, model)); line.addWidget(button)
        return row

    def browse(self, field, model):
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose GGUF writing model' if model else 'Choose llama-server',
                                                 field.text(), 'GGUF model (*.gguf)' if model else 'All files (*)')
        if filename:
            field.setText(filename)

    def preset_changed(self):
        model = MODELS.get(self.preset.currentData())
        if model:
            self.context.setValue(model['context'])
            candidate = self.data_dir / 'ai_writer' / 'models' / model['filename']
            self.model.setText(str(candidate) if candidate.is_file() else '')
        self.update_controls()

    def update_controls(self):
        model = MODELS.get(self.preset.currentData())
        if model:
            self.model_note.setText(f'{model["size"] / 1e9:.2f} GB download, plus runtime and working memory. '
                                    'Community GGUF; download is verified against a pinned SHA-256.')
        else:
            self.model_note.setText('Use a text-writing model supported by this llama.cpp version, with a chat template. '
                                    'Select its native context size. Other models require separate validation.')
        busy = self.thread is not None
        self.install_button.setEnabled(not busy and platform.system() in ('Windows', 'Linux') and platform.machine().lower() in ('amd64', 'x86_64'))
        self.download_button.setEnabled(not busy and model is not None)
        for control in (self.preset, self.backend, self.context, self.cpu_threads, self.disable_repack, self.cache_mode, self.auto_recover, self.server, self.model, self.save_button, self.close_button):
            control.setEnabled(not busy)
        self.server.parentWidget().setEnabled(not busy)
        self.model.parentWidget().setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    def download_runtime(self):
        if platform.system() == 'Windows':
            variant = 'windows-vulkan' if self.backend.currentText() == 'Vulkan' else 'windows-cpu'
        elif self.backend.currentText() == 'Vulkan':
            self.state.setText('The Linux installer supplies CPU binaries. Select your own Vulkan llama-server or choose CPU.')
            return
        else:
            variant = 'linux-cpu'
        self.begin('runtime', variant)

    def download_model(self):
        self.begin('model', self.preset.currentData())

    def begin(self, operation, selection):
        if self.thread is not None:
            return
        self._operation = operation
        self.thread = QThread(self)
        self.worker = DownloadWorker(self.data_dir, operation, selection)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.success.connect(self.on_success)
        self.worker.error.connect(self.state.setText)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.on_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.progress.setRange(0, 0)
        self.state.setText('Connecting to download source...')
        self.update_controls()
        self.thread.start()

    @pyqtSlot(int, int, str)
    def on_progress(self, done, total, message):
        self.progress.setRange(0, total if total else 0)
        self.progress.setValue(done)
        self.state.setText(f'{message}\n{done:,} / {total:,} MiB' if total else message)

    @pyqtSlot(str)
    def on_success(self, path):
        (self.server if self._operation == 'runtime' else self.model).setText(path)
        self.state.setText('Ready. Save setup when the runtime and model paths are both selected.')
        self.progress.setRange(0, 100); self.progress.setValue(100)

    @pyqtSlot()
    def on_finished(self):
        self.thread = self.worker = None
        self.update_controls()

    def cancel_download(self):
        if self.worker:
            self.worker.cancelled.set()
            self.cancel_button.setEnabled(False)
            self.state.setText('Stopping download. A stalled network request may take up to 30 seconds to return.')

    def commit(self):
        if self.thread is not None:
            return
        candidate = deepcopy(self.settings)
        candidate.update(server_path=self.server.text().strip(), model_path=self.model.text().strip(),
                         model_preset=self.preset.currentData(), backend=self.backend.currentText(),
                         context_size=self.context.value(), cpu_threads=self.cpu_threads.value(),
                         disable_repack=self.disable_repack.isChecked(), kv_cache_mode=self.cache_mode.currentData(),
                         auto_memory_recovery=self.auto_recover.isChecked())
        if candidate['server_path'] and not Path(candidate['server_path']).is_file():
            QMessageBox.warning(self, 'Runtime path', 'Select the llama-server executable, keeping its DLLs/libraries beside it.'); return
        if candidate['model_path'] and (not Path(candidate['model_path']).is_file() or Path(candidate['model_path']).suffix.lower() != '.gguf'):
            QMessageBox.warning(self, 'Model path', 'Select a text-writing .gguf model file.'); return
        if self.preset.currentData() == 'gemma-writer' and self.context.value() > 8192:
            QMessageBox.warning(self, 'Model context', 'Gemma The Writer’s native context is 8,192 tokens. Use that value for this preset.'); return
        try:
            self.save_callback(self.data_dir / 'ai_studio.json', candidate)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Cannot save AI setup', str(exc)); return
        self.settings = candidate
        self.accept()

    def reject(self):
        if self.thread is not None:
            self.cancel_download()
            return
        super().reject()

    def closeEvent(self, event):
        if self.thread is not None:
            self.cancel_download(); event.ignore()
        else:
            event.accept()
