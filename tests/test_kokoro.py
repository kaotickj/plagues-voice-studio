"""Kokoro preset protocol and actual Qt controls, without model dependencies."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from chatterbox_studio import optional_engines as oe


@pytest.fixture
def kokoro_request(tmp_path):
    models = tmp_path / 'kokoro'
    models.mkdir()
    (models / 'kokoro-v1.0.int8.onnx').write_bytes(b'model fixture')
    (models / 'voices-v1.0.bin').write_bytes(b'voice fixture')
    return dict(engine='kokoro', model=oe.ENGINES['kokoro']['models'][0],
                model_dir=str(models), preset_voice='am_michael', language='English (US)',
                device='cpu', speed=1.15, text='An ordinary voice test.',
                output_path=str(tmp_path / 'spoken.wav'))


def test_preset_generation_needs_no_reference_and_retains_provenance(kokoro_request, monkeypatch, tmp_path):
    request = oe.clean_request(kokoro_request)
    assert request['voice_path'] == '' and request['preset_voice'] == 'am_michael'
    runner = tmp_path / 'runner.py'
    runner.write_text("""import json,sys,wave
from pathlib import Path
r=json.loads(Path(sys.argv[2]).read_text())
assert not r['voice_path'] and r['preset_voice']=='am_michael'
with wave.open(r['output_path'],'wb') as f:
    f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\\0\\0'*2400)
