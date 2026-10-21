"""Qt controls and background jobs for the separate local writing engine."""
from copy import deepcopy
from pathlib import Path
import os
import platform
import threading
import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from speech_director import clean_spoken_text
from lore_library import LoreLibrary
from character_library import CharacterLibrary
from spot_templates import (templates_for, resolve_template, checked_terms, context as spot_context,
                            prepared_copy, load_terms, save_terms)
from lore_dialog import LoreDialog
from ai_writer import (Cancelled, DEFAULT_PROFILES, LocalWriter, MODELS, ScriptRequest,
                       build_messages, install_model, install_runtime, save_settings, station_for)


from writer_core.setup_dialog import SetupDialog as SharedSetupDialog, DownloadWorker

class SetupDialog(SharedSetupDialog):
    def __init__(self, settings, data_dir, parent=None):
        super().__init__(settings, data_dir, parent, save_callback=save_settings)


class ProfilesDialog(QDialog):
    def __init__(self, settings, data_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle('DJ profiles, lore and continuity')
        self.resize(820, 680)
        self.settings = deepcopy(settings)
        self.data_dir = Path(data_dir)
        layout = QVBoxLayout(self)
        note = QLabel('Continuity is maintained by you. New model inventions never become saved facts automatically. '
                      'Label observations, rumors, disproven theories and unresolved threads separately.')
        note.setWordWrap(True); layout.addWidget(note)
        tabs = QTabWidget(); layout.addWidget(tabs, 1)
        self.profiles = {}; self.continuity = {}
        for name in DEFAULT_PROFILES:
            page = QWidget(); box = QVBoxLayout(page)
            box.addWidget(QLabel('Voice and character profile (up to 2,000 characters)'))
            profile = QTextEdit(); profile.setAcceptRichText(False); profile.setPlainText(settings['profiles'][name])
            box.addWidget(profile, 1); self.profiles[name] = profile
            box.addWidget(QLabel('Episode continuity and case notes (up to 6,000 characters)'))
            continuity = QTextEdit(); continuity.setAcceptRichText(False); continuity.setPlainText(settings['continuity'][name])
            continuity.setPlaceholderText('Observed facts:\nRumors / theories:\nDisproven:\nUnresolved threads:')
            box.addWidget(continuity, 2); self.continuity[name] = continuity
            tabs.addTab(page, name)
        page = QWidget(); box = QVBoxLayout(page)
        box.addWidget(QLabel('Shared setting and lore (up to 4,000 characters)'))
        self.lore = QTextEdit(); self.lore.setAcceptRichText(False); self.lore.setPlainText(settings['lore'])
        box.addWidget(self.lore); tabs.addTab(page, 'Shared lore')
        footer = QHBoxLayout(); footer.addStretch()
        save = QPushButton('Save profiles'); save.clicked.connect(self.commit)
        cancel = QPushButton('Cancel'); cancel.clicked.connect(self.reject)
        footer.addWidget(save); footer.addWidget(cancel); layout.addLayout(footer)

    def commit(self):
        candidate = deepcopy(self.settings)
        candidate['profiles'] = {name: field.toPlainText() for name, field in self.profiles.items()}
        candidate['continuity'] = {name: field.toPlainText() for name, field in self.continuity.items()}
        candidate['lore'] = self.lore.toPlainText()
        try:
            save_settings(self.data_dir / 'ai_studio.json', candidate)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Cannot save profiles', str(exc)); return
        self.settings = candidate
        self.accept()


class WritingWorker(QObject):
    text = pyqtSignal(str)
    status = pyqtSignal(str)
    success = pyqtSignal(object)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, writer, request, recent):
        super().__init__()
        self.writer, self.request, self.recent = writer, request, recent

    @pyqtSlot()
    def run(self):
        try:
            self.success.emit(self.writer.generate(self.request, self.recent, self.text.emit, self.status.emit))
        except Cancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class TermsDialog(QDialog):
    def __init__(self, template, values, parent=None):
        super().__init__(parent)
        self.setWindowTitle(template.label + ' — offer terms')
        self.resize(640, 480)
        self.template = template
        self.values = values
        layout = QVBoxLayout(self)
        note = QLabel('Enter the actual offer terms. Required fields are marked *. '
                      'Optional details are omitted when blank. Saved terms can be reused; check dates and prices each time.')
        note.setWordWrap(True); layout.addWidget(note)
        form = QFormLayout(); self.fields = {}
        for term in template.terms:
            control = QLineEdit(values.get(term.key, ''))
            control.setMaxLength(300); control.setPlaceholderText(term.hint)
            self.fields[term.key] = control
            form.addRow(term.label + (' *' if term.required else ''), control)
        layout.addLayout(form)
        row = QHBoxLayout(); row.addStretch()
        apply = QPushButton('Apply terms'); apply.clicked.connect(self.commit)
        cancel = QPushButton('Cancel'); cancel.clicked.connect(self.reject)
        row.addWidget(apply); row.addWidget(cancel); layout.addLayout(row)

    def commit(self):
        try:
            self.values = checked_terms(self.template, {key: field.text() for key, field in self.fields.items()})
        except ValueError as exc:
            QMessageBox.warning(self, 'Offer terms', str(exc)); return
        self.accept()


