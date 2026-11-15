import json
import os
import sys
import time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtCore import QCoreApplication,QProcess,QProcessEnvironment
from PyQt6.QtWidgets import QApplication
import pytest
from chatterbox_studio.warm_client import WarmClient

SCRIPT='''import sys,json,time,os
from pathlib import Path
for line in sys.stdin:
 r=json.loads(line)
 if r.get('progress'):
  print('[PVS] Loading IndexTTS model and checkpoints',file=sys.stderr,flush=True)
 if r.get('sleep'):time.sleep(20)
 if r.get('crash'):sys.exit(5)
 if r.get('malformed'):
  print('bad protocol',flush=True);continue
 Path(r['output_path']).write_bytes(b'fake audio')
 print(json.dumps(dict(id=r['id'],ok=True,output_path=r['output_path'],pid=os.getpid(),seconds=0,warm=False)),flush=True)
'''


def until(predicate,seconds=4):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        QCoreApplication.processEvents()
        if predicate():return
        time.sleep(.005)
    assert predicate()


@pytest.fixture
def worker(tmp_path):
    app=QApplication.instance() or QApplication([])
    client=WarmClient(idle_ms=10000)
    script=tmp_path/'fake.py';script.write_text(SCRIPT)
    req=dict(engine='chatterbox',device='cpu',output_path=str(tmp_path/'out.wav'))
    yield client,script,req
    assert client.stop(wait=True)


def submit(w,**extra):
    c,script,req=w
    c.submit(sys.executable,dict(req,**extra),QProcessEnvironment.systemEnvironment(),script=script)


def test_reuse_then_configuration_change_restarts(worker):
    c,_,_=worker;out=[];c.completed.connect(out.append)
    submit(worker);until(lambda:len(out)==1)
    submit(worker);until(lambda:len(out)==2)
    assert out[0]['pid']==out[1]['pid']
    submit(worker,weights='different');until(lambda:len(out)==3)
    assert out[2]['pid']!=out[1]['pid']


def test_cancel_during_inference_then_restart(worker):
    c,_,_=worker;out=[];c.completed.connect(out.append)
    submit(worker,sleep=True);until(lambda:c.process.state()==QProcess.ProcessState.Running)
    assert c.stop(wait=True)
    assert not c.busy and not out
    submit(worker);until(lambda:len(out)==1)


def test_idle_releases_process(worker):
    c,_,_=worker;c.idle.setInterval(25)
    submit(worker);until(lambda:not c.busy)
    until(lambda:c.process.state()==QProcess.ProcessState.NotRunning)


@pytest.mark.parametrize('flag',['crash','malformed'])
def test_failure_releases_worker(worker,flag):
    c,_,_=worker;errors=[];c.failed.connect(errors.append)
    submit(worker,**{flag:True});until(lambda:bool(errors))
    until(lambda:c.process.state()==QProcess.ProcessState.NotRunning)
    assert not c.busy


def test_stale_result_cannot_complete_new_request(worker):
    c,_,req=worker;out=[];c.completed.connect(out.append)
    submit(worker,sleep=True);until(lambda:c.process.state()==QProcess.ProcessState.Running)
    c.stdout.extend((json.dumps(dict(id='old',ok=True,output_path=req['output_path']))+'\n').encode())
    c._read()
    assert c.busy and not out


@pytest.mark.parametrize('metadata', [{}, {'seconds': -1, 'warm': False},
    {'seconds': float('nan'), 'warm': False}, {'seconds': 0, 'warm': 'yes'}])
def test_invalid_result_metadata_fails_without_playback(worker, metadata):
    c, _, req = worker
    errors = []; completed = []
    c.failed.connect(errors.append); c.completed.connect(completed.append)
    submit(worker, sleep=True)
    until(lambda: c.process.state() == QProcess.ProcessState.Running)
    result = dict(id=c.request['id'], ok=True, output_path=req['output_path'], **metadata)
    c.stdout.extend((json.dumps(result) + '\n').encode())
    c._read()
    until(lambda: c.process.state() == QProcess.ProcessState.NotRunning)
    assert errors and 'invalid conversion' in errors[0]
    assert not completed


