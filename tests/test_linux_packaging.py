"""Portable archives must preserve executable bits/links and exclude weights."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tarfile
import sys
from types import ModuleType, SimpleNamespace

import pytest
from chatterbox_studio import optional_engines

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_linux_test', ROOT / 'scripts/package_linux.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def test_frozen_librosa_uses_source_files_for_numba_cache_locators(monkeypatch):
    build_main = pytest.importorskip('PyInstaller.building.build_main')
    hooks = ModuleType('PyInstaller.utils.hooks')
    hooks.collect_all = lambda *args, **kwargs: ([], [], [])
    hooks.collect_submodules = lambda *args, **kwargs: []
    hooks.copy_metadata = lambda *args, **kwargs: []
    monkeypatch.setitem(sys.modules, hooks.__name__, hooks)
    monkeypatch.setenv('PVS_SLIM_BUILD', '1')
    captured = {}

    def analysis(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

    namespace = dict(SPECPATH=str(ROOT), Analysis=analysis,
                     PYZ=lambda *args, **kwargs: None,
                     EXE=lambda *args, **kwargs: None,
                     COLLECT=lambda *args, **kwargs: None)
    path = ROOT / 'ChatterboxStudio.spec'
    exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), namespace)
    modes = captured['module_collection_mode']
    resolve = build_main._get_module_collection_mode
    # Use PyInstaller's own inheritance logic: affected lazy-loaded children
    # must load from source; unrelated ML modules retain normal PYZ packaging.
    for name in ('librosa', 'librosa.core', 'librosa.core.notation'):
        assert resolve(modes, name, captured['noarchive']) == build_main._ModuleCollectionMode.PY
    for name in ('chatterbox', 'numba', 'torch'):
        assert resolve(modes, name, captured['noarchive']) == build_main._ModuleCollectionMode.PYZ


def test_linux_archive_and_checksum(tmp_path):
    app = tmp_path / 'App with spaces'
    app.mkdir()
    executable = app / 'PlaguesVoiceStudio030Experimental'
    executable.write_bytes(b'\x7fELFtest-fixture')
    executable.chmod(0o755)
    if os.name != 'nt':
        (app / 'library-link').symlink_to(executable.name)
    output = tmp_path / 'output'
    packager.package(app, output)
    archive, = output.glob('*.tar.gz')
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert (output / 'SHA256SUMS.txt').read_text() == f'{expected}  {archive.name}\n'
    with tarfile.open(archive) as bundle:
        assert bundle.getmember(f'{app.name}/BUILD-INFO.json').isfile()
        if os.name != 'nt':
            assert bundle.getmember(f'{app.name}/start-voice-studio.sh').mode & 0o111
            assert bundle.getmember(f'{app.name}/library-link').issym()
            assert bundle.getmember(f'{app.name}/{executable.name}').mode & 0o111


def test_linux_package_rejects_windows_binary_and_weights(tmp_path):
    app = tmp_path / 'app'
    app.mkdir()
    executable = app / 'PlaguesVoiceStudio030Experimental'
    executable.write_bytes(b'MZ-windows-fixture')
    with pytest.raises(ValueError, match='ELF'):
        packager.package(app, tmp_path / 'output')
    executable.write_bytes(b'\x7fELFtest-fixture')
    (app / 'accidental.safetensors').write_bytes(b'model-fixture')
    with pytest.raises(ValueError, match='weights'):
        packager.package(app, tmp_path / 'output')


@pytest.mark.parametrize('original', [None, '/usr/local/lib'])
def test_frozen_linux_engine_does_not_inherit_host_libraries(monkeypatch, original):
    monkeypatch.setattr(optional_engines.sys, 'platform', 'linux')
    monkeypatch.setattr(optional_engines.sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/tmp/host/_internal')
    if original is None:
        monkeypatch.delenv('LD_LIBRARY_PATH_ORIG', raising=False)
    else:
        monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', original)
    env = optional_engines._isolated_engine_environment()
    assert env.get('LD_LIBRARY_PATH') == original
    assert 'LD_LIBRARY_PATH_ORIG' not in env
