"""PyQt6 GUI for Plague's Voice Studio."""
from __future__ import annotations
import sys
import re
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSettings, QThread, Qt, QUrl, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QFont, QKeySequence, QIcon, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSlider, QSpinBox, QSplitter, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout,
    QWidget, QHeaderView, QAbstractItemView, QDialog,
)
from . import __version__
from .jobs import LANGUAGES, MODEL_CHOICES, NarrationJob
from .paths import user_data_dir
from .settings_migration import copy_legacy_settings
from .pvs_library import CompatibleVoiceLibrary, new_export_directory, narration_basename
from .export_browser import ExportBrowser
from .worker import RenderWorker
from .narration_markup import plan_script, MarkupError
from .engine_lab import EngineLab
from .model_manager import ModelManager
from .help_center import HelpCenter
from .about_dialog import AboutDialog
from .update_dialog import UpdateDialog
from .ui_theme import CSS
from .plugin_manager import PluginManager




def row(*widgets):
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout


class FloatControl(QWidget):
    def __init__(self, text: str, value: float, min_value: int, max_value: int):
        super().__init__()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_value, max_value)
        self.slider.setValue(int(value * 100))
        self.label = QLabel(f"{value:.2f}")
        self.label.setFixedWidth(35)
        self.slider.valueChanged.connect(lambda v: self.label.setText(f"{v / 100:.2f}"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 3)
        layout.addWidget(QLabel(text))
        layout.addLayout(row(self.slider, self.label))

    def value(self) -> float:
        return self.slider.value() / 100


def _asset_path(name: str) -> Path:
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return base / 'assets' / name

def _application_icon() -> QIcon:
    """Locate branding artwork for source and PyInstaller launches."""
    return QIcon(str(_asset_path('plagues-voice-studio-icon.png')))

def _load_pixmap(name: str, width: int | None = None, height: int | None = None) -> QPixmap:
    pixmap = QPixmap(str(_asset_path(name)))
    if pixmap.isNull():
        return pixmap
    if width or height:
        if width and not height:
            pixmap = pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        elif height and not width:
            pixmap = pixmap.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
        else:
            pixmap = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return pixmap


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Plague's Voice Studio {__version__}")
        self.setWindowIcon(_application_icon())
        self.resize(1330, 880)
        self.setMinimumSize(940, 650)
        self.storage = user_data_dir()
        self.voices = CompatibleVoiceLibrary(self.storage)
        self.settings = QSettings("KaotickJay", "PlaguesVoiceStudio")
        copy_legacy_settings(self.settings, QSettings("KaotickJay", "PlaguesVoiceStudio030Experimental"))
        self.queue: list[NarrationJob] = []
        self.results: dict[str, str] = {}
        self.states: dict[str, str] = {}
        self.current_jobs: list[NarrationJob] = []
        self.thread: QThread | None = None
        self.worker: RenderWorker | None = None
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.85)
        self.playback_file = ""
        self._about_dialog: AboutDialog | None = None
        self._update_dialog: UpdateDialog | None = None
        self._preferred_voice_id = str(self.settings.value('last_voice', '') or '')
        self.player.playbackStateChanged.connect(self._playback_changed)
        self._build_ui()
        self.plugins = PluginManager(self)
        self._restore_settings()
        self._refresh_voices()
        if self.bethesda_tab is not None:
            self.bethesda_tab.reapply_selected_voice()
        self._on_model_changed()
        self._on_text_changed()
        # Update checks are disabled by default and never block the first paint.
        if UpdateDialog._setting_enabled(self.settings.value(UpdateDialog.SETTING, False)):
            QTimer.singleShot(1500, self._check_updates_on_start)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        body = QVBoxLayout(root)
        body.setContentsMargins(15, 12, 15, 12)
        body.setSpacing(12)
        brand = QFrame()
        brand.setObjectName('brandHeader')
        header = QHBoxLayout(brand)
        header.setContentsMargins(16, 8, 16, 8)
        header.setSpacing(12)
        header_logo = QLabel()
        header_logo.setPixmap(_load_pixmap('plagues-voice-studio-icon.png', 70, 70))
        header_logo.setFixedSize(76, 76)
        header_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(header_logo)
        title_block = QVBoxLayout()
        title = QLabel("PLAGUE'S VOICE STUDIO")
        title.setObjectName('sectionTitle')
        title.setStyleSheet('font-size: 23px; letter-spacing: 1px;')
        title_block.addWidget(title)
        tagline = QLabel('CREATED BY KAOTICK JAY   |   LOCAL AI VOICE PRODUCTION')
        tagline.setObjectName('mutedText')
        title_block.addWidget(tagline)
        header.addLayout(title_block)
        header.addStretch()
        updates_button = QPushButton('Check for updates')
        updates_button.setObjectName('updates_button')
        updates_button.setToolTip('Check official GitHub releases. No automatic download or install.')
        updates_button.clicked.connect(self._show_updates)
        header.addWidget(updates_button)
        help_button = QPushButton('Help center')
        help_button.setObjectName('quietButton')
        help_button.clicked.connect(self._show_help)
        header.addWidget(help_button)
        about = QPushButton('About')
        about.setObjectName('about_button')
        about.clicked.connect(self._about)
        header.addWidget(about)
        body.addWidget(brand)

        self.tabs = QTabWidget()
        body.addWidget(self.tabs, 1)
        narrate_tab = QWidget()
        self.tabs.addTab(narrate_tab, "Narration Studio")
        narrate_layout = QVBoxLayout(narrate_tab)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        narrate_layout.addWidget(splitter)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(2, 10, 7, 4)
        controls = QHBoxLayout()
        load_script = QPushButton("Import text...")
        load_script.clicked.connect(self._load_script)
        save_script = QPushButton("Save text...")
        save_script.clicked.connect(self._save_script)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self.editor.clear())
        controls.addWidget(load_script)
        controls.addWidget(save_script)
        controls.addWidget(clear)
        controls.addStretch()
        self.counter = QLabel("0 characters")
        self.counter.setStyleSheet("color: #a4b9a9;")
        controls.addWidget(self.counter)
        left_layout.addLayout(controls)
        tag_tools = QHBoxLayout()
        for label, callback, tooltip in [
            ("Pause...", self._insert_pause, "Insert a precise 0–10 second silent pause"),
            ("Emphasis", lambda: self._wrap_selection("emphasis"), "Increase gain modestly on selected words"),
            ("Rate...", self._insert_rate, "Change speaking speed without changing pitch"),
            ("Volume...", self._insert_volume, "Set linear volume for selected passage"),
            ("Check tags", self._check_tags, "Validate markup before generating; show the render plan"),
        ]:
            action = QPushButton(label)
            action.setToolTip(tooltip)
            action.clicked.connect(callback)
            tag_tools.addWidget(action)
        left_layout.addLayout(tag_tools)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Paste your script here. Keep natural punctuation for expressive narration.\n\n"
            "For Turbo and Nano, use supported tags such as [chuckle] or [laugh] where appropriate.\n\n"
            "App directives: [pause:0.8s], [emphasis]text[/emphasis], "
            "[rate:0.90]text[/rate], [volume:0.85]text[/volume].\n"
            "Native tags such as [chuckle] are best suited to Turbo and Nano."
        )
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.editor.textChanged.connect(self._on_text_changed)
        left_layout.addWidget(self.editor, 1)
        self.tag_warning = QLabel('')
        self.tag_warning.setObjectName('warningText')
        self.tag_warning.setWordWrap(True)
        self.tag_warning.setVisible(False)
        self.tag_warning.setAccessibleName('Model tag compatibility warning')
        left_layout.addWidget(self.tag_warning)

        export = QGroupBox("Export")
        exp_layout = QVBoxLayout(export)
        self.output = QLineEdit()
        self.output.setPlaceholderText("Output filename, auto-generated if empty")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._choose_export)
        exp_layout.addLayout(row(self.output, browse))
        self.format = QComboBox()
        self.format.addItem("WAV (PCM 16-bit)", "wav")
        self.format.addItem("MP3 (192 kbps)", "mp3")
        self.format.currentIndexChanged.connect(self._update_export_suffix)
        self.pause = QSpinBox()
        self.pause.setRange(0, 2500)
        self.pause.setSuffix(" ms")
        self.pause.setValue(180)
        self.chunk = QSpinBox()
        self.chunk.setRange(60, 2000)
        self.chunk.setSingleStep(20)
        self.chunk.setValue(220)
        fmtrow = QHBoxLayout()
        fmtrow.addWidget(QLabel("Format"))
        fmtrow.addWidget(self.format)
        fmtrow.addWidget(QLabel("Segment gap"))
        fmtrow.addWidget(self.pause)
        fmtrow.addWidget(QLabel("Max characters"))
        fmtrow.addWidget(self.chunk)
        exp_layout.addLayout(fmtrow)
        left_layout.addWidget(export)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(7, 10, 2, 4)
        model_group = QGroupBox("Speech engine")
        model_form = QFormLayout(model_group)
        self.model = QComboBox()
        for key, description in MODEL_CHOICES.items():
            self.model.addItem(description, key)
        self.model.currentIndexChanged.connect(self._on_model_changed)
        model_form.addRow("Model", self.model)
        self.device = QComboBox()
        self.device.addItem("Auto (CUDA if supported, otherwise CPU)", "auto")
        self.device.addItem("CPU", "cpu")
        self.device.addItem("NVIDIA CUDA", "cuda")
        model_form.addRow("Processor", self.device)
        self.language = QComboBox()
        for key, description in LANGUAGES.items():
            self.language.addItem(f"{description} ({key})", key)
        self.language.setCurrentIndex(list(LANGUAGES).index("en"))
        model_form.addRow("Language", self.language)
        self.model_hint = QLabel("")
        self.model_hint.setWordWrap(True)
        self.model_hint.setStyleSheet("color: #a9bba9;")
        model_form.addRow(self.model_hint)
        right_layout.addWidget(model_group)

        voice_group = QGroupBox("Voice library")
        voice_layout = QVBoxLayout(voice_group)
        self.voice = QComboBox()
        voice_layout.addWidget(self.voice)
        self.voice.currentIndexChanged.connect(self._voice_changed)
        add_voice = QPushButton("Import reference...")
        add_voice.clicked.connect(self._add_voice)
        self.remove_voice = QPushButton("Remove")
        self.remove_voice.clicked.connect(self._remove_voice)
        self.preview_voice = QPushButton("Listen")
        self.preview_voice.clicked.connect(self._preview_voice)
        voice_layout.addLayout(row(add_voice, self.preview_voice, self.remove_voice))
        self.voice_hint = QLabel("Use 6–20 seconds of clean speech from a voice you own or have permission to clone.")
        self.voice_hint.setWordWrap(True)
        self.voice_hint.setStyleSheet("color: #a9bba9;")
        voice_layout.addWidget(self.voice_hint)
        right_layout.addWidget(voice_group)

        tune = QGroupBox("Generation settings")
        tunes = QVBoxLayout(tune)
        self.exaggeration = FloatControl("Expressiveness", 0.50, 0, 100)
        self.cfg = FloatControl("CFG / pacing influence", 0.50, 0, 100)
        self.temperature = FloatControl("Temperature", 0.80, 10, 150)
        tunes.addWidget(self.exaggeration)
        tunes.addWidget(self.cfg)
        tunes.addWidget(self.temperature)
        right_layout.addWidget(tune)
        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([760, 400])

        actions = QHBoxLayout()
        self.generate = QPushButton("Generate now")
        self.generate.setObjectName("primary")
        self.generate.clicked.connect(self._generate_now)
        self.add_to_queue = QPushButton("Add to batch queue")
        self.add_to_queue.clicked.connect(self._add_job)
        self.cancel_button = QPushButton("Cancel after current segment")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        self.play = QPushButton("Play last result")
        self.play.clicked.connect(self._toggle_playback)
        self.play.setEnabled(False)
        self.open_folder = QPushButton("Open export folder")
        self.open_folder.clicked.connect(self._open_export_folder)
        self.open_folder.setEnabled(False)
        actions.addWidget(self.generate)
        actions.addWidget(self.add_to_queue)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.play)
        all_exports = QPushButton("Browse all exports")
        all_exports.clicked.connect(self._show_exports)
        actions.addWidget(all_exports)
        actions.addWidget(self.open_folder)
        narrate_layout.addLayout(actions)

        batch = QWidget()
        self.tabs.addTab(batch, "Batch Queue")
        batch_layout = QVBoxLayout(batch)
        batch_layout.addWidget(QLabel("Each queued job keeps a snapshot of its text, model, voice and export settings."))
        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setHorizontalHeaderLabels(["Job", "Model", "Voice", "Output", "Status"])
        self.queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        batch_layout.addWidget(self.queue_table)
        batch_controls = QHBoxLayout()
        self.run_queue = QPushButton("Run queued jobs")
        self.run_queue.setObjectName("primary")
        self.run_queue.clicked.connect(self._run_queue)
        self.remove_job = QPushButton("Remove selected")
        self.remove_job.clicked.connect(self._remove_job)
        self.clear_finished = QPushButton("Clear finished")
        self.clear_finished.clicked.connect(self._clear_finished)
        batch_controls.addWidget(self.run_queue)
        batch_controls.addWidget(self.remove_job)
        batch_controls.addWidget(self.clear_finished)
        batch_controls.addStretch()
        batch_layout.addLayout(batch_controls)

        self._build_bethesda_tab()
        self.export_browser = ExportBrowser(self)
        self.tabs.addTab(self.export_browser, "Export Library")
        self.engine_lab = EngineLab(self)
        self.tabs.addTab(self.engine_lab, "Voice Engines")

        self.model_manager = ModelManager(self)
        self.tabs.addTab(self.model_manager, "Model Manager")

        self.help_center = HelpCenter(self)
        self.tabs.addTab(self.help_center, 'Help')

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(240)
        self.progress.setFormat("Idle")
        bottom.addWidget(self.progress)
        self.status_label = QLabel("Ready")
        bottom.addWidget(self.status_label, 1)
        body.addLayout(bottom)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(92)
        self.log.setPlaceholderText("Session log")
        body.addWidget(self.log)
        self.setStatusBar(QStatusBar())
        for title, shortcut, slot in [
            ("Open script", "Ctrl+O", self._load_script),
            ("Save script", "Ctrl+S", self._save_script),
            ("Generate", "Ctrl+Return", self._generate_now),
            ("Help center", "F1", self._show_help),
        ]:
            action = QAction(title, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(slot)
            self.addAction(action)

    def _wrap_selection(self, tag: str):
        cursor = self.editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        if not selected:
            selected = "your text"
        opening = "[emphasis]" if tag == "emphasis" else "[" + tag + "]"
        closing = "[/" + tag.split(":", 1)[0] + "]"
        cursor.insertText(opening + selected + closing)
        self.editor.setFocus()

    def _insert_pause(self):
        seconds, ok = QInputDialog.getDouble(self, "Insert exact pause",
            "Length of silence in seconds (0–10):", 0.8, 0, 10, 2)
        if ok:
            self.editor.textCursor().insertText(f"[pause:{seconds:.2f}s]")
            self.editor.setFocus()

    def _insert_rate(self):
        speed, ok = QInputDialog.getDouble(self, "Speaking rate",
            "Rate multiplier (0.50 to 2.00; 1.00 is normal):", 0.90, 0.50, 2, 2)
        if ok:
            self._wrap_selection(f"rate:{speed:.2f}")

    def _insert_volume(self):
        gain, ok = QInputDialog.getDouble(self, "Passage volume",
            "Volume multiplier (0.00 to 2.00; 1.00 is normal):", 0.85, 0, 2, 2)
        if ok:
            self._wrap_selection(f"volume:{gain:.2f}")

    def _check_tags(self):
        try:
            steps = plan_script(self.editor.toPlainText(), self.chunk.value(), self.pause.value())
        except MarkupError as exc:
            QMessageBox.warning(self, "Narration markup error", str(exc))
            return
        spoken = sum(x.kind == 'speech' for x in steps)
        silence = sum(x.pause_ms for x in steps if x.kind == 'pause')
        preview = []
        for i, step in enumerate(steps, 1):
            if step.kind == 'pause':
                preview.append(f"{i}. PAUSE {step.pause_ms} ms")
            else:
                preview.append(f"{i}. SPEAK rate={step.rate:g} volume={step.volume:g} "
                               f"emphasis={step.emphasis}: {step.text}")
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Narration markup verified")
        dialog.setText(f"Valid script: {spoken} speech segments; {silence / 1000:g} seconds of inserted silence.")
        dialog.setInformativeText("Open Details to inspect the exact render plan. Model tags are passed through.")
        dialog.setDetailedText("\n".join(preview))
        dialog.exec()

    def _on_text_changed(self):
        text = self.editor.toPlainText() if hasattr(self, 'editor') else ''
        self.counter.setText(f'{len(text):,} characters  •  {len(text.split()):,} words')
        self._update_tag_compatibility()

    def _update_tag_compatibility(self):
        """Warn; do not strip or rewrite the writer's intended vocal effects."""
        if not all(hasattr(self, name) for name in ('editor', 'model', 'tag_warning')):
            return
        text = self.editor.toPlainText()
        unsupported = self.model.currentData() in ('english', 'multilingual-v3')
        has_effects = bool(re.search(r'\[(?:laugh|chuckle|sigh|cough|gasp|groan|cry|whisper|shout)\]', text, re.I))
        if unsupported and has_effects:
            self.tag_warning.setText('This model does not natively support Turbo/Nano vocal-event tags. '
                                     'They may be spoken aloud. Use Turbo or Nano, or remove those tags.')
            self.tag_warning.setVisible(True)
        else:
            self.tag_warning.setVisible(False)

    def _on_model_changed(self):
        key = self.model.currentData()
        multilingual = key == "multilingual-v3"
        standard = key in ("english", "multilingual-v3")
        self.language.setEnabled(multilingual)
        self.cfg.setVisible(standard)
        self.exaggeration.setVisible(standard)
        self.model_hint.setText(
            'Turbo requires a voice reference. Nano can use its available built-in voice. '
            'Both can interpret supported vocal-event tags; CFG / expressiveness controls do not apply.' if not standard else
            'Multilingual V3 offers language selection and generation controls; Turbo vocal tags may be spoken literally.' if multilingual else
            'Original English offers expressiveness and CFG controls; Turbo vocal tags are not natively supported.'
        )
        self._update_tag_compatibility()

    def _refresh_voices(self, select_id: str = ""):
        current = select_id or (self.voice.currentData() if self.voice.count() else self._preferred_voice_id)
        self.voice.blockSignals(True)
        try:
            self.voice.clear()
            self.voice.addItem('Built-in voice (when available)', '')
            for item in self.voices.list_voices():
                self.voice.addItem(f"{item['name']}  ({item['duration']}s)", item['id'])
            idx = self.voice.findData(current)
            self.voice.setCurrentIndex(max(idx, 0))
        finally:
            self.voice.blockSignals(False)
        if hasattr(self, "engine_lab"):
            self.engine_lab.refresh_voices()
        self._voice_changed()

    def _voice_changed(self):
        selected = self.voice.currentData() or ''
        self._preferred_voice_id = selected
        self.settings.setValue('last_voice', selected)
        has_voice = bool(selected)
        self.remove_voice.setEnabled(has_voice and not str(selected).startswith(('legacy:', 'stable:')))
        self.preview_voice.setEnabled(has_voice)

    def _preview_voice(self):
        path = self.voices.resolve(self.voice.currentData() or "")
        if not path:
            return
        self._play_file(path)

    def _add_voice(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose reference voice", "", "Audio (*.wav *.flac *.ogg *.mp3)")
        if not path:
            return
        name, ok = QInputDialog.getText(self, "Voice name", "Name this voice:", text=Path(path).stem)
        if not ok:
            return
        consent = QMessageBox.question(self, "Voice permission",
            "Do you own this recording or have the speaker's permission to clone their voice?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if consent != QMessageBox.StandardButton.Yes:
            return
        try:
            item = self.voices.import_voice(name, Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "Voice import failed", str(exc))
            return
        self._refresh_voices(item['id'])
        self._log(f"Imported reference voice: {name}")

    def _remove_voice(self):
        vid = self.voice.currentData()
        if not vid:
            return
        if self.thread is not None:
            QMessageBox.warning(self, "Generation running", "Wait until generation finishes before removing voices.")
            return
        if QMessageBox.question(self, "Remove voice", "Delete this saved reference audio?",
              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.voices.remove_voice(vid)
        except ValueError as exc:
            QMessageBox.information(self, "Read-only legacy voice", str(exc))
            return
        self._refresh_voices()

    def _default_output(self):
        directory = new_export_directory(self.storage)
        current = self.voice.currentData()
        names = {item['id']: item['name'].replace(' (v0.1.x)', '') for item in self.voices.list_voices()}
        voice_name = names.get(current) if current else None
        stem = narration_basename(voice_name)
        ext = self.format.currentData()
        used = {Path(j.output_path) for j in self.queue}
        candidate = directory / f'{stem}.{ext}'
        index = 2
        while candidate.exists() or candidate in used:
            candidate = directory / f'{stem}_{index}.{ext}'
            index += 1
        return str(candidate)

    def _show_exports(self):
        self.export_browser.refresh()
        self.tabs.setCurrentWidget(self.export_browser)

    def _choose_export(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export narration",
                      self.output.text().strip() or self._default_output(),
                      "WAV (*.wav);;MP3 (*.mp3)")
        if filename:
            fmt = Path(filename).suffix.lower().lstrip('.')
            if fmt not in ("wav", "mp3"):
                fmt = self.format.currentData()
                filename += f".{fmt}"
            self.format.setCurrentIndex(self.format.findData(fmt))
            self.output.setText(filename)

    def _update_export_suffix(self):
        path = self.output.text().strip()
        if path and Path(path).suffix.lower() in (".wav", ".mp3"):
            self.output.setText(str(Path(path).with_suffix('.' + self.format.currentData())))

    def _accept_plugin_text(self, text: str) -> bool:
        """Transfer reviewed copy into the editor without starting speech generation."""
        if self.thread is not None:
            QMessageBox.information(self, 'Narration running', 'Wait for narration to finish before replacing the script.')
            return False
        if not text.strip():
            return False
        if self.editor.toPlainText().strip():
            answer = QMessageBox.question(self, 'Replace narration script?',
                'Replace the current narration text with the reviewed plugin text? Copy or save the current text first if needed.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return False
        self.editor.setPlainText(text)
        self.tabs.setCurrentIndex(0)
        self.raise_(); self.activateWindow()
        self.status_label.setText('Reviewed plugin text loaded. Choose a voice and Generate when ready.')
        return True

    def _load_script(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open script", "", "Text files (*.txt *.md);;All files (*)")
        if filename:
            try:
                self.editor.setPlainText(Path(filename).read_text(encoding="utf-8-sig"))
            except Exception as exc:
                QMessageBox.warning(self, "Open failed", str(exc))

    def _save_script(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save script", "narration.txt", "Text files (*.txt)")
        if filename:
            try:
                Path(filename).write_text(self.editor.toPlainText(), encoding="utf-8")
            except Exception as exc:
                QMessageBox.warning(self, "Save failed", str(exc))

    def _snapshot(self) -> NarrationJob | None:
        output = self.output.text().strip() or self._default_output()
        output_path = Path(output).expanduser()
        if not output_path.is_absolute():
            output_path = Path.home() / output_path
        job = NarrationJob.new(
            text=self.editor.toPlainText(), model=self.model.currentData(),
            device=self.device.currentData(), language=self.language.currentData(),
            voice_path=self.voices.resolve(self.voice.currentData() or ""),
            output_path=str(output_path), format=self.format.currentData(),
            max_chars=self.chunk.value(), pause_ms=self.pause.value(),
            exaggeration=self.exaggeration.value(), cfg_weight=self.cfg.value(),
            temperature=self.temperature.value(),
        )
        try:
            job.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Check narration settings", str(exc))
            return None
        return job

    def _append_job(self, job):
        self.queue.append(job)
        self.states[job.job_id] = "Queued"
        self._refresh_queue()

    def _add_job(self):
        job = self._snapshot()
        if job is not None:
            self._append_job(job)
            self._log(f"Queued: {Path(job.output_path).name}")

    def _generate_now(self):
        if self.thread is not None:
            return
        job = self._snapshot()
        if job is not None:
            self._append_job(job)
            self._start_jobs([job])

    def _run_queue(self):
        ready = [j for j in self.queue if self.states.get(j.job_id) == "Queued"]
        if not ready:
            QMessageBox.information(self, "Batch queue", "No queued jobs to run.")
            return
        self._start_jobs(ready)

    def _start_jobs(self, jobs: list[NarrationJob]):
        if self.plugins.is_busy:
            QMessageBox.information(self, 'Writer running', 'Finish or cancel the writer operation before starting narration.')
            return
        if self.thread is not None:
            return
        if any(getattr(getattr(self, name, None), 'is_busy', False)
               for name in ('engine_lab', 'model_manager', 'bethesda_tab')):
            QMessageBox.information(self, 'Operation running',
                'Finish or cancel the active voice, model, or export operation before starting narration.')
            return
        self.current_jobs = jobs[:]
        self.thread = QThread(self)
        self.worker = RenderWorker(jobs)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.message.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.job_started.connect(self._job_started)
        self.worker.job_finished.connect(self._job_finished)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        for button in (self.generate, self.run_queue, self.remove_job, self.clear_finished):
            button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setFormat("Starting...")
        self.tabs.setCurrentIndex(1 if len(jobs) > 1 else 0)
        self.thread.start()

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self._log("Cancellation requested, finishing current segment...")
            self.cancel_button.setEnabled(False)

    def _job_started(self, job_id):
        self.states[job_id] = "Running"
        self.progress.setValue(0)
        self._refresh_queue()

    def _on_progress(self, count, total):
        self.progress.setValue(int(100 * count / total))
        self.progress.setFormat(f"Segment {count}/{total}, %p%")

    def _job_finished(self, job_id, output, error):
        self.states[job_id] = "Failed" if error and error != "Cancelled" else "Cancelled" if error else "Complete"
        if output:
            self.results[job_id] = output
            self.last_output = output
            self.play.setEnabled(True)
            self.open_folder.setEnabled(True)
            # Newly generated files may be outside the current Export Library root.
            self.export_browser.add_root(Path(output).parent)
        if error:
            self._log(f"{job_id[:8]}: {error}")
        self._refresh_queue()

    def _thread_finished(self):
        self.thread = None
        self.worker = None
        self.current_jobs = []
        for button in (self.generate, self.run_queue, self.remove_job, self.clear_finished):
            button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setFormat("Idle")
        self.status_label.setText("Ready")
        self._log("Batch finished.")

    def _refresh_queue(self):
        self.queue_table.setRowCount(len(self.queue))
        for i, job in enumerate(self.queue):
            voice = Path(job.voice_path).stem[:18] if job.voice_path else "Default"
            for col, value in enumerate((job.job_id[:8], job.model, voice,
                                          Path(job.output_path).name, self.states.get(job.job_id, "Queued"))):
                item = QTableWidgetItem(value)
                if col == 3:
                    item.setToolTip(self.results.get(job.job_id, job.output_path))
                self.queue_table.setItem(i, col, item)

    def _remove_job(self):
        if self.thread is not None:
            return
        row_index = self.queue_table.currentRow()
        if 0 <= row_index < len(self.queue):
            job = self.queue.pop(row_index)
            self.states.pop(job.job_id, None)
            self.results.pop(job.job_id, None)
            self._refresh_queue()

    def _clear_finished(self):
        if self.thread is not None:
            return
        self.queue = [j for j in self.queue if self.states.get(j.job_id) == "Queued"]
        self._refresh_queue()

    def _play_file(self, path: str):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and self.playback_file == path:
            self.player.stop()
            return
        self.playback_file = path
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _toggle_playback(self):
        if getattr(self, "last_output", None):
            self._play_file(self.last_output)

    def _playback_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        if hasattr(self, "play"):
            self.play.setText("Stop playback" if playing and self.playback_file == getattr(self, "last_output", "") else "Play last result")
        if hasattr(self, "preview_voice"):
            selected = self.voices.resolve(self.voice.currentData() or "")
            self.preview_voice.setText("Stop reference" if playing and self.playback_file == selected else "Listen")

    def _open_export_folder(self):
        if getattr(self, "last_output", None):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.last_output).parent)))

    def _log(self, message: str):
        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.status_label.setText(message[-115:])

    def _show_help(self):
        self.tabs.setCurrentWidget(self.help_center)
        self.help_center.focus_search()

    def _get_updates_dialog(self) -> UpdateDialog:
        if self._update_dialog is None:
            self._update_dialog = UpdateDialog(self)
        return self._update_dialog

    def _show_updates(self):
        dialog = self._get_updates_dialog()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _check_updates_on_start(self):
        if UpdateDialog._setting_enabled(self.settings.value(UpdateDialog.SETTING, False)):
            self._get_updates_dialog().check_now(automatic=True)

    def _about(self):
        """Persistent About dialog, no nested Qt event loop or model imports."""
        if self._about_dialog is None:
            self._about_dialog = AboutDialog(self)
        self._about_dialog.show()
        self._about_dialog.raise_()
        self._about_dialog.activateWindow()

    def _restore_settings(self):
        key = self.settings.value("model", "nano")
        i = self.model.findData(key)
        if i >= 0:
            self.model.setCurrentIndex(i)
        fmt = self.settings.value("format", "wav")
        i = self.format.findData(fmt)
        if i >= 0:
            self.format.setCurrentIndex(i)
        self.pause.setValue(int(self.settings.value("pause_ms", 180)))
        self.chunk.setValue(int(self.settings.value("max_chars", 220)))

    def _build_bethesda_tab(self):
        # The production converter depends on Windows FaceFX/xWMA tooling.
        # Portable container/project helpers remain usable independently.
        self.bethesda_tab = None
        if sys.platform == 'win32':
            from .bethesda_widget import BethesdaExportTab
            self.bethesda_tab = BethesdaExportTab(self)
            self.tabs.addTab(self.bethesda_tab, "Bethesda Voice Export")

    def closeEvent(self, event: QCloseEvent):
        if self.plugins.is_busy:
            self.plugins.cancel_all()
            QMessageBox.information(self, 'Stopping plugin operation',
                'The writer is stopping its model or download. Close Voice Studio again after it finishes.')
            event.ignore()
            return
        if self._update_dialog is not None and self._update_dialog.is_checking:
            QMessageBox.information(self, 'Checking for updates',
                'An update check is finishing. Please try closing Voice Studio again shortly.')
            event.ignore()
            return
        if self.thread is not None or any(
                getattr(getattr(self, name, None), 'is_busy', False)
                for name in ('bethesda_tab', 'engine_lab', 'model_manager')):
            QMessageBox.information(self, "Generation running",
                "Please stop generation or model downloads and wait until all tasks finish before closing.")
            event.ignore()
            return
        self.settings.setValue("model", self.model.currentData())
        self.settings.setValue("format", self.format.currentData())
        self.settings.setValue("pause_ms", self.pause.value())
        self.settings.setValue("max_chars", self.chunk.value())
        if self.bethesda_tab is not None:
            self.bethesda_tab._save_tools()
        self.player.stop()
        self.plugins.close_all()
        super().closeEvent(event)


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Plague's Voice Studio")
    app.setWindowIcon(_application_icon())
    app.setOrganizationName("KaotickJay")
    app.setStyle("Fusion")
    app.setStyleSheet(CSS)
    window = MainWindow()
    window.show()
    return app.exec()