@pytest.mark.parametrize('engine',['index25','chatterbox'])
def test_staged_launchers_preserve_protocol_and_cancellation(worker,engine):
    directory=os.environ.get('PVS_TEST_LAUNCHER_DIR')
    if not directory:
        pytest.skip('Optional model-free local launcher qualification')
    c,script,req=worker;results=[];c.completed.connect(results.append)
    launcher=str(Path(directory)/('python-'+engine))
    env=QProcessEnvironment.systemEnvironment()
    for count in (1,2):
        c.submit(launcher,req,env,script=script)
        until(lambda:len(results)==count)
    assert results[0]['pid']==results[1]['pid']
    c.submit(launcher,dict(req,sleep=True),env,script=script)
    assert c.stop(wait=True)
    assert not c.busy


def test_model_stage_progress_is_visible_without_completion(worker):
    c, _, _ = worker
    stages = []; results = []
    c.progress.connect(stages.append); c.completed.connect(results.append)
    submit(worker, progress=True, sleep=True)
    until(lambda: bool(stages))
    assert stages == ['Loading IndexTTS model and checkpoints']
    assert not results and c.busy
    assert c.stop(wait=True)


def test_recording_and_asr_hold_idle_model_then_resume_release(worker):
    c, _, _ = worker
    c.idle.setInterval(30)
    submit(worker)
    until(lambda:not c.busy)
    pid=c.process.processId()
    c.hold_idle()
    end=time.monotonic()+.12
    while time.monotonic()<end:
        QCoreApplication.processEvents();time.sleep(.005)
    assert c.process.state()==QProcess.ProcessState.Running
    assert c.process.processId()==pid
    c.resume_idle()
    until(lambda:c.process.state()==QProcess.ProcessState.NotRunning)


def test_gpu_worker_is_not_killed_by_app_temperature_policy(worker, tmp_path):
    from test_gpu_safety import sensors
    c, script, req = worker
    errors = []
    c.failed.connect(errors.append)
    root = sensors(tmp_path / 'gpu', junction=99)
    env = QProcessEnvironment.systemEnvironment()
    env.insert('PVS_GPU_SYSFS', str(root))
    c.submit(sys.executable, dict(req, device='cuda', sleep=True), env, script=script)
    until(lambda: c.process.state() == QProcess.ProcessState.Running)
    end = time.monotonic() + .3
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(.005)
    assert c.process.state() == QProcess.ProcessState.Running
    assert c.busy and not errors
    assert not hasattr(c, 'gpu_monitor')
    assert c.stop(wait=True)


def test_warm_gpu_request_has_no_assistant_temperature_refusal(worker, tmp_path):
    from test_gpu_safety import sensors
    c, script, req = worker
    out = []
    c.completed.connect(out.append)
    root = sensors(tmp_path / 'gpu')
    env = QProcessEnvironment.systemEnvironment()
    env.insert('PVS_GPU_SYSFS', str(root))
    request = dict(req, device='cuda')
    c.submit(sys.executable, request, env, script=script)
    until(lambda: len(out) == 1)
    sensors(root, junction=99)
    c.submit(sys.executable, request, env, script=script)
    until(lambda: len(out) == 2)
    assert out[0]['pid'] == out[1]['pid']


def test_gpu_and_cpu_requests_do_not_require_temperature_telemetry(worker, tmp_path):
    c, script, req = worker
    out = []
    c.completed.connect(out.append)
    env = QProcessEnvironment.systemEnvironment()
    env.insert('PVS_GPU_SYSFS', str(tmp_path / 'absent'))
    for count, device in enumerate(('cuda', 'cpu'), 1):
        c.submit(sys.executable, dict(req, device=device), env, script=script)
        until(lambda: len(out) == count)
    assert not c.busy
