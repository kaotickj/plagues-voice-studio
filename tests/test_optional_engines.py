"""Process-isolation and config regression tests; require no ML dependencies."""
import json
import sys
import os
import wave
from pathlib import Path
from threading import Event

import pytest

from chatterbox_studio import optional_engines as oe


def sample(tmp_path, engine='qwen3'):
    voice = tmp_path / 'voice.wav'
    with wave.open(str(voice), 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(b'\x00\x00' * 16000)
    return {
        'engine': engine, 'model': oe.ENGINES[engine]['models'][0],
        'text': 'The night belongs to the blues.',
        'voice_path': str(voice), 'output_path': str(tmp_path / 'render.wav'),
        'language': 'EN' if engine == 'index25' else 'English',
        'speed': 1.0, 'device': 'cpu', 'emotion': 'neutral',
    }


def test_engine_registry_isolated_from_stable(tmp_path):
    stable = tmp_path / 'PlaguesVoiceStudio-v021'
    stable.mkdir()
    marker = stable / 'voices.json'; marker.write_text('[]')
    lab = tmp_path / 'PlaguesVoiceStudio-v030-Experimental'
    reg = oe.EngineRegistry(lab)
    assert reg.read()['qwen3']['python'] == ''
    reg.save({'qwen3': {'python': 'C:/engine/python.exe'}})
    assert reg.read()['qwen3']['python'] == 'C:/engine/python.exe'
    assert marker.read_text() == '[]'
    assert not (stable / 'optional_engines.json').exists()


def test_character_profiles_keep_two_engine_presets(tmp_path):
    store = oe.CharacterStore(tmp_path)
    p = {'voice_id': 'stable:a', 'engines': {'qwen3': {'model': 'small'}, 'index25': {'model': 'large'}}}
    store.save_profile('Mama Mire', p)
    assert store.read()['Mama Mire']['engines']['index25']['model'] == 'large'
    assert store.read()['Mama Mire']['engines']['qwen3']['model'] == 'small'
    store.delete_profile('Mama Mire')
    assert store.read() == {}


def test_request_validation_and_no_overwrite(tmp_path):
    r = sample(tmp_path)
    assert oe.clean_request(r)['model'].endswith('Base')
    Path(r['output_path']).write_bytes(b'keep')
    with pytest.raises(oe.EngineError, match='overwrite'):
        oe.clean_request(r)


def test_reject_unknown_engines_and_models(tmp_path):
    r = sample(tmp_path)
    r['engine'] = 'forbidden'
    with pytest.raises(oe.EngineError): oe.clean_request(r)
    r = sample(tmp_path)
    r['model'] = 'some random model'
    with pytest.raises(oe.EngineError): oe.clean_request(r)


def test_unique_output_names(tmp_path):
    p = oe.new_output_path(tmp_path, 'Mama Mire / demo')
    q = oe.new_output_path(tmp_path, 'Mama Mire / demo')
    assert p != q and p.parent == tmp_path
    assert p.name.startswith('Mama_Mire_demo_')


def fake_runner(tmp_path):
    # Pure-stdlib mock of the transport/protocol, not a model quality test.
    script = tmp_path / 'runner.py'
    script.write_text('''import json,sys,wave
from pathlib import Path
if sys.argv[1] == '--probe':
    print(json.dumps({'ready':True,'torch':'test','cuda_available':False}))
else:
    data = json.loads(Path(sys.argv[2]).read_text())
    with wave.open(data['output_path'], 'wb') as wf:
        wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(16000);wf.writeframes(b'\\x00\\x00'*1600)
    Path(sys.argv[3]).write_text(json.dumps({'ok':True}))
''')
    return script


def test_subprocess_and_json_sidecar_without_ml(tmp_path, monkeypatch):
    runner = fake_runner(tmp_path)
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner)
    r = sample(tmp_path)
    probe = oe.execute_probe('qwen3', sys.executable)
    assert probe['ready'] is True
    rendered = oe.execute_generation(r, sys.executable)
    assert rendered.is_file()
    info = json.loads(rendered.with_suffix('.json').read_text())
    assert info['engine'] == 'qwen3'
    assert info['text'] == r['text']
    assert info['voice_path'] == str((tmp_path / 'voice.wav').resolve())


def test_pre_cancel_does_not_launch_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: fake_runner(tmp_path))
    event = Event(); event.set()
    with pytest.raises(oe.EngineCancelled):
        oe.execute_generation(sample(tmp_path), sys.executable, event)
    assert not (tmp_path / 'render.wav').exists()


def test_index_requires_repo_and_checkpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: fake_runner(tmp_path))
    with pytest.raises(oe.EngineError, match='repository'):
        oe.check_configuration('index25', sys.executable, str(tmp_path))
    (tmp_path/'indextts').mkdir()
    (tmp_path/'indextts'/'infer_v2_5.py').write_text('')
    with pytest.raises(oe.EngineError, match='checkpoint'):
        oe.check_configuration('index25', sys.executable, str(tmp_path))


def test_source_includes_lab_and_frozen_bundle(tmp_path):
    root = Path(__file__).resolve().parents[1]
    app = (root/'src/chatterbox_studio/app.py').read_text()
    spec = (root/'ChatterboxStudio.spec').read_text()
    assert 'EngineLab(self)' in app
    assert "'optional_engine_runner.py'" in spec


