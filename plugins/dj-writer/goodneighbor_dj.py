#!/usr/bin/env python3
"""Goodneighbor / Plague Radio: local AI writing and a preserved classic library."""
import json
import os
import random
import re
import sys
from pathlib import Path
if '--smoke-test' in sys.argv:
    # Persist diagnostics even in a windowed executable without a console.
    import faulthandler
    _smoke_log = open(sys.argv[sys.argv.index('--smoke-test') + 1] + '.log', 'w', encoding='utf-8')
    sys.stdout = sys.stderr = _smoke_log
    faulthandler.enable(file=_smoke_log)
    faulthandler.dump_traceback_later(20, file=_smoke_log)
    print('Importing DJ Writer GUI', flush=True)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, QFileDialog,
    QMessageBox, QCheckBox, QSplitter, QScrollArea, QFrame, QToolButton,
    QDialog, QTextBrowser, QDialogButtonBox, QSizePolicy)
from writer_theme import THEME, apply_theme

from dj_engine import DialogueEngine, CATEGORIES, MOODS, LENGTHS, DJS, load_content
from ad_manager import load_campaigns
from ad_manager_gui import AdManagerDialog
from ai_writer import default_settings, load_settings
from ai_studio import AIControls
from script_prompts import DEFAULT_WORDS
from speech_director import render, export_json, clean_spoken_text, CHATTERBOX_TAGS

