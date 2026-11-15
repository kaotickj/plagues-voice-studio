import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from types import SimpleNamespace
from PyQt6.QtCore import QBuffer, QIODevice, QProcess
from PyQt6.QtWidgets import QApplication, QWidget
import pytest
from chatterbox_studio import speak_as

@pytest.fixture
def dialog(tmp_path, monkeypatch):
    monkeypatch.setattr(speak_as.QMessageBox, 'question', lambda *args: speak_as.QMessageBox.StandardButton.Discard)
    monkeypatch.delenv('PVS_SPEAK_AS_CONFIG', raising=False)
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    weights = tmp_path / 'weights'
    weights.mkdir()
    (weights / 's3gen.safetensors').touch()
    reference = tmp_path / 'reference.wav'
    reference.touch()
    parent.storage = tmp_path
    parent.voices = SimpleNamespace(list_voices=lambda: [{'id':'a', 'name':'Test'}], resolve=lambda value: reference)
    parent.voice = SimpleNamespace(currentData=lambda:'a')
    parent.settings = SimpleNamespace(value=lambda key, default='': default)
    monkeypatch.setattr(speak_as, 'installed_model_directory', lambda *args: weights)
    signal = SimpleNamespace(connect=lambda cb:None)
    monkeypatch.setattr(speak_as, 'QAudioOutput', lambda *args:object())
    monkeypatch.setattr(speak_as, 'QMediaPlayer', lambda *args:SimpleNamespace(
        setAudioOutput=lambda v:None, errorOccurred=signal, stop=lambda:None,
        setSource=lambda v:None, play=lambda:None))
    monkeypatch.setattr(speak_as.QMediaDevices, 'defaultAudioInput',
        lambda: pytest.fail('Test attempted to access a real microphone'))
    monkeypatch.setattr(speak_as, 'QAudioSource',
        lambda *args: pytest.fail('Test attempted to open a real microphone'))
    d = speak_as.SpeakAsDialog(parent)
    yield d
    d.done(0)

def capture(d, frames):
    d.source = SimpleNamespace(stop=lambda:None, deleteLater=lambda:None)
    d.buffer = QBuffer()
    d.buffer.open(QIODevice.OpenModeFlag.ReadWrite)
    d.buffer.write(b'\x10\x00' * frames)

def test_open_never_opens_microphone(dialog):
    assert dialog.source is None
    assert dialog.process.state() == QProcess.ProcessState.NotRunning
    assert dialog.record.isEnabled()

def test_short_recording_is_rejected(dialog):
    capture(dialog, 100)
    dialog.finish_recording()
    assert dialog.source is None
    assert 'too short' in dialog.status.text()
    assert dialog.process.state() == QProcess.ProcessState.NotRunning

def test_cancel_recording_cleans_capture(dialog):
    capture(dialog, 16000)
    dialog.stop()
    assert dialog.source is None and dialog.buffer is None
    assert not (Path(dialog.temp.name) / 'input.wav').exists()


def test_worker_release_preserves_conversion_failure(dialog):
    dialog._conversion_error('The GPU is reserved by another application.')
    message = dialog.status.text()
    dialog._released()
    assert dialog.status.text() == message


def test_worker_release_preserves_timeout_and_cancel_feedback(dialog):
    dialog._timeout()
    message = dialog.status.text()
    dialog._released()
    assert dialog.status.text() == message
    dialog.stop()
    dialog._released()
    assert dialog.status.text().startswith('Stopped.')


def test_successful_idle_release_shows_model_released(dialog):
    dialog.model_ready = True
    dialog._released()
    assert dialog.status.text().startswith('Model released.')
    assert not dialog.model_ready

def test_completed_recording_launches_offline(dialog, monkeypatch):
    import wave
    capture(dialog, 16000)
    calls=[]
    monkeypatch.setattr(dialog.warm, 'submit', lambda *args: calls.append(args))
    dialog.finish_recording()
    assert dialog.source is None and not dialog.record.isEnabled()
    assert calls and calls[0][1]['device'] == 'cpu'
    assert dialog.process.processEnvironment().value('HF_HUB_OFFLINE') == '1'
    with wave.open(str(Path(dialog.temp.name)/'input.wav')) as w:
        assert w.getnframes() == 16000
    dialog._timeout()
    assert dialog.cancelled and '120-second' in dialog.status.text()

def test_failed_process_and_cancel_never_play(dialog, monkeypatch):
    played=[]
    monkeypatch.setattr(dialog.player, 'play', lambda:played.append(True))
    dialog._finished(1, QProcess.ExitStatus.NormalExit)
    assert 'failed' in dialog.status.text()
    dialog.cancelled=True
    (Path(dialog.temp.name)/'output.wav').touch()
    dialog._finished(0, QProcess.ExitStatus.NormalExit)
    assert not played

def test_cancel_kills_running_child(dialog):
    import sys
    dialog.process.start(sys.executable, ['-c', 'import time; time.sleep(20)'])
    assert dialog.process.waitForStarted(2000)
    dialog.stop()
    assert dialog.process.waitForFinished(3000)
    assert dialog.cancelled

def test_index_missing_runtime_never_opens_mic(dialog):
    dialog.mode.setCurrentIndex(1)
    dialog.start_recording()
    assert dialog.source is None
    assert 'No microphone opened' in dialog.status.text()

