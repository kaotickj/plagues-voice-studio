"""Unbranded promotional writing panel embedded by Voice Studio."""
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget)
from PyQt6.QtCore import Qt
from writer_core.downloads import Cancelled
from writer_core.runtime import WriterRuntime
from writer_core.settings import default_settings, existing_runtime_settings, load_settings
from writer_core.setup_dialog import SetupDialog
from .prompts import CopyRequest, RECIPES, TONES, build_messages
from .advertisers import AdvertiserLibrary
from .advertiser_dialog import AdvertiserDialog
from writer_core.downloads import MODELS
from plagued_ai import app_dir, find_writer_model


class WriteWorker(QObject):
    text = pyqtSignal(str)
    status = pyqtSignal(str)
    success = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, runtime, request):
        super().__init__()
        self.runtime, self.request = runtime, request

    @pyqtSlot()
    def run(self):
        try:
            result = self.runtime.generate_messages(build_messages(self.request), self.request.words,
                         on_text=self.text.emit, status=self.status.emit)
            self.success.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class PromotionalWriter(QWidget):
    def __init__(self, context):
        super().__init__(context.parent)
        arrow = (Path(__file__).resolve().parent / 'dropdown.svg').as_posix()
        self.setStyleSheet('QComboBox {padding-right:32px;} '
            'QComboBox::drop-down {width:28px; border-left:1px solid #4b7255; background:#273d30;} '
            f'QComboBox::down-arrow {{image:url("{arrow}"); width:12px; height:8px;}} '
            'QPushButton#primary:disabled {background:#1e2924; color:#8a9d90; border-color:#37483c;} '
            'QCheckBox {background:transparent; spacing:7px;} '
            'QCheckBox::indicator {width:16px; height:16px; border:1px solid #7baa80; border-radius:3px; background:#0e1716;} '
            'QCheckBox::indicator:checked {background:#8ceba0; border:2px solid #b4ffc3;}')
        self.context = context
        self.data_dir = Path(context.data_dir)
        self.thread = self.worker = self.runtime = None
        self.setup_dialog = None
        self.advertiser_dialog = None
        self.advertisers = AdvertiserLibrary(self.data_dir)
        self._prior_text = ''; self._stream = ''; self._result = None
        self._prior_review = False
        self.settings = default_settings()
        settings_error = ''
        try:
            settings_path = self.data_dir / 'ai_studio.json'
            if settings_path.exists():
                self.settings = load_settings(settings_path)
            else:
                # Import only runtime preferences, never DJ profile/lore or drafts.
                prior = app_dir('dj-writer')/'ai_studio.json'
                previous = existing_runtime_settings(prior if prior.is_file() else Path.home() / '.goodneighbor_blues_dj' / 'ai_studio.json')
                if previous:
                    self.settings = previous
        except (OSError, ValueError, TypeError) as exc:
            settings_error = f'Could not read writer setup: {exc}. Saved files were not changed.'
        if not Path(self.settings['model_path']).is_file():
            for folder in (find_writer_model(self.data_dir, MODELS['gemma-writer']['filename']).parent, self.data_dir/'ai_writer'/'models',Path.home()/'.goodneighbor_blues_dj'/'ai_writer'/'models'):
                candidate=folder/MODELS['gemma-writer']['filename']
                if candidate.is_file():
                    self.settings.update(model_path=str(candidate),model_preset='gemma-writer');break
        self.interview_settings = dict(self.settings)
        try:
            interview_path = self.data_dir / 'interview' / 'ai_studio.json'
            if interview_path.exists():self.interview_settings = load_settings(interview_path)
            else:
                for folder in (find_writer_model(self.data_dir, MODELS['qwen-small']['filename']).parent, Path(self.settings['model_path']).parent, self.data_dir/'ai_writer'/'models', Path.home()/'.goodneighbor_blues_dj'/'ai_writer'/'models'):
                    candidate = folder / MODELS['qwen-small']['filename']
                    if candidate.is_file():
                        self.interview_settings.update(model_path=str(candidate),model_preset='qwen-small',context_size=8192);break
        except (OSError,ValueError) as exc:settings_error += ' Interview setup: '+str(exc)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(7)
        heading = QHBoxLayout()
        title = QLabel('Promotional Writer'); title.setObjectName('sectionTitle'); heading.addWidget(title)
        heading.addStretch()
        self.setup_button = QPushButton('Writing model…'); self.setup_button.clicked.connect(self.open_setup)
        help_button = QPushButton('Help / About'); help_button.clicked.connect(self.show_help)
        self.interview_setup_button = QPushButton('Interview model…');self.interview_setup_button.clicked.connect(self.open_interview_setup)
        heading.addWidget(self.setup_button); heading.addWidget(self.interview_setup_button); heading.addWidget(help_button); layout.addLayout(heading)
        self.model_label = QLabel(); self.model_label.setWordWrap(True); self.model_label.setObjectName('mutedText')
        layout.addWidget(self.model_label)
        advertiser_row = QHBoxLayout()
        advertiser_row.addWidget(QLabel('Advertiser'))
        self.advertiser = QComboBox();self.advertiser.setMinimumContentsLength(20);self.advertiser.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);advertiser_row.addWidget(self.advertiser,1)
        self.profile_button = QPushButton('Profile / interview…');self.profile_button.clicked.connect(self.open_advertiser)
        advertiser_row.addWidget(self.profile_button);layout.addLayout(advertiser_row)
        try:self.reload_advertisers()
        except (OSError,ValueError) as exc:settings_error += ' Advertiser library: '+str(exc)

        self.brief_group = QGroupBox('1 · Writing brief'); form = QGridLayout(self.brief_group)
        self.category = QComboBox(); self.category.addItems(RECIPES)
        self.tone = QComboBox(); self.tone.addItems(TONES)
        for combo in (self.category, self.tone):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        self.words = QSpinBox(); self.words.setRange(10, 2000); self.words.setValue(120); self.words.setSingleStep(10)
        self.product = QLineEdit(); self.product.setPlaceholderText('Product, service, event or organization')
        self.audience = QLineEdit(); self.audience.setPlaceholderText('Who should this reach?')
        self.cta = QLineEdit(); self.cta.setPlaceholderText('Exact next step; include a URL or contact only if supplied')
        for col, (label, control) in enumerate((('Format', self.category), ('Tone', self.tone), ('Words', self.words))):
            form.addWidget(QLabel(label), 0, col*2); form.addWidget(control, 0, col*2+1)
        form.addWidget(QLabel('Product'), 1, 0); form.addWidget(self.product, 1, 1, 1, 2)
        form.addWidget(QLabel('Audience'), 1, 3); form.addWidget(self.audience, 1, 4, 1, 2)
        form.addWidget(QLabel('Call to action'), 2, 0); form.addWidget(self.cta, 2, 1, 1, 5)
        for col in (1, 3, 5): form.setColumnStretch(col, 1)
        layout.addWidget(self.brief_group)

        self.output_group = QGroupBox('2 · Draft and narration handoff'); output_layout = QVBoxLayout(self.output_group)
        toolbar = QHBoxLayout()
        self.generate_button = QPushButton('Write draft'); self.generate_button.setObjectName('primary')
        self.generate_button.clicked.connect(self.generate)
        self.cancel_button = QPushButton('Cancel'); self.cancel_button.setEnabled(False); self.cancel_button.clicked.connect(self.cancel)
        self.count = QLabel('0 words'); self.count.setObjectName('mutedText')
        toolbar.addWidget(self.generate_button); toolbar.addWidget(self.cancel_button); toolbar.addStretch(); toolbar.addWidget(self.count)
        output_layout.addLayout(toolbar)
        self.output = QPlainTextEdit(); self.output.setMinimumHeight(90)
        self.output.setPlaceholderText('Your draft appears here. Edit and review its claims before export or narration.')
        output_layout.addWidget(self.output, 1)
        handoff = QHBoxLayout()
        self.reviewed = QCheckBox('Reviewed for narration')
        self.reviewed.setToolTip('Check factual claims, offer details, pronunciation and spoken wording. Editing clears approval.')
        self.copy_button = QPushButton('Copy'); self.copy_button.clicked.connect(self.copy)
        self.export_button = QPushButton('Export text…'); self.export_button.clicked.connect(self.export_text)
        self.send_button = QPushButton('Send to Voice Studio'); self.send_button.setObjectName('primary')
        self.send_button.clicked.connect(self.send_to_studio)
        handoff.addWidget(self.reviewed); handoff.addStretch()
        for button in (self.copy_button, self.export_button, self.send_button): handoff.addWidget(button)
        output_layout.addLayout(handoff)
        note = QLabel('Draft copy: check the facts and offer terms. Review approval is required for narration handoff.')
        note.setWordWrap(True); note.setObjectName('mutedText'); output_layout.addWidget(note)
        layout.addWidget(self.output_group, 1)

        self.source_group = QGroupBox('3 · Source material and custom direction'); source_layout = QHBoxLayout(self.source_group)
        self.facts = QPlainTextEdit(); self.facts.setMinimumHeight(65); self.facts.setMaximumHeight(150)
        self.facts.setPlaceholderText('SUPPLIED FACTS / OFFER\nFeatures, benefits, price, dates, terms and required wording. The writer must not invent missing facts.')
        self.instructions = QPlainTextEdit(); self.instructions.setMinimumHeight(65); self.instructions.setMaximumHeight(150)
        self.instructions.setPlaceholderText('CUSTOM PROMPT / DIRECTION\nAngle, length constraints, wording to avoid or a complete custom writing request.')
        source_layout.addWidget(self.facts, 1); source_layout.addWidget(self.instructions, 1)
        layout.addWidget(self.source_group)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setObjectName('mutedText'); layout.addWidget(self.status)
        self.preview_timer = QTimer(self); self.preview_timer.setInterval(100); self.preview_timer.timeout.connect(self.flush_stream)
        self.output.textChanged.connect(self.on_edit); self.reviewed.toggled.connect(self.update_actions)
        self.category.currentTextChanged.connect(self.category_changed)
        self.refresh_model(); self.update_actions()
        if settings_error: self.status.setText(settings_error)

    @property
    def is_busy(self):
        return (self.thread is not None or bool(self.setup_dialog and self.setup_dialog.thread is not None)
                or bool(self.advertiser_dialog and self.advertiser_dialog.is_busy))

    def refresh_model(self):
        model = Path(self.settings['model_path'])
        self.model_label.setText(f'Writing model: {model.name} · {self.settings["backend"]}' if model.is_file()
                                else 'Select or download a writing model in Model setup. Writing runs locally after setup.')
        self.model_label.setText(self.model_label.text()+' | Interview: '+Path(self.interview_settings['model_path']).name)

    def reload_advertisers(self, selected=''):
        self.advertiser.clear();self.advertiser.addItem('No saved advertiser / one-off brief','')
        self.advertiser_rows=self.advertisers.load()
        for row in self.advertiser_rows:self.advertiser.addItem(row['name'],row['id'])
        self.advertiser.setCurrentIndex(max(0,self.advertiser.findData(selected)))

    def selected_profile(self):
        return next((r for r in self.advertiser_rows if r['id']==self.advertiser.currentData()),{})

    def open_advertiser(self):
        if self.is_busy:return
        try:dialog=AdvertiserDialog(self.context,self.interview_settings,self.facts.toPlainText()+' '+self.instructions.toPlainText(),self.advertiser.currentData(),self)
        except (OSError,ValueError) as exc:self.status.setText(str(exc));return
        self.advertiser_dialog=dialog
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.reload_advertisers(dialog.profile['id'])
            for answer in dialog.session_answers:
                self.facts.appendPlainText(answer['question']+' '+answer['answer'])
        self.advertiser_dialog=None;dialog.deleteLater();self.update_actions()

    def open_interview_setup(self):
        if self.is_busy:return
        dialog=SetupDialog(self.interview_settings,self.data_dir/'interview',self)
        self.setup_dialog=dialog
        if dialog.exec()==QDialog.DialogCode.Accepted:self.interview_settings=dialog.settings
        self.setup_dialog=None;dialog.deleteLater();self.refresh_model()

    def category_changed(self, category):
        self.words.setValue(10 if category == 'Tagline' else 120)

    def request(self):
        profile=self.selected_profile()
        return CopyRequest(self.category.currentText(), self.tone.currentText(), self.words.value(),
                           self.product.text() or profile.get('description','') or profile.get('name',''), self.audience.text() or profile.get('audience',''), self.facts.toPlainText(),
                           self.cta.text() or profile.get('cta',''), self.instructions.toPlainText(),
                           self.advertisers.context(profile) if profile else '')

    def on_edit(self):
        self.reviewed.setChecked(False)
        self.count.setText(f'{len(self.output.toPlainText().split())} words')
        self.update_actions()

    def update_actions(self):
        busy = self.is_busy
        text = bool(self.output.toPlainText().strip())
        self.copy_button.setEnabled(text and not busy)
        self.export_button.setEnabled(text and not busy)
        self.send_button.setEnabled(text and self.reviewed.isChecked() and not busy)
        self.reviewed.setEnabled(not busy)

    def set_busy(self, busy):
        for widget in (self.brief_group, self.source_group, self.setup_button, self.interview_setup_button, self.advertiser, self.profile_button, self.generate_button):
            widget.setEnabled(not busy)
        self.output.setReadOnly(busy); self.cancel_button.setEnabled(busy)
        self.update_actions()

    def open_setup(self):
        if self.is_busy: return
        dialog = SetupDialog(self.settings, self.data_dir, self)
        self.setup_dialog = dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings; self.refresh_model()
        self.setup_dialog = None
        dialog.deleteLater(); self.update_actions()

    def generate(self):
        if self.is_busy: return
        reason = self.context.can_generate()
        if reason:
            self.status.setText(reason); return
        profile=self.selected_profile()
        if profile and not (profile.get('description') or profile.get('facts') or self.facts.toPlainText().strip()):
            self.status.setText('Describe this advertiser’s offer before drafting. The interview can help fill the gaps.')
            self.open_advertiser();return
        request = self.request()
        try:
            build_messages(request)
            runtime = WriterRuntime(self.settings, self.data_dir)
            runtime._paths()
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc)); return
        self.runtime = runtime
        self._prior_text = self.output.toPlainText(); self._prior_review = self.reviewed.isChecked()
        self._stream = ''; self._result = None
        self.reviewed.setChecked(False)
        self.thread = QThread(self); self.worker = WriteWorker(runtime, request)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.text.connect(self.append_text); self.worker.status.connect(self.status.setText)
        self.worker.success.connect(self.completed); self.worker.error.connect(self.failed)
        self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.finished); self.thread.finished.connect(self.thread.deleteLater)
        self.set_busy(True); self.preview_timer.start(); self.status.setText('Starting local writing model…')
        self.thread.start()

    @pyqtSlot(str)
    def append_text(self, text):
        self._stream += text

    def flush_stream(self):
        if self.thread and self._stream and self.output.toPlainText() != self._stream:
            self.output.setPlainText(self._stream)

    @pyqtSlot(dict)
    def completed(self, result):
        self.preview_timer.stop(); self._result = result
        self.output.setPlainText(result['text'])
        timings = (f' Load {result["load_seconds"]}s; first text {result["first_text_seconds"]}s; CPU threads {result["generation_threads"]}/{result["prompt_threads"]}.' if 'load_seconds' in result else '')
        self.status.setText(f'Draft ready · {result["model"]} · {result["elapsed_seconds"]}s. Review before narration.'+timings)

    @pyqtSlot(str)
    def failed(self, message):
        self.preview_timer.stop(); self.output.setPlainText(self._prior_text)
        self.reviewed.setChecked(self._prior_review)
        self.status.setText(message)

    @pyqtSlot()
    def finished(self):
        self.preview_timer.stop(); self.thread = self.worker = self.runtime = None
        self.set_busy(False)

    def cancel(self):
        if self.advertiser_dialog:self.advertiser_dialog.cancel()
        if self.runtime:
            self.runtime.cancel(); self.status.setText('Stopping writer; waiting for its model process to exit…')
        if self.setup_dialog and self.setup_dialog.thread:
            self.setup_dialog.cancel_download()

    def copy(self):
        if not self.is_busy:
            QApplication.clipboard().setText(self.output.toPlainText())
            self.status.setText('Copied draft text.')

    def export_text(self):
        if self.is_busy or not self.output.toPlainText().strip(): return
        filename, _ = QFileDialog.getSaveFileName(self, 'Export copy', 'promotional-copy.txt', 'Text (*.txt)')
        if filename:
            try:
                Path(filename).write_text(self.output.toPlainText(), encoding='utf-8')
                self.status.setText('Exported editable copy. Review before narration.')
            except OSError as exc:
                QMessageBox.warning(self, 'Export failed', str(exc))

    def send_to_studio(self):
        if self.is_busy or not self.reviewed.isChecked() or not self.output.toPlainText().strip(): return
        if self.context.handoff(self.output.toPlainText()):
            self.status.setText('Reviewed text sent to Voice Studio. Speech generation starts only when you choose Generate.')

    def show_help(self):
        QMessageBox.information(self, 'Promotional Writer · Help and credits',
            'Choose a format, audience and tone. Supply the product facts and call to action, '
            'then write a draft. Custom prompt accepts your own writing instructions.\n\n'
            'The model can invent claims: review prices, dates, offer terms and all other facts. '
            'Editing clears narration approval. Copy/export are available for draft editing; '
            'Send to Voice Studio requires review and asks before replacing existing text.\n\n'
            'Local inference: llama.cpp (ggml community). Models: Gemma-based community GGUF / Qwen; '
            'their upstream licenses apply. Plugin by Kaotick Jay / Plagued Mods. '
            'Model files remain at their selected paths. No model weights are bundled.')