APP_NAME = 'Goodneighbor / Plague Radio DJ Writer'
VERSION = '0.8.12'
DATA = Path(os.environ.get('GOODNEIGHBOR_DJ_HOME', str(Path.home() / '.goodneighbor_blues_dj')))
HISTORY = DATA / 'history.json'
CAMPAIGNS = DATA / 'advertisers.json'
ADS = ['Goodneighbor Blues', 'Plague Radio', 'The Third Rail', 'Memory Den', 'Daisy’s Discounts', 'KL-E-0’s Guns', 'Hotel Rexford', 'The Rusty Lantern', 'Mirelight Repairs', 'The Last Stop Diner', 'Commonwealth Casket Company', 'Rad-Roach Exterminators', 'Ash & Ember Salvage', 'The Midnight Courier', 'Vault-Tec Surplus Outlet', 'The Tin Can Clinic', 'The Red Rocket Wash']
CATS = CATEGORIES

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        apply_theme(QApplication.instance())
        self.setWindowTitle(f'{APP_NAME} • {VERSION}')
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / 'assets' / 'dj-writer.ico')))
        self.resize(1320, 960)
        self.setMinimumSize(1000, 720)
        DATA.mkdir(parents=True, exist_ok=True)
        self.records = self.load_history()
        self.history_index = len(self.records)
        try:
            self.campaigns = load_campaigns(CAMPAIGNS)
        except (OSError, ValueError) as exc:
            self.campaigns = []
            QMessageBox.warning(self, 'Ad database', f'Unable to load custom advertisements. Your file was not modified.\n{exc}')
        self.engine = DialogueEngine(campaigns=self.campaigns)
        root = QWidget(); self.setCentralWidget(root)
        main = QVBoxLayout(root); main.setSpacing(6); main.setContentsMargins(14, 8, 14, 8)
        masthead = QFrame(); masthead.setObjectName('masthead')
        brand_row = QHBoxLayout(masthead); brand_row.setContentsMargins(15, 8, 20, 8)
        logo = QLabel(); logo.setObjectName('brandLogo')
        logo.setPixmap(QPixmap(str(Path(__file__).resolve().parent / 'assets/dj-writer.png')).scaled(62, 62, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setFixedSize(66, 66); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(logo)
        brand_text = QVBoxLayout(); brand_text.setSpacing(3)
        eyebrow = QLabel('PLAGUED MODS  /  GOODNEIGHBOR RECORDS'); eyebrow.setObjectName('eyebrow')
        title = QLabel('DJ WRITER'); title.setObjectName('brand')
        sub = QLabel('A voice begins with a good script.'); sub.setObjectName('muted')
        brand_text.addWidget(eyebrow); brand_text.addWidget(title); brand_text.addWidget(sub)
        brand_row.addLayout(brand_text, 1)
        badge = QLabel(f'VOICE STUDIO COMPANION\nVersion {VERSION}'); badge.setObjectName('badge')
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter); brand_row.addWidget(badge)
        main.addWidget(masthead)
        mode_row = QHBoxLayout(); mode_row.addWidget(QLabel('Writing mode'))
        self.mode = QComboBox(); self.mode.addItems(['AI Studio', 'Classic Generator'])
        mode_row.addWidget(self.mode); mode_row.addStretch();
        self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setHandleWidth(5)
        self.workspace_splitter.setToolTip('Drag the horizontal dividers to resize the three control rows.')
        controls_page = QWidget(); controls = QHBoxLayout(controls_page)
        controls.setContentsMargins(0, 0, 0, 0); controls.setSpacing(6)
        self.controls_scroll = controls_page
        self.workspace_splitter.addWidget(controls_page)
        result_page = QGroupBox('Script desk'); result_layout = QVBoxLayout(result_page)
        result_layout.setContentsMargins(10, 15, 10, 5)
        result_page.setMinimumHeight(260); result_layout.setSpacing(5)
        self.workspace_splitter.addWidget(result_page)
        bottom_page = QWidget(); bottom_layout = QHBoxLayout(bottom_page)
        bottom_layout.setContentsMargins(0, 0, 0, 0); bottom_layout.setSpacing(8)
        bottom_scroll = QScrollArea(); bottom_scroll.setWidgetResizable(True)
        bottom_scroll.setFrameShape(QFrame.Shape.NoFrame); bottom_scroll.setWidget(bottom_page)
        bottom_scroll.setMinimumHeight(125)
        self.settings_scroll = bottom_scroll
        self.workspace_splitter.addWidget(bottom_scroll)
        main.addWidget(self.workspace_splitter, stretch=1)
        self.request_group = QGroupBox('Broadcast controls'); grid = QGridLayout(self.request_group)
        grid.setVerticalSpacing(5)
        self.dj = QComboBox(); self.dj.addItems(DJS); self.dj.currentTextChanged.connect(self.on_dj_changed)
        self.cat = QComboBox(); self.cat.addItems(CATS); self.cat.currentTextChanged.connect(self.on_category_changed)
        self.title_field = QLineEdit(); self.title_field.setPlaceholderText('Optional song title')
        self.artist = QLineEdit(); self.artist.setPlaceholderText('Optional artist name')
        self.sponsor = QComboBox(); self.sponsor.setEditable(True); self.refresh_advertisers()
        self.sponsor.setToolTip('Choose an advertiser from the dropdown or type a custom name. Used for Ad / promo scripts.')
        self.sponsor.setMaxVisibleItems(18)
        self.mood = QComboBox(); self.mood.addItems(MOODS)
        self.length = QComboBox(); self.length.addItems(LENGTHS); self.length.setCurrentText('Medium')
        for combo in (self.dj, self.cat, self.sponsor, self.mood, self.length):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(10)
            combo.setMinimumWidth(0)
        for index, (label, widget) in enumerate((('DJ', self.dj), ('Format', self.cat), ('Song', self.title_field), ('Artist', self.artist), ('Advertiser', self.sponsor), ('Mood', self.mood))):
            row_index, column = divmod(index, 3)
            grid.addWidget(QLabel(label), row_index, column * 2); grid.addWidget(widget, row_index, column * 2 + 1)
        for column in (1, 3, 5): grid.setColumnStretch(column, 1)
        self.length_label = QLabel('Classic length')
        grid.addWidget(self.length_label, 2, 0); grid.addWidget(self.length, 2, 1)
        grid.addLayout(mode_row, 2, 2, 1, 3)
        controls.addWidget(self.request_group)
        try:
            settings = load_settings(DATA / 'ai_studio.json')
        except (OSError, ValueError) as exc:
            settings = default_settings()
            QMessageBox.warning(self, 'AI settings', f'Unable to load AI settings. The saved file was not changed.\n{exc}')
        self.ai = AIControls(self, settings, DATA)
        bottom_layout.addWidget(self.ai, 1)
        desk = QHBoxLayout()
        desk_title = QLabel('SCRIPT DESK'); desk_title.setObjectName('sectionTitle'); desk.addWidget(desk_title)
        desk.addStretch()
        self.script_stats = QLabel('0 words'); self.script_stats.setObjectName('scriptStats'); desk.addWidget(self.script_stats)
        desk_title.hide()
        row = QHBoxLayout()
        self.generate_button = QPushButton('Generate'); self.generate_button.setObjectName('primary'); self.generate_button.clicked.connect(self.on_generate)
        self.cancel_button = QPushButton('Cancel'); self.cancel_button.setEnabled(False); self.cancel_button.clicked.connect(self.ai.cancel)
        self.copy_button = QPushButton('Copy script'); self.copy_button.clicked.connect(self.copy)
        self.save_button = QPushButton('Export for Voice Studio'); self.save_button.clicked.connect(self.save_txt); self.save_button.setEnabled(False)
        self.history_button = QPushButton('Previous result'); self.history_button.clicked.connect(self.restore_history)
        self.ads_button = QPushButton('Ad Manager'); self.ads_button.clicked.connect(self.open_ad_manager)
        row.addWidget(self.generate_button); row.addWidget(self.cancel_button); row.addLayout(desk, 1); row.addWidget(self.history_button)
        grid.addWidget(self.ads_button, 2, 5)
        result_layout.addLayout(row)
        self.direction_toggle = QToolButton(); self.direction_toggle.setObjectName('disclosure')
        self.direction_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.direction_toggle.setCheckable(True); self.direction_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.direction_toggle.setArrowType(Qt.ArrowType.RightArrow)
        narration_group = QGroupBox('Narration tools'); narration_layout = QVBoxLayout(narration_group)
        bottom_layout.addWidget(narration_group, 1)
        narration_layout.addWidget(self.direction_toggle)
        direction_panel = QWidget(); direction_layout = QVBoxLayout(direction_panel); direction_layout.setContentsMargins(0, 0, 0, 0)
        direction_panel.setVisible(False)
        self.direction_toggle.toggled.connect(direction_panel.setVisible)
        self.direction_toggle.toggled.connect(lambda checked: self.direction_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow))
        narration_layout.addWidget(direction_panel)
        narration_layout.addStretch(1)
        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel('Engine'))
        self.tts_engine = QComboBox()
        self.tts_engine.addItems(['Chatterbox Turbo', 'Chatterbox Nano', 'IndexTTS 2.5', 'Qwen3-TTS (official)', 'Plain text'])
        self.tts_engine.setToolTip('Turbo/Nano: show native tags in the script. IndexTTS/Qwen3: clean text plus JSON metadata.')
        direction_row.addWidget(self.tts_engine)
        direction_row.addWidget(QLabel('Cues'))
        self.tts_intensity = QComboBox(); self.tts_intensity.addItems(['Subtle', 'Balanced', 'Expressive'])
        self.tts_intensity.setCurrentText('Balanced')
        direction_row.addWidget(self.tts_intensity)
        self.auto_speech = QCheckBox('Speech-ready output')
        self.auto_speech.setChecked(True)
        self.auto_speech.setToolTip('Automatically prepare every finished script for the selected speech engine. Chatterbox tags appear directly in the editor.')
        self.apply_speech_button = QPushButton('Apply cues')
        self.apply_speech_button.setToolTip('Reapply speech direction to the current edited script using the selected engine.')
        self.apply_speech_button.clicked.connect(self.apply_speech_to_editor)
        direction_layout.addLayout(direction_row)
        actions_row = QGridLayout()
        self.auto_speech.setText('Auto cues'); actions_row.addWidget(self.auto_speech, 0, 0)
        actions_row.addWidget(self.apply_speech_button, 0, 1)
        self.speech_preview = QPushButton('Preview cues')
        self.speech_preview.clicked.connect(self.preview_speech)
        actions_row.addWidget(self.speech_preview, 1, 0)
        self.speech_export = QPushButton('Export TTS')
        self.speech_export.clicked.connect(self.export_speech)
        actions_row.addWidget(self.speech_export, 1, 1)
        self.tag_pick = QComboBox()
        self.tag_pick.addItems([f'[{t}]' for t in CHATTERBOX_TAGS])
        for combo in (self.tts_engine, self.tts_intensity, self.tag_pick):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(5)
            combo.setMinimumWidth(0)
        self.tag_pick.setToolTip('All 19 native Turbo/Nano tags, for intentional manual fine-tuning.')
        self.tag_insert = QPushButton('Insert tag')
        self.tag_insert.clicked.connect(self.insert_manual_tag)
        direction_layout.addLayout(actions_row)
        tags_row = QHBoxLayout(); tags_row.addWidget(self.tag_pick, 1); tags_row.addWidget(self.tag_insert)
        direction_layout.addLayout(tags_row)
        def direction_summary():
            self.direction_toggle.setText('Narration settings')
            self.direction_toggle.setToolTip(self.tts_engine.currentText() if self.auto_speech.isChecked() else 'Plain script')
        self.tts_engine.currentTextChanged.connect(direction_summary); self.auto_speech.toggled.connect(direction_summary)
        direction_summary()
        self.tts_engine.currentTextChanged.connect(self.update_tag_controls)
        self.update_tag_controls()

        self.output = QTextEdit(); self.output.setObjectName('scriptEditor'); self.output.setAcceptRichText(False); self.output.setPlaceholderText('Your next broadcast starts here.\n\nChoose a DJ and format, add an optional brief, then write a draft.\n\nEdit the script here before marking it ready for narration.')
        self.output.setMinimumHeight(80)
        result_layout.addWidget(self.output, stretch=1)
        review_card = QFrame(); review_card.setObjectName('reviewCard'); review_card.setProperty('approved', False)
        review_layout = QVBoxLayout(review_card); review_layout.setContentsMargins(14, 11, 14, 11); review_layout.setSpacing(5)
        review_title = QLabel('NARRATION HANDOFF'); review_title.setObjectName('sectionTitle');
        review_row = QHBoxLayout()
        self.reviewed = QCheckBox('Reviewed for narration')
        self.reviewed.setToolTip('I have checked the facts, DJ voice, continuity and speech cues in this script.')
        self.reviewed.toggled.connect(lambda checked: self.save_button.setEnabled(checked and bool(self.output.toPlainText().strip())))
        def approval_style(checked):
            review_card.setProperty('approved', checked)
            review_card.style().unpolish(review_card); review_card.style().polish(review_card)
        self.reviewed.toggled.connect(approval_style)
        self.save_button.setText('Export reviewed script'); self.save_button.setObjectName('primary')
        review_row.addWidget(self.reviewed); review_row.addStretch(); review_row.addWidget(self.copy_button); review_row.addWidget(self.save_button)
        review_layout.addLayout(review_row)
        result_layout.addWidget(review_card)
        self.output.textChanged.connect(self.on_script_edited)
        self.review_notes = QLabel('AI scripts are drafts. Check facts, character voice and continuity before narration.')
        self.review_notes.setObjectName('reviewNotes'); self.review_notes.setWordWrap(True)
        notes_scroll = QScrollArea(); notes_scroll.setWidgetResizable(True); notes_scroll.setWidget(self.review_notes)
        notes_scroll.setMinimumHeight(25); notes_scroll.setMaximumHeight(38)
        result_layout.addWidget(notes_scroll)
        self.classic_note = QLabel('Classic stories are authored fiction; other classic formats use the curated library.')
        self.classic_note.setWordWrap(True); self.classic_note.setObjectName('muted'); bottom_layout.addWidget(self.classic_note, 1)
        result_page.setMinimumHeight(max(260, result_layout.minimumSize().height()))
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setStretchFactor(2, 0)
        self.build_menus()
        self.setStyleSheet(THEME)
        self.mode.currentTextChanged.connect(self.on_mode_changed)
        self.on_mode_changed(self.mode.currentText())
    def build_menus(self):
        def action(menu, label, callback, shortcut=None):
            item = QAction(label, self)
            if shortcut: item.setShortcut(shortcut)
            item.triggered.connect(lambda checked=False: callback()); menu.addAction(item)
            return item
        file_menu = self.menuBar().addMenu('File')
        self.copy_action = action(file_menu, 'Copy script', self.copy, 'Ctrl+Shift+C')
        self.export_action = action(file_menu, 'Export reviewed script…', self.save_txt, 'Ctrl+Shift+S')
        def sync_file_actions():
            self.copy_action.setEnabled(not self.ai.busy and bool(self.output.toPlainText().strip()))
            self.export_action.setEnabled(not self.ai.busy and self.reviewed.isChecked() and bool(self.output.toPlainText().strip()))
        self.output.textChanged.connect(sync_file_actions)
        self.reviewed.toggled.connect(sync_file_actions)
        file_menu.aboutToShow.connect(sync_file_actions)
        sync_file_actions()
        file_menu.addSeparator(); action(file_menu, 'Close Writer', self.close, 'Alt+F4')
        tools = self.menuBar().addMenu('Tools')
        action(tools, 'AI setup…', self.ai.open_setup)
        action(tools, 'DJ profiles & continuity…', self.ai.open_profiles)
        action(tools, 'Ad Manager…', self.open_ad_manager)
        tools.aboutToShow.connect(lambda: [item.setEnabled(not self.ai.busy) for item in tools.actions()])
        help_menu = self.menuBar().addMenu('Help')
        action(help_menu, 'Getting started', self.instructions, 'F1')
        action(help_menu, 'Review & narration', lambda: self.show_help('Review & narration',
            '<h2>Before narration</h2><p>AI scripts are drafts. Check facts, character voice, continuity and the ending. '
            'Review the visible narration tags too. Editing resets approval.</p><p>Mark <b>Reviewed for narration</b> '
            'to enable script export. Copy remains available for editing elsewhere.</p>'
            '<h3>Speech direction</h3><p>Expand Narration controls to choose an engine, intensity, automatic cues, '
            'manual tags, preview or a TTS package. Qwen and IndexTTS direction data needs a compatible consumer.</p>'
            '<h3>Creative notices</h3><p>Classic stories are authored fan fiction. Fictional in-world ads are creative '
            'copy, not claims of real sponsorship. No result is automatically sent to a speech engine.</p>'))
        action(help_menu, 'Models & memory', lambda: self.show_help('Models & memory',
            '<h2>Local writing models</h2><p>AI Setup selects the writing runtime and GGUF model. Gemma 9B is a '
            'quality candidate; Qwen 4B is smaller. These are separate from Qwen3-TTS speech weights.</p>'
            '<p>Run large AI jobs one at a time. Available system memory and the Windows commit limit both matter. '
            'Keep weight repacking disabled if it causes allocation failures. Generation status and logs help diagnose failures.</p>'
            '<p>Models remain draft generators. Strong prompts and editing checks do not guarantee facts or good prose.</p>'))
        about_menu = self.menuBar().addMenu('About')
        action(about_menu, 'About DJ Writer…', self.about)
        action(about_menu, 'Third-party credits…', lambda: self.show_help('Third-party credits',
            '<h2>Software & model credits</h2><p>DJ Writer plugin created by <b>Kaotick Jay</b> for '
            '<b>Plagued Mods / Goodneighbor Records</b>.</p><p>Desktop UI: PyQt6 / Qt. Local inference: llama.cpp '
            '(ggml community). Optional writing models: Qwen and Gemma-based community GGUF releases, as identified '
            'in AI Setup. Upstream software and model licenses apply to their respective components.</p>'
            '<p>Fallout and associated game names belong to their respective rights holders. This is an independent '
            'fan project, not an official Bethesda product or endorsement.</p>'))

    def show_help(self, title, content):
        dialog = QDialog(self); dialog.setWindowTitle(title); dialog.resize(700, 520)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser(); browser.setOpenExternalLinks(False)
        browser.setHtml('<style>body{font-family:Segoe UI;color:#e2e7d5;} h2,h3{color:#bed597;} p{line-height:145%;}</style>' + content)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons); dialog.exec()

    def create_about_dialog(self):
        dialog = QDialog(self); dialog.setWindowTitle('About DJ Writer'); dialog.resize(570, 410)
        layout = QVBoxLayout(dialog); layout.setContentsMargins(28, 22, 28, 22)
        logo = QLabel(); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(QPixmap(str(Path(__file__).resolve().parent / 'assets/dj-writer.png')).scaled(135, 135, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo)
        title = QLabel('DJ WRITER'); title.setObjectName('brand'); title.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title)
        text = QLabel(f'Voice Studio companion plugin · v{VERSION}\n\nCreated by Kaotick Jay\nPlagued Mods / Goodneighbor Records\n\nLocal script writing, editorial review and narration handoff.')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter); text.setWordWrap(True); layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        return dialog

    def refresh_advertisers(self):
        previous = self.sponsor.currentText() if self.sponsor.count() else 'Goodneighbor Blues'
        self.sponsor.blockSignals(True)
        self.sponsor.clear()
        self.sponsor.addItems(ADS + [c['name'] for c in self.campaigns if c.get('enabled', True) and c['name'] not in ADS])
        self.sponsor.setCurrentText(previous)
        self.sponsor.blockSignals(False)

    def open_ad_manager(self):
        dialog = AdManagerDialog(self.campaigns, CAMPAIGNS, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.campaigns = dialog.campaigns
            self.engine.campaigns = self.campaigns
            self.refresh_advertisers()
            self.statusBar().showMessage('Ad Manager changes saved', 5000)

    def on_dj_changed(self, dj):
        # Default to the selected host's own station for promotional copy.
        if self.sponsor.currentText() in ('Goodneighbor Blues', 'Plague Radio'):
            self.sponsor.setCurrentText('Plague Radio' if dj == 'Mister The Plague' else 'Goodneighbor Blues')
        if hasattr(self, 'ai'):
            self.ai.refresh_prompt()

    def load_history(self):
        try:
            data = json.loads(HISTORY.read_text(encoding='utf-8'))
            return [x for x in data if isinstance(x, str) and x.strip()] if isinstance(data, list) else []
        except (OSError, ValueError): return []
    def on_category_changed(self, category, suggest_length=True):
        story = category == 'Stories From the Commonwealth'
        ai_mode = hasattr(self, 'mode') and self.mode.currentText() == 'AI Studio'
        self.length.setEnabled(not story and not ai_mode)
        self.title_field.setEnabled(category in ('Song introduction', 'Song outro') if ai_mode else not story)
        self.artist.setEnabled(category in ('Song introduction', 'Song outro') if ai_mode else not story)
        self.sponsor.setEnabled(True)
        self.length.setToolTip('Stories are delivered whole, with paragraph breaks.' if story else '')
        if ai_mode and hasattr(self, 'ai') and suggest_length:
            self.ai.words.setValue(DEFAULT_WORDS[category])
        if hasattr(self, 'ai'):
            self.ai.refresh_prompt()

    def on_mode_changed(self, mode):
        ai_mode = mode == 'AI Studio'
        self.ai.setVisible(ai_mode)
        self.classic_note.setVisible(not ai_mode)
        self.length.setVisible(not ai_mode); self.length_label.setVisible(not ai_mode)
        self.generate_button.setText('Write with AI' if ai_mode else 'Generate classic')
        self.cancel_button.setVisible(ai_mode)
        self.workspace_splitter.setSizes([170, 330, 300])
        self.on_category_changed(self.cat.currentText())

    def on_script_edited(self):
        self.reviewed.setChecked(False)
        self.save_button.setEnabled(False)
        words = len(clean_spoken_text(self.output.toPlainText()).split())
        self.script_stats.setText(f'{words:,} words, about {words / 140:.1f} minutes at 140 spoken words/minute')

    def on_generate(self):
        if self.ai.busy:
            return
        if self.mode.currentText() == 'AI Studio':
            self.ai.generate()
            return
        try:
            script, warning = self.engine.generate_one(
                self.cat.currentText(), self.dj.currentText(), self.title_field.text(),
                self.artist.text(), self.sponsor.currentText(), self.mood.currentText(),
                self.length.currentText(), self.records)
        except (ValueError, OSError, KeyError) as exc:
            QMessageBox.warning(self, 'Generation failed', str(exc))
            return
        if not script:
            self.statusBar().showMessage(warning or 'No matching script available.', 14000)
            return
        self.set_generated_script(script)
        history_error = self.remember_script(clean_spoken_text(script))
        self.review_notes.setText('Classic library result. Edit and review before narration. ' + history_error)
        self.statusBar().showMessage(history_error or warning or 'Generated one complete script. Review before export.', 14000 if warning or history_error else 6000)

    def update_tag_controls(self):
        enabled = self.tts_engine.currentText() in ('Chatterbox Turbo', 'Chatterbox Nano')
        self.tag_pick.setEnabled(enabled)
        self.tag_insert.setEnabled(enabled)

    def insert_manual_tag(self):
        if self.tts_engine.currentText() not in ('Chatterbox Turbo', 'Chatterbox Nano'):
            return
        # Insert at the current cursor; this counts as an edit and revokes review.
        cursor = self.output.textCursor()
        cursor.insertText(self.tag_pick.currentText() + ' ')
        self.output.setTextCursor(cursor)
        self.output.setFocus()

    def set_generated_script(self, script):
        """Display the actual TTS-ready draft, not only a hidden preview."""
        if self.auto_speech.isChecked():
            # Writing-model tags are *not* authoritative. Normalize incoming
            # [dialog] / repeated [advertisement] before applying native cues.
            directed, _ = render(clean_spoken_text(script), self.tts_engine.currentText(), self.dj.currentText(),
                                 self.cat.currentText(), self.tts_intensity.currentText())
            self.output.setPlainText(directed)
        else:
            self.output.setPlainText(clean_spoken_text(script))

    def apply_speech_to_editor(self):
        """Explicit regeneration from clean text avoids duplicating prior tags."""
        source = clean_spoken_text(self.output.toPlainText())
        if not source:
            return
        directed, _ = render(source, self.tts_engine.currentText(), self.dj.currentText(),
                             self.cat.currentText(), self.tts_intensity.currentText())
        self.output.setPlainText(directed)
        self.review_notes.setText('Speech cues updated. Review the script and narration tags before export.')
        self.statusBar().showMessage('Applied engine-specific speech direction to the visible script.', 9000)

    def remember_script(self, script):
        self.records = (self.records + [script])[-1000:]
        self.history_index = len(self.records) - 1
        try:
            temporary = HISTORY.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.records, indent=2, ensure_ascii=False), encoding='utf-8')
            temporary.replace(HISTORY)
        except OSError as exc:
            return f'History could not be saved: {exc}. Copy or export the script before closing.'
        return ''

    def copy(self):
        QApplication.clipboard().setText(self.output.toPlainText())
        self.statusBar().showMessage('Copied to clipboard', 4000)
    def save_txt(self):
        if not self.output.toPlainText().strip() or not self.reviewed.isChecked(): return
        fname, _ = QFileDialog.getSaveFileName(self, 'Export reviewed narration script', 'radio_script.txt', 'Text (*.txt)')
        if fname:
            try:
                if not Path(fname).suffix: fname += '.txt'
                Path(fname).write_text(self.output.toPlainText(), encoding='utf-8')
                self.statusBar().showMessage('Exported one script. Open it with Load script in Voice Studio.', 12000)
            except OSError as exc: QMessageBox.critical(self, 'Export error', str(exc))
    def preview_speech(self):
        source = self.output.toPlainText().strip()
        if not source:
            QMessageBox.information(self, 'Narration', 'Write or paste a script first.')
            return
        speech, manifest = render(source, self.tts_engine.currentText(), self.dj.currentText(),
                                  self.cat.currentText(), self.tts_intensity.currentText())
        if manifest:
            summary = manifest.get('note', '')
            if 'segments' in manifest:
                summary += f"\n\n{len(manifest['segments'])} individually directed segments."
                summary += '\n\n' + json.dumps(manifest['segments'][:3], ensure_ascii=False, indent=2)
            else:
                summary += '\n\n' + speech[:1700]
        else:
            summary = speech[:2000]
        QMessageBox.information(self, 'Speech direction preview (source unchanged)', summary[:3500])

    def export_speech(self):
        if not self.reviewed.isChecked():
            QMessageBox.information(self, 'Review required', 'Review the script and check the narration approval box first.')
            return
        source = self.output.toPlainText().strip()
        if not source:
            return
        engine = self.tts_engine.currentText()
        filename, _ = QFileDialog.getSaveFileName(self, 'Save engine-specific speech package',
                                                   'radio_speech.json', 'JSON (*.json)')
        if not filename:
            return
        try:
            path = Path(filename)
            if path.suffix.lower() != '.json': path = path.with_suffix('.json')
            path.write_text(export_json(source, engine, self.dj.currentText(), self.cat.currentText(),
                                        self.tts_intensity.currentText()), encoding='utf-8')
            self.statusBar().showMessage('Exported original speech with separate, engine-specific direction metadata.', 10000)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, 'Speech export failed', str(exc))

    def restore_history(self):
        if not self.records:
            self.statusBar().showMessage('No previous results saved.', 5000)
            return
        self.history_index = (self.history_index - 1) % len(self.records)
        self.set_generated_script(self.records[self.history_index])
        self.review_notes.setText('Saved result. Review again before narration; history does not imply approval.')
        self.statusBar().showMessage(f'History result {self.history_index + 1} of {len(self.records)}', 5000)
    def instructions(self):
        self.show_help('Getting started', '<h2>Your script desk</h2><p>Choose a DJ, format and mood on the left. '
            'In AI Studio, add an optional brief and word target. AI Setup selects the separate local writing model. '
            'Classic Generator uses the curated library.</p><p>Write a draft, edit it in the script desk, '
            'check the editorial notes, then mark it reviewed and export. Drag the horizontal dividers to resize the three rows.</p>'
            '<h3>Your DJ\'s voice</h3><p>Profiles & continuity stores personality and editor-maintained facts. '
            'View writing prompt shows the format guidance. Recent drafts are not established lore.</p>'
            '<h3>Speech handoff</h3><p>Expand Narration controls for cue settings. Export a reviewed script '
            'for Voice Studio, or use the TTS package for supported direction metadata. Writing and speech remain separate.</p>')
        return
    def about(self):
        self.create_about_dialog().exec()

    def closeEvent(self, event):
        if self.ai.busy:
            self.ai.cancel()
            self.statusBar().showMessage('Stopping the writing engine. Close again after it stops.', 10000)
            event.ignore()
        else:
            event.accept()

if __name__ == '__main__':
    if '--smoke-test' in sys.argv:
        print('Creating QApplication', flush=True)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / 'assets' / 'dj-writer.ico')))
    if '--smoke-test' in sys.argv:
        # Packaging checks must never open or modify the user's real profile.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='dj-writer-smoke-') as test_home:
            os.environ['GOODNEIGHBOR_DJ_HOME'] = test_home
            DATA = Path(test_home)
            HISTORY = DATA / 'history.json'
            CAMPAIGNS = DATA / 'advertisers.json'
            print('Creating DJ Writer window', flush=True)
            w = Window()
            if w.windowIcon().isNull() or app.windowIcon().isNull():
                raise RuntimeError('Packaged DJ Writer icon is missing')
            for name in ('dialogue.json', 'stories.json'):
                json.loads((Path(__file__).resolve().parent / name).read_text(encoding='utf-8'))
            w.close()
            report = Path(sys.argv[sys.argv.index('--smoke-test') + 1])
            report.write_text(json.dumps({'ok': True, 'version': VERSION, 'icon': True}), encoding='utf-8')
        sys.exit(0)
    w = Window(); w.show(); sys.exit(app.exec())