def test_index_passes_mic_as_emotion_not_speaker(dialog, monkeypatch):
    import json
    (Path(dialog.temp.name)/'transcript.txt').write_text('Test words')
    calls=[]
    monkeypatch.setattr(dialog.warm, 'submit', lambda *args: calls.append(args))
    dialog._start_index()
    req=json.loads((Path(dialog.temp.name)/'index.json').read_text())
    assert req['text']=='Test words'
    assert req['voice_path'] != req['emotion_audio_path']
    assert req['emotion_audio_path'].endswith('input.wav')
    assert calls
    assert dialog.stage_timeout_ms == 300000
    dialog._timeout()
    assert '300-second' in dialog.status.text()

def test_index_adapter_emotion_audio_takes_precedence():
    import importlib.util, sys
    from unittest.mock import patch
    spec=importlib.util.spec_from_file_location('runner',Path(__file__).parents[1]/'optional_engine_runner.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    calls=[]
    fake=SimpleNamespace(IndexTTS2=lambda **kw:SimpleNamespace(infer=lambda **opts:calls.append(opts)))
    torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:False),set_num_threads=lambda n:None,
                          get_num_threads=lambda:2,__version__='test')
    with patch.dict(sys.modules, {'torch':torch,'indextts.infer_v2_5':fake}), patch.object(runner,'windows_cpu_tensor_reader'), patch.object(runner,'_device',return_value='cpu'):
        runner.index_run(dict(repo='.',voice_path='speaker.wav',text='hello',language='en',output_path='out.wav',emotion='happy',emotion_audio_path=__file__))
    assert calls[0]['emo_audio_prompt']==__file__
    assert 'emo_vector' not in calls[0]


@pytest.mark.parametrize('engine', ['chatterbox', 'index25', 'seed_v1'])
def test_ui_snapshot(dialog, tmp_path, engine):
    dialog.mode.setCurrentIndex(dialog.mode.findData(engine))
    dialog.show()
    QApplication.processEvents()
    target=tmp_path/'speak-as-ui.png'
    assert dialog.grab().save(str(target))


def test_feedback_prevention_and_missing_device(dialog, monkeypatch):
    stopped=[]
    monkeypatch.setattr(dialog.player, 'stop', lambda:stopped.append(True))
    monkeypatch.setattr(speak_as, 'QMediaDevices', SimpleNamespace(defaultAudioInput=lambda:SimpleNamespace(isNull=lambda:True)))
    dialog.start_recording()
    assert stopped and dialog.source is None
    assert 'No microphone' in dialog.status.text()


def test_microphone_error_stops_capture(dialog):
    from PyQt6.QtMultimedia import QAudio
    capture(dialog, 16000)
    dialog.source.error=lambda:QAudio.Error.OpenError
    dialog._audio_state(None)
    assert dialog.source is None
    assert 'Microphone failed' in dialog.status.text()


def test_focus_loss_cancels_recording(dialog):
    from PyQt6.QtCore import QEvent
    capture(dialog, 16000)
    dialog.changeEvent(QEvent(QEvent.Type.ActivationChange))
    assert dialog.source is None
    assert 'lost focus' in dialog.status.text()


def test_index_asr_to_warm_worker_pipeline(dialog,tmp_path,monkeypatch):
    import sys,time
    from PyQt6.QtCore import QCoreApplication
    fake_asr=tmp_path/'asr'
    fake_asr.write_text('#!/usr/bin/python3\nimport sys\nfrom pathlib import Path\np=sys.argv[sys.argv.index("-of")+1]\nPath(p+".txt").write_text("Test spoken words")\n')
    fake_asr.chmod(0o700)
    fake_worker=tmp_path/'fake_worker.py'
    fake_worker.write_text('''import sys,json,os
from pathlib import Path
n=0
for line in sys.stdin:
 r=json.loads(line); n+=1
 assert r['text']=='Test spoken words'
 assert r['voice_path']!=r['emotion_audio_path']
 assert Path(r['emotion_audio_path']).is_file()
 Path(r['output_path']).write_bytes(b'fake wave')
 print(json.dumps(dict(id=r['id'],ok=True,output_path=r['output_path'],pid=os.getpid(),warm=n>1,seconds=0)),flush=True)
''')
    dialog.mode.setCurrentIndex(1)
    for field,value in zip(dialog.index_fields,[sys.executable,str(tmp_path),str(fake_asr),'model']):
        field.setText(value)
    submit=dialog.warm.submit
    monkeypatch.setattr(dialog.warm,'submit',lambda python,req,env:submit(python,req,env,script=fake_worker))
    results=[];dialog.warm.completed.connect(results.append)
    for expected in (1,2):
        capture(dialog,16000)
        dialog.finish_recording()
        end=time.monotonic()+5
        while len(results)<expected and time.monotonic()<end:
            QCoreApplication.processEvents();time.sleep(.005)
        assert len(results)==expected, dialog.status.text()
    assert results[0]['pid']==results[1]['pid']
    assert results[1]['warm']
    dialog.stop()
    assert dialog.warm.stop(wait=True)


