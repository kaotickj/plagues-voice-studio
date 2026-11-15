from types import SimpleNamespace
import os,sys,socket
import pytest
from chatterbox_studio import fast_asr

def args(tmp_path):
    site=tmp_path/'site';site.mkdir();model=tmp_path/'model';model.mkdir()
    for name in ('model.bin','tokenizer.json'):(model/name).touch()
    source=tmp_path/'input.wav';source.touch()
    return ['--site',str(site),'-m',str(model),'-f',str(source),'-of',str(tmp_path/'transcript'),'-otxt','-ng','-l','auto','-t','4']

def test_forces_cpu_offline_english_and_writes_text(tmp_path,monkeypatch):
    arguments=args(tmp_path);calls=[]
    for key in ('CUDA_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE'):
        monkeypatch.setenv(key,'original')
    monkeypatch.setattr(sys,'path',list(sys.path))
    original=socket.socket.connect
    def create(model,**kwargs):
        calls.append(kwargs)
        assert os.environ['CUDA_VISIBLE_DEVICES']==''
        # Exercise the guard without opening a real network socket.
        for method in (socket.socket.connect, socket.socket.connect_ex):
            for family in (socket.AF_INET, socket.AF_INET6):
                with pytest.raises(OSError,match='local-only'):
                    method(SimpleNamespace(family=family),('127.0.0.1',9))
        def transcribe(source,**opts):
            assert opts['language']=='en'
            return iter([SimpleNamespace(text=' Test words. ')]),None
        return SimpleNamespace(transcribe=transcribe)
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=create))
    assert fast_asr.main(arguments)==0
    assert calls[0]['device']=='cpu' and calls[0]['compute_type']=='int8' and calls[0]['local_files_only']
    assert (tmp_path/'transcript.txt').read_text()=='Test words.\n'
    assert socket.socket.connect is original

def test_requires_no_gpu_flag_before_import(tmp_path):
    arguments=args(tmp_path);arguments.remove('-ng')
    with pytest.raises(SystemExit):fast_asr.main(arguments)

def test_refuses_existing_transcript(tmp_path):
    arguments=args(tmp_path);(tmp_path/'transcript.txt').write_text('preserve')
    with pytest.raises(SystemExit):fast_asr.main(arguments)
    assert (tmp_path/'transcript.txt').read_text()=='preserve'
