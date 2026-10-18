"""Searchable, keyboard-friendly help center. No WebEngine or internet required."""
from __future__ import annotations
import re
import sys
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QListWidget, QLineEdit,
    QTextBrowser, QPushButton, QFrame, QSplitter, QComboBox,
)

# (Title, tags used for filtering, human-maintained documentation).
# Text is not externally loaded and does not execute scripts.
TOPICS: tuple[tuple[str, str, str], ...] = (
    ('Getting started', 'quick start narrator beginner generate', '''
<h2>Getting started</h2>
<p>Plague's Voice Studio is a local voice-production workstation with supported Chatterbox, Qwen3-TTS and IndexTTS 2.5 speech generation. Write scripts, manage voice references, and review recordings without an application account.</p>
<ol><li><b>Choose a model</b> in Narration Studio. For a quick CPU test, try Nano.</li>
<li><b>Choose a voice</b>, if that model requires a reference recording.</li>
<li><b>Write or import</b> your script. Short paragraphs work well for spoken delivery.</li>
<li><b>Generate now</b> or add multiple jobs to the Batch Queue.</li>
<li><b>Review</b> the result in Export Library, then send it to Bethesda Voice Export if needed.</li></ol>
<h3>Qwen3-TTS voice cloning</h3><p>For Qwen3-TTS, open the <b>Voice Engines</b> tab, configure the separate Qwen Python environment, choose your reference voice and model, and generate speech. The generated WAV joins Export Library and can be sent to Bethesda Voice Export. IndexTTS 2.5 is also supported through Voice Engines and uses its own installed runtime and checkpoints.</p>
<h3>Offline models</h3><p>Models bundled during a <b>FullOffline</b> build are available without downloads. Otherwise the program may download model weights on first use. The build option and the model chosen in the GUI are separate.</p>
'''),
    ('Models and voices', 'nano turbo original english multilingual tags reference expressive clone', '''
<h2>Models and voices</h2>
<table width="100%" cellspacing="0" cellpadding="7">
<tr><th align="left">Model</th><th align="left">Best use</th><th align="left">Vocal tags</th></tr>
<tr><td><b>Nano</b></td><td>Compact English / CPU-first</td><td>Some native tags</td></tr>
<tr><td><b>Turbo</b></td><td>Expressive English, voice reference required</td><td>Native vocal-event tags</td></tr>
<tr><td><b>Original English</b></td><td>Expressiveness and CFG controls</td><td>Not native vocal-event tags</td></tr>
<tr><td><b>Multilingual V3</b></td><td>Language selection and voice controls</td><td>Not Turbo-style tags</td></tr></table>
<p><b>References:</b> Prefer 6–20 seconds of clean, single-speaker audio with no music. Only use recordings you own or have permission to clone.</p>
<p>Legacy voice references from v0.1.x are offered read-only. The current app stores newly imported recordings in its own data directory.</p>
<p><b>Original English controls:</b> Start around expressiveness 0.50 and CFG 0.50, then make small adjustments while listening.</p>
<h3>Qwen3-TTS and IndexTTS 2.5</h3><p>Both are supported local speech engines using separately configured Python environments. Qwen3-TTS offers 0.6B and 1.7B Base choices; IndexTTS 2.5 provides reference-voice speech and emotion/duration controls. Live synthesis with both engines has been confirmed on the creator's Windows installation. Performance and acceleration still depend on installed model weights and hardware.</p>
'''),
    ('Script tags', 'pause rate volume emphasis laugh chuckle sigh cough syntax markup', '''
<h2>Script tags and markup</h2>
<h3>Handled by Plague's Voice Studio</h3>
<p>These directives are interpreted by the <b>Chatterbox Narration Studio</b> workflow. The model does not pronounce the directives. The separate Qwen3-TTS and IndexTTS workflows currently receive plain text and do not process this markup.</p>
<pre>[pause:0.8s]
[pause:800ms]
[rate:0.90]Speak slowly.[/rate]
[volume:0.85]Speak quietly.[/volume]
[emphasis]Important words.[/emphasis]</pre>
<p>Maximum exact pause: 10 seconds. Rate: 0.50 to 2.00, volume: 0.00 to 2.00. App emphasis adds gain; it does not guarantee the model changes its performance.</p>
<h3>Chatterbox vocal-event tags</h3>
<p>Tags such as <code>[laugh]</code>, <code>[chuckle]</code>, and <code>[sigh]</code> are passed to the speech model. They are best suited to Turbo or Nano. Original English and Multilingual V3 do not have the same native tag support and may read them as words.</p>
<p>Use <b>Check tags</b> to validate app-level syntax and inspect how the script will be split. Non-native vocal tags are not a guaranteed effect.</p>
'''),
    ('Export Library', 'recordings browse play wav mp3 older file folders playback script preview json text copy', '''
<h2>Export Library</h2>
<p>Choose a folder to browse and play earlier renders. Double-click a recording or use <b>Play selected</b>.</p>
<p>Select a recording to preview its original script in the read-only <b>Script preview</b> pane, then choose <b>Copy script</b> to reuse it. The text comes from the matching <code>.json</code> file; Qwen3-TTS and IndexTTS save JSON metadata with their recordings. Chatterbox script metadata is available in builds that include its matching sidecar-export update. Older or imported audio without this metadata shows an explanatory message. Vocal tags, punctuation and paragraph breaks are preserved.</p><p>Use <b>Add folder</b> to include another export directory. Older exported audio is not moved, edited, or deleted. Supported playback formats depend on codecs available to Qt Multimedia on your computer.</p>
<p><b>Use selected for Bethesda export</b> loads the file path into the game-audio converter; it does not alter the recording itself.</p>
<p>New exports are automatically named from the selected voice and a timestamp, unless you explicitly enter a filename. Existing files are not silently overwritten.</p>
'''),
    ('Bethesda voice export', 'fallout skyrim lip xwm fuz game data mo2 mod voice type response facefx', '''
<h2>Bethesda voice export</h2>
<p>This workflow builds a Fallout 4 / Skyrim-compatible FUZ file and can place it in an exact game or mod folder. <b>The game plugin is not opened or edited.</b></p>
<ol><li>Save a project with the owning plugin filename and the target <b>Data</b> folder or MO2 mod root.</li>
<li>Save a Voice Profile pairing a Creation Kit <b>VoiceType EditorID</b> with a Chatterbox voice/model.</li>
<li>Choose the generated recording and enter the <b>exact dialogue response filename</b> from the Creation Kit.</li>
<li>Supply the correctly licensed external FaceFX, Fonix, xWMA and optionally FFmpeg tools.</li>
<li>Check the destination preview and approve any replacement.</li></ol>
<p><b>Expected path:</b> <code>Sound/Voice/&lt;OwningPlugin&gt;/&lt;VoiceType&gt;/&lt;Response&gt;.fuz</code></p>
<p>WAV recordings created with Qwen3-TTS can also be sent to this export workflow from the engine results panel.</p>
<p><b>Important:</b> Real LIP and XWM generation depends on compatible external tools; structurally valid FUZ packing does not guarantee in-game audio or lip-sync success. Test in the target game.</p>
'''),
    ('Model Manager', 'model downloads install cache nano turbo qwen weights offline status stop', '''
<h2>Model Manager</h2>
<p>Choose <b>Model Manager</b> to download Chatterbox Nano, Turbo, Original English or Multilingual V3, or Qwen3-TTS Base 0.6B or 1.7B. You choose when to download models, and each download can take several gigabytes of disk space.</p>
<ol><li>Select a model and inspect its status. Chatterbox files already included in the application appear as <b>Included with application</b>.</li>
<li>Select <b>Download selected model</b>, then confirm. Files are downloaded from their official Hugging Face repositories.</li>
<li>Use <b>Stop</b> to cancel. Qwen subprocess downloads stop promptly; Chatterbox checks cancellation between individual file downloads. Incomplete downloads can be retried.</li>
<li>For Qwen3, first configure its separate Python runtime in <b>Voice Engines</b>. <b>Check Qwen cache</b> reports whether the selected model has a cached snapshot. This does not validate model inference.</li></ol>
<p>Chatterbox models downloaded from the GUI are stored in the writable user data directory and are used automatically on the next generation. Qwen models are downloaded to the Hugging Face cache used by the configured Qwen Python interpreter.</p>
<p><b>Important:</b> Installing Qwen model weights is not the same as installing Qwen's Python runtime. IndexTTS 2.5 works through Voice Engines with its own runtime and checkpoints; its weights are not downloaded by Model Manager.</p>
'''),
    ('Build and troubleshooting', 'install windows offline build model download paging error 1455 python exe', '''
<h2>Build and troubleshooting</h2>
<h3>Windows portable build</h3>
<pre>powershell -ExecutionPolicy Bypass -File .\\scripts\\build_windows.ps1 -Models turbo</pre>
<h3>All models, fully offline</h3>
<pre>powershell -ExecutionPolicy Bypass -File .\\scripts\\build_windows.ps1 -FullOffline</pre>
<p>Once all four models are already downloaded in the project, <code>-FullOffline -SkipModels</code> skips the downloads but still verifies the model files.</p>
<h3>Common problems</h3>
<p><b>OS error 1455:</b> Windows has insufficient available virtual memory (RAM plus paging file) for the model load. Close memory-intensive applications and check your system-managed paging file and disk space.</p>
<p><b>A Python traceback when opening a dialog:</b> rebuild the executable after source edits. An old desktop shortcut may still point to an older version.</p>
<p><b>First generation seems slow:</b> first use may load or download model weights and initialize PyTorch. CPU inference can be significantly slower than GPU inference.</p><p><b>Out-of-memory or native crashes when running DJ Writer too:</b> large writing and speech models can compete for RAM and Windows paging resources. Finish or close the DJ Writer before running IndexTTS or Qwen3, especially on CPU. If a native process exits with <code>3221225477</code> (<code>0xC0000005</code>), inspect its diagnostic log and Windows Event Viewer; resource contention is one possible cause, not a guaranteed explanation.</p>
<p><b>Windows AMD GPU:</b> this build does not automatically enable AMD acceleration. Auto selects CUDA only where supported; otherwise it uses CPU.</p>
<p><b>Qwen3-TTS runtime:</b> install it in its own Python environment and use <b>Test selected engine</b> to verify imports. Loading cached model weights and CPU speech generation can take time. Generation progress, errors, and saved logs appear in the engine diagnostics panel.</p>
<p><b>SoX warning:</b> if SoX is already installed but not found, run <code>sox --version</code> in a new terminal and ensure the directory containing <code>sox.exe</code> is on PATH. The warning is not always fatal to generation.</p>
'''),
    ('Checking for updates', 'update upgrades version github releases notify startup install download', '''
<h2>Checking for updates</h2>
<p>Select <b>Check for updates</b> in the application header. Voice Studio checks the official GitHub Releases API for a newer <b>stable</b> release. If one is available, choose <b>View official release</b> to read the notes and download the installer in your browser.</p>
<p><b>Nothing is installed or downloaded automatically.</b> The app does not replace its own executable, model files, scripts, saved voices, character profiles or local project data.</p>
<p><b>Optional startup checks:</b> In the Updates dialog, enable <b>Check for updates automatically when Voice Studio starts</b>. This preference is <b>off by default</b>. An automatic check runs once when the program starts, does not interrupt speech generation, and opens the dialog only when a newer stable release is found. It skips beta and release-candidate builds until a stable release is published.</p>
<p>An update check contacts GitHub to retrieve public release metadata. No audio, script, profile or reference voice is uploaded. As with any visit to GitHub, its servers may see the usual request information such as IP address. Without network access, the app continues to work and the update check displays an error.</p>
<p><b>Installing an update:</b> Download the installer from the official project Releases page, finish any active speech generation, close Voice Studio, then run the installer. Keep the existing installation and data paths unless release notes explicitly require a migration. Preserve the v0.2.4 installation separately.</p>
<p>Official releases: <a href="https://github.com/kaotickj/plagues-voice-studio/releases">github.com/kaotickj/plagues-voice-studio/releases</a>.</p>
'''),
    ('Privacy and licenses', 'permissions watermark local data licensing credits copyright internet', '''
<h2>Privacy, permissions and licenses</h2>
<p>Chatterbox, Qwen3-TTS and IndexTTS 2.5 synthesize speech locally after their required models have been downloaded. Initial model retrieval may contact Hugging Face or other upstream model providers. Qwen3-TTS uses its own local Python environment.</p>
<p>Only clone a person's voice with their permission. <b>Chatterbox's upstream watermarking has not been removed.</b></p>
<p>Chatterbox TTS is developed by <b>Resemble AI</b> and Qwen3-TTS by the Qwen team. IndexTTS 2.5 is developed by the IndexTTS team. Each upstream library, model and game conversion utility retains its individual terms. See <code>THIRD_PARTY_NOTICES.md</code> in the project.</p>
<p><a href="https://github.com/resemble-ai/chatterbox">Resemble AI's Chatterbox source</a></p>
'''),
    ('Qwen3-TTS and IndexTTS', 'qwen cloning indextts supported voice engines compare character profiles independent python', '''
<h2>Qwen3-TTS and IndexTTS 2.5</h2>
<p><b>Qwen3-TTS and IndexTTS 2.5 are supported speech engines.</b> Local speech generation and WAV export with both have been verified on the creator's Windows system, alongside Chatterbox. This records successful real-world use, not a blanket guarantee for every CPU/GPU, model size or upstream version.</p>
<p>These engines run in separately configured Python processes. Their packages and model weights are not bundled with the application or mixed with Chatterbox dependencies. Use the <b>Voice Engines</b> tab to configure Qwen3-TTS and IndexTTS controls.</p>
<ol><li>Install the desired engine according to its upstream instructions, using a separate Python environment.</li>
<li>In the engine tab, enter the interpreter path. IndexTTS also needs its official repository and checkpoints directory.</li>
<li>Select <b>Test selected engine</b> to check imports; an import test does not prove live synthesis.</li>
<li>Choose a reference voice, a Base model, a language, and your narration text. For Qwen3, an accurate reference transcript can help cloning quality.</li>
<li>Select <b>Generate with selected engine</b>. The <b>Compare Engines</b> action requires both engines to be installed and configured.</li></ol>
<p>Generated WAV recordings include JSON metadata, appear in Export Library, and can be sent to Bethesda Voice Export. Reusable character profiles retain per-engine settings and reference-voice choices without modifying the voice files. The engine view provides live progress, elapsed time, cancellation, and diagnostic logs.</p>
<p><b>Current limitations:</b> Qwen3 and IndexTTS workflows accept plain text; Chatterbox narration tags and its batch/MP3 workflow are not applied. Windows AMD GPU acceleration is not established, and CPU generation may take time. Live IndexTTS output has been confirmed on the creator's machine; individual model sizes and hardware configurations may require additional testing. IndexTTS uses a separate Bilibili model-use license.</p>
<p><a href="https://github.com/QwenLM/Qwen3-TTS">Qwen3-TTS official installation guide</a></p>
<p><a href="https://github.com/index-tts/index-tts">IndexTTS official installation guide</a></p>
'''),
    ('Support Project Development', 'support sponsor sponsorship funding donate donate development github patreon paypal', '''
<h2>Support Project Development</h2>
<p>Plague's Voice Studio is an independently developed application created by <b>Kaotick Jay</b>. If the studio has been useful to you, voluntary sponsorship helps support maintenance, documentation, bug fixes, and future improvements.</p>
<p><b>Choose a way to support the project:</b></p>
<ul>
<li><a href="https://github.com/sponsors/kaotickj">Sponsor on GitHub</a></li>
<li><a href="https://www.patreon.com/KaotickJay">Support on Patreon</a></li>
<li><a href="https://paypal.me/kaotickj">Contribute through PayPal</a></li>
</ul>
<p>Sponsorship is always optional. The application's local voice-production features do not require a contribution.</p>
'''),
)