def test_emotion_cache_is_invalidated_even_when_filename_reused(tmp_path):
    import importlib.util,sys
    from unittest.mock import patch
    spec=importlib.util.spec_from_file_location('runner',Path(__file__).parents[1]/'optional_engine_runner.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    emotion=tmp_path/'mic.wav';emotion.touch()
    model=SimpleNamespace(cache_emo_cond='stale',cache_emo_audio_prompt=str(emotion))
    def infer(**opts):
        assert model.cache_emo_cond is None
        assert model.cache_emo_audio_prompt is None
        assert opts['emo_audio_prompt']==str(emotion)
    model.infer=infer
    torch=SimpleNamespace(get_num_threads=lambda:2,__version__='test')
    with patch.dict(sys.modules,{'torch':torch,'indextts.infer_v2_5':SimpleNamespace(IndexTTS2=lambda **kw:None)}), patch.object(runner,'windows_cpu_tensor_reader'), patch.object(runner,'_device',return_value='cpu'):
        result=runner.index_run(dict(repo='.',voice_path='speaker',text='test',language='en',output_path='out',emotion_audio_path=str(emotion)),synthesizer=model)
    assert result is model


def test_capture_holds_warm_model_and_short_recording_resumes_idle(dialog,monkeypatch):
    held=[];resumed=[]
    monkeypatch.setattr(dialog.warm,'hold_idle',lambda:held.append(True))
    monkeypatch.setattr(dialog.warm,'resume_idle',lambda:resumed.append(True))
    fake=SimpleNamespace(isNull=lambda:False,isFormatSupported=lambda fmt:True)
    monkeypatch.setattr(speak_as,'QMediaDevices',SimpleNamespace(defaultAudioInput=lambda:fake))
    source=SimpleNamespace(stateChanged=SimpleNamespace(connect=lambda callback:None),
        start=lambda buffer:None,stop=lambda:None,deleteLater=lambda:None)
    monkeypatch.setattr(speak_as,'QAudioSource',lambda *args:source)
    dialog.start_recording()
    assert held and dialog.source is source
    dialog.finish_recording()
    assert resumed and dialog.source is None


def test_optional_fast_english_selection_restores_original_paths(dialog):
    dialog.mode.setCurrentIndex(1)
    original=tuple(f.text() for f in dialog.index_fields[2:])
    dialog.launchers.update(fast_asr_executable='/test/fast-asr',fast_asr_model='/test/small.en')
    dialog.asr_mode.addItem('Fast English','fast_en')
    dialog.asr_mode.setCurrentIndex(1)
    assert tuple(f.text() for f in dialog.index_fields[2:])==('/test/fast-asr','/test/small.en')
    assert all(not f.isEnabled() for f in dialog.index_fields[2:])
    dialog.asr_mode.setCurrentIndex(0)
    assert tuple(f.text() for f in dialog.index_fields[2:])==original


def test_reference_modes_preserve_speaker_and_recording(dialog, monkeypatch):
    root = Path(dialog.temp.name)
    (root / 'transcript.txt').write_text('The entire spoken line.')
    original = b'original microphone audio'
    (root / 'input.wav').write_bytes(original)
    calls = []
    monkeypatch.setattr(dialog.warm, 'submit', lambda *args: calls.append(args))
    for seconds in (5, 0):
        dialog.reference_mode.setCurrentIndex(dialog.reference_mode.findData(seconds))
        dialog._start_index()
        request = calls[-1][1]
        assert request['reference_seconds'] == seconds
        assert request['voice_path'] == dialog.voices.currentData()
        assert request['emotion_audio_path'] == str(root / 'input.wav')
        assert request['text'] == 'The entire spoken line.'
        assert (root / 'input.wav').read_bytes() == original
    assert dialog.transcript.text() == 'The entire spoken line.'


def test_reference_controls_are_index_only(dialog):
    assert dialog.reference_mode.isHidden()
    assert dialog.reference_label.isHidden()
    assert dialog.asr_label.isHidden()
    dialog.mode.setCurrentIndex(dialog.mode.findData('index25'))
    assert not dialog.reference_mode.isHidden()
    assert not dialog.reference_label.isHidden()
    assert not dialog.asr_label.isHidden()
    assert dialog.reference_mode.currentData() == 5
    assert 'new audio length' in dialog.runtime_note.text()


def test_configured_index_defaults_work_without_chatterbox_weights(dialog, tmp_path, monkeypatch):
    import json
    import sys
    repo = tmp_path / 'index'
    (repo / 'indextts').mkdir(parents=True)
    (repo / 'indextts/infer_v2_5.py').touch()
    (repo / 'checkpoints').mkdir()
    (repo / 'checkpoints/config.yaml').touch()
    executable = tmp_path / 'asr'
    executable.touch()
    model = tmp_path / 'small.en'
    model.mkdir()
    config = tmp_path / 'launchers.json'
    config.write_text(json.dumps(dict(index_python=sys.executable, index_repo=str(repo),
        fast_asr_executable=str(executable), fast_asr_model=str(model))))
    monkeypatch.setenv('PVS_SPEAK_AS_CONFIG', str(config))
    preferred = speak_as.SpeakAsDialog(dialog.parent())
    try:
        assert preferred.mode.currentData() == 'chatterbox'
    finally:
        preferred.done(0)
    (dialog.weights / 's3gen.safetensors').unlink()
    configured = speak_as.SpeakAsDialog(dialog.parent())
    try:
        assert configured.mode.currentData() == 'index25'
        assert configured.asr_mode.currentData() == 'fast_en'
        assert configured.record.isEnabled()
        assert configured.reference_mode.currentData() == 5
        assert configured.source is None
        assert configured.device.findData('cuda') >= 0
    finally:
        configured.done(0)


def test_capture_start_exception_restores_controls(dialog, monkeypatch):
    fake = SimpleNamespace(isNull=lambda: False, isFormatSupported=lambda fmt: True)
    monkeypatch.setattr(speak_as, 'QMediaDevices', SimpleNamespace(defaultAudioInput=lambda: fake))
    def fail(buffer):
        raise RuntimeError('capture disconnected')
    source = SimpleNamespace(stateChanged=SimpleNamespace(connect=lambda callback: None),
        start=fail, stop=lambda: None, deleteLater=lambda: None)
    monkeypatch.setattr(speak_as, 'QAudioSource', lambda *args: source)
    dialog.start_recording()
    assert dialog.source is None and dialog.buffer is None
    assert dialog.record.isEnabled() and dialog.device.isEnabled()
    assert dialog.reference_mode.isEnabled()
    assert not dialog.timer.isActive()
    assert 'capture disconnected' in dialog.status.text()


def test_odd_capture_bytes_are_safely_trimmed(dialog, monkeypatch):
    import wave
    capture(dialog, 16000)
    dialog.buffer.write(b'\x01')
    monkeypatch.setattr(dialog.warm, 'submit', lambda *args: None)
    dialog.finish_recording()
    with wave.open(str(Path(dialog.temp.name) / 'input.wav')) as recording:
        assert recording.getnframes() == 16000


def test_recording_write_failure_restores_controls(dialog, monkeypatch):
    capture(dialog, 16000)
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr(speak_as.wave, 'open', fail)
    dialog.finish_recording()
    assert dialog.record.isEnabled()
    assert dialog.source is None and dialog.buffer is None
    assert 'disk full' in dialog.status.text()


def test_unreadable_transcript_restores_controls(dialog):
    (Path(dialog.temp.name) / 'transcript.txt').write_bytes(b'\xff')
    dialog._start_index()
    assert dialog.record.isEnabled()
    assert 'Could not read local transcription' in dialog.status.text()


def test_completed_result_can_replay_and_shows_reference_note(dialog, monkeypatch):
    played = []
    monkeypatch.setattr(dialog.player, 'play', lambda: played.append(True))
    (Path(dialog.temp.name) / 'output.wav').write_bytes(b'converted wave')
    dialog._converted(dict(warm=True, seconds=1.5, output_path=str(Path(dialog.temp.name) / 'output.wav'),
        reference_note='Full reference used because fast conditioning was unavailable.'))
    assert dialog.replay.isEnabled()
    assert 'Full reference used' in dialog.status.text()
    assert played == [True]
    dialog.cancelled = True
    dialog._converted(dict(warm=True, seconds=1.5, output_path='cancelled.wav'))
    assert played == [True]


def test_gpu_choice_is_forwarded_without_device_fallback(dialog, monkeypatch):
    dialog.device.setCurrentIndex(dialog.device.findData('cuda'))
    capture(dialog, 16000)
    calls = []
    monkeypatch.setattr(dialog.warm, 'submit', lambda *args: calls.append(args))
    dialog.finish_recording()
    assert calls[-1][1]['device'] == 'cuda'
    assert 'reference_seconds' not in calls[-1][1]


def test_cancelled_start_failure_preserves_stop_feedback(dialog):
    dialog.stop()
    feedback = dialog.status.text()
    dialog._process_error(QProcess.ProcessError.FailedToStart)
    assert dialog.status.text() == feedback


def test_capture_locks_reference_selection_until_stopped(dialog, monkeypatch):
    fake = SimpleNamespace(isNull=lambda: False, isFormatSupported=lambda fmt: True)
    monkeypatch.setattr(speak_as, 'QMediaDevices', SimpleNamespace(defaultAudioInput=lambda: fake))
    source = SimpleNamespace(stateChanged=SimpleNamespace(connect=lambda callback: None),
        start=lambda buffer: None, stop=lambda: None, deleteLater=lambda: None)
    monkeypatch.setattr(speak_as, 'QAudioSource', lambda *args: source)
    dialog.start_recording()
    assert not dialog.reference_mode.isEnabled()
    assert not dialog.mode.isEnabled()
    dialog.stop()
    assert dialog.reference_mode.isEnabled()
    assert dialog.mode.isEnabled()


def test_saved_local_runtime_config_is_read_without_writing(dialog, monkeypatch):
    import json
    config = Path(dialog.parent().storage) / 'speak_as.json'
    content = json.dumps({'index_python': '/existing/runtime', 'index_repo': '/existing/repo'})
    config.write_text(content)
    monkeypatch.delenv('PVS_SPEAK_AS_CONFIG', raising=False)
    other = speak_as.SpeakAsDialog(dialog.parent())
    try:
        assert other.launchers['index_python'] == '/existing/runtime'
        assert config.read_text() == content
    finally:
        other.done(0)


def test_explicit_launcher_config_overrides_saved_config(dialog, monkeypatch):
    import json
    saved = Path(dialog.parent().storage) / 'speak_as.json'
    saved.write_text(json.dumps({'index_python': '/saved'}))
    selected = saved.with_name('selected.json')
    selected.write_text(json.dumps({'index_python': '/selected'}))
    monkeypatch.setenv('PVS_SPEAK_AS_CONFIG', str(selected))
    other = speak_as.SpeakAsDialog(dialog.parent())
    try:
        assert other.launchers['index_python'] == '/selected'
    finally:
        other.done(0)


def complete(dialog):
    output = Path(dialog.temp.name) / 'output.wav'
    output.write_bytes(b'exact converted WAV')
    dialog.pending_metadata = dict(engine='chatterbox', voice='Original voice', text='', transcription=None)
    dialog._converted(dict(warm=False, seconds=1, output_path=str(output)))
    return output


def test_save_exact_result_and_snapshot_survives_close(dialog, tmp_path, monkeypatch):
    import json
    output = complete(dialog)
    target = tmp_path / 'saved.wav'
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    dialog.mode.setCurrentIndex(1)
    dialog.transcript.setText('Unrelated edited transcript')
    roots = []
    dialog.parent().export_browser = SimpleNamespace(add_root=roots.append)
    assert dialog.save_recording()
    assert target.read_bytes() == output.read_bytes()
    metadata = json.loads(target.with_suffix('.json').read_text())
    assert metadata['engine'] == 'chatterbox'
    assert metadata['voice'] == 'Original voice'
    assert metadata['text'] == '' and metadata['transcription'] is None
    assert roots == [tmp_path]
    dialog.done(0)
    assert target.read_bytes() == b'exact converted WAV'
    assert not output.exists()


def test_save_cancel_and_conflict_preserve_result(dialog, tmp_path, monkeypatch):
    output = complete(dialog)
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: ('', ''))
    assert not dialog.save_recording()
    assert not dialog.last_result['saved']
    target = tmp_path / 'existing.wav'
    target.with_suffix('.json').write_text('old metadata')
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    assert not dialog.save_recording()
    assert output.exists() and not target.exists()
    assert target.with_suffix('.json').read_text() == 'old metadata'
    assert dialog.replay.isEnabled() and dialog.save.isEnabled()


