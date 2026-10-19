"""Alpha4 tests use a miniature Python runner and no AI libraries."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import wave
import subprocess

import pytest
from chatterbox_studio import optional_engines as oe


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows venv/child process cancellation')
def test_cancellation_stops_owned_descendants_and_releases_their_files(tmp_path):
    held = tmp_path / 'child-held.log'
    script = tmp_path / 'owned_parent.py'
    child = "import time; f=open(" + repr(str(held)) + ", 'w'); f.write('ready'); f.flush(); time.sleep(20)"
    script.write_text('import subprocess,sys,time\n'
                     f'subprocess.Popen([sys.executable,"-I","-c",{child!r}])\n'
                     'time.sleep(20)\n', encoding='utf-8')
    proc = oe._spawn_optional_interpreter([sys.executable, '-I', str(script)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while not held.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert held.exists(), 'Owned test child did not start'
        oe._stop_process(proc)
        assert proc.poll() is not None
        # Windows refuses removal while the surviving child holds this handle.
        held.unlink()
    finally:
        if proc.poll() is None:
            oe._stop_process(proc)


def runner(tmp_path):
    f = tmp_path / 'mini_runner.py'
    f.write_text("import sys, json, time, wave\nfrom pathlib import Path\nprint('[PVS] Loading model', flush=True)\ntime.sleep(.35)\nprint('[PVS] Generating speech', flush=True)\nif sys.argv[1] == '--probe':\n    print(json.dumps({'ready': True,'torch': 'stub','cuda_available': False}))\nelse:\n    data = json.loads(Path(sys.argv[2]).read_text())\n    time.sleep(.75)\n    with wave.open(data['output_path'], 'wb') as wf:\n        wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(16000)\n        wf.writeframes(b'\\x00\\x00' * 512)\n    Path(sys.argv[3]).write_text(json.dumps({'ok': True}))\n", encoding='utf-8')
    return f


def req(tmp_path):
    audio = tmp_path / 'voice.wav'
    audio.write_bytes(b'WAVE')
    return dict(engine='qwen3', model=oe.ENGINES['qwen3']['models'][0],
                text='howdy pardner', language='English', voice_path=str(audio),
                output_path=str(tmp_path/'out.wav'), device='cpu')


def test_live_generation_logs_and_saved_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner(tmp_path))
    lines = []
    path = oe.execute_generation(req(tmp_path), sys.executable, log=lines.append,
                                 diagnostic_dir=tmp_path/'logs')
    assert path.is_file()
    assert any('Loading model' in item for item in lines)
    assert any('Generating speech' in item for item in lines)
    assert any('Diagnostic file:' in item for item in lines)
    diag = json.loads(path.with_suffix('.json').read_text())
    logfile = Path(diag['diagnostic_log'])
    assert logfile.exists() and '[PVS] Loading model' in logfile.read_text()


def test_probe_live_output_and_saved_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner(tmp_path))
    lines = []
    result = oe.execute_probe('qwen3', sys.executable, log=lines.append,
                              diagnostic_dir=tmp_path/'logs')
    assert result['ready']
    assert any('Checking' in line for line in lines)
    assert len(list((tmp_path/'logs').glob('qwen3-probe-*.log'))) == 1


def test_cancel_during_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner(tmp_path))
    flag = threading.Event()
    t = threading.Timer(.2, flag.set)
    t.start()
    try:
        with pytest.raises(oe.EngineCancelled):
            oe.execute_generation(req(tmp_path), sys.executable, cancelled=flag,
                                  diagnostic_dir=tmp_path/'logs')
    finally:
        t.join()
    assert not (tmp_path/'out.wav').exists()
    assert list((tmp_path/'logs').glob('*.log'))


def test_cancel_during_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner(tmp_path))
    flag = threading.Event()
    t = threading.Timer(.1, flag.set)
    t.start()
    try:
        with pytest.raises(oe.EngineCancelled):
            oe.execute_probe('qwen3', sys.executable, cancelled=flag)
    finally:
        t.join()


def test_engine_commands_use_isolated_unbuffered_python(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner(tmp_path))
    before = oe._spawn_optional_interpreter
    captured = []
    def spawn(cmd, **kwargs):
        captured.append(cmd)
        return before(cmd, **kwargs)
    monkeypatch.setattr(oe, '_spawn_optional_interpreter', spawn)
    oe.execute_probe('qwen3', sys.executable)
    oe.execute_generation(req(tmp_path), sys.executable)
    assert len(captured) == 2
    assert all(cmd[1:3] == ['-I','-u'] for cmd in captured)


def test_windows_console_is_suppressed(monkeypatch):
    seen = []
    monkeypatch.setattr(oe.sys, 'platform', 'win32')
    monkeypatch.setattr(oe.subprocess, 'CREATE_NO_WINDOW', 0x08000000, raising=False)
    class FakeProcess:
        pass
    def fake_popen(*args, **kwargs):
        seen.append(kwargs)
        return FakeProcess()
    monkeypatch.setattr(oe.subprocess, 'Popen', fake_popen)
    oe._spawn_optional_interpreter(['python.exe', '-I', '-u', 'runner.py'])
    assert seen[0]['creationflags'] & 0x08000000
    assert 'PYTHONPATH' not in seen[0]['env']


def test_alpha4_gui_wiring_no_chatterbox_modifications():
    root = Path(__file__).resolve().parents[1]
    ui = (root/'src/chatterbox_studio/engine_lab.py').read_text()
    assert "QTimer" in ui and "open_diagnostic_logs" in ui
    assert "self.diagnostics.setReadOnly(True)" in ui
    assert "self.worker.message.connect(self._diagnostic_message)" in ui
