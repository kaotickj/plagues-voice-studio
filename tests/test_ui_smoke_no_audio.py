"""The explicit no-audio diagnostic cannot initialize or play real media."""
import json
import os
from pathlib import Path
import runpy
import sys
from types import ModuleType

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6.QtWidgets')


@pytest.mark.parametrize('no_audio', [False, True])
def test_diagnostic_mode_is_explicit_and_restores_media_and_settings(monkeypatch, tmp_path, no_audio):
    from PyQt6.QtCore import QSettings, QUrl
    from PyQt6.QtWidgets import QApplication
    from chatterbox_studio import app, ui_smoke_test

    qt_app = QApplication.instance() or QApplication([])
    previous_name = qt_app.applicationName()
    previous_organization = qt_app.organizationName()
    previous_format = QSettings.defaultFormat()

    class ForbiddenPlayer:
        PlaybackState = app.QMediaPlayer.PlaybackState

        def __init__(self, *_):
            raise AssertionError('Test attempted real media initialization')

    class ForbiddenOutput:
        def __init__(self, *_):
            raise AssertionError('Test attempted real audio output initialization')

    def forbidden_native_settings(*args):
        raise AssertionError('Diagnostic accessed normal application settings')

    def inspect_without_constructing_mainwindow():
        settings = app.QSettings('KaotickJay', 'PlaguesVoiceStudio')
        assert settings.format() == QSettings.Format.IniFormat
        assert not settings.fallbacksEnabled()
        assert settings.value('updates/check_on_startup', False) is False
        assert Path(settings.fileName()).suffix == '.ini'
        settings.setValue('diagnostic-only', 'temporary')
        settings.sync()
        assert Path(settings.fileName()).is_file()
        if no_audio:
            assert app.QMediaPlayer is not ForbiddenPlayer
            assert app.QAudioOutput is not ForbiddenOutput
            player = app.QMediaPlayer()
            output = app.QAudioOutput()
            player.setAudioOutput(output)
            output.setVolume(.85)
            assert output.volume() == .85
            stopped = []
            player.playbackStateChanged.connect(stopped.append)
            player.stop()
            assert stopped == [ForbiddenPlayer.PlaybackState.StoppedState]
            assert player.playbackState() == ForbiddenPlayer.PlaybackState.StoppedState
            with pytest.raises(RuntimeError, match='forbids loading audio sources'):
                player.setSource(QUrl.fromLocalFile(str(tmp_path / 'never-opened.wav')))
            with pytest.raises(RuntimeError, match='forbids audio playback'):
                player.play()
        else:
            assert app.QMediaPlayer is ForbiddenPlayer
            assert app.QAudioOutput is ForbiddenOutput
        raise RuntimeError('Intentional stop after diagnostic isolation check')

    monkeypatch.setattr(app, 'QSettings', forbidden_native_settings)
    monkeypatch.setattr(app, 'QMediaPlayer', ForbiddenPlayer)
    monkeypatch.setattr(app, 'QAudioOutput', ForbiddenOutput)
    monkeypatch.setattr(app, 'MainWindow', inspect_without_constructing_mainwindow)
    monkeypatch.setenv('PLAGUES_VOICE_STUDIO_030_HOME', str(tmp_path / 'original'))
    report_path = tmp_path / 'report.json'
    try:
        result = (ui_smoke_test.run(report_path, no_audio=True) if no_audio
                  else ui_smoke_test.run(report_path))
        assert result == 1
        report = json.loads(report_path.read_text())
        assert report['mode'] == ('no_audio' if no_audio else 'standard')
        assert report['real_audio'] is (not no_audio)
        assert report['playback'] is False
        assert 'Intentional stop after diagnostic isolation check' in report['errors'][0]
        assert ('NO AUDIO' in report['test']) is no_audio
        if no_audio:
            assert 'Real audio is disabled' in report['audio_note']
        else:
            assert 'playback is not tested' in report['audio_note']
        assert app.QSettings is forbidden_native_settings
        assert app.QMediaPlayer is ForbiddenPlayer
        assert app.QAudioOutput is ForbiddenOutput
        assert os.environ['PLAGUES_VOICE_STUDIO_030_HOME'] == str(tmp_path / 'original')
    finally:
        QSettings.setDefaultFormat(previous_format)
        qt_app.setApplicationName(previous_name)
        qt_app.setOrganizationName(previous_organization)


@pytest.mark.parametrize('flag,kwargs', [
    ('--ui-self-test', {}),
    ('--ui-self-test-no-audio', {'no_audio': True}),
])
def test_launcher_dispatches_explicit_diagnostic_flag_without_app_launch(monkeypatch, tmp_path, flag, kwargs):
    calls = []
    diagnostic = ModuleType('chatterbox_studio.ui_smoke_test')

    def run(report_path=None, **options):
        calls.append((report_path, options))
        return 17

    diagnostic.run = run
    report_path = tmp_path / 'report.json'
    monkeypatch.setitem(sys.modules, diagnostic.__name__, diagnostic)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'argv', ['frozen-candidate', flag, str(report_path)])
    launcher = Path(__file__).parents[1] / 'launcher.py'
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(launcher), run_name='__main__')
    assert exited.value.code == 17
    assert calls == [(report_path, kwargs)]