def test_unsaved_close_and_new_take_cancel_keep_result(dialog, monkeypatch):
    output = complete(dialog)
    monkeypatch.setattr(speak_as.QMessageBox, 'question', lambda *a: speak_as.QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr(speak_as.QMediaDevices, 'defaultAudioInput', lambda: pytest.fail('microphone opened'))
    dialog.start_recording()
    assert dialog.last_result['path'] == output
    dialog.done(0)
    assert output.exists()
    monkeypatch.setattr(speak_as.QMessageBox, 'question', lambda *a: speak_as.QMessageBox.StandardButton.Discard)


def test_unsaved_save_cancel_blocks_close(dialog, monkeypatch):
    output = complete(dialog)
    monkeypatch.setattr(speak_as.QMessageBox, 'question', lambda *a: speak_as.QMessageBox.StandardButton.Save)
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: ('', ''))
    dialog.done(0)
    assert output.exists() and not dialog.last_result['saved']
    monkeypatch.setattr(speak_as.QMessageBox, 'question', lambda *a: speak_as.QMessageBox.StandardButton.Discard)


def test_result_missing_does_not_enable_save(dialog):
    dialog._converted(dict(warm=False, seconds=1, output_path='/missing/converted.wav'))
    assert not dialog.save.isEnabled()
    assert 'missing' in dialog.status.text()


