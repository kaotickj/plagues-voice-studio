"""Frozen/source real-inference checker preserves transcripts and isolates output paths."""
import json
import struct
import types
import wave

import pytest
from chatterbox_studio import speech_check as sc


@pytest.mark.parametrize('silent,expected',[(False,0),(True,1)])
def test_check_records_audio_and_rejects_silence(tmp_path,monkeypatch,silent,expected):
    reference=tmp_path/'reference.wav';reference.write_bytes(b'reference remains unchanged')
    request=tmp_path/'request.json'
    request.write_text(json.dumps(dict(engine='qwen3',model='test-model',text='A test script.',
                                      voice_path=str(reference),output_path=str(reference))))
    monkeypatch.setattr(sc,'EngineRegistry',lambda path:types.SimpleNamespace(read=lambda:{'qwen3':{'python':'isolated'}}))
    def generate(req,python,**kwargs):
        output=sc.Path(req['output_path'])
        assert output!=reference
        with wave.open(str(output),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
            f.writeframes(struct.pack('<h',0 if silent else 1000)*2400)
        output.with_suffix('.json').write_text(json.dumps({'text':req['text']}))
        return output
    monkeypatch.setattr(sc,'execute_generation',generate)
    monkeypatch.setattr(sc,'user_data_dir',lambda:tmp_path)
    report=tmp_path/'result.json'
    assert sc.run(request,report)==expected
    data=json.loads(report.read_text())
    assert data['status']==('passed' if expected==0 else 'failed')
    assert reference.read_bytes()==b'reference remains unchanged'
