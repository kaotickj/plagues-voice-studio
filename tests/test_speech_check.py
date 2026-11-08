"""Frozen/source real-inference checker preserves transcripts and isolates output paths."""
import json
import struct
import types
import sys
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


def test_chatterbox_check_forwards_requested_profile_scope_and_settings(tmp_path, monkeypatch):
    from chatterbox_studio import engine
    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(
        set_num_threads=lambda _: None, manual_seed=lambda _: None))
    received = []

    class FakeEngine:
        def render(self, job, *_):
            received.append(job)
            job.validate()
            output = sc.Path(job.output_path)
            with wave.open(str(output), 'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000)
                audio.writeframes(struct.pack('<h', 1000) * 800)
            output.with_suffix('.json').write_text(json.dumps({
                **job.as_json(), 'prepared_text': job.render_text,
                'effective_settings': job.effective_settings(),
            }))
            return output

    monkeypatch.setattr(engine, 'Engine', FakeEngine)
    request = tmp_path / 'request.json'
    request.write_text(json.dumps(dict(
        engine='chatterbox', model='english', text='Opening. Selected. Ending.',
        prepared_text='Selected.', render_scope='selection', profile='clear_narration',
        voice_id='', voice_path='', language='en', device='cpu',
        temperature=.61, exaggeration=.72, cfg_weight=.28, max_chars=100, pause_ms=90,
    )))
    report = tmp_path / 'report.json'
    assert sc.run(request, report) == 0
    job = received[0]
    assert job.render_scope == 'selection' and job.render_text == 'Selected.'
    assert job.text == 'Opening. Selected. Ending.'
    assert job.temperature == .61 and job.exaggeration == .72 and job.cfg_weight == .28
    result = json.loads(report.read_text())
    assert result['profile'] == 'clear_narration'
    assert result['effective_settings'] == job.effective_settings()
    assert result['prepared_text'] == 'Selected.'