def test_export_helper_rollback_and_overwrite_safety(tmp_path, monkeypatch):
    from chatterbox_studio import speak_as_export
    source = tmp_path / 'source.wav'
    source.write_bytes(b'converted')
    target = tmp_path / 'saved.wav'
    def fail(*a):
        raise OSError('disk full')
    monkeypatch.setattr(speak_as_export.shutil, 'copyfileobj', fail)
    with pytest.raises(OSError, match='disk full'):
        speak_as_export.save_recording(source, target, {'text': ''})
    assert not target.exists() and not target.with_suffix('.json').exists()
    target.write_bytes(b'old WAV')
    with pytest.raises(FileExistsError):
        speak_as_export.save_recording(source, target, {'text': ''})
    assert target.read_bytes() == b'old WAV'


def test_completion_uses_submitted_metadata(dialog, monkeypatch):
    monkeypatch.setattr(dialog.warm, 'submit', lambda *a: None)
    request = dict(engine='index25', voice_path='reference.wav', text='Actual words', device='cpu')
    dialog._submit_conversion('python', request, None, 100)
    dialog.transcript.setText('changed')
    dialog.mode.setCurrentIndex(1)
    output = Path(dialog.temp.name) / 'output.wav'
    output.write_bytes(b'converted')
    dialog._converted(dict(warm=False, seconds=1, output_path=str(output)))
    assert dialog.last_result['metadata']['text'] == 'Actual words'
    assert dialog.last_result['metadata']['conversion'] == 'transcription_resynthesis'


def test_save_rejects_temporary_session_destination(dialog, monkeypatch):
    complete(dialog)
    target = Path(dialog.temp.name) / 'would-be-lost.wav'
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    assert not dialog.save_recording()
    assert not target.exists()
    assert 'permanent folder' in dialog.status.text()


def test_export_helper_does_not_follow_existing_symlink(tmp_path):
    from chatterbox_studio.speak_as_export import save_recording
    source = tmp_path / 'source.wav'
    source.write_bytes(b'converted')
    target = tmp_path / 'target.wav'
    victim = tmp_path / 'absent.wav'
    target.symlink_to(victim)
    with pytest.raises(FileExistsError):
        save_recording(source, target, {'text': ''})
    assert not victim.exists()
    assert not target.with_suffix('.json').exists()


def test_missing_direct_runtime_never_opens_mic(dialog, monkeypatch):
    dialog.python = '/missing/python'
    monkeypatch.setattr(speak_as.QMediaDevices, 'defaultAudioInput', lambda: pytest.fail('microphone opened'))
    dialog.start_recording()
    assert dialog.source is None
    assert 'No microphone opened' in dialog.status.text()


def test_save_again_uses_same_bytes_and_original_metadata(dialog, tmp_path, monkeypatch):
    import json
    complete(dialog)
    targets = iter([tmp_path / 'first.wav', tmp_path / 'second.wav'])
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(next(targets)), ''))
    assert dialog.save_recording()
    dialog.pending_metadata = {'engine': 'unrelated'}
    assert dialog.save_recording()
    assert (tmp_path / 'first.wav').read_bytes() == (tmp_path / 'second.wav').read_bytes()
    assert json.loads((tmp_path / 'second.json').read_text())['engine'] == 'chatterbox'


