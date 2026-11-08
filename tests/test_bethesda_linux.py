"""Wine/native command contracts and failure cleanup; no Bethesda tools bundled."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import os
import struct
import sys
import threading
import time

import pytest
from chatterbox_studio import bethesda_export as be
from test_bethesda_validation import configured_export

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Linux Wine contract suite; native Windows covered by shared export tests")


@pytest.fixture
def wine_config(configured_export, tmp_path):
    config, state, calls = configured_export
    runner = tmp_path / 'wine runner'
    runner.write_text('#!/bin/sh\n')
    runner.chmod(0o755)
    prefix = tmp_path / 'dedicated prefix'
    (prefix / 'dosdevices').mkdir(parents=True)
    (prefix / 'system.reg').write_text('test prefix')
    return replace(config, tool_runner='wine', wine_path=str(runner), wine_prefix=str(prefix)), state


def test_wine_maps_only_file_arguments_preserves_transcript(wine_config, monkeypatch):
    config, _ = wine_config
    seen = []
    def call(args, action, **kwargs):
        seen.append((args, action, kwargs))
        return 'Z:' + args[-1].replace('/', '\\') if action == 'Wine path conversion' else ''
    monkeypatch.setattr(be, '_call', call)
    before = dict(os.environ)
    runner = be._ToolRunner(config, lambda: False)
    source = runner.path(config.source_audio)
    runner.call([runner.path(config.facefx_path), 'Fallout4', 'USEnglish',
                 runner.path(config.fonix_path), source, r'Z:\out file.lip', config.text],
                'test', windows=True)
    args, _, kw = seen[-1]
    assert args[0] == config.wine_path
    assert args[-1] == config.text  # Quotes/directives remain one literal argument.
    assert args[1].startswith('Z:\\') and ' ' in source
    assert kw['env']['WINEPREFIX'] == config.wine_prefix
    assert kw['timeout'] == 240
    assert dict(os.environ) == before


@pytest.mark.parametrize('value', ['', 'not a Windows path', 'Z:\\okay\nother', 'Z:\\okay\rbroken'])
def test_wine_rejects_invalid_mapping(wine_config, monkeypatch, value):
    config, _ = wine_config
    monkeypatch.setattr(be, '_call', lambda *args, **kwargs: value)
    with pytest.raises(be.BethesdaExportError, match='map a file path'):
        be._ToolRunner(config, lambda: False).path(config.source_audio)


def test_wine_requires_initialized_explicit_prefix(wine_config, tmp_path):
    config, _ = wine_config
    for prefix in ('', 'relative', str(tmp_path / 'missing')):
        with pytest.raises(be.BethesdaExportError, match='prefix'):
            be._validate_tools(replace(config, wine_prefix=prefix))
    be._validate_tools(config)


def test_rejects_proton_launcher(wine_config, tmp_path):
    config, _ = wine_config
    launcher = tmp_path / 'proton'
    launcher.write_text('#!/bin/sh\n')
    launcher.chmod(0o755)
    with pytest.raises(be.BethesdaExportError, match='not the proton launcher'):
        be._validate_tools(replace(config, wine_path=str(launcher)))


def test_windows_native_contract_unchanged(configured_export, monkeypatch):
    config, _, _ = configured_export
    native_os = SimpleNamespace(name='nt', environ=os.environ)
    monkeypatch.setattr(be, 'os', native_os)
    be._validate_tools(config)
    seen = []
    monkeypatch.setattr(be, '_call', lambda args, action, **kw: seen.append((args, kw)))
    runner = be._ToolRunner(config, lambda: False)
    command = [config.facefx_path, 'Fallout4', 'USEnglish', config.fonix_path,
               config.source_audio, 'voice.lip', 'Hi "friend".']
    runner.call(command, 'FaceFX', windows=True)
    assert seen[0][0] == command
    assert seen[0][1]['env'] is None
    with pytest.raises(be.BethesdaExportError, match='native tools on Windows'):
        be._validate_tools(replace(config, tool_runner='wine'))


def test_official_backend_is_fo4_only(configured_export):
    config, _, _ = configured_export
    for game in ('skyrim', 'skyrimse'):
        with pytest.raises(be.BethesdaExportError, match='Fallout 4 only'):
            be._validate_tools(replace(config, lip_backend='lipgenerator', game=game))


def test_native_linux_rejects_windows_exe(configured_export):
    config, _, _ = configured_export
    Path(config.facefx_path).write_bytes(b'MZ\0\0')
    with pytest.raises(be.BethesdaExportError, match='Wine runner'):
        be._validate_tools(config)


def test_official_tool_is_staged_never_modifies_installation(configured_export, monkeypatch):
    config, state, _ = configured_export
    config = replace(config, lip_backend='lipgenerator')
    previous = be._call
    official_calls = []
    def call(args, action, **kwargs):
        if action != 'Official Fallout 4 LIP generation':
            return previous(args, action, **kwargs)
        exe = Path(args[0]); cwd = kwargs['cwd']
        assert exe.parent == cwd and exe.name == 'LipGenerator.exe'
        assert exe.read_bytes() == Path(config.facefx_path).read_bytes()
        assert (cwd / 'FonixData.cdf').read_bytes() == Path(config.fonix_path).read_bytes()
        assert args[2] == 'Hello "friend".'
        assert args[3].startswith('-OutputFileName:')
        output = Path(args[3].split(':', 1)[1])
        assert not output.exists()
        output.write_bytes(struct.pack('<III', 1, 42, 13) + b'animation')
        (cwd / 'tmp16khz.wav').write_bytes(b'tool intermediate')
        official_calls.append(cwd)
    monkeypatch.setattr(be, '_call', call)
    out = be.export_dialogue(config)
    assert be.read_fuz(out)[1].startswith(struct.pack('<I', 1))
    assert official_calls and not official_calls[0].exists()
    assert not (Path(config.facefx_path).parent / 'tmp16khz.wav').exists()


@pytest.mark.parametrize('payload', [None, b'', b'corrupt not a LIP'])
def test_official_zero_exit_without_valid_new_output_fails(configured_export, monkeypatch, payload):
    config, _, _ = configured_export
    config = replace(config, lip_backend='lipgenerator', overwrite_existing=True)
    target = be.expected_fuz_path(config)
    target.parent.mkdir(parents=True)
    target.write_bytes(b'preserved')
    previous = be._call
    def call(args, action, **kwargs):
        if action == 'Official Fallout 4 LIP generation':
            if payload is not None:
                Path(args[3].split(':', 1)[1]).write_bytes(payload)
        else:
            return previous(args, action, **kwargs)
    monkeypatch.setattr(be, '_call', call)
    with pytest.raises(be.BethesdaExportError):
        be.export_dialogue(config)
    assert target.read_bytes() == b'preserved'
    assert not list(target.parent.glob('*.pvs-partial'))


def test_cancelled_before_start_creates_nothing(configured_export):
    config, _, calls = configured_export
    with pytest.raises(be.BethesdaExportCancelled):
        be.export_dialogue(config, cancelled=lambda: True)
    assert not calls and not be.expected_fuz_path(config).exists()


def test_cancel_before_publication_preserves_target(configured_export, monkeypatch):
    config, _, _ = configured_export
    config = replace(config, overwrite_existing=True)
    target = be.expected_fuz_path(config)
    target.parent.mkdir(parents=True)
    target.write_bytes(b'preserved')
    cancel = threading.Event()
    copy = be.shutil.copy2
    def copied(source, dest, **kwargs):
        result = copy(source, dest, **kwargs)
        if str(dest).endswith('.pvs-partial'):
            cancel.set()
        return result
    monkeypatch.setattr(be.shutil, 'copy2', copied)
    with pytest.raises(be.BethesdaExportCancelled):
        be.export_dialogue(config, cancelled=cancel.is_set)
    assert target.read_bytes() == b'preserved'
    assert not list(target.parent.glob('*.pvs-partial'))


@pytest.mark.parametrize('mode', ['timeout', 'cancel'])
def test_active_tool_is_stopped(mode, tmp_path):
    pidfile = tmp_path / 'pid'
    args = [sys.executable, '-c',
            'import os,time,pathlib; pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(30)' % str(pidfile)]
    cancel = threading.Event()
    timer = threading.Timer(0.3, cancel.set)
    if mode == 'cancel': timer.start()
    started = time.monotonic()
    try:
        error = be.BethesdaExportCancelled if mode == 'cancel' else be.BethesdaExportError
        with pytest.raises(error, match='cancelled|timed out'):
            be._call(args, 'sleeping tool', timeout=1, cancelled=cancel.is_set)
    finally:
        timer.cancel()
    assert time.monotonic() - started < 5
    if pidfile.exists():
        with pytest.raises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)


def test_symlink_destination_escape_rejected(configured_export, tmp_path):
    config, _, calls = configured_export
    other = tmp_path / 'outside'
    other.mkdir()
    (Path(config.output_root) / 'Sound').symlink_to(other, target_is_directory=True)
    with pytest.raises(be.BethesdaExportError, match='link outside'):
        be.export_dialogue(config)
    assert not calls and not list(other.iterdir())


def test_diagnostics_never_launch_tools(configured_export, monkeypatch):
    config, _, _ = configured_export
    monkeypatch.setattr(be, '_call', lambda *a, **kw: pytest.fail('diagnostics launched software'))
    messages = be.diagnose_tools(replace(config, source_audio='', text='', plugin_name='', output_root=''))
    assert any('valid' in message for message in messages)
    assert any('do not prove' in message for message in messages)


def test_runner_does_not_inherit_ck_ipc_or_frozen_library_path(wine_config, monkeypatch):
    config, _ = wine_config
    monkeypatch.setenv('Ckpid', '1234')
    monkeypatch.setenv('LD_LIBRARY_PATH', '/bundled/qt')
    monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', '/system/optional')
    monkeypatch.setenv('WINEARCH', 'win32')
    runner = be._ToolRunner(config, lambda: False)
    assert not any(key.casefold() == 'ckpid' for key in runner.env)
    assert runner.env['LD_LIBRARY_PATH'] == '/system/optional'
    assert 'WINEARCH' not in runner.env
    assert os.environ['Ckpid'] == '1234'


def test_cancellation_kills_child_that_ignores_sigterm(tmp_path):
    pidfile = tmp_path / 'child.pid'
    child = ('import os,signal,time,pathlib; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
             'pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(30)' % str(pidfile))
    parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable, "-c", %r]); time.sleep(30)' % child
    def cancel():
        return pidfile.exists()
    with pytest.raises(be.BethesdaExportCancelled):
        be._call([sys.executable, '-c', parent], 'parent and child', cancelled=cancel)
    pid = int(pidfile.read_text())
    # An orphaned zombie can await the system reaper, but cannot keep running or
    # writing output. /proc makes that distinction without killing another PID.
    deadline = time.monotonic() + 2
    state = Path('/proc') / str(pid) / 'stat'
    while state.exists() and time.monotonic() < deadline:
        if state.read_text().split(') ', 1)[1].startswith('Z '):
            break
        time.sleep(.02)
    assert not state.exists() or state.read_text().split(') ', 1)[1].startswith('Z ')