class AIControls(QGroupBox):
    """One drafting request, sharing the host window's single script editor."""
    def __init__(self, host, settings, data_dir):
        super().__init__('AI Studio | Original writing', host)
        self.host, self.settings, self.data_dir = host, settings, Path(data_dir)
        self.thread = self.worker = self.writer = None
        self._prior_text = ''
        self._live_text = ''
        self._phase = 'Ready'
        self._template_category = None
        self._selected_templates = {}
        self._terms_path = self.data_dir / 'spot_template_terms.json'
        self._terms_load_error = ''
        try:
            self.template_values = load_terms(self._terms_path)
        except (OSError, ValueError) as exc:
            self.template_values = {}
            self._terms_load_error = str(exc)
        # Worker's text stream is the source of truth. Keep a read-only tagged
        # preview in the editor, without feeding previously injected tags back
        # to the writing model or repeatedly rewriting the text on each token.
        self.live_timer = QTimer(self)
        self.live_timer.setSingleShot(True)
        self.live_timer.setInterval(350)
        self.live_timer.timeout.connect(self.refresh_live_preview)
        layout = QHBoxLayout(self)
        settings_column = QVBoxLayout()
        row = QHBoxLayout(); row.addWidget(QLabel('Words'))
        self.words = QSpinBox(); self.words.setObjectName('target_words'); self.words.setRange(20, 2000); self.words.setValue(160)
        self.words.setSingleStep(20); row.addWidget(self.words)
        settings_column.addLayout(row)
        self.setup_button = QPushButton('AI Setup'); self.setup_button.clicked.connect(self.open_setup)
        self.profiles_button = QPushButton('Profiles'); self.profiles_button.clicked.connect(self.open_profiles)
        settings_column.addWidget(self.setup_button); settings_column.addWidget(self.profiles_button)
        self.lore_button = QPushButton('Lore library'); self.lore_button.clicked.connect(self.open_lore)
        settings_column.addWidget(self.lore_button)
        self.view_prompt_button = QPushButton('View prompt'); self.view_prompt_button.clicked.connect(self.view_prompt)
        settings_column.addWidget(self.view_prompt_button)
        self.prepared_button = QPushButton('Prepared copy'); self.prepared_button.clicked.connect(self.use_prepared_copy)
        self.prepared_button.setToolTip('Use the edited template terms directly, without a model. The optional AI brief is not applied.')
        settings_column.insertWidget(1, self.prepared_button); settings_column.addStretch()
        layout.addLayout(settings_column)
        brief_column = QVBoxLayout()
        template_row = QHBoxLayout()
        self.template_combo = QComboBox(); self.template_combo.setObjectName('spot_template')
        self.template_combo.setMinimumWidth(0)
        self.template_combo.setMinimumContentsLength(6)
        self.template_combo.setAccessibleName('Quick template')
        self.template_combo.setToolTip('Prepared spot recipe. Select a template, then Edit terms when it has offer variables.')
        self.template_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.template_combo.currentIndexChanged.connect(self.template_changed)
        self.terms_button = QPushButton('Edit terms…'); self.terms_button.clicked.connect(self.edit_terms)
        settings_column.insertWidget(2, self.terms_button)
        template_row.addWidget(self.template_combo, 1); brief_column.addLayout(template_row)
        self.prompt_label = QLabel(); self.prompt_label.setWordWrap(True); brief_column.addWidget(self.prompt_label)
        self.brief = QTextEdit(); self.brief.setAcceptRichText(False); self.brief.setMinimumHeight(55)
        self.brief.setPlaceholderText('Optional direction or premise. Leave blank to use the built-in prompt. Maximum 4,000 characters.')
        brief_column.addWidget(self.brief, 1)
        self.state = QLabel(); self.state.setWordWrap(True); brief_column.addWidget(self.state)
        layout.addLayout(brief_column, 1)
        self.timer = QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.show_elapsed)
        self.refresh_state()
        self.refresh_prompt()

    @property
    def busy(self):
        return self.thread is not None

    def refresh_state(self):
        ready = Path(self.settings['server_path']).is_file() and Path(self.settings['model_path']).is_file()
        self.state.setText(f'Ready: {Path(self.settings["model_path"]).name} • {self.settings["backend"]}' if ready
                           else 'First use: open AI Setup to install a writing runtime and select or download a writing model.')

    def open_setup(self):
        dialog = SetupDialog(self.settings, self.data_dir, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings
            self.refresh_state()

    def open_lore(self):
        dialog = LoreDialog(self.settings, self.data_dir, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings
            self.refresh_state()

    def open_profiles(self):
        dialog = ProfilesDialog(self.settings, self.data_dir, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings
            self.refresh_state()

    def refresh_prompt(self):
        category = self.host.cat.currentText()
        if category != self._template_category:
            self._template_category = category
            self.template_combo.blockSignals(True)
            self.template_combo.clear()
            for template in templates_for(category):
                self.template_combo.addItem(template.label, template.key)
            remembered = self._selected_templates.get(category, '')
            self.template_combo.setCurrentIndex(max(0, self.template_combo.findData(remembered)))
            self.template_combo.blockSignals(False)
        template = resolve_template(category, self.template_combo.currentData() or '')
        self.terms_button.setEnabled(bool(template.terms) and not self.busy)
        self.prepared_button.setEnabled(template.copy is not None and not self.busy)
        brand = 'goodneighborblues.com' if template.website else station_for(self.host.dj.currentText())
        values = self.template_values.get(template.key, {})
        missing = [term.label for term in template.terms if term.required and not values.get(term.key)]
        detail = (' — add ' + ', '.join(missing)) if missing else (' — saved terms; check before reuse' if template.terms else '')
        self.prompt_label.setText(f'Prepared prompt: {category} | {brand}{detail}')
        if self._terms_load_error:
            self.prompt_label.setToolTip('Saved terms could not be loaded; original file is retained. Edits work for this session. ' + self._terms_load_error)

    def template_changed(self):
        self._selected_templates[self.host.cat.currentText()] = self.template_combo.currentData()
        self.refresh_prompt()

    def edit_terms(self):
        template = resolve_template(self.host.cat.currentText(), self.template_combo.currentData() or '')
        dialog = TermsDialog(template, self.template_values.get(template.key, {}), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.template_values[template.key] = dialog.values
            if not self._terms_load_error:
                try:
                    save_terms(self._terms_path, self.template_values)
                except (OSError, ValueError) as exc:
                    QMessageBox.warning(self, 'Terms used for this session', 'Could not save terms: ' + str(exc))
            self.refresh_prompt()

    def use_prepared_copy(self):
        if self.busy:
            return
        request = self.current_request()
        try:
            text = prepared_copy(request.category, request.template_id, request.template_values,
                                 spot_context(request.dj, station_for(request.dj), request.title, request.artist, request.sponsor))
            if request.category == 'Ad / promo' and not resolve_template(request.category, request.template_id).website and request.advertiser_slogan:
                text += ' ' + request.advertiser_slogan
        except ValueError as exc:
            QMessageBox.warning(self, 'Prepared copy', str(exc)); return
        self.host.set_generated_script(text)
        error = self.host.remember_script(clean_spoken_text(text))
        self.host.review_notes.setText('Prepared copy. Check current offer terms and narration cues. The optional AI brief is not applied. ' + error)
        self.host.statusBar().showMessage(error or 'Prepared copy is ready to edit and review. No writing model was loaded.', 7000)

    def current_request(self):
        h = self.host
        advertiser = (next((c for c in h.campaigns if c.get('enabled', True) and c['name'].casefold() == h.sponsor.currentText().casefold()), {})
                      if h.cat.currentText() == 'Ad / promo' else {})
        notes = '\n'.join(x for x in (advertiser.get('description', ''),
                                      f'Required slogan: {advertiser["slogan"]}' if advertiser.get('slogan') else '') if x)
        return ScriptRequest(dj=h.dj.currentText(), category=h.cat.currentText(), mood=h.mood.currentText(),
                                words=self.words.value(), brief=self.brief.toPlainText().strip(), title=h.title_field.text().strip(),
                                artist=h.artist.text().strip(), sponsor=h.sponsor.currentText().strip(), advertiser_notes=notes,
                                advertiser_slogan=advertiser.get('slogan', ''),
                                template_id=self.template_combo.currentData() or '',
                                template_values=dict(self.template_values.get(self.template_combo.currentData(), {})))

    def active_prompt_text(self):
        request = self.current_request()
        website = resolve_template(request.category, request.template_id).website
        preview = '\n\n'.join(message['content'] for message in build_messages(request, self.settings, self.host.records, '' if website else LoreLibrary(self.data_dir).context(
            ' '.join((request.brief, request.sponsor, request.advertiser_notes)).strip() or 'Goodneighbor Commonwealth'),
            '' if website else CharacterLibrary(self.data_dir).context(request.dj)))
        if request.category == 'Stories From the Commonwealth':
            preview = ('STORY WORKFLOW: first create an internal source/goal/obstacle/action/'
                       'outcome/closing/wasteland-cause plan, then write the spoken anecdote. The plan '
                       'is generated at runtime and is not shown in the script editor.\n\n'
                       'DRAFTING GUIDANCE:\n' + preview)
        elif self.settings.get('model_preset') == 'gemma-writer' and request.category in (
                'Broadcast opener', 'Station ID', 'Broadcast closer', 'Song introduction', 'Song outro'):
            preview = ('RADIO LINK WORKFLOW: draft, then copy-edit to remove unsupported '
                       'time/duration claims and stock patter. Only the edited result '
                       'is saved as a completed script.\n\nDRAFTING GUIDANCE:\n' + preview)
        return preview

    def view_prompt(self):
        try:
            text = self.active_prompt_text()
        except ValueError as exc:
            QMessageBox.warning(self, 'Writing prompt', str(exc)); return
        dialog = QDialog(self); dialog.setWindowTitle('Active writing prompt')
        dialog.resize(850, 650); layout = QVBoxLayout(dialog)
        note = QLabel('The built-in format, station and DJ guidance is always included. Your optional brief adds direction; it does not replace those defaults.')
        note.setWordWrap(True); layout.addWidget(note)
        preview = QTextEdit(); preview.setObjectName('active_prompt_preview')
        preview.setAcceptRichText(False); preview.setReadOnly(True); preview.setPlainText(text)
        layout.addWidget(preview, 1)
        close = QPushButton('Close'); close.clicked.connect(dialog.accept); layout.addWidget(close)
        dialog.exec()

    def generate(self):
        if self.busy:
            return
        request = self.current_request()
        try:
            build_messages(request, self.settings)
        except ValueError as exc:
            self.state.setText(str(exc)); return
        if not Path(self.settings['server_path']).is_file() or not Path(self.settings['model_path']).is_file():
            self.open_setup()
            return
        h = self.host
        if len(request.brief) > 4000 or len(request.advertiser_notes) > 2000:
            self.state.setText('Shorten the brief to 4,000 characters and advertiser description/slogan to 2,000 before generating.'); return
        self._prior_text = h.output.toPlainText()
        self._live_text = ''
        self.live_timer.stop()
        self.writer = LocalWriter(self.settings, self.data_dir)
        self.worker = WritingWorker(self.writer, request, list(h.records))
        self.thread = QThread(self); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.text.connect(self.append_text)
        self.worker.status.connect(self.set_phase)
        self.worker.success.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.on_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        h.output.clear(); h.review_notes.setText('AI draft in progress. Review is available after generation finishes.')
        self.set_busy(True)
        self._started = time.monotonic(); self._phase = 'Starting local writing engine'
        self.timer.start(); self.show_elapsed()
        self.thread.start()

    def set_busy(self, busy):
        h = self.host
        for control in (h.mode, h.request_group, h.generate_button, h.history_button, h.ads_button,
                        self.setup_button, self.profiles_button, self.lore_button, self.view_prompt_button, self.words, self.brief,
                        self.template_combo, self.terms_button, self.prepared_button,
                        h.reviewed, h.copy_button, h.tts_engine, h.tts_intensity, h.auto_speech,
                        h.apply_speech_button, h.speech_preview, h.speech_export, h.tag_pick, h.tag_insert):
            control.setEnabled(not busy)
        h.output.setReadOnly(busy)
        h.cancel_button.setEnabled(busy)
        if busy:
            h.save_button.setEnabled(False)
        else:
            # Restore engine-dependent controls, not merely their generic
            # enabled state: IndexTTS and Qwen3 cannot insert native tags.
            h.update_tag_controls()
            self.refresh_prompt()

    @pyqtSlot(str)
    def append_text(self, fragment):
        self._live_text += fragment
        if not self.host.auto_speech.isChecked():
            cursor = self.host.output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(fragment)
            self.host.output.setTextCursor(cursor)
            return
        if not self.live_timer.isActive():
            # The preview is deliberately throttled to prevent GUI slowdowns
            # during fast local inference; the final script is always refreshed.
            self.live_timer.start()

    @pyqtSlot()
    def refresh_live_preview(self):
        if not self.busy or not self._live_text:
            return
        self.host.set_generated_script(self._live_text)
        cursor = self.host.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.host.output.setTextCursor(cursor)

    @pyqtSlot(str)
    def set_phase(self, phase):
        self._phase = phase
        self.show_elapsed()

    def show_elapsed(self):
        elapsed = int(time.monotonic() - getattr(self, '_started', time.monotonic()))
        self.state.setText(f'{self._phase}\nElapsed {elapsed // 60:02d}:{elapsed % 60:02d}. Cancel stops this writing process.')

    @pyqtSlot(object)
    def on_success(self, result):
        self.live_timer.stop()
        self._live_text = ''
        self.host.set_generated_script(result['text'])
        history_error = self.host.remember_script(clean_spoken_text(result['text']))
        notes = ('Review notes: ' + ' '.join(result['warnings']) if result['warnings']
                 else 'AI draft. Check story facts, host voice and ending before marking reviewed.')
        if result.get('character_candidates'):
            notes += f' {result["character_candidates"]} character detail(s) saved for review in Lore library > DJ character notes.'
        if result.get('memory_fallback'):
            notes += (f' Memory recovery reduced context to {result["context_tokens_used"]:,} tokens for this run; '
                      'the saved AI Setup context was not changed.')
        self.host.review_notes.setText(notes + (' ' + history_error if history_error else ''))
        self._phase = f'Wrote one draft in {result["elapsed_seconds"]:.1f} seconds on {result["backend"]}. Model unloaded.'
        self.host.statusBar().showMessage(history_error or 'AI writing complete. Edit and review the script before export.', 15000)

    def restore_previous(self):
        self.live_timer.stop()
        self._live_text = ''
        self.host.output.setPlainText(self._prior_text)
        # Cancellation or failure never approves any text, including a restored draft.
        self.host.reviewed.setChecked(False)

    @pyqtSlot(str)
    def on_error(self, message):
        self.restore_previous()
        self._phase = 'Writing failed: ' + message
        self.host.review_notes.setText('Writing failed. The previous script was restored; no new history entry was added.')

    @pyqtSlot()
    def on_cancelled(self):
        self.restore_previous()
        self._phase = 'Writing cancelled. Previous script restored.'
        self.host.review_notes.setText('Cancelled draft was discarded. Review the restored script before export.')

    @pyqtSlot()
    def on_finished(self):
        self.live_timer.stop()
        self._live_text = ''
        self.timer.stop()
        self.state.setText(self._phase)
        self.thread = self.worker = self.writer = None
        self.set_busy(False)
        self.host.on_category_changed(self.host.cat.currentText(), suggest_length=False)

    def cancel(self):
        if self.writer:
            self.writer.cancel()
            self.host.cancel_button.setEnabled(False)
            self._phase = 'Stopping local writing engine'
            self.show_elapsed()
