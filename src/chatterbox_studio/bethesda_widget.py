"""Direct Bethesda voice export with reusable mod and voice profiles.

No plugin reading, editing or Creation Kit dialogue configuration.
All mod metadata comes from the user. Legacy application data remains intact.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QComboBox, QLabel, QLineEdit, QPushButton, QFileDialog,
    QPlainTextEdit, QMessageBox, QCheckBox, QScrollArea, QInputDialog)
from .bethesda_export import (BethesdaExportSettings, BethesdaExportError,
    export_dialogue, expected_fuz_path, clean_transcript, audio_transcript)
from .mod_profiles import ModProfileStore, ProfileError


class ExportTask(QObject):
    message = pyqtSignal(str)
    complete = pyqtSignal(str, str)

    def __init__(self, config):
        super().__init__()
        self.config = config

    @pyqtSlot()
    def run(self):
        try:
            result = export_dialogue(self.config, self.message.emit)
            self.complete.emit(str(result), '')
        except Exception as exc:
            self.complete.emit('', str(exc))


class BethesdaExportTab(QWidget):
    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self.host = mainwindow
        self.settings = mainwindow.settings
        self.store = ModProfileStore(mainwindow.storage)
        self.projects = []
        self.thread = None
        self.worker = None
        self._build()
        self._load()

    @property
    def is_busy(self):
        return self.thread is not None

    def _build(self):
        whole = QVBoxLayout(self)
        intro = QLabel('Create narration in the main tab or select existing audio, then generate LIP + XWM + FUZ and install the FUZ directly. Plugin editing remains in the Creation Kit. External audio and FaceFX tools must be installed locally.')
        intro.setWordWrap(True)
        whole.addWidget(intro)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        whole.addWidget(scroll, 1)
        panel = QWidget()
        scroll.setWidget(panel)
        layout = QVBoxLayout(panel)

        group = QGroupBox('1. Saved mod project')
        form = QFormLayout(group)
        self.project_select = QComboBox()
        self.project_select.currentIndexChanged.connect(self._project_selected)
        form.addRow('Saved project', self.project_select)
        actions = QHBoxLayout()
        for label, action in [('New project', self._new_project), ('Save project', self._save_project), ('Delete', self._delete_project)]:
            btn = QPushButton(label)
            btn.clicked.connect(action)
            actions.addWidget(btn)
        form.addRow(_container(actions))
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText('e.g. Goodneighbor Companion')
        form.addRow('Project name', self.project_name)
        self.game = QComboBox()
        for title, value in [('Fallout 4', 'fallout4'), ('Skyrim (2011)', 'skyrim'), ('Skyrim Special Edition / Anniversary Edition', 'skyrimse')]:
            self.game.addItem(title, value)
        form.addRow('Game', self.game)
        self.plugin = QLineEdit()
        self.plugin.setPlaceholderText('Exact owning plugin: YourMod.esp')
        form.addRow('Dialogue owner plugin', self.plugin)
        self.mode = QComboBox()
        self.mode.addItem('Install into game Data directory', 'game_data')
        self.mode.addItem('Install into MO2 mod root', 'mod_root')
        form.addRow('Destination type', self.mode)
        self.root = QLineEdit()
        self.root.setPlaceholderText(r'C:\Games\Fallout 4\Data  OR  ...\ModOrganizer\mods\YourMod')
        choose = QPushButton('Browse folder...')
        choose.clicked.connect(lambda: self._browse(self.root, 'folder'))
        form.addRow('Exact destination root', _container(_horizontal(self.root, choose)))
        layout.addWidget(group)

        voice_group = QGroupBox('2. Saved voice assignment (Bethesda VoiceType + Chatterbox voice)')
        voice_form = QFormLayout(voice_group)
        self.voice_select = QComboBox()
        self.voice_select.currentIndexChanged.connect(self._voice_selected)
        voice_form.addRow('Saved voice profile', self.voice_select)
        v_actions = QHBoxLayout()
        for label, action in [('Save voice profile', self._save_voice_profile), ('Delete voice profile', self._delete_voice_profile)]:
            b = QPushButton(label)
            b.clicked.connect(action)
            v_actions.addWidget(b)
        voice_form.addRow(_container(v_actions))
        self.voice_type = QLineEdit()
        self.voice_type.setPlaceholderText('Exact CK VoiceType EditorID, not the NPC name')
        voice_form.addRow('VoiceType EditorID', self.voice_type)
        note = QLabel('A saved voice assignment also remembers the selected Chatterbox voice and model. Applying it updates the Narration Studio selection. VoiceType cannot be inferred from an audio sample.')
        note.setWordWrap(True)
        voice_form.addRow(note)
        layout.addWidget(voice_group)

        audio_group = QGroupBox('3. Dialogue and source audio')
        audio_layout = QVBoxLayout(audio_group)
        self.audio = QLineEdit()
        audio_choose = QPushButton('Choose audio...')
        audio_choose.clicked.connect(lambda: self._browse(self.audio, 'audio'))
        latest = QPushButton('Last narration')
        latest.clicked.connect(self._last_audio)
        audio_layout.addLayout(_horizontal(self.audio, audio_choose, latest))
        self.transcript = QPlainTextEdit()
        self.transcript.setPlaceholderText('Exact text spoken by the recording. Used by FaceFX for mouth movements.')
        self.transcript.setMinimumHeight(80)
        audio_layout.addWidget(self.transcript)
        self.audio.textChanged.connect(self._audio_changed)
        copy = QPushButton('Copy dialogue from Narration Studio (remove tags)')
        copy.clicked.connect(lambda: self.transcript.setPlainText(clean_transcript(self.host.editor.toPlainText())))
        audio_layout.addWidget(copy)
        self.response = QLineEdit()
        self.response.setPlaceholderText('Exact CK response filename; Fallout 4 example: 000F1B2C_1')
        audio_layout.addWidget(QLabel('Exact expected response filename (extension optional)'))
        audio_layout.addWidget(self.response)
        layout.addWidget(audio_group)

        tool_group = QGroupBox('4. Installed conversion tools')
        tool_form = QFormLayout(tool_group)
        self.facefx = QLineEdit()
        self.fonix = QLineEdit()
        self.encoder = QLineEdit()
        self.ffmpeg = QLineEdit()
        for label, edit, kind in [
            ('FaceFXWrapper executable', self.facefx, 'exe'),
            ('FonixData.cdf (local CK resource)', self.fonix, 'cdf'),
            ('xWMA encoder executable', self.encoder, 'exe'),
            ('FFmpeg executable (optional)', self.ffmpeg, 'exe'),
        ]:
            browse = QPushButton('Browse...')
            browse.clicked.connect(lambda _=False, e=edit, k=kind: self._browse(e, k))
            tool_form.addRow(label, _container(_horizontal(edit, browse)))
        self.encoder_type = QComboBox()
        self.encoder_type.addItem('WMAEncodeRS', 'wmaencoders')
        self.encoder_type.addItem('Creation Kit xwmaencode', 'xwmaencode')
        tool_form.addRow('Encoder', self.encoder_type)
        self.bitrate = QComboBox()
        self.bitrate.addItem('48 kbps', 48)
        self.bitrate.addItem('32 kbps', 32)
        tool_form.addRow('Bitrate', self.bitrate)
        self.keep = QCheckBox('Keep WAV, XWM, LIP and transcript separately in this application’s project files')
        self.keep.setChecked(True)
        tool_form.addRow(self.keep)
        layout.addWidget(tool_group)

        target = QGroupBox('5. Verify destination and install')
        target_layout = QVBoxLayout(target)
        self.preview = QLabel('Configure a project, voice type and response filename to preview installation.')
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        target_layout.addWidget(self.preview)
        recalc = QPushButton('Check destination')
        recalc.clicked.connect(self._update_preview)
        target_layout.addWidget(recalc)
        layout.addWidget(target)
        for edit in (self.root, self.plugin, self.voice_type, self.response):
            edit.textChanged.connect(self._update_preview)
        self.mode.currentIndexChanged.connect(self._update_preview)

        self.run_button = QPushButton('Build LIP + XWM + FUZ and install to destination')
        self.run_button.setObjectName('primary')
        self.run_button.clicked.connect(self._start)
        whole.addWidget(self.run_button)
        self.status = QLabel('Ready. You must supply the expected CK dialogue filename.')
        self.status.setWordWrap(True)
        whole.addWidget(self.status)

    def _browse(self, edit, kind):
        if kind == 'folder':
            value = QFileDialog.getExistingDirectory(self, 'Select the actual game Data folder or MO2 mod root', edit.text())
        else:
            filt = {'audio': 'Audio files (*.wav *.mp3 *.flac *.ogg);;All files (*)',
                    'exe': 'Executable files (*.exe);;All files (*)',
                    'cdf': 'Fonix files (*.cdf);;All files (*)'}[kind]
            value, _ = QFileDialog.getOpenFileName(self, 'Select conversion file', edit.text(), filt)
        if value:
            edit.setText(value)

    def _last_audio(self):
        path = getattr(self.host, 'last_output', '')
        if path and Path(path).is_file():
            self.audio.setText(path)
        else:
            QMessageBox.information(self, 'No completed narration', 'Generate narration or select an existing export from the Export Library.')

    def _audio_changed(self, path):
        # All entry points (browser, engine comparison, picker, typed paths)
        # must discard the previous recording's dialogue before loading a new one.
        transcript = audio_transcript(Path(path)) if path else ''
        if not transcript and path:
            results = getattr(self.host, 'results', {})
            for job in getattr(self.host, 'queue', []):
                if results.get(job.job_id) == path:
                    transcript = clean_transcript(job.text)
                    break
        self.transcript.setPlainText(transcript)

    def _get_project(self):
        pid = self.project_select.currentData()
        return next((p for p in self.projects if p['id'] == pid), None)

    def _new_project(self):
        self.project_select.setCurrentIndex(0)
        self.project_name.clear()
        self.plugin.clear()
        self.root.clear()
        self.voice_type.clear()
        self.voice_select.setCurrentIndex(0)
        self._update_preview()

    def _save_project(self):
        name = self.project_name.text().strip()
        if not name:
            QMessageBox.warning(self, 'Project name', 'Enter a project name first.')
            return
        p = self._get_project()
        if p is None:
            p = self.store.new_project(name)
            self.projects.append(p)
        p.update(name=name, game=self.game.currentData(), plugin=self.plugin.text().strip(),
                 destination_mode=self.mode.currentData(), root=self.root.text().strip())
        self.store.save(self.projects)
        self.settings.setValue('bethesda/last_project', p['id'])
        # Saving this project's paths must preserve a VoiceType being edited.
        voice_type = self.voice_type.text()
        self._refresh_project_select(p['id'])
        self.voice_type.setText(voice_type)
        self.host._log('Saved Bethesda project: ' + name)

    def _delete_project(self):
        p = self._get_project()
        if not p:
            return
        if QMessageBox.question(self, 'Delete saved project', f'Delete saved configuration for {p["name"]}? This will not delete any audio or installed FUZ files.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.projects = [v for v in self.projects if v['id'] != p['id']]
        self.store.save(self.projects)
        self._refresh_project_select('')
        self._new_project()

    def _refresh_project_select(self, selected):
        self.project_select.blockSignals(True)
        self.project_select.clear()
        self.project_select.addItem('Unsaved project', '')
        for p in self.projects:
            self.project_select.addItem(p.get('name', '(unnamed)'), p['id'])
        idx = self.project_select.findData(selected)
        self.project_select.setCurrentIndex(max(0, idx))
        self.project_select.blockSignals(False)
        self._project_selected()

    def _project_selected(self):
        p = self._get_project()
        if p is None:
            self.voice_type.clear()
            self.voice_select.blockSignals(True)
            self.voice_select.clear()
            self.voice_select.addItem('Unsaved voice assignment', '')
            self.voice_select.blockSignals(False)
            return
        self.project_name.setText(p.get('name', ''))
        self.plugin.setText(p.get('plugin', ''))
        self.root.setText(p.get('root', ''))
        self._select_combo(self.game, p.get('game', 'fallout4'))
        self._select_combo(self.mode, p.get('destination_mode', 'game_data'))
        self._refresh_voice_select(self.settings.value('bethesda/last_voice/' + p['id'], ''))
        self._update_preview()

    @staticmethod
    def _select_combo(combo, data):
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _refresh_voice_select(self, selected):
        p = self._get_project()
        self.voice_type.clear()
        self.voice_select.blockSignals(True)
        self.voice_select.clear()
        self.voice_select.addItem('Unsaved voice assignment', '')
        for v in (p or {}).get('voices', []):
            self.voice_select.addItem(v['name'], v['id'])
        self._select_combo(self.voice_select, selected)
        self.voice_select.blockSignals(False)
        if selected:
            self._voice_selected()

    def _voice_selected(self):
        p = self._get_project()
        vid = self.voice_select.currentData()
        v = next((v for v in (p or {}).get('voices', []) if v['id'] == vid), None)
        if not v:
            return
        self.settings.setValue('bethesda/last_voice/' + p['id'], vid)
        self.voice_type.setText(v.get('voice_type', ''))
        voice_id = v.get('voice_id', '')
        if self.host.voice.count() > 1:
            if voice_id and self.host.voice.findData(voice_id) < 0:
                QMessageBox.warning(self, 'Missing voice reference', 'The saved voice reference is not available in the current or legacy voice library.')
            else:
                self._select_combo(self.host.voice, voice_id)
        self._select_combo(self.host.model, v.get('model', 'nano'))

    def reapply_selected_voice(self):
        """Call after the host populates the voice library during startup."""
        if self.voice_select.currentData():
            self._voice_selected()

    def _save_voice_profile(self):
        p = self._get_project()
        if not p:
            QMessageBox.information(self, 'Save the project first', 'Save a mod project before saving voice assignments.')
            return
        voice_type = self.voice_type.text().strip()
        if not voice_type:
            QMessageBox.warning(self, 'Voice type required', 'Enter the exact Creation Kit VoiceType EditorID.')
            return
        current = next((v for v in p.get('voices', []) if v['id'] == self.voice_select.currentData()), None)
        name, ok = QInputDialog.getText(self, 'Voice assignment name', 'Profile name:', text=current['name'] if current else voice_type)
        if not ok or not name.strip():
            return
        if current is None:
            current = self.store.new_voice(name, voice_type, self.host.voice.currentData() or '', self.host.model.currentData())
            p['voices'].append(current)
        else:
            current.update(name=name.strip(), voice_type=voice_type, voice_id=self.host.voice.currentData() or '', model=self.host.model.currentData())
        self.store.save(self.projects)
        self._refresh_voice_select(current['id'])
        self.host._log('Saved voice assignment: ' + name.strip())

    def _delete_voice_profile(self):
        p = self._get_project()
        if p and self.voice_select.currentData():
            p['voices'] = [v for v in p['voices'] if v['id'] != self.voice_select.currentData()]
            self.store.save(self.projects)
            self._refresh_voice_select('')

    def _config(self):
        sidecars = self.host.storage / 'bethesda_source'
        return BethesdaExportSettings(
            source_audio=self.audio.text().strip(), text=self.transcript.toPlainText(),
            game=self.game.currentData(), plugin_name=self.plugin.text().strip(),
            voice_type=self.voice_type.text().strip(), response_filename=self.response.text().strip(),
            output_root=self.root.text().strip(), facefx_path=self.facefx.text().strip(),
            fonix_path=self.fonix.text().strip(), encoder_path=self.encoder.text().strip(),
            ffmpeg_path=self.ffmpeg.text().strip(), encoder_type=self.encoder_type.currentData(),
            bitrate_kbps=self.bitrate.currentData(), keep_intermediate=self.keep.isChecked(),
            destination_mode=self.mode.currentData(), sidecar_root=str(sidecars))

    def _update_preview(self):
        try:
            # Path calculation does not need a source file, nor installed tools.
            config = self._config()
            path = expected_fuz_path(config)
            self.preview.setText('FUZ installation target:\n' + str(path) +
                ('\nExisting file: replacement needs confirmation and a backup.' if path.exists() else '\nNew file: no overwrite required.'))
        except (ValueError, OSError, BethesdaExportError) as exc:
            self.preview.setText('Incomplete destination: ' + str(exc))

    def _start(self):
        if self.thread is not None or self.host.thread is not None:
            QMessageBox.information(self, 'Busy', 'Finish the active job first.')
            return
        if any(getattr(getattr(self.host, name, None), 'is_busy', False)
               for name in ('plugins', 'engine_lab', 'model_manager')):
            QMessageBox.information(self, 'Operation running',
                'Finish or cancel the active voice, model, or plugin operation before starting an export.')
            return
        try:
            # Previewing a target never creates project files. Only a real
            # export needs its source/backup directory to be writable.
            sidecars = self.host.storage / 'bethesda_source'
            sidecars.mkdir(parents=True, exist_ok=True)
            config = self._config()
            config.validate()
            path = expected_fuz_path(config)
        except (BethesdaExportError, OSError) as exc:
            QMessageBox.warning(self, 'Check export settings', str(exc))
            return
        if path.exists():
            choice = QMessageBox.question(self, 'Replace existing dialogue?',
                'This FUZ already exists:\n' + str(path) +
                '\n\nReplace it? The original will first be backed up in this application’s project files.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                return
            config = replace(config, overwrite_existing=True)
        self._save_tools()
        self.run_button.setEnabled(False)
        self.thread = QThread(self)
        self.worker = ExportTask(config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.message.connect(self._progress)
        self.worker.complete.connect(self._finished)
        self.worker.complete.connect(self.thread.quit)
        self.worker.complete.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _progress(self, text):
        self.status.setText(text)
        self.host._log(text)

    def _finished(self, path, error):
        if error:
            self.status.setText('Export failed: ' + error)
            QMessageBox.warning(self, 'Bethesda export failed', error)
            self.host._log('Bethesda export failed: ' + error)
        else:
            self.status.setText('Installed: ' + path)
            self.host._log('Installed FUZ: ' + path)
            QMessageBox.information(self, 'FUZ installed', 'FUZ successfully generated and installed:\n' + path +
                '\n\nIn-game voice and lip synchronization still require testing. No plugin was modified.')
            self._update_preview()

    def _thread_finished(self):
        self.thread = None
        self.worker = None
        self.run_button.setEnabled(True)

    def _save_tools(self):
        for name in ('facefx', 'fonix', 'encoder', 'ffmpeg'):
            self.settings.setValue('bethesda/tools/' + name, getattr(self, name).text())
        self.settings.setValue('bethesda/tools/encoder_type', self.encoder_type.currentData())
        self.settings.setValue('bethesda/tools/bitrate', self.bitrate.currentData())

    def _load(self):
        for name in ('facefx', 'fonix', 'encoder', 'ffmpeg'):
            getattr(self, name).setText(str(self.settings.value('bethesda/tools/' + name, '')))
        self._select_combo(self.encoder_type, self.settings.value('bethesda/tools/encoder_type', 'wmaencoders'))
        self._select_combo(self.bitrate, int(self.settings.value('bethesda/tools/bitrate', 48)))
        try:
            self.projects = self.store.load()
        except ProfileError as exc:
            QMessageBox.warning(self, 'Cannot read saved projects', str(exc))
            self.projects = []
        self._refresh_project_select(self.settings.value('bethesda/last_project', ''))
        self._update_preview()


def _horizontal(*items):
    line = QHBoxLayout()
    for widget in items:
        line.addWidget(widget)
    return line


def _container(layout):
    widget = QWidget()
    widget.setLayout(layout)
    return widget
