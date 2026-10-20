"""Offline preparation with explicit review and the host's normal handoff."""
import difflib
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
    QGroupBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from .library import Library, validate
from .preparation import prepare


class ScriptPrep(QWidget):
    is_busy = False

    def __init__(self, context):
        super().__init__(context.parent)
        self.setStyleSheet('QCheckBox {background:transparent; spacing:7px;} '
            'QCheckBox::indicator {width:15px; height:15px; border:1px solid #7baa80; border-radius:3px; background:#0e1716;} '
            'QCheckBox::indicator:checked {background:#8ceba0; border:2px solid #b4ffc3;}')
        self.context = context
        self.library = Library(context.data_dir)
        self.load_error = ''
        try:
            self.data = self.library.load()
        except (OSError, ValueError) as exc:
            self.load_error = str(exc)
            self.data = {'version': 1, 'profiles': {'Unsaved recovery': []}}
        self.current = next(iter(self.data['profiles']))
        layout = QVBoxLayout(self)
        title = QLabel('Pronunciation & Script Prep'); title.setObjectName('sectionTitle')
        layout.addWidget(title)
        note = QLabel('Prepare spoken wording locally. Compare every change before sending it to narration.')
        note.setWordWrap(True); layout.addWidget(note)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Dictionary'))
        self.profile = QComboBox(); self.profile.addItems(self.data['profiles']); controls.addWidget(self.profile, 1)
        self._button(controls, 'New profile…', self.new_profile)
        self._button(controls, 'Save dictionaries', self.save)
        self._button(controls, 'Help / About', self.help)
        layout.addLayout(controls)
        dictionary = QGroupBox('Pronunciations · whole words and phrases')
        dl = QVBoxLayout(dictionary)
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(['Written term', 'Spoken form'])
        self.table.horizontalHeader().setStretchLastSection(True); self.table.setColumnWidth(0, 270)
        self.table.setMinimumHeight(65); self.table.setMaximumHeight(110); dl.addWidget(self.table)
        row = QHBoxLayout(); self._button(row, 'Add entry', self.add_entry); self._button(row, 'Remove selected', self.remove_entries)
        row.addStretch(); dl.addLayout(row); layout.addWidget(dictionary)
        options = QHBoxLayout()
        self.numbers = QCheckBox('Spoken numbers'); self.numbers.setChecked(True)
        self.numbers.setToolTip('Dollar prices, percentages, explicit AM/PM times, ISO dates and FM/AM/MHz frequencies.')
        self.abbreviations = QCheckBox('Titles & abbreviations'); self.abbreviations.setChecked(True)
        self.pauses = QCheckBox('Comma pauses')
        self.pauses.setToolTip('Replace long dashes with commas. Actual timing depends on the voice.')
        for item in (self.numbers, self.abbreviations, self.pauses): options.addWidget(item)
        layout.addLayout(options)
        engine_note = QLabel('Plain spoken text for Chatterbox, IndexTTS and Qwen3-TTS. No SSML, emotion or pause tags are added. Punctuation timing varies by voice; audition the result.')
        engine_note.setWordWrap(True); engine_note.setObjectName('mutedText'); layout.addWidget(engine_note)
        tools = QHBoxLayout()
        self._button(tools, 'Load Studio script', self.load_studio)
        self._button(tools, 'Open text…', self.open_text)
        self._button(tools, 'Prepare preview', self.preview, primary=True)
        tools.addStretch(); layout.addLayout(tools)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.source = QPlainTextEdit(); self.source.setPlaceholderText('Original script — paste here or load from Voice Studio.')
        self.output = QPlainTextEdit(); self.output.setPlaceholderText('Prepared script — editable after preparation.')
        for name, editor in [('Original script', self.source), ('Prepared script', self.output)]:
            group = QGroupBox(name); gl = QVBoxLayout(group); gl.addWidget(editor); splitter.addWidget(group)
        layout.addWidget(splitter, 1)
        self.diff = QPlainTextEdit(); self.diff.setReadOnly(True); self.diff.setMaximumHeight(125)
        self.diff.setPlaceholderText('Change summary and line comparison appear here.'); layout.addWidget(self.diff)
        actions = QHBoxLayout()
        self.reviewed = QCheckBox('Reviewed wording')
        self.reviewed.setToolTip('I checked the prepared wording and pronunciation hints before narration.')
        actions.addWidget(self.reviewed); actions.addStretch()
        self.copy_button = self._button(actions, 'Copy', self.copy)
        self.export_button = self._button(actions, 'Export text…', self.export)
        self.send_button = self._button(actions, 'Send to Voice Studio', self.send, primary=True)
        layout.addLayout(actions)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.show_entries()
        self.profile.currentTextChanged.connect(self.switch_profile)
        self.table.itemChanged.connect(self.invalidate)
        for item in (self.numbers, self.abbreviations, self.pauses): item.toggled.connect(self.invalidate)
        self.source.textChanged.connect(self.invalidate)
        self.output.textChanged.connect(self.output_changed)
        self.reviewed.toggled.connect(self.actions)
        self.status.setText('Dictionary could not be loaded; saving disabled to preserve the original file: '+self.load_error if self.load_error else 'Ready. Your original script is preserved.')
        self.actions()

    def _button(self, row, title, callback, primary=False):
        button = QPushButton(title); button.clicked.connect(callback)
        if primary: button.setObjectName('primary')
        row.addWidget(button); return button

    def cancel(self):
        pass

    def entries(self):
        result = []
        for row in range(self.table.rowCount()):
            values = [(self.table.item(row, col).text().strip() if self.table.item(row, col) else '') for col in range(2)]
            if any(values): result.append(dict(zip(('term', 'spoken'), values)))
        validate({'version': 1, 'profiles': {self.current: result}})
        return result

    def show_entries(self):
        self.table.blockSignals(True); self.table.setRowCount(0)
        for entry in self.data['profiles'][self.current]:
            row = self.table.rowCount(); self.table.insertRow(row)
            for col, key in enumerate(('term', 'spoken')): self.table.setItem(row, col, QTableWidgetItem(entry[key]))
        self.table.blockSignals(False)

    def switch_profile(self, name):
        if name == self.current: return
        try:
            self.data['profiles'][self.current] = self.entries()
        except ValueError as exc:
            self.status.setText(str(exc)); self.profile.blockSignals(True)
            self.profile.setCurrentText(self.current); self.profile.blockSignals(False); return
        self.current = name; self.show_entries(); self.invalidate()

    def new_profile(self):
        name, ok = QInputDialog.getText(self, 'New dictionary', 'Profile name (advertiser, DJ or project):')
        if not ok or not name.strip(): return
        name = name.strip()
        if len(name) > 100 or name in self.data['profiles'] or len(self.data['profiles']) >= 100:
            self.status.setText('Choose a unique name of at most 100 characters; maximum 100 profiles.'); return
        self.data['profiles'][name] = []; self.profile.addItem(name); self.profile.setCurrentText(name)

    def add_entry(self):
        self.table.insertRow(self.table.rowCount()); self.invalidate()

    def remove_entries(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True): self.table.removeRow(row)
        self.invalidate()

    def save(self):
        try:
            if self.load_error: raise ValueError('Resolve the existing dictionary file before saving: '+self.load_error)
            self.data['profiles'][self.current] = self.entries(); self.library.save(self.data)
            self.status.setText('Dictionaries saved in '+str(self.library.path))
        except (OSError, ValueError) as exc: self.status.setText(str(exc))

    def invalidate(self, *args):
        self.reviewed.setChecked(False); self.output.clear()
        self.diff.clear(); self.status.setText('Inputs changed. Prepare a new preview.'); self.actions()

    def output_changed(self):
        self.reviewed.setChecked(False); self.update_diff(); self.actions()

    def update_diff(self):
        comparison = '\n'.join(difflib.unified_diff(self.source.toPlainText().splitlines(), self.output.toPlainText().splitlines(), fromfile='Original', tofile='Prepared', lineterm=''))
        self.diff.setPlainText(comparison or 'No wording changes.')

    def preview(self):
        try:
            result = prepare(self.source.toPlainText(), self.entries(), self.numbers.isChecked(), self.abbreviations.isChecked(), self.pauses.isChecked())
            self.output.setPlainText(result.text)
            self.diff.setPlainText('\n'.join(result.changes) + '\n\n' + self.diff.toPlainText())
            self.status.setText(f'{len(result.changes)} substitutions. '+(' '.join(result.warnings) or 'Review the wording and audition pronunciation before final use.'))
        except ValueError as exc: self.status.setText(str(exc))

    def load_studio(self):
        self.source.setPlainText(self.context.parent.editor.toPlainText())

    def open_text(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open script', '', 'Text files (*.txt);;All files (*)')
        if path:
            try:
                from pathlib import Path
                if Path(path).stat().st_size > 400000: raise ValueError('Script file is too large.')
                self.source.setPlainText(Path(path).read_text(encoding='utf-8-sig'))
            except (OSError, ValueError) as exc: self.status.setText(str(exc))

    def actions(self):
        has_text = bool(self.output.toPlainText().strip())
        self.copy_button.setEnabled(has_text); self.export_button.setEnabled(has_text)
        self.send_button.setEnabled(has_text and self.reviewed.isChecked())

    def copy(self):
        QApplication.clipboard().setText(self.output.toPlainText())

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export prepared text', 'prepared-script.txt', 'Text files (*.txt)')
        if path:
            try:
                from pathlib import Path
                Path(path).write_text(self.output.toPlainText(), encoding='utf-8')
            except OSError as exc: self.status.setText(str(exc))

    def send(self):
        if not self.reviewed.isChecked() or not self.output.toPlainText().strip(): return
        reason = self.context.can_generate()
        if reason: self.status.setText(reason); return
        if self.context.handoff(self.output.toPlainText()): self.status.setText('Prepared script loaded in Voice Studio. Choose the target engine and audition it.')

    def help(self):
        QMessageBox.information(self, 'About Pronunciation & Script Prep',
            'Pronunciation & Script Prep 1.0.0\nCreated by Kaotick Jay / Plagued Mods · MIT license\n\n'
            'Offline rules; no AI model, internet connection or extra downloads. Profiles stay in this plugin’s data folder. '
            'Save dictionaries explicitly before closing. Pronunciations use spoken spellings, not IPA or engine tags. '
            'The engine still determines their sound. The original remains untouched until reviewed handoff.\n\n'
            'US English: dollar amounts, percentages, explicit AM/PM times, ISO calendar dates and FM/AM/MHz frequencies. '
            'Other numbers are preserved. Ambiguous dates, addresses and existing tags need manual review. '
            'Comma pauses are optional; emphasis is best conveyed by wording and auditioning your chosen engine.')
