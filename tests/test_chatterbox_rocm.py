"""Software protocol tests only: no Torch/model imports, CLI or GPU use."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys
import subprocess
import textwrap

import pytest

from chatterbox_studio.engine import Engine, GenerationCancelled, load_model
from chatterbox_studio.jobs import NarrationJob
from chatterbox_studio import rocm


def job(tmp_path, **changes):
    values = dict(text='First sentence. Second sentence.', model='english', device='rocm',
        language='en', voice_path='', output_path=str(tmp_path / 'output.wav'),
        rocm_python=sys.executable, rocm_overlay=str(tmp_path / 'overlay'))
    values.update(changes)
    return NarrationJob(**values)


def test_external_dispatch_precedes_host_torch_import(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name in ('torch', 'soundfile'):
            pytest.fail('External dispatch imported host ML/audio runtime')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    expected = tmp_path / 'sentinel.wav'
    received = []
    monkeypatch.setattr(rocm, 'render_external', lambda candidate, *_: received.append(candidate) or expected)
    candidate = job(tmp_path)
    assert Engine().render(candidate, lambda _: None, lambda *_: None, lambda: False) == expected
    assert received == [candidate]


def test_job_roundtrip_and_legacy_settings_remain_exact(tmp_path):
    candidate = job(tmp_path, profile='natural_narration', prepared_text='Selected passage.', render_scope='selection')
    candidate.validate()
    assert NarrationJob(**json.loads(json.dumps(candidate.as_json()))) == candidate
    cpu = replace(candidate, device='cpu')
    assert candidate.generation_kwargs() == cpu.generation_kwargs() == dict(temperature=.8, exaggeration=.5, cfg_weight=.3)
    assert candidate.render_steps() == cpu.render_steps()
    with pytest.raises(ValueError, match='1,000'):
        replace(candidate, prepared_text='x' * 1001).validate()


def test_strict_local_loader_refuses_missing_weights_before_import(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in ('torch', 'chatterbox', 'huggingface_hub'):
            pytest.fail('Missing local weights imported/downloaded a model')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    with pytest.raises(RuntimeError, match='never downloads'):
        load_model('english', 'cuda', local_only=True, model_path=tmp_path / 'absent')


@pytest.fixture
def protocol(tmp_path, monkeypatch):
    from chatterbox_studio import engine
    runner = tmp_path / 'stdlib_runner.py'
    source = Path(__file__).resolve().parents[1] / 'src'
    lock = tmp_path / 'absent-legacy-gpu.lock'
    def configure(mode='success'):
        runner.write_text(textwrap.dedent(f'''\
            import hashlib, json, os, resource, sys, time, wave
            from pathlib import Path
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            data = json.loads(Path(sys.argv[1]).read_text())
            sys.path.insert(0, data['source_root'])
            from dataclasses import asdict
            from chatterbox_studio.jobs import NarrationJob
            candidate = NarrationJob(**data['job'])
            if {mode!r} == 'hang':
                time.sleep(30)
            if {mode!r} == 'crash':
                Path(data['proof_path']).write_text(json.dumps({{'phase':'synthetic GPU evidence before failure'}}))
                raise RuntimeError('synthetic child failure')
            audio = Path(data['work']) / 'render.wav'
            with wave.open(str(audio), 'wb') as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(8000)
                stream.writeframes(b'\\x00\\x01' * 80)
            metadata = dict(candidate.as_json(), text=candidate.text, prepared_text=candidate.render_text,
                effective_settings=candidate.effective_settings(), generation_kwargs=candidate.generation_kwargs(),
                render_plan=[asdict(step) for step in candidate.render_steps()])
            audio.with_suffix('.json').write_text(json.dumps(metadata))
            runtime = dict(actual_backend='rocm', hip_version='software-fixture', actual_device='cuda:0', cpu_fallback=False,
                engine_source_sha256=hashlib.sha256((Path(data['source_root'])/'chatterbox_studio/engine.py').read_bytes()).hexdigest(),
                dsp_evidence={{name:dict(device='cuda:0',gpu_outputs=1) for name in ('_stft','_istft')}},
                module_parameters={{name:dict(gpu_parameters=1, non_gpu_parameters=0) for name in ('t3','s3gen','ve')}},
                forward_evidence={{name:dict(gpu_tensor_seen=True) for name in ('t3','s3gen')}})
            if {mode!r} == 'cpu': runtime['actual_backend']='cpu'
            if {mode!r} == 'collision': Path(candidate.output_path).with_suffix('.json').write_text('{{"foreign":true}}')
            Path(sys.argv[2]).write_text(json.dumps(dict(ok=True,runtime=runtime)))
            '''))
    configure()
    monkeypatch.setattr(rocm, 'runtime_paths', lambda _: (Path(sys.executable), tmp_path / 'overlay', runner, source))
    monkeypatch.setattr(engine, 'local_model_path', lambda _: tmp_path / 'existing-model')
    return configure, lock


def test_supervisor_preserves_exact_selection_profile_and_sidecar(tmp_path, protocol):
    _, lock = protocol
    candidate = job(tmp_path, rocm_gpu_lock=str(lock), text='Entire original manuscript.',
                    prepared_text='The selected passage.', render_scope='selection', profile='natural_narration')
    progress = []
    output = Engine().render(candidate, lambda _: None, lambda *args: progress.append(args), lambda: False)
    saved = json.loads(output.with_suffix('.json').read_text())
    assert saved['text'] == candidate.text and saved['prepared_text'] == candidate.render_text
    assert saved['render_scope'] == 'selection' and saved['voice_id'] == ''
    assert saved['device'] == saved['device_used'] == 'rocm'
    assert saved['generation_kwargs'] == candidate.generation_kwargs()
    assert saved['render_plan'] == [asdict(step) for step in candidate.render_steps()]
    assert saved['runtime']['actual_backend'] == 'rocm' and saved['runtime']['cpu_fallback'] is False
    assert progress[-1] == (1, 1)


@pytest.mark.parametrize('mode', ['cpu', 'crash'])
def test_failure_or_cpu_claim_never_publishes_audio(tmp_path, protocol, mode):
    configure, lock = protocol; configure(mode)
    with pytest.raises(RuntimeError, match='failed|prove'):
        Engine().render(job(tmp_path, rocm_gpu_lock=str(lock)), lambda _: None, lambda *_: None, lambda: False)
    assert not (tmp_path / 'output.wav').exists()
    assert list((tmp_path / '.pvs-rocm-diagnostics').glob('*/process.log'))


def test_midrun_sidecar_collision_preserves_foreign_file(tmp_path, protocol):
    configure, lock = protocol; configure('collision')
    with pytest.raises(FileExistsError):
        Engine().render(job(tmp_path, rocm_gpu_lock=str(lock)), lambda _: None, lambda *_: None, lambda: False)
    assert not (tmp_path / 'output.wav').exists()
    assert json.loads((tmp_path / 'output.json').read_text()) == {'foreign': True}


def test_cancel_never_starts_external_process(tmp_path, monkeypatch):
    monkeypatch.setattr(rocm, 'runtime_paths', lambda _: pytest.fail('Precancel inspected runtime'))
    with pytest.raises(GenerationCancelled):
        Engine().render(job(tmp_path), lambda _: None, lambda *_: None, lambda: True)


def test_deadline_stops_child_without_external_gpu_lock(tmp_path, protocol, monkeypatch):
    import fcntl
    import os
    configure, lock = protocol; configure('hang')
    monkeypatch.setattr(rocm, 'TIME_LIMIT', 5.2)
    with pytest.raises(RuntimeError, match='bound'):
        Engine().render(job(tmp_path, rocm_gpu_lock=str(lock)), lambda _: None, lambda *_: None, lambda: False)
    receipt = json.loads(next((tmp_path / '.pvs-rocm-diagnostics').glob('*/process.json')).read_text())
    with pytest.raises(ProcessLookupError): os.kill(receipt['pid'], 0)
    assert not lock.exists()
    assert not (tmp_path / 'output.wav').exists()


def test_bootstrap_disables_core_dumps_before_plain_source_child_import(tmp_path):
    source = tmp_path / 'sources' / 'chatterbox_studio'; source.mkdir(parents=True)
    (source / '__init__.py').write_text('')
    (source / 'rocm_child.py').write_text('import resource,json,ctypes\ndef run(request,response):\n'
        ' signal=ctypes.c_int();ctypes.CDLL(None).prctl(2,ctypes.byref(signal),0,0,0)\n'
        ' response.write_text(json.dumps({"core_limit":resource.getrlimit(resource.RLIMIT_CORE),"source":__file__,"parent_death_signal":signal.value}))\n')
    request, response = tmp_path / 'request.json', tmp_path / 'response.json'
    request.write_text(json.dumps(dict(source_root=str(source.parent), overlay=str(tmp_path / 'overlay'), parent_pid=os.getpid())))
    runner = Path(__file__).resolve().parents[1] / 'chatterbox_rocm_runner.py'
    result = subprocess.run([sys.executable, '-I', str(runner), str(request), str(response)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    saved = json.loads(response.read_text())
    assert saved['core_limit'] == [0, 0] and Path(saved['source']).parent == source
    import signal
    assert saved['parent_death_signal'] == signal.SIGTERM


def test_postspawn_diagnostic_failure_still_stops_child_without_lock(tmp_path, protocol, monkeypatch):
    import fcntl
    configure, lock = protocol; configure('hang')
    spawned = []
    original_popen, original_write = subprocess.Popen, Path.write_text
    def capture(*args, **kwargs):
        child = original_popen(*args, **kwargs); spawned.append(child); return child
    def fail_receipt(path, *args, **kwargs):
        if path.name == 'process.json':
            raise OSError('synthetic diagnostic disk failure')
        return original_write(path, *args, **kwargs)
    monkeypatch.setattr(rocm.subprocess, 'Popen', capture)
    monkeypatch.setattr(Path, 'write_text', fail_receipt)
    with pytest.raises(OSError, match='diagnostic disk failure'):
        Engine().render(job(tmp_path, rocm_gpu_lock=str(lock)), lambda _: None, lambda *_: None, lambda: False)
    assert len(spawned) == 1 and spawned[0].poll() is not None
    assert not lock.exists()
    assert not (tmp_path / 'output.wav').exists()


@pytest.mark.parametrize('free_gib', [0, 1, 2, 6, 16])
def test_vram_capacity_is_reported_without_artificial_budget(free_gib):
    from chatterbox_studio.rocm_child import vram_budget
    gib = 1024**3
    assert vram_budget(free_gib * gib, 16 * gib) == 16 * gib


def test_gpu_activity_attests_hardware_without_busy_threshold(tmp_path):
    from chatterbox_studio.rocm_child import gpu_activity
    root = tmp_path / 'drm'; card = root / 'card1' / 'device'; card.mkdir(parents=True)
    for name, value in {'vendor': '0x1002', 'device': '0x7480', 'gpu_busy_percent': '17'}.items():
        (card / name).write_text(value)
    assert gpu_activity(root)['busy_percent'] == 17
    (card / 'gpu_busy_percent').write_text('100')
    assert gpu_activity(root)['busy_percent'] == 100
    (card / 'vendor').write_text('0x8086')
    with pytest.raises(RuntimeError, match='AMD GPU'):
        gpu_activity(root)


def test_rocm_runtime_paths_accept_absent_legacy_lock(tmp_path):
    overlay = tmp_path / 'overlay' / 'chatterbox'; overlay.mkdir(parents=True)
    (overlay / '__init__.py').touch()
    candidate = job(tmp_path, rocm_gpu_lock=str(tmp_path / 'absent.lock'))
    assert rocm.runtime_paths(candidate)[0] == Path(sys.executable).absolute()
    assert not Path(candidate.rocm_gpu_lock).exists()


def test_rocm_supervisor_has_no_ram_or_thread_quota(tmp_path, protocol, monkeypatch):
    _, lock = protocol
    captured = []
    original = subprocess.Popen
    def spawn(*args, **kwargs):
        captured.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(rocm.subprocess, 'Popen', spawn)
    monkeypatch.setattr(rocm, 'group_rss', lambda _: 64 * 1024**3)
    for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        monkeypatch.setenv(key, '23')
    output = Engine().render(job(tmp_path, rocm_gpu_lock=str(lock)), lambda _: None, lambda *_: None, lambda: False)
    assert output.is_file() and rocm.RAM_LIMIT is None
    assert 'pass_fds' not in captured[0]
    for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        assert captured[0]['env'][key] == '23'
    assert not lock.exists()


def test_restored_sources_do_not_impose_torch_thread_or_allocator_caps():
    import ast
    from chatterbox_studio import rocm_child, speech_check
    for module in (rocm_child, speech_check):
        tree = ast.parse(Path(module.__file__).read_text())
        calls = [node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        assert not {'set_num_threads', 'set_num_interop_threads', 'set_per_process_memory_fraction'} & set(calls)


@pytest.mark.parametrize('fail', [False, True])
def test_reference_fft_glue_records_live_counters_after_prepare(monkeypatch, fail):
    from copy import deepcopy
    from types import SimpleNamespace
    from chatterbox_studio import rocm_reference_fft
    from chatterbox_studio.rocm_child import attach_reference_fft
    state = {'method': 'thread_local_direct_reference_dft', 'counters': {'prepare_completed': 0}}
    records = []
    def prepare(path, exaggeration=.5):
        state['counters']['stft_replaced'] = 2
        if fail:
            state['counters']['prepare_failures'] = 1
            raise ValueError('synthetic conditioning failure')
        state['counters']['prepare_completed'] = 1
        return (path, exaggeration)
    model = SimpleNamespace(prepare_conditionals=prepare)
    monkeypatch.setattr(rocm_reference_fft, 'install_rocm_reference_fft_compat', lambda candidate: state)
    installed = attach_reference_fft(model, lambda live: records.append(deepcopy(live)))
    assert installed is state and not records
    if fail:
        with pytest.raises(ValueError, match='conditioning failure'):
            model.prepare_conditionals('/private/reference.wav', exaggeration=.75)
        assert records[-1]['counters']['prepare_failures'] == 1
    else:
        assert model.prepare_conditionals('/private/reference.wav', exaggeration=.75) == ('/private/reference.wav', .75)
        assert records[-1]['counters']['prepare_completed'] == 1
    assert records[-1]['counters']['stft_replaced'] == 2


def test_bootstrap_parent_identity_mismatch_stops_before_model_import(tmp_path):
    request, response = tmp_path / 'request.json', tmp_path / 'response.json'
    request.write_text(json.dumps(dict(source_root='/not/imported', overlay='/not/imported', parent_pid=os.getpid()+1)))
    runner = Path(__file__).resolve().parents[1] / 'chatterbox_rocm_runner.py'
    result = subprocess.run([sys.executable, '-I', str(runner), str(request), str(response)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode != 0 and 'parent exited' in result.stderr
    assert not response.exists()
