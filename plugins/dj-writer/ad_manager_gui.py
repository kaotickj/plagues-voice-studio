"""Graphical editor for personally authored in-world radio advertising campaigns."""
from copy import deepcopy
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QListWidget, QLineEdit, QTextEdit, QComboBox, QCheckBox, QPushButton,
    QMessageBox, QWidget, QSplitter, QInputDialog)
from PyQt6.QtCore import Qt
from ad_manager import new_campaign, save_campaigns, validate_campaigns, MOODS

class AdManagerDialog(QDialog):
    def __init__(self, campaigns, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Ad Manager | Goodneighbor / Plague Radio')
        self.resize(1060, 710)
        self.campaigns = deepcopy(campaigns)
        self.path = path
        self.index = -1
        self.script_index = -1
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Manage custom advertisers and fully authored spots. Bundled advertisers remain untouched.'))
        split = QSplitter()
        layout.addWidget(split, 1)
        left = QWidget(); left_layout = QVBoxLayout(left)
        self.ad_list = QListWidget(); self.ad_list.currentRowChanged.connect(self.select_ad)
        left_layout.addWidget(self.ad_list)
        buttons = QHBoxLayout()
        for label, fn in [('New', self.add_ad), ('Delete', self.remove_ad)]:
            b = QPushButton(label); b.clicked.connect(fn); buttons.addWidget(b)
        left_layout.addLayout(buttons)
        split.addWidget(left)
        right = QWidget(); r = QVBoxLayout(right)
        form = QFormLayout()
        self.name = QLineEdit(); form.addRow('Advertiser', self.name)
        self.slogan = QLineEdit(); form.addRow('Slogan', self.slogan)
        self.description = QLineEdit(); form.addRow('Product / notes', self.description)
        self.enabled = QCheckBox('Enabled for generation'); form.addRow('', self.enabled)
        r.addLayout(form)
        r.addWidget(QLabel('Complete commercial scripts (no randomized sentence mixing):'))
        self.script_list = QListWidget(); self.script_list.currentRowChanged.connect(self.select_script)
        r.addWidget(self.script_list, 1)
        sb = QHBoxLayout()
        for label, fn in [('Add script', self.add_script), ('Remove script', self.remove_script)]:
            b = QPushButton(label); b.clicked.connect(fn); sb.addWidget(b)
        r.addLayout(sb)
        opts = QHBoxLayout()
        self.profile = QComboBox(); self.profile.addItem('Goodneighbor Blues (Tal / Hattie)', 'blues'); self.profile.addItem('Plague Radio (MTP)', 'plague')
        self.length = QComboBox(); self.length.addItems(['Short', 'Medium', 'Long'])
        self.mood = QComboBox(); self.mood.addItems(MOODS)
        opts.addWidget(QLabel('Station')); opts.addWidget(self.profile, 2)
        opts.addWidget(QLabel('Length')); opts.addWidget(self.length)
        opts.addWidget(QLabel('Mood')); opts.addWidget(self.mood)
        r.addLayout(opts)
        self.script_text = QTextEdit(); self.script_text.setPlaceholderText('Write the complete spot exactly as it should be read aloud.')
        r.addWidget(self.script_text, 2)
        split.addWidget(right); split.setStretchFactor(1, 3)
        footer = QHBoxLayout()
        self.save_button = QPushButton('Save changes'); self.save_button.clicked.connect(self.commit)
        close = QPushButton('Cancel'); close.clicked.connect(self.reject)
        footer.addStretch(1); footer.addWidget(self.save_button); footer.addWidget(close)
        layout.addLayout(footer)
        self.name.editingFinished.connect(self.update_ad)
        self.slogan.editingFinished.connect(self.update_ad)
        self.description.editingFinished.connect(self.update_ad)
        self.enabled.toggled.connect(self.update_ad)
        self.profile.currentIndexChanged.connect(self.update_script)
        self.length.currentTextChanged.connect(self.update_script)
        self.mood.currentTextChanged.connect(self.update_script)
        self.script_text.textChanged.connect(self.update_script)
        self.populate_ads()

    def populate_ads(self, row=0):
        self.ad_list.blockSignals(True); self.ad_list.clear()
        for c in self.campaigns:
            self.ad_list.addItem(c['name'] + ('' if c.get('enabled', True) else ' [disabled]'))
        self.ad_list.blockSignals(False)
        self.select_ad(min(row, len(self.campaigns)-1))
        self.ad_list.setCurrentRow(self.index)

    def update_ad(self):
        if self.index < 0: return
        c = self.campaigns[self.index]
        c.update(name=self.name.text().strip(), slogan=self.slogan.text().strip(),
                 description=self.description.text().strip(), enabled=self.enabled.isChecked())
        self.ad_list.item(self.index).setText((c['name'] or '(unnamed)') + ('' if c['enabled'] else ' [disabled]'))

    def select_ad(self, row):
        self.index = row if 0 <= row < len(self.campaigns) else -1
        c = self.campaigns[self.index] if self.index >= 0 else None
        for field, value in [(self.name, c['name'] if c else ''), (self.slogan, c.get('slogan', '') if c else ''),
                             (self.description, c.get('description','') if c else '')]:
            field.blockSignals(True); field.setText(value); field.blockSignals(False)
        self.enabled.blockSignals(True); self.enabled.setChecked(c.get('enabled', True) if c else False); self.enabled.blockSignals(False)
        self.name.setEnabled(c is not None)
        self.slogan.setEnabled(c is not None)
        self.description.setEnabled(c is not None)
        self.enabled.setEnabled(c is not None)
        self.refresh_scripts()

    def add_ad(self):
        name, ok = QInputDialog.getText(self, 'Add advertiser', 'Advertiser name:')
        if not ok or not name.strip(): return
        if any(x['name'].casefold() == name.strip().casefold() for x in self.campaigns):
            QMessageBox.warning(self, 'Already exists', 'That advertiser is already in the custom library.'); return
        self.campaigns.append(new_campaign(name)); self.populate_ads(len(self.campaigns)-1)

    def remove_ad(self):
        if self.index < 0: return
        if QMessageBox.question(self, 'Delete advertiser', 'Delete this advertiser and its custom scripts?') != QMessageBox.StandardButton.Yes: return
        row = self.index; self.campaigns.pop(row); self.populate_ads(max(0, row-1))

    def refresh_scripts(self, row=0):
        self.script_list.blockSignals(True); self.script_list.clear()
        if self.index >= 0:
            for s in self.campaigns[self.index]['scripts']:
                self.script_list.addItem(f"{s['profile']} | {s['length']} | {s['mood']} | {s['text'][:44]}")
        self.script_list.blockSignals(False)
        self.select_script(min(row, self.script_list.count()-1))
        self.script_list.setCurrentRow(self.script_index)

    def select_script(self, row):
        self.script_index = row if 0 <= row < self.script_list.count() else -1
        script = self.campaigns[self.index]['scripts'][row] if self.index >= 0 and self.script_index >= 0 else None
        for cb, value in [(self.profile, script['profile'] if script else 'blues'),
                          (self.length, script['length'] if script else 'Medium'),
                          (self.mood, script['mood'] if script else 'Reflective')]:
            cb.blockSignals(True)
            if cb is self.profile: cb.setCurrentIndex(0 if value == 'blues' else 1)
            else: cb.setCurrentText(value)
            cb.blockSignals(False)
            cb.setEnabled(script is not None)
        self.script_text.blockSignals(True); self.script_text.setPlainText(script['text'] if script else ''); self.script_text.blockSignals(False)
        self.script_text.setEnabled(script is not None)

    def add_script(self):
        if self.index < 0: return
        self.campaigns[self.index]['scripts'].append({'profile':'blues', 'length':'Medium', 'mood':'Reflective',
                                                       'text':'Write this commercial before saving.'})
        self.refresh_scripts(len(self.campaigns[self.index]['scripts'])-1)

    def remove_script(self):
        if self.index < 0 or self.script_index < 0: return
        row = self.script_index
        self.campaigns[self.index]['scripts'].pop(row)
        self.refresh_scripts(max(0,row-1))

    def update_script(self, *_):
        if self.index < 0 or self.script_index < 0: return
        s = self.campaigns[self.index]['scripts'][self.script_index]
        s.update(profile=self.profile.currentData(), length=self.length.currentText(),
                 mood=self.mood.currentText(), text=self.script_text.toPlainText())
        self.script_list.item(self.script_index).setText(f"{s['profile']} | {s['length']} | {s['mood']} | {s['text'][:44]}")

    def commit(self):
        try:
            validate_campaigns(self.campaigns)
            # Duplicate names are rejected by validation before anything is saved.
            save_campaigns(self.path, self.campaigns)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Cannot save', str(exc)); return
        self.accept()
