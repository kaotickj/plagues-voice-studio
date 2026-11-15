import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
from chatterbox_studio.warm_worker import Session, serve


def test_protocol_keeps_library_stdout_out_of_json(capsys):
    def work(req):
        print('model progress')
        return {'output_path':'test.wav'}
    dest=io.StringIO()
    serve(work,io.StringIO('{"id":"a"}\n'),dest)
    assert json.loads(dest.getvalue())['ok']
    assert 'model progress' in capsys.readouterr().err


def test_errors_end_session_without_running_next_request():
    calls=[]
    def work(req):
        calls.append(req)
        raise ValueError('failure')
    dest=io.StringIO()
    serve(work,io.StringIO('{"id":"a"}\n{"id":"b"}\n'),dest)
    assert len(calls)==1
    assert json.loads(dest.getvalue())=={'id':'a','ok':False,'error':'failure'}


def test_chatterbox_reuses_exact_model_and_rejects_config_change():
    import pytest
    model=object();seen=[]
    def convert(*args,model=None):
        seen.append(model)
        return marker
    marker=model
    s=Session(validator=lambda path:None)
    with patch.dict(sys.modules, {'voice_conversion':SimpleNamespace(convert=convert)}):
        req=dict(engine='chatterbox',source='in',reference='ref',weights='weights',output_path='out',device='cpu')
        assert s(req)['warm'] is False
        assert s(req)['warm'] is True
        assert seen==[None,marker]
        with pytest.raises(ValueError,match='configuration changed'):
            s(dict(req,weights='other'))
    s.release()
    assert s.model is None


def test_index_reuses_model_with_new_speaker_and_emotion(tmp_path, monkeypatch):
    repo=tmp_path/'repo';repo.mkdir()
    calls=[];marker=object()
    def run(req,synthesizer=None):
        calls.append((req,synthesizer));return marker
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    s=Session(validator=lambda path:None)
    with patch('chatterbox_studio.warm_worker.load_index_runner', return_value=run):
        req=dict(engine='index25',repo=str(repo),output_path='out',device='cpu',voice_path='a',emotion_audio_path='emotion-a')
        assert not s(req)['warm']
        assert s(dict(req,voice_path='b',emotion_audio_path='emotion-b'))['warm']
        assert calls[1][1] is marker
        assert calls[1][0]['voice_path']=='b'
        assert calls[1][0]['emotion_audio_path']=='emotion-b'
    s.release()


def test_output_validation(tmp_path):
    import numpy as np
    import soundfile as sf
    import pytest
    from chatterbox_studio.warm_worker import validate_audio
    p=tmp_path/'output.wav'
    sf.write(p,np.zeros(16000),16000)
    with pytest.raises(ValueError,match='silent'):
        validate_audio(p)
    sf.write(p,np.ones(16000)*.1,16000)
    validate_audio(p)


def test_index_adapter_does_not_add_frozen_library_directory_to_import_path():
    from chatterbox_studio.warm_worker import load_index_runner
    original = list(sys.path)
    runner = load_index_runner()
    assert callable(runner)
    assert sys.path == original
    assert Path(runner.__code__.co_filename).name == 'optional_engine_runner.py'