def test_save_io_error_keeps_unsaved_replay(dialog, tmp_path, monkeypatch):
    from chatterbox_studio import speak_as_export
    complete(dialog)
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(tmp_path / 'saved.wav'), ''))
    def fail(*a):
        raise OSError('disk full')
    monkeypatch.setattr(speak_as_export, 'save_recording', fail)
    assert not dialog.save_recording()
    assert not dialog.last_result['saved']
    assert dialog.save.isEnabled() and dialog.replay.isEnabled()
    assert 'disk full' in dialog.status.text()


@pytest.mark.parametrize('answer', [speak_as.QMessageBox.StandardButton.Save,
                                  speak_as.QMessageBox.StandardButton.Discard])
def test_unsaved_prompt_requires_fresh_press_before_microphone(dialog, tmp_path, monkeypatch, answer):
    complete(dialog)
    saved = tmp_path / 'saved-before-next.wav'
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(saved), ''))
    def release_during_prompt(*args):
        dialog.record.setDown(False)
        dialog.finish_recording()
        return answer
    monkeypatch.setattr(speak_as.QMessageBox, 'question', release_during_prompt)
    opened = []
    fake = SimpleNamespace(isNull=lambda: False, isFormatSupported=lambda fmt: True)
    monkeypatch.setattr(speak_as, 'QMediaDevices', SimpleNamespace(defaultAudioInput=lambda: fake))
    source = SimpleNamespace(stateChanged=SimpleNamespace(connect=lambda callback: None),
        start=lambda buffer: opened.append(True), stop=lambda: None, deleteLater=lambda: None)
    monkeypatch.setattr(speak_as, 'QAudioSource', lambda *args: source)
    dialog.record.setDown(True)
    dialog.start_recording()
    assert dialog.source is None and not opened
    assert dialog.last_result is None
    assert saved.exists() == (answer == speak_as.QMessageBox.StandardButton.Save)
    assert 'Hold to speak again' in dialog.status.text()
    dialog.record.setDown(True)
    dialog.start_recording()
    assert dialog.source is source and opened == [True]
    dialog.finish_recording()


def test_metadata_does_not_export_reference_absolute_path(dialog, monkeypatch):
    monkeypatch.setattr(dialog.warm, 'submit', lambda *a: None)
    dialog._submit_conversion('python', dict(engine='chatterbox', reference='/private/reference.wav',
                              device='cpu'), None, 100)
    assert 'voice_path' not in dialog.pending_metadata
    assert '/private' not in str(dialog.pending_metadata)


@pytest.fixture
def seed_launchers(tmp_path):
    import json
    import sys
    repo = tmp_path / 'seed-repo'
    repo.mkdir()
    (repo / 'inference.py').touch()
    cache = tmp_path / 'seed-cache'
    cache.mkdir()
    manifest = tmp_path / 'seed-manifest.json'
    manifest.write_text(json.dumps([]), encoding='utf-8')
    return dict(seed_python=sys.executable, seed_repo=str(repo), seed_cache=str(cache),
        seed_manifest=str(manifest))


@pytest.mark.parametrize('chatterbox_available', [True, False])
def test_configured_seed_is_preferred_without_reordering_existing_engines(
        dialog, seed_launchers, monkeypatch, chatterbox_available):
    import json
    if not chatterbox_available:
        (dialog.weights / 's3gen.safetensors').unlink()
    config = Path(dialog.parent().storage) / 'speak_as.json'
    content = json.dumps(seed_launchers)
    config.write_text(content, encoding='utf-8')
    preferred = speak_as.SpeakAsDialog(dialog.parent())
    try:
        assert preferred.mode.itemData(0) == 'chatterbox'
        assert preferred.mode.itemData(1) == 'index25'
        assert preferred.mode.currentData() == 'seed_v1'
        assert preferred.record.isEnabled()
        assert preferred.runtime_label.text() == 'Seed-VC V1 runtime'
        assert preferred.runtime_path.text() == seed_launchers['seed_python']
        assert preferred.runtime_path.isReadOnly()
        assert '44.1 kHz' in preferred.mode.currentText()
        assert preferred.reference_mode.isHidden() and preferred.transcript.isHidden()
        assert preferred.source is None and not preferred.warm.busy
        assert config.read_text(encoding='utf-8') == content
    finally:
        preferred.done(0)


@pytest.mark.parametrize('missing', ['seed_python', 'seed_repo', 'seed_cache', 'seed_manifest'])
def test_missing_seed_configuration_is_visible_before_microphone(
        dialog, seed_launchers, missing):
    del seed_launchers[missing]
    dialog.launchers.update(seed_launchers)
    dialog.mode.setCurrentIndex(dialog.mode.findData('seed_v1'))
    assert not dialog.record.isEnabled()
    assert missing in dialog.runtime_note.text()
    assert 'No microphone opened' in dialog.runtime_note.text()
    dialog.start_recording()
    assert dialog.source is None
    assert missing in dialog.status.text()
    assert dialog.mode.currentData() == 'seed_v1'
    dialog.mode.setCurrentIndex(0)
    assert dialog.record.isEnabled()
    assert dialog.runtime_label.text() == 'Chatterbox runtime'
    assert dialog.runtime_path.text() == dialog.python
    dialog.mode.setCurrentIndex(1)
    assert dialog.record.isEnabled()
    dialog.index_fields[0].setText('/other/index/python')
    assert dialog.runtime_path.text() == '/other/index/python'


