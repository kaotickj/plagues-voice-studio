"""The explicit GUI diagnostic must not inherit real Windows preferences."""
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6.QtWidgets')


def test_diagnostic_uses_file_settings_and_restores_on_failure(monkeypatch, tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    from chatterbox_studio import app, ui_smoke_test

    qt_app = QApplication.instance() or QApplication([])
    previous_name = qt_app.applicationName()
    previous_organization = qt_app.organizationName()
    previous_format = QSettings.defaultFormat()

    def forbidden_native_settings(*args):
        raise AssertionError('Diagnostic accessed normal application settings')

    def inspect_settings():
        settings = app.QSettings('KaotickJay', 'PlaguesVoiceStudio')
        assert settings.format() == QSettings.Format.IniFormat
        assert not settings.fallbacksEnabled()
        assert settings.value('updates/check_on_startup', False) is False
        path = Path(settings.fileName())
        assert path.suffix == '.ini'
        settings.setValue('isolated-fixture', 'temporary')
        settings.sync()
        assert path.is_file()
        raise RuntimeError('Intentional stop after settings isolation check')

    monkeypatch.setattr(app, 'QSettings', forbidden_native_settings)
    monkeypatch.setattr(app, 'MainWindow', inspect_settings)
    monkeypatch.setenv('PLAGUES_VOICE_STUDIO_030_HOME', str(tmp_path / 'original'))
    report = tmp_path / 'report.json'
    try:
        assert ui_smoke_test.run(report) == 1
        assert 'Intentional stop' in json.loads(report.read_text())['errors'][0]
        assert app.QSettings is forbidden_native_settings
        assert os.environ['PLAGUES_VOICE_STUDIO_030_HOME'] == str(tmp_path / 'original')
    finally:
        QSettings.setDefaultFormat(previous_format)
        qt_app.setApplicationName(previous_name)
        qt_app.setOrganizationName(previous_organization)
