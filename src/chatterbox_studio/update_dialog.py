"""Opt-in, non-blocking GitHub Releases check for the Windows desktop app.

The application never downloads or executes an installer on the user's behalf.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)
from . import __version__
from .update_checker import ReleaseInfo, find_update, trusted_release_url


class _ReleaseCheckWorker(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    @pyqtSlot()
    def run(self):
        try:
            self.result.emit(find_update(__version__))
        except Exception as exc:
            # Network/API errors must never abort narration or the main GUI.
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class UpdateDialog(QDialog):
    """Open the official release page only after validating its URL and user click."""

    SETTING = "updates/check_on_startup"

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setObjectName("pvs_updates_dialog")
        self.setWindowTitle("Plague's Voice Studio — Updates")
        self.setModal(False)
        self.resize(520, 270)
        self.setMinimumWidth(440)
        self._thread: QThread | None = None
        self._worker: _ReleaseCheckWorker | None = None
        self._automatic = False
        self._release: ReleaseInfo | None = None

        layout = QVBoxLayout(self)
        heading = QLabel(f"Installed version: {__version__}")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        about = QLabel(
            "Checks the official GitHub Releases page for newer stable versions. "
            "The check sends no scripts, audio, voice samples, profiles, or model data. "
            "Only public release information is fetched."
        )
        about.setWordWrap(True)
        layout.addWidget(about)
        self.status = QLabel("No update check has been performed.")
        self.status.setObjectName("update_status")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)

        self.auto = QCheckBox("Check for updates automatically when Voice Studio starts")
        self.auto.setObjectName("updates_check_on_startup")
        self.auto.setChecked(self._setting_enabled(host.settings.value(self.SETTING, False)))
        self.auto.toggled.connect(lambda enabled: host.settings.setValue(self.SETTING, enabled))
        layout.addWidget(self.auto)
        note = QLabel(
            "Updates are never downloaded or installed automatically. Your installed "
            "models, voice references, character profiles and existing recordings remain unchanged."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        controls = QHBoxLayout()
        self.check_button = QPushButton("Check now")
        self.check_button.setObjectName("updates_check_now")
        self.check_button.clicked.connect(lambda: self.check_now(automatic=False))
        controls.addWidget(self.check_button)
        self.view_button = QPushButton("View official release")
        self.view_button.setObjectName("updates_open_release")
        self.view_button.setEnabled(False)
        self.view_button.clicked.connect(self.open_release)
        controls.addWidget(self.view_button)
        controls.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        controls.addWidget(close_button)
        layout.addLayout(controls)

    @staticmethod
    def _setting_enabled(value) -> bool:
        return value is True or str(value).lower() in ("1", "true", "yes")

    @property
    def is_checking(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def check_now(self, *, automatic=False):
        if self._thread is not None:
            return
        self._automatic = automatic
        self._release = None
        self.check_button.setEnabled(False)
        self.view_button.setEnabled(False)
        self.status.setText("Checking the official GitHub Releases page…")
        self._thread = QThread(self)
        self._worker = _ReleaseCheckWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.result.connect(self._got_result)
        self._worker.error.connect(self._got_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._check_finished)
        self._thread.start()

    def _got_result(self, release):
        if release is None:
            self.status.setText(
                "You're up to date with the latest published stable GitHub release, "
                "or no stable release has been published yet."
            )
            return
        self._release = release
        self.status.setText(
            f"A new stable version is available: {release.version}. "
            "Review its release notes and download it from GitHub when you're ready."
        )
        self.view_button.setEnabled(True)
        if self._automatic:
            self.show()
            self.raise_()
            self.activateWindow()

    def _got_error(self, message: str):
        self.status.setText(
            "The update check could not be completed. Voice generation is unaffected. "
            + message[:300]
        )

    def _check_finished(self):
        self._thread = None
        self._worker = None
        self.check_button.setEnabled(True)

    def open_release(self):
        release = self._release
        if release is None or not trusted_release_url(release.url, release.tag):
            self.status.setText("Could not validate the official GitHub release link.")
            return
        if not QDesktopServices.openUrl(QUrl(release.url)):
            self.status.setText("Could not open your browser. Open the official repository's Releases page manually.")