@pytest.mark.parametrize('content', ['broken JSON', '{}', 'null'])
def test_invalid_seed_manifest_never_opens_microphone(dialog, seed_launchers, content):
    Path(seed_launchers['seed_manifest']).write_text(content, encoding='utf-8')
    dialog.launchers.update(seed_launchers)
    dialog.mode.setCurrentIndex(dialog.mode.findData('seed_v1'))
    dialog.start_recording()
    assert dialog.source is None
    assert not dialog.record.isEnabled()
    assert 'seed_manifest' in dialog.status.text()


def test_seed_python_must_be_executable(dialog, seed_launchers, tmp_path):
    python = tmp_path / 'not-executable'
    python.touch(mode=0o600)
    seed_launchers['seed_python'] = str(python)
    dialog.launchers.update(seed_launchers)
    dialog.mode.setCurrentIndex(dialog.mode.findData('seed_v1'))
    dialog.start_recording()
    assert dialog.source is None
    assert 'seed_python' in dialog.status.text()


def test_unavailable_seed_does_not_replace_default_engine(dialog, seed_launchers, monkeypatch):
    import json
    config = Path(dialog.parent().storage) / 'speak_as.json'
    del seed_launchers['seed_manifest']
    config.write_text(json.dumps(seed_launchers), encoding='utf-8')
    other = speak_as.SpeakAsDialog(dialog.parent())
    try:
        assert other.mode.currentData() == 'chatterbox'
        assert other.record.isEnabled()
    finally:
        other.done(0)


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_seed_request_uses_recording_reference_and_fixed_profile(
        dialog, seed_launchers, monkeypatch, device):
    import wave
    dialog.launchers.update(seed_launchers)
    dialog.mode.setCurrentIndex(dialog.mode.findData('seed_v1'))
    dialog.device.setCurrentIndex(dialog.device.findData(device))
    calls = []
    monkeypatch.setattr(dialog.warm, 'submit', lambda *args: calls.append(args))
    capture(dialog, 16000)
    dialog.finish_recording()
    python, request, environment = calls[0]
    root = Path(dialog.temp.name)
    assert python == seed_launchers['seed_python']
    assert request == dict(engine='seed_v1', source=str(root / 'input.wav'),
        reference=dialog.voices.currentData(), repo=seed_launchers['seed_repo'],
        cache=seed_launchers['seed_cache'], manifest=seed_launchers['seed_manifest'],
        output_path=str(root / 'output.wav'), device=device, f0_condition=True,
        auto_f0_adjust=True, length_adjust=1.0, semi_tone_shift=0,
        diffusion_steps=30, inference_cfg_rate=0.7)
    assert environment.value('HF_HUB_OFFLINE') == '1'
    assert environment.value('TRANSFORMERS_OFFLINE') == '1'
    assert request['source'] != request['reference']
    assert not (root / 'transcript.txt').exists()
    assert dialog.transcript.text() == ''
    assert dialog.pending_metadata['engine'] == 'seed_v1'
    assert dialog.pending_metadata['conversion'] == 'direct_audio'
    assert dialog.pending_metadata['text'] == ''
    assert dialog.pending_metadata['transcription'] is None
    assert dialog.stage_timeout_ms == 600000
    assert not dialog.record.isEnabled()
    with wave.open(request['source']) as audio:
        assert audio.getframerate() == 16000 and audio.getnframes() == 16000
    dialog._timeout()
    assert '600-second' in dialog.status.text()
    assert dialog.mode.currentData() == 'seed_v1'
    assert dialog.record.isEnabled()


def test_seed_failure_does_not_fallback_or_retry(dialog, seed_launchers, monkeypatch):
    dialog.launchers.update(seed_launchers)
    dialog.mode.setCurrentIndex(dialog.mode.findData('seed_v1'))
    calls = []
    def fail(*args):
        calls.append(args)
        raise RuntimeError('Missing local Seed checkpoint')
    monkeypatch.setattr(dialog.warm, 'submit', fail)
    capture(dialog, 16000)
    dialog.finish_recording()
    assert len(calls) == 1
    assert dialog.mode.currentData() == 'seed_v1'
    assert dialog.record.isEnabled()
    assert 'Missing local Seed checkpoint' in dialog.status.text()
    assert not dialog.replay.isEnabled() and not dialog.save.isEnabled()
    assert not dialog.watchdog.isActive()


