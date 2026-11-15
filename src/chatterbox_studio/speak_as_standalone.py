"""Run Speak As without starting or modifying the installed Studio application."""
import argparse
import json
import time
import wave
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QWidget
from plagued_ai import root as shared_ai_root
from .paths import canonical_data_dir
from .voices import VoiceLibrary
from .speak_as import SpeakAsDialog


def create_dialog():
    parent = QWidget()
    parent.storage = canonical_data_dir()
    parent.voices = VoiceLibrary(shared_ai_root(), read_only=True)
    parent.voice = SimpleNamespace(currentData=lambda: '')
    # Do not migrate/write settings belonging to the installed application.
    parent.settings = SimpleNamespace(value=lambda key, default='': default)
    dialog = SpeakAsDialog(parent)
    dialog.setWindowTitle('Speak as… — local standalone')
    return parent, dialog


def log_timings(dialog):
    """Record timing/device metadata only, never recordings or transcript text."""
    began = time.monotonic()
    asr = {}

    def event(name, **values):
        print(json.dumps(dict(event=name, elapsed=round(time.monotonic() - began, 3), **values)), flush=True)

    def started():
        asr['start'] = time.monotonic()
        event('asr_started', device='cpu')

    def finished(code, *_):
        start = asr.pop('start', None)
        if start is not None:
            event('asr_finished', seconds=round(time.monotonic() - start, 3), exit_code=code)

    def converted(result):
        duration = None
        try:
            with wave.open(result['output_path'], 'rb') as wav:
                duration = wav.getnframes() / wav.getframerate()
        except (OSError, wave.Error):
            pass
        event('conversion_finished', engine=dialog.mode.currentData(), device=dialog.device.currentData(),
              seconds=result['seconds'], warm=result['warm'], output_seconds=duration)

    dialog.process.started.connect(started)
    dialog.process.finished.connect(finished)
    dialog.warm.completed.connect(converted)
    dialog.warm.progress.connect(lambda message: event('model_stage', message=message))
    dialog.warm.failed.connect(lambda _: event('conversion_failed'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test', action='store_true', help='Inspect UI readiness without microphone or models')
    parser.add_argument('--screenshot', type=Path, help='Optional smoke-test UI image')
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication([])
    if args.smoke_test:
        # Fail closed if construction ever starts capturing or inference.
        from unittest.mock import patch
        from . import speak_as
        signal = SimpleNamespace(connect=lambda callback: None)
        player = SimpleNamespace(setAudioOutput=lambda value: None, errorOccurred=signal,
                                 stop=lambda: None, setSource=lambda value: None, play=lambda: None)
        with (patch.object(speak_as, 'QAudioSource', side_effect=AssertionError('Microphone opened during smoke test')),
              patch.object(speak_as, 'QMediaPlayer', return_value=player),
              patch.object(speak_as, 'QAudioOutput', return_value=object())):
            parent, dialog = create_dialog()
            dialog.show()
            app.processEvents()
            if args.screenshot:
                if not dialog.grab().save(str(args.screenshot)):
                    raise RuntimeError('Could not save smoke-test screenshot')
            result = {'voices': dialog.voices.count(), 'mode': dialog.mode.currentData(),
                      'device': dialog.device.currentData(), 'microphone_open': dialog.source is not None,
                      'worker_running': dialog.warm.busy, 'config_error': dialog.config_error,
                      'index_paths_exist': all(Path(field.text()).exists() for field in dialog.index_fields)}
            dialog.done(0)
            print(json.dumps(result))
            return 0 if result['voices'] and result['index_paths_exist'] and not result['config_error'] else 1
    parent, dialog = create_dialog()
    log_timings(dialog)
    dialog.show()
    app.processEvents()
    print(json.dumps({'status': 'window-ready', 'voices': dialog.voices.count(),
                      'microphone_open': dialog.source is not None, 'worker_running': dialog.warm.busy}), flush=True)
    dialog.exec()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