# QTextDocument HTML support is a subset of browser HTML. Keep it conservative.
DOC_CSS = '''<style>
body { color: #e0eee2; background: #0e1716; font-family: Segoe UI, sans-serif; font-size: 14px; }
h2 { color: #b0f8b9; font-size: 22px; margin-bottom: 12px; }
h3 { color: #c6ead0; font-size: 17px; margin-top: 18px; }
p, li { line-height: 1.4; margin-bottom: 8px; }
a { color: #8cddff; } code, pre { color: #e8f0de; background: #233528; }
th { color: #b1ffbe; background: #20382a; } td { background: #18251e; }
</style>'''


def matched_topic_indices(query: str) -> list[int]:
    words = query.lower().strip().split()
    if not words:
        return list(range(len(TOPICS)))
    return [i for i, (title, keywords, html) in enumerate(TOPICS)
            if all(word in (title + ' ' + keywords + ' ' + html).lower() for word in words)]


class HelpCenter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('help_center')
        self._zoom = 100
        self._current_html = ''
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        title_row = QHBoxLayout()
        label = QLabel('Help center')
        label.setObjectName('sectionTitle')
        title_row.addWidget(label)
        title_row.addStretch()
        subtitle = QLabel('Local guide  •  Search topics and examples')
        subtitle.setObjectName('mutedText')
        title_row.addWidget(subtitle)
        outer.addLayout(title_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        sidebar = QFrame()
        sidebar.setObjectName('helpSidebar')
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 12, 12, 12)
        artwork = QLabel()
        artwork.setObjectName('help_logo')
        artwork.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
        logo = QPixmap(str(base / 'assets' / 'plagues-voice-studio-logo.png'))
        if not logo.isNull():
            artwork.setPixmap(logo.scaled(134, 134, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
        artwork.setFixedHeight(136)
        side.addWidget(artwork)
        side.addWidget(QLabel('FIND A TOPIC'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search help topics…')
        self.search.setAccessibleName('Search help topics')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        side.addWidget(self.search)
        self.topic_list = QListWidget()
        self.topic_list.setObjectName('help_topics')
        self.topic_list.setAccessibleName('Help topics')
        self.topic_list.currentRowChanged.connect(self._select)
        side.addWidget(self.topic_list, 1)
        shortcuts = QLabel('Ctrl+F focuses search.\nUse Up/Down to browse topics.')
        shortcuts.setObjectName('mutedText')
        shortcuts.setWordWrap(True)
        side.addWidget(shortcuts)
        splitter.addWidget(sidebar)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(6, 0, 0, 0)
        tools = QHBoxLayout()
        tools.addWidget(QLabel('Guide'))
        tools.addStretch()
        tools.addWidget(QLabel('Text size'))
        self.font_size = QComboBox()
        self.font_size.setAccessibleName('Help text size')
        for p in (90, 100, 115, 130, 150):
            self.font_size.addItem(f'{p}%', p)
        self.font_size.setCurrentIndex(1)
        self.font_size.currentIndexChanged.connect(self._font_changed)
        tools.addWidget(self.font_size)
        main_layout.addLayout(tools)
        self.browser = QTextBrowser()
        self.browser.setObjectName('help_article')
        self.browser.setAccessibleName('Help article')
        self.browser.setOpenExternalLinks(True)
        main_layout.addWidget(self.browser, 1)
        splitter.addWidget(main)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([245, 690])
        outer.addWidget(splitter, 1)
        self._filter('')

    def _filter(self, query: str):
        previous = self.topic_list.currentItem()
        previous_id = previous.data(Qt.ItemDataRole.UserRole) if previous is not None else 0
        ids = matched_topic_indices(query)
        self.topic_list.blockSignals(True)
        self.topic_list.clear()
        for i in ids:
            self.topic_list.addItem(TOPICS[i][0])
            self.topic_list.item(self.topic_list.count() - 1).setData(Qt.ItemDataRole.UserRole, i)
        self.topic_list.blockSignals(False)
        if not ids:
            self._current_html = '<h2>No matches found</h2><p>Try a shorter search term.</p>'
            self._apply_zoom()
        else:
            idx = ids.index(previous_id) if previous_id in ids else 0
            self.topic_list.setCurrentRow(idx)

    def _select(self, row: int):
        if row < 0:
            return
        item = self.topic_list.item(row)
        if item is None:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        self._current_html = TOPICS[int(idx)][2]
        self._apply_zoom()
        self.browser.moveCursor(QTextCursor.MoveOperation.Start)

    def _font_changed(self, _index: int):
        self._zoom = self.font_size.currentData() or 100
        self._apply_zoom()

    def _apply_zoom(self):
        if self._current_html:
            css = re.sub(r'font-size: (\d+)px;',
                         lambda m: f'font-size: {round(int(m.group(1)) * self._zoom / 100)}px;',
                         DOC_CSS)
            self.browser.setHtml(css + self._current_html)

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()