def test_seed_result_saves_exact_audio_and_safe_conversion_metadata(
        dialog, seed_launchers, tmp_path, monkeypatch):
    import json
    import wave
    dialog.launchers.update(seed_launchers)
    dialog.mode.setCurrentIndex(dialog.mode.findData('seed_v1'))
    monkeypatch.setattr(dialog.warm, 'submit', lambda *args: None)
    capture(dialog, 16000)
    dialog.finish_recording()
    output = Path(dialog.temp.name) / 'output.wav'
    with wave.open(str(output), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        audio.writeframes(b'\x10\x00' * 4410)
    conversion = dict(f0_condition=True, auto_f0_adjust=True, length_adjust=1.0,
        semi_tone_shift=0, seed_diffusion_steps=30, inference_cfg_rate=0.7,
        reference_duration=5.5, output_sample_rate=44100, output_peak=0.97,
        output_gain_db=-2.5)
    protected = dict(engine='wrong', voice='Wrong speaker', workflow='wrong', text='Wrong words',
        transcription='Wrong words', conversion='wrong', device='wrong',
        reference='/private/reference.wav', manifest='/private/manifest.json')
    note = 'Target register adjusted; relative inflection retained where possible.'
    dialog._converted(dict(warm=False, seconds=214.3, output_path=str(output),
        conversion_metadata=dict(conversion, **protected), conversion_note=note))
    assert dialog.save.isEnabled() and dialog.replay.isEnabled()
    assert note in dialog.status.text()
    metadata = dialog.last_result['metadata']
    assert all(metadata[key] == value for key, value in conversion.items())
    assert metadata['engine'] == 'seed_v1' and metadata['voice'] == 'Test'
    assert metadata['workflow'] == 'speak_as' and metadata['conversion'] == 'direct_audio'
    assert metadata['text'] == '' and metadata['transcription'] is None
    assert metadata['device'] == 'cpu'
    assert '/private/' not in str(metadata)
    dialog.mode.setCurrentIndex(1)
    target = tmp_path / 'saved-seed.wav'
    monkeypatch.setattr(speak_as.QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(target), ''))
    assert dialog.save_recording()
    assert target.read_bytes() == output.read_bytes()
    assert json.loads(target.with_suffix('.json').read_text()) == metadata


@pytest.mark.parametrize('conversion', [None, [], 'invalid',
    {'output_peak': float('nan'), 'output_gain_db': float('inf'),
     'reference_duration': '/private/path', 'f0_condition': {'unexpected': True}}])
def test_unusable_conversion_metadata_cannot_break_save(dialog, conversion):
    output = Path(dialog.temp.name) / 'output.wav'
    output.write_bytes(b'converted')
    dialog._converted(dict(warm=False, seconds=1, output_path=str(output),
        conversion_metadata=conversion, conversion_note=['invalid']))
    assert dialog.save.isEnabled()
    assert not (set(dialog.last_result['metadata']) & speak_as._CONVERSION_METADATA_KEYS)

@pytest.fixture
def countdown_capture(dialog, monkeypatch):
    fake = SimpleNamespace(isNull=lambda: False, isFormatSupported=lambda fmt: True)
    monkeypatch.setattr(speak_as, 'QMediaDevices', SimpleNamespace(defaultAudioInput=lambda: fake))
    from PyQt6.QtMultimedia import QAudio
    source = SimpleNamespace(stateChanged=SimpleNamespace(connect=lambda callback: None),
        start=lambda buffer: None, stop=lambda: None, deleteLater=lambda: None,
        error=lambda: QAudio.Error.NoError)
    monkeypatch.setattr(speak_as, 'QAudioSource', lambda *args: source)
    return source


def test_countdown_repeated_start_stop_and_finish(dialog, countdown_capture):
    from PyQt6.QtTest import QTest
    for finish in (dialog.stop, dialog.finish_recording, dialog.stop):
        dialog.start_recording()
        assert dialog.recording_countdown.text().endswith('20.0 s')
        assert dialog.timer.interval() == 20000
        assert dialog.countdown_timer.isActive()
        QTest.qWait(230)
        assert 19.6 <= float(dialog.recording_countdown.text().split()[-2]) < 20
        finish()
        assert not dialog.countdown_timer.isActive()
        assert not dialog.timer.isActive()
        text = dialog.recording_countdown.text()
        QTest.qWait(150)
        assert dialog.recording_countdown.text() == text


def test_countdown_uses_deadline_not_ticks(dialog, countdown_capture, monkeypatch):
    dialog.start_recording()
    monkeypatch.setattr(dialog.timer, 'remainingTime', lambda: 1234)
    dialog._update_recording_countdown()
    assert dialog.recording_countdown.text().endswith('1.3 s')
    monkeypatch.setattr(dialog.timer, 'remainingTime', lambda: -1)
    dialog._update_recording_countdown()
    assert dialog.recording_countdown.text().endswith('0.0 s')


def test_countdown_actual_limit_stops_capture(dialog, countdown_capture):
    from PyQt6.QtTest import QTest
    dialog.start_recording()
    QTest.qWait(20200)
    assert dialog.source is None
    assert not dialog.countdown_timer.isActive()
    assert dialog.recording_countdown.text().endswith('0.0 s')
    assert 'too short' in dialog.status.text()


@pytest.mark.parametrize('failure', ['start', 'device', 'runtime'])
def test_countdown_microphone_errors(dialog, countdown_capture, monkeypatch, failure):
    from PyQt6.QtMultimedia import QAudio
    if failure == 'start':
        def fail(buffer):
            raise RuntimeError('test failure')
        countdown_capture.start = fail
    elif failure == 'device':
        monkeypatch.setattr(speak_as.QMediaDevices, 'defaultAudioInput', lambda: SimpleNamespace(isNull=lambda: True))
    dialog.start_recording()
    if failure == 'runtime':
        countdown_capture.error = lambda: QAudio.Error.IOError
        dialog._audio_state(None)
    assert dialog.source is None
    assert not dialog.countdown_timer.isActive()
    assert not dialog.timer.isActive()


def test_countdown_ui_readable(dialog, countdown_capture, tmp_path):
    dialog.show()
    QApplication.processEvents()
    assert dialog.recording_countdown.isVisible()
    assert dialog.recording_countdown.font().pointSize() >= 14
    assert dialog.recording_countdown.font().bold()
    assert dialog.recording_countdown.width() >= dialog.recording_countdown.sizeHint().width()
    assert dialog.grab().save(str(tmp_path / 'countdown-ui.png'))
