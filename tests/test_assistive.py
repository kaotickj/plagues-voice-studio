import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from types import SimpleNamespace
import pytest
from PyQt6.QtWidgets import QApplication,QWidget
from chatterbox_studio import speak_as, assistive

@pytest.fixture
def dialog(tmp_path,monkeypatch):
 app=QApplication.instance() or QApplication([])
 p=QWidget();p.storage=tmp_path
 ref=tmp_path/'reference.wav';ref.touch()
 p.voices=SimpleNamespace(list_voices=lambda:[{'id':'a','name':'Test'}],resolve=lambda _:ref)
 p.voice=SimpleNamespace(currentData=lambda:'a');p.settings=SimpleNamespace(value=lambda key,default='':default)
 signal=SimpleNamespace(connect=lambda _:None)
 plays=[]
 monkeypatch.setattr(speak_as,'QAudioOutput',lambda *args:object())
 monkeypatch.setattr(speak_as,'QMediaPlayer',lambda *args:SimpleNamespace(setAudioOutput=lambda _:None,errorOccurred=signal,stop=lambda:None,setSource=lambda _:None,play=lambda:plays.append(True)))
 monkeypatch.setattr(speak_as,'QAudioSource',lambda *args:pytest.fail('Unexpected microphone access'))
 d=assistive.AssistiveDialog(p)
 yield d,plays
 d.done(0)

def test_prepared_result_never_autoplays_or_sends(dialog,tmp_path):
 d,plays=dialog
 f=tmp_path/'out.wav';f.touch()
 d._converted(dict(output_path=str(f),seconds=1))
 assert d.last_result and not plays and not d.send.isEnabled()
 assert d.sender.state().name=='NotRunning'

def test_cancelled_result_is_not_made_sendable(dialog,tmp_path):
 d,plays=dialog
 f=tmp_path/'out.wav';f.touch()
 d.stop();d._converted(dict(output_path=str(f),seconds=1))
 assert d.last_result is None and not plays and not d.send.isEnabled()

def test_transcription_requires_review(dialog):
 d,plays=dialog
 (Path(d.temp.name)/'transcript.txt').write_text('Please help me.')
 d._start_index()
 assert d.text.toPlainText()=='Please help me.'
 assert d.last_result is None and not d.warm.busy and not plays
 assert 'Review and correct' in d.status.text()

def test_missing_route_does_not_fallback_to_speakers(dialog,tmp_path,monkeypatch):
 d,plays=dialog
 f=tmp_path/'out.wav';f.touch()
 d._converted(dict(output_path=str(f),seconds=1));d.send_audio()
 assert d.sender.state().name=='NotRunning' and not plays
 assert 'Enable' in d.status.text()

def test_input_limit_and_empty_input_do_not_start_worker(dialog):
 d,_=dialog
 for text in ('','a'*2001):
  d.text.setPlainText(text);d.prepare_text()
  assert not d._busy() and '2,000' in d.status.text()
