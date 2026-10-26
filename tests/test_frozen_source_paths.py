"""Exercise frozen-source comparisons with native paths and a tiny fake archive."""
import importlib.util
import marshal
from pathlib import Path
import sys
from types import ModuleType

import pytest


@pytest.mark.parametrize('damage', [None, 'missing_rocm', 'changed_plugin'])
def test_native_payload_paths_keep_required_checks_and_detect_damage(tmp_path, monkeypatch, damage):
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'verify_frozen_source.py'
    spec = importlib.util.spec_from_file_location('frozen_source_checker', script)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    monkeypatch.setattr(checker, 'ROOT', tmp_path)

    internal = tmp_path / 'dist' / '_internal'
    modules = {}

    def write(path, content='value = 1\n'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    names = ('engine', 'speech_check', 'tokenizer_assets', 'optional_engines',
             'native_vulkan', 'text_preparation', 'engine_lab', 'rocm', 'jobs',
             'rocm_child', 'rocm_fft', 'rocm_reference_fft')
    for package, relative_names in [('chatterbox_studio', names), ('plagued_ai', ('__init__',))]:
        for name in relative_names:
            relative = Path(package) / (name + '.py')
            write(tmp_path / 'src' / relative)
            write(internal / 'rocm_source' / relative)
            module_name = package if name == '__init__' else package + '.' + name
            modules[module_name] = compile('value = 1\n', 'frozen.py', 'exec')
    write(tmp_path / 'plugins' / 'writer_core' / 'runtime.py')
    modules['writer_core.runtime'] = compile('value = 1\n', 'frozen.py', 'exec')
    for name in ('optional_engine_runner.py', 'chatterbox_rocm_runner.py'):
        write(tmp_path / name)
        write(internal / name)
    write(tmp_path / 'launcher.py')
    plugin = Path('promotional-writer') / 'nested' / 'plugin.json'
    write(tmp_path / 'plugins' / plugin, '{}')
    write(internal / 'plugins' / plugin, '{}')

    readers = ModuleType('PyInstaller.archive.readers')

    class FakeArchive:
        def __init__(self, _path):
            self.toc = modules

        def extract(self, name):
            if name == 'PYZ.pyz':
                return b'fake archive'
            if name == 'launcher':
                return marshal.dumps(compile('value = 1\n', 'frozen.py', 'exec'))
            return modules[name]

    readers.CArchiveReader = readers.ZlibArchiveReader = FakeArchive
    monkeypatch.setitem(sys.modules, 'PyInstaller.archive.readers', readers)
    if damage == 'missing_rocm':
        (internal / 'rocm_source' / 'chatterbox_studio' / 'rocm.py').unlink()
    elif damage == 'changed_plugin':
        write(internal / 'plugins' / plugin, '{"changed": true}')

    report = checker.verify(tmp_path / 'dist' / 'app.exe')
    assert report['status'] == ('passed' if damage is None else 'failed')
    assert all('\\' not in key for key in report['checks'])
    assert report['checks']['rocm_source/chatterbox_studio/rocm.py'] is (damage != 'missing_rocm')
    assert report['checks']['plugins/promotional-writer/nested/plugin.json'] is (damage != 'changed_plugin')