Path(sys.argv[3]).write_text(json.dumps({'ok':True}))
""", encoding='utf-8')
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner)
    audio = oe.execute_generation(request, sys.executable)
    metadata = json.loads(audio.with_suffix('.json').read_text())
    assert metadata['preset_voice'] == 'am_michael' and metadata['speed'] == 1.15
    assert metadata['model_dir'] == str(Path(request['model_dir']).resolve())
    with pytest.raises(oe.EngineError, match='overwrite'):
        oe.clean_request(request)


@pytest.mark.parametrize('change,message', [
    ({'preset_voice':'my-reference.wav'}, 'preset voice'),
    ({'preset_voice':'bf_emma'}, 'accent'),
    ({'device':'cuda'}, 'CPU'),
    ({'speed':0.1}, 'Speed'),
    ({'model_dir':'missing'}, 'model folder'),
])
def test_rejects_unsupported_kokoro_requests(kokoro_request, change, message):
    with pytest.raises(oe.EngineError, match=message):
        oe.clean_request(dict(kokoro_request, **change))


def test_registry_adds_kokoro_without_losing_old_engine_paths(tmp_path, monkeypatch):
    monkeypatch.setenv('PLAGUED_AI_HOME', str(tmp_path / 'vault'))
    python = tmp_path/'vault/runtimes/python/kokoro-onnx'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    python.parent.mkdir(parents=True); python.touch()
    registry = oe.EngineRegistry(tmp_path)
    registry.path.write_text(json.dumps({'index25': {'python':'old-python', 'repo':'old-repo'}}))
    config = registry.read()
    assert config['kokoro']['python'] == str(python)
    config['kokoro']['model_dir'] = str(tmp_path / 'custom-models')
    registry.save(config)
    assert registry.read()['index25'] == {'python':'old-python','repo':'old-repo'}
    assert registry.read()['kokoro']['model_dir'] == str(tmp_path / 'custom-models')


def test_runner_preset_uses_cpu_session_and_speed(kokoro_request, monkeypatch):
    import numpy as np
    spec = importlib.util.spec_from_file_location('kokoro_runner_test', oe.runtime_script_path())
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    observed = {}
    def session(path, sess_options, providers):
        observed.update(path=path, providers=providers, threads=sess_options.intra_op_num_threads)
        return SimpleNamespace(get_providers=lambda:['CPUExecutionProvider'])
    class Synth:
        def create(self, text, **kwargs):
            observed.update(text=text, **kwargs)
            return np.ones(2400, dtype=np.float32)*0.1, 24000
    monkeypatch.setitem(sys.modules,'onnxruntime', SimpleNamespace(
        __version__='test', SessionOptions=lambda:SimpleNamespace(), InferenceSession=session,
        get_available_providers=lambda:['CPUExecutionProvider']))
    monkeypatch.setitem(sys.modules,'kokoro_onnx',SimpleNamespace(
        Kokoro=SimpleNamespace(from_session=lambda session, voices:Synth())))
    runner.kokoro_run(kokoro_request)
    assert observed['providers'] == ['CPUExecutionProvider']
    assert observed['voice'] == 'am_michael' and observed['speed'] == 1.15
    assert observed['lang'] == 'en-us'
    assert 1 <= observed['threads'] <= 6
    assert Path(kokoro_request['output_path']).stat().st_size > 44
    with pytest.raises(FileExistsError):
        runner.kokoro_run(kokoro_request)


def test_kokoro_controls_profiles_and_no_reference_dependency(kokoro_request, tmp_path, monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PyQt6.QtWidgets import QApplication, QWidget, QPlainTextEdit
    from chatterbox_studio.engine_lab import EngineLab
    from chatterbox_studio import pvs_library
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.storage = tmp_path
    def reject_reference(*args):
        raise AssertionError('Kokoro must not resolve reference audio')
    host.voices = SimpleNamespace(list_voices=lambda:[], resolve=reject_reference)
    host.editor = QPlainTextEdit()
    host.player = SimpleNamespace(stop=lambda:None)
    monkeypatch.setattr(pvs_library,'new_export_directory',lambda storage:tmp_path/'exports')
    lab = EngineLab(host)
    lab.kokoro_models.setText(kokoro_request['model_dir'])
    lab.engine.setCurrentIndex(lab.engine.findData('kokoro'))
    lab.preset_voice.setCurrentIndex(lab.preset_voice.findData('bf_emma'))
    lab.speed.setValue(1.2)
    lab.text.setPlainText('Testing the UK voice.')
    lab.character.setEditText('Announcer')
    lab.save_profile()
    request = lab._make_request('kokoro')
    assert request['voice_path']=='' and request['preset_voice']=='bf_emma'
    assert request['language']=='English (UK)' and request['speed']==1.2
    assert lab.voice.isHidden() and lab.ref_text.isHidden() and not lab.preset_voice.isHidden()
    assert lab.device.currentData()=='auto'
    assert (lab.device.findData('directml')>=0) == (sys.platform=='win32')
    assert not lab.compare.isEnabled()
    lab.engine.setCurrentIndex(lab.engine.findData('index25'))
    assert not lab.voice.isHidden() and lab.preset_voice.isHidden()
    lab.engine.setCurrentIndex(lab.engine.findData('kokoro'))
    assert lab.preset_voice.currentData()=='bf_emma' and lab.speed.value()==1.2
    assert lab.profiles.read()['Announcer']['engines']['kokoro']['preset_voice']=='bf_emma'
    host.close(); host.deleteLater(); app.processEvents()


def test_directml_options_and_explicit_failure_in_cpu_environment(kokoro_request, monkeypatch):
    import numpy as np
    spec = importlib.util.spec_from_file_location('kokoro_gpu_runner_test', oe.runtime_script_path())
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    observed = {}
    def session(path, sess_options, providers):
        observed.update(path=path,providers=providers,options=sess_options)
        return SimpleNamespace(get_providers=lambda:['DmlExecutionProvider','CPUExecutionProvider'])
    ort = SimpleNamespace(__version__='test',SessionOptions=lambda:SimpleNamespace(),
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL='sequential'),
        GraphOptimizationLevel=SimpleNamespace(ORT_DISABLE_ALL='disabled'),
        get_available_providers=lambda:['DmlExecutionProvider','CPUExecutionProvider'],InferenceSession=session)
    monkeypatch.setitem(sys.modules,'onnxruntime',ort)
    monkeypatch.setattr(runner,'kokoro_directml_model',lambda source:source.parent/'cached.onnx')
    monkeypatch.setitem(sys.modules,'kokoro_onnx',SimpleNamespace(Kokoro=SimpleNamespace(
        from_session=lambda *args:SimpleNamespace(create=lambda *args,**kwargs:(np.ones(2400)*0.1,24000)))))
    runtime = runner.kokoro_run(dict(kokoro_request,device='auto'))
    assert runtime['backend']=='directml'
    assert observed['path'].endswith('cached.onnx')
    assert observed['options'].enable_mem_pattern is False
    assert observed['options'].execution_mode=='sequential'
    assert observed['options'].graph_optimization_level=='disabled'
    assert observed['providers'][0]==('DmlExecutionProvider',{'device_id':'0'})
    ort.get_available_providers=lambda:['CPUExecutionProvider']
    with pytest.raises(RuntimeError,match='DirectML is not installed'):
        runner.kokoro_run(dict(kokoro_request,device='directml'))


def test_cloning_engines_do_not_offer_directml(kokoro_request, tmp_path):
    voice=tmp_path/'reference.wav'; voice.write_bytes(b'fixture')
    request=dict(kokoro_request,engine='qwen3',model=oe.ENGINES['qwen3']['models'][0],
                 voice_path=str(voice),language='English',device='directml')
    with pytest.raises(oe.EngineError,match='Kokoro only'):
        oe.clean_request(request)
