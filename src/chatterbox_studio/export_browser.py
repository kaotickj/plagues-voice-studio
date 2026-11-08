"""Browse and play ANY audio export, including files made by older versions."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,
    QPlainTextEdit, QSplitter, QTabWidget)
from .pvs_library import old_export_directories, new_export_directory
from .export_metadata import read_export_script

SUPPORTED = {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}


class ExportBrowser(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.roots: list[Path] = []
        self._build()
        saved = host.settings.value('export_browser/roots', [])
        if isinstance(saved, str):
            saved = [saved]
        for folder in [new_export_directory(host.storage), *old_export_directories(), *saved]:
            self.add_root(Path(folder), refresh=False)
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        description = QLabel("Play any narration in your exports, including recordings from older Plague's Voice Studio and Plagued Voice Studio versions. Older files are never moved or modified.")
        description.setWordWrap(True)
        layout.addWidget(description)
        tools = QHBoxLayout()
        self.folders = QComboBox()
        self.folders.currentIndexChanged.connect(self.refresh)
        tools.addWidget(self.folders, 1)
        add = QPushButton('Add folder...')
        add.clicked.connect(self._browse)
        tools.addWidget(add)
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.refresh)
        tools.addWidget(refresh)
        layout.addLayout(tools)
        self.list = QTreeWidget()
        self.list.setHeaderLabels(['File', 'Modified', 'Location'])
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.setSortingEnabled(True)
        self.list.itemDoubleClicked.connect(lambda *_: self.play_selected())
        self.list.currentItemChanged.connect(lambda *_: self.preview_selected())
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.list)
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 4, 0, 0)
        preview_layout.addWidget(QLabel('Saved text (read-only, including speech tags)'))
        self.text_views = QTabWidget()
        self.script_preview = QPlainTextEdit()
        self.script_preview.setReadOnly(True)
        self.script_preview.setAccessibleName('Saved render input')
        self.script_preview.setPlaceholderText('Select an audio export to see its render input.')
        self.script_preview.setMinimumHeight(110)
        self.text_views.addTab(self.script_preview, 'Render input')
        self.original_preview = QPlainTextEdit()
        self.original_preview.setReadOnly(True)
        self.original_preview.setAccessibleName('Saved original manuscript')
        self.text_views.addTab(self.original_preview, 'Original manuscript')
        preview_layout.addWidget(self.text_views, 1)
        preview_footer = QHBoxLayout()
        self.preview_status = QLabel('Select a recording to view its saved text.')
        self.preview_status.setWordWrap(True)
        preview_footer.addWidget(self.preview_status, 1)
        self.copy_script = QPushButton('Copy render input')
        self.copy_script.setEnabled(False)
        self.copy_script.clicked.connect(self._copy_script)
        preview_footer.addWidget(self.copy_script)
        preview_layout.addLayout(preview_footer)
        split.addWidget(preview_panel)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        layout.addWidget(split, 1)
        action = QHBoxLayout()
        self.play = QPushButton('Play selected')
        self.play.clicked.connect(self.play_selected)
        action.addWidget(self.play)
        stop = QPushButton('Stop')
        stop.clicked.connect(self.host.player.stop)
        action.addWidget(stop)
        if getattr(self.host, 'bethesda_tab', None) is not None:
            send = QPushButton('Use selected for Bethesda export')
            send.setObjectName('bethesda_export_handoff')
            send.clicked.connect(self.send_selected)
            action.addWidget(send)
        show = QPushButton('Open containing folder')
        show.clicked.connect(self.open_selected)
        action.addWidget(show)
        layout.addLayout(action)
        self.info = QLabel('')
        layout.addWidget(self.info)

    def add_root(self, path: Path, *, refresh=True):
        path = path.expanduser()
        if path not in self.roots:
            self.roots.append(path)
            self.folders.addItem(str(path), str(path))
        if refresh:
            self.folders.setCurrentIndex(self.roots.index(path))
            self.host.settings.setValue('export_browser/roots', [str(x) for x in self.roots])
            self.refresh()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose a folder containing narration exports')
        if path:
            self.add_root(Path(path))

    def refresh(self):
        if not hasattr(self, 'list'):
            return
        self.list.clear()
        self._clear_preview()
        root_str = self.folders.currentData()
        if not root_str:
            return
        root = Path(root_str)
        if not root.is_dir():
            self.info.setText('This folder does not exist yet. Generate audio there or choose another directory.')
            return
        count = 0
        # Capped to avoid freezing Qt when a user chooses an entire drive.
        try:
            for path in root.rglob('*'):
                if not path.is_file() or path.suffix.lower() not in SUPPORTED:
                    continue
                modified = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                item = QTreeWidgetItem([path.name, modified, str(path.parent)])
                item.setData(0, Qt.ItemDataRole.UserRole, str(path))
                self.list.addTopLevelItem(item)
                count += 1
                if count >= 3000:
                    break
        except OSError as exc:
            self.info.setText(f'Unable to scan export folder: {exc}')
            return
        self.info.setText(f'{count} playable files' + (' (first 3000 shown)' if count >= 3000 else ''))

    def _clear_preview(self):
        self.script_preview.clear()
        self.original_preview.clear()
        self.preview_status.setText('Select a recording to view its saved text.')
        self.copy_script.setEnabled(False)

    def preview_selected(self):
        audio = self.selected_path()
        if audio is None or not audio.is_file():
            self._clear_preview()
            return
        script, status = read_export_script(audio)
        original, _ = read_export_script(audio, original=True)
        self.script_preview.setPlainText(script if script is not None else '')
        self.original_preview.setPlainText(original if original is not None else '')
        self.preview_status.setText(status)
        self.copy_script.setEnabled(script is not None)

    def _copy_script(self):
        if self.copy_script.isEnabled():
            QApplication.clipboard().setText(self.script_preview.toPlainText())

    def selected_path(self) -> Path | None:
        item = self.list.currentItem()
        return Path(item.data(0, Qt.ItemDataRole.UserRole)) if item else None

    def play_selected(self):
        file = self.selected_path()
        if file and file.is_file():
            self.host._play_file(str(file))
        else:
            QMessageBox.information(self, 'Select an export', 'Choose a recording from the list first.')

    def send_selected(self):
        tab = getattr(self.host, 'bethesda_tab', None)
        if tab is None:
            return
        file = self.selected_path()
        if file and file.is_file():
            tab.audio.setText(str(file))
            self.host.tabs.setCurrentWidget(tab)
        else:
            QMessageBox.information(self, 'Select an export', 'Choose a recording first.')

    def open_selected(self):
        file = self.selected_path()
        if file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file.parent)))