def test_isolated_environment_removes_host_python_variables(monkeypatch, tmp_path):
    monkeypatch.setenv('PYTHONHOME', '/bad/python311')
    monkeypatch.setenv('PYTHONPATH', '/bad/host-packages')
    monkeypatch.setenv('PYTHONEXECUTABLE', '/bad/python')
    monkeypatch.setenv('PVS_CUSTOM', 'keep-me')
    child = oe._isolated_engine_environment()
    assert 'PYTHONHOME' not in child
    assert 'PYTHONPATH' not in child
    assert 'PYTHONEXECUTABLE' not in child
    assert child['PVS_CUSTOM'] == 'keep-me'
    assert oe._isolated_engine_environment() != {}  # Environment not replaced wholesale


def test_frozen_windows_dll_directory_restored_after_engine_launch(monkeypatch, tmp_path):
    """Regression for python311.dll conflict when a bundled app launches 3.12."""
    runner = fake_runner(tmp_path)
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner)
    monkeypatch.setattr(oe, '_is_frozen_windows', lambda: True)
    monkeypatch.setattr(oe.sys, '_MEIPASS', str(tmp_path / '_internal'), raising=False)
    observed = []
    monkeypatch.setattr(oe, '_set_windows_dll_directory', lambda path: observed.append(path))
    probe = oe.execute_probe('qwen3', sys.executable)
    assert probe['ready']
    assert observed == [None, str(tmp_path / '_internal')]
    observed.clear()
    result = oe.execute_generation(sample(tmp_path), sys.executable)
    assert result.is_file()
    assert observed == [None, str(tmp_path / '_internal')]


def test_frozen_windows_dll_directory_restored_on_spawn_error(monkeypatch, tmp_path):
    monkeypatch.setattr(oe, '_is_frozen_windows', lambda: True)
    monkeypatch.setattr(oe.sys, '_MEIPASS', str(tmp_path / '_internal'), raising=False)
    observed = []
    monkeypatch.setattr(oe, '_set_windows_dll_directory', lambda path: observed.append(path))
    def cannot_launch(*args, **kwargs):
        raise OSError('simulated CreateProcess error')
    monkeypatch.setattr(oe.subprocess, 'Popen', cannot_launch)
    with pytest.raises(OSError, match='simulated'):
        oe._spawn_optional_interpreter([sys.executable, '-c', 'pass'])
    assert observed == [None, str(tmp_path / '_internal')]


def test_frozen_bundle_path_removed_from_engine_child_environment(monkeypatch, tmp_path):
    bundle = str(tmp_path / '_internal')
    good = str(tmp_path / 'good')
    monkeypatch.setattr(oe.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(oe.sys, '_MEIPASS', bundle, raising=False)
    monkeypatch.setenv('PATH', os.pathsep.join([bundle, good, bundle + os.sep + 'Qt6', good]))
    monkeypatch.setenv('_PYI_ARCHIVE_FILE', 'host-bootloader')
    env = oe._isolated_engine_environment()
    assert env['PATH'] == os.pathsep.join([good, good])
    assert '_PYI_ARCHIVE_FILE' not in env


def test_external_runner_does_not_import_from_pyinstaller_bundle(tmp_path, monkeypatch):
    """A 3.12 child must not import extensions next to the bundled 3.11 runner.

    Normally Python places the script directory on sys.path[0]. That directory
    is PyInstaller's _internal/ in the Windows frozen build. Isolated Python -I
    prevents that path from entering the external interpreter's import search.
    """
    internal = tmp_path / '_internal'
    internal.mkdir()
    (internal / 'pvs_bundle_poison_0312.py').write_text(
        'raise RuntimeError("Bundled host module leaked into external engine")\n')
    script = internal / 'optional_engine_runner.py'
    script.write_text("""import json,sys,wave
from pathlib import Path
try:
    import pvs_bundle_poison_0312
except ModuleNotFoundError:
    pass
else:
    raise RuntimeError('host module imported')
if sys.argv[1] == '--probe':
    print(json.dumps({'ready':True,'torch':'test','cuda_available':False}))
else:
    data=json.loads(Path(sys.argv[2]).read_text())
    with wave.open(data['output_path'], 'wb') as wf:
        wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(16000);wf.writeframes(b'\\x00\\x00'*1600)
    Path(sys.argv[3]).write_text(json.dumps({'ok':True}))
""")
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: script)
    assert oe.execute_probe('qwen3', sys.executable)['ready']
    out = oe.execute_generation(sample(tmp_path), sys.executable)
    assert out.exists()


def test_both_optional_engine_commands_enable_python_isolated_mode(tmp_path, monkeypatch):
    """Assert -I is used in BOTH probe and generation paths."""
    original = oe._spawn_optional_interpreter
    commands = []
    def record_spawn(cmd, **kwargs):
        commands.append(list(cmd))
        return original(cmd, **kwargs)
    monkeypatch.setattr(oe, '_spawn_optional_interpreter', record_spawn)
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: fake_runner(tmp_path))
    oe.execute_probe('qwen3', sys.executable)
    oe.execute_generation(sample(tmp_path), sys.executable)
    assert len(commands) == 2
    assert all(cmd[1] == '-I' for cmd in commands)
    assert all(cmd[3:5] == ['-X', 'faulthandler'] for cmd in commands)

def test_native_windows_access_violation_is_explained():
    assert 'access violation' in oe.native_exit_hint(3221225477).lower()
    assert '0xC0000005' in oe.native_exit_hint(-1073741819)
    assert oe.native_exit_hint(1) == ''
