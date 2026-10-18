"""Branded, non-modal About / Credits dialog.

A persistent child of MainWindow, intentionally no nested exec() and no
heavy model imports. All art is scaled once for cheap repeated opens.
"""
from __future__ import annotations
import platform
import sys
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)
from . import __version__
from .paths import bundled_models_dir


def _assets(name: str) -> Path:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return root / 'assets' / name


def diagnostics_text() -> str:
    """Unprivileged local diagnostic info, nothing identifying or secret."""
    installed = bundled_models_dir()
    models = ('nano', 'turbo', 'english', 'multilingual-v3')
    state = []
    for model in models:
        folder = installed / model
        has_weight = folder.is_dir() and any(folder.glob('*.safetensors'))
        state.append(f'  {model}: {"weights present" if has_weight else "not bundled / cache may be available"}')
    return '\n'.join([
        "Plague's Voice Studio", f'Version: {__version__}',
        f'Platform: {platform.system()} {platform.release()}',
        f'Python: {platform.python_version()}',
        f'Frozen executable: {bool(getattr(sys, "frozen", False))}',
        'Speech engines: Chatterbox, Qwen3-TTS and IndexTTS 2.5 supported.',
        'Qwen3 and IndexTTS use separate Python runtimes; no external engine packages bundled.',
        'Bundled model checks:', *state,
        'Note: cached models are not enumerated. Do not include personal voice files in bug reports.',
    ])


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('plagues_about_dialog')
        self.setWindowTitle("About Plague's Voice Studio")
        self.setWindowIcon(QIcon(str(_assets('plagues-voice-studio-icon.png'))))
        self.setModal(False)
        self.setMinimumSize(500, 540)
        self.resize(620, 690)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        card = QFrame()
        card.setObjectName('heroCard')
        hero = QHBoxLayout(card)
        hero.setContentsMargins(16, 14, 16, 14)
        logo = QLabel()
        logo.setObjectName('about_logo')
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image = QPixmap(str(_assets('plagues-voice-studio-logo.png')))
        if not image.isNull():
            logo.setPixmap(image.scaled(170, 170, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
        logo.setFixedSize(180, 180)
        hero.addWidget(logo)
        heading = QVBoxLayout()
        heading.addStretch()
        title = QLabel("PLAGUE'S\nVOICE STUDIO")
        title.setObjectName('sectionTitle')
        title.setWordWrap(True)
        heading.addWidget(title)
        subtitle = QLabel('LOCAL VOICE PRODUCTION\nNarration  •  Games  •  Radio')
        subtitle.setObjectName('mutedText')
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        heading.addStretch()
        hero.addLayout(heading, 1)
        outer.addWidget(card)

        info = QHBoxLayout()
        byline = QLabel(f'<b>Created by Kaotick Jay</b>  |  Version {__version__}')
        byline.setTextFormat(Qt.TextFormat.RichText)
        info.addWidget(byline)
        info.addStretch()
        outer.addLayout(info)

        tabs = QTabWidget()
        tabs.setObjectName('about_tabs')
        self.overview = QTextBrowser()
        self.overview.setOpenExternalLinks(True)
        self.overview.setHtml('''<h3>What it does</h3>
<p>Plague's Voice Studio supports <b>Chatterbox</b>, <b>Qwen3-TTS</b>, and
<b>IndexTTS 2.5</b> speech synthesis. Generate natural-sounding local voice recordings,
manage reusable voice references and character profiles, and audition finished audio.</p>
<p>Chatterbox Narration Studio offers script markup, narration jobs and batch production
with WAV/MP3 export. Choose <b>Voice Engines</b> to use Qwen3-TTS or IndexTTS 2.5
with independently configured Python runtimes. Both offer reference-voice WAV generation,
per-engine settings, metadata and live diagnostics. Both have produced working audio on
the creator's Windows installation.</p>
<p>Browse earlier recordings in Export Library and prepare Fallout 4 / Skyrim
WAV, LIP, XWM and FUZ voice assets using compatible external utilities you supply.
Game dialogue plugins are not edited.</p>
<h3>Updates</h3><p>Select <b>Check for updates</b> in the main window to compare your version with the official GitHub stable releases. Update checks are optional. Voice Studio does not download or install updates itself and does not upload scripts, recordings or voice profiles.</p><h3>Our approach</h3><p>Local-first voice production, clear engine choices,
reusable creative workflows, previewable exports and respect for speaker permission.
An initial model download may require an internet connection.</p>
<p>© 2026 Kaotick Jay. Original application.</p>''')
        tabs.addTab(self.overview, 'Overview')

        credits = QTextBrowser()
        credits.setOpenExternalLinks(True)
        credits.setHtml('''<h3>Credits and acknowledgements</h3>
<p><b>Application design and development:</b> Kaotick Jay.</p>
<p><b>Chatterbox TTS:</b> Developed by Resemble AI. Its source and
components are distributed under their respective license terms.
<a href="https://github.com/resemble-ai/chatterbox">Visit Chatterbox upstream</a>.</p>
<p><b>Qwen3-TTS:</b> By the Qwen team. Its integration has completed live
Windows CPU speech generation. Its separate Python runtime and model weights
are not redistributed here.
<a href="https://github.com/QwenLM/Qwen3-TTS">Visit Qwen3-TTS upstream</a>.</p>
<p><b>IndexTTS 2.5:</b> By the upstream IndexTTS authors. Local speech generation
has been verified working on the creator's Windows machine. Install it in a
separate Python environment and check the Bilibili Model Use License before use.
<a href="https://github.com/index-tts/index-tts">Visit IndexTTS upstream</a>.</p>
<p><b>Qt/PyQt6:</b> Desktop user interface. PyQt6 has separate
GPL/commercial licensing requirements.</p>
<p><b>Bethesda export:</b> Game-specific conversion utilities and
Creation Kit resources are supplied by the user, never redistributed here.</p>
<p>This independent application is not affiliated with or endorsed by Resemble AI,
Bethesda Game Studios, or their respective publishers.</p>
<p><b>Voice permissions:</b> Only clone voices with permission. Upstream
Chatterbox audio watermarking remains unchanged.</p>
<p>See <code>THIRD_PARTY_NOTICES.md</code> in the application folder.</p>''')
        tabs.addTab(credits, 'Credits & licenses')

        diagnostics = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics)
        diagnostics_layout.setContentsMargins(10, 12, 10, 8)
        note = QLabel('Copy a short environment summary when reporting a bug. No voice recordings are included.')
        note.setWordWrap(True)
        diagnostics_layout.addWidget(note)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setObjectName('about_diagnostics')
        self.diagnostics.setPlainText(diagnostics_text())
        diagnostics_layout.addWidget(self.diagnostics, 1)
        copy = QPushButton('Copy diagnostics')
        copy.clicked.connect(self._copy_diagnostics)
        diagnostics_layout.addWidget(copy)
        tabs.addTab(diagnostics, 'Diagnostics')
        outer.addWidget(tabs, 1)

        footer = QHBoxLayout()
        footer.addWidget(QLabel('Plague’s Voice Studio  •  Independent local production'))
        footer.addStretch()
        close = QPushButton('Close')
        close.setObjectName('primary')
        close.setDefault(True)
        close.clicked.connect(self.close)
        footer.addWidget(close)
        outer.addLayout(footer)

    def _copy_diagnostics(self):
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.diagnostics.toPlainText())
