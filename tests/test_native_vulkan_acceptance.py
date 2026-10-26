"""Independent native-route acceptance using only stdlib process fixtures.

No real native CLI, checkpoint, model import, GPU operation or active application
is used. Stub placement messages test protocol enforcement, not GPU execution.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
from threading import Event, Thread
import time
from types import SimpleNamespace
import wave

import pytest

from chatterbox_studio import optional_engines as oe


ROOT = Path(__file__).resolve().parents[1]
# Synthetic protocol evidence, never an observation of the host GPU.
AMD_DEVICE_ZERO = 'ggml_vulkan: 0 = AMD Radeon RX 7600 XT (RADV NAVI33)'


@pytest.fixture(autouse=True)
def private_homes(tmp_path, monkeypatch):
    # Even runtime discovery checks stay within this private Linux fixture.
    for name, folder in [('PLAGUED_AI_HOME', 'shared'), ('HF_HOME', 'hf'),
                         ('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'),
                         ('XDG_CACHE_HOME', 'cache'), ('HOME', 'home'),
                         ('PLAGUES_VOICE_STUDIO_030_HOME', 'studio'),
                         ('PLAGUES_VOICE_STUDIO_HOME', 'studio')]:
        monkeypatch.setenv(name, str(tmp_path / folder))


def pcm(path, seconds=0.1, sample=1):
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(sample.to_bytes(2, 'little', signed=True) * int(24000 * seconds))


@pytest.fixture
def native_case(tmp_path):
    """A private executable, metadata-only fake weights, reference and lock."""
    from chatterbox_studio import native_vulkan as nv

    if sys.platform != 'linux':
        pytest.skip('First native Vulkan route uses Linux process groups and flock')
    folder = tmp_path / 'native model with spaces'
    folder.mkdir()
    (folder / 'config.json').write_text(json.dumps({'tts_model_type': 'base', 'tts_model_size': '0b6'}))
    for relative in ('model.safetensors', 'tokenizer_config.json', 'vocab.json', 'merges.txt',
                     'preprocessor_config.json', 'generation_config.json',
                     'speech_tokenizer/config.json', 'speech_tokenizer/model.safetensors',
                     'speech_tokenizer/preprocessor_config.json'):
        path = folder / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text('{}')
    capture = tmp_path / 'stub-request.json'
    executable = tmp_path / 'native cli ; literal $(name)'

    def configure(mode='success'):
        executable.write_text(f'#!{sys.executable}\n' + textwrap.dedent(f'''\
            import hashlib, json, os, subprocess, sys, time, wave
            from pathlib import Path
            args = sys.argv[1:]
            reference = Path(args[args.index('--voice-ref') + 1])
            Path({str(capture)!r}).write_text(json.dumps({{'args': args, 'pid': os.getpid(),
                'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest()}}))
            print('[stdlib native stub] ' + {mode!r}, flush=True)
            if {mode!r} == 'software_device':
                print('ggml_vulkan: 0 = llvmpipe (LLVM software renderer)', flush=True)
            elif {mode!r} == 'wrong_device':
                print('ggml_vulkan: 1 = AMD Radeon RX 7600 XT (RADV NAVI33)', flush=True)
            elif {mode!r} != 'missing_device':
                print({AMD_DEVICE_ZERO!r}, flush=True)
            if {mode!r} == 'contradictory_device':
                print('ggml_vulkan: 0 = SwiftShader Device (software)', flush=True)
            if {mode!r} != 'missing_gpu':
                print('qwen3_tts.talker.weights.buffer_name Vulkan0', flush=True)
                print('qwen3_tts.speech_tokenizer_decoder.weights.buffer_name Vulkan0', flush=True)
            if {mode!r} in ('child_hang', 'orphan'):
                child = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(20)'])
                Path({str(capture)!r}).write_text(json.dumps({{'args': args, 'pid': os.getpid(), 'child': child.pid}}))
                if {mode!r} == 'child_hang':
                    time.sleep(20)
            if {mode!r} == 'hang':
                time.sleep(20)
            output = args[args.index('--out') + 1]
            if {mode!r} == 'invalid_wav':
                Path(output).write_bytes(b'not a wave file' * 10)
            else:
                with wave.open(output, 'wb') as audio:
                    audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
                    audio.writeframes(b'\\x01\\x00' * 4800)
                if {mode!r} == 'truncated_wav':
                    Path(output).write_bytes(Path(output).read_bytes()[:44])
            '''))
        executable.chmod(0o700)
        return hashlib.sha256(executable.read_bytes()).hexdigest()

    digest = configure()
    reference = tmp_path / 'reference A.wav'
    pcm(reference)
    lock = tmp_path / 'private-gpu.lock'
    lock.touch()
    request = {
        'engine': 'qwen3', 'model': oe.ENGINES['qwen3']['models'][0],
        'backend': 'native_vulkan', 'device': 'vulkan', 'language': 'English',
        'text': 'Meet at 9:05am.', 'voice_path': str(reference),
        'ref_text': 'Reference A says 9:05am.', 'speed': 1.0, 'emotion': 'neutral',
        'output_path': str(tmp_path / 'output.wav'),
        'native_executable': str(executable), 'native_sha256': digest,
        'native_model_dir': str(folder), 'native_gpu_lock': str(lock),
    }
    return nv, request, capture, configure


def test_native_host_import_does_not_load_ml_libraries():
    code = (
        'import sys; sys.path.insert(0, ' + repr(str(ROOT / 'src')) + '); '
        'import chatterbox_studio.optional_engines; import chatterbox_studio.native_vulkan; '
        'assert not any(n.split(".")[0] in {"torch", "qwen_tts", "indextts", "onnxruntime"} '
        'for n in sys.modules), sorted(sys.modules)'
    )
    result = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


def test_command_preserves_exact_transcript_and_explicit_embedding_mode(native_case):
    nv, request, _, _ = native_case
    config = nv.validate_native_configuration(request['engine'], request['model'], request)
    transcript = '  Reference says 9:05am.\nExact spelling stays.  '
    request['ref_text'] = transcript
    command = nv.build_native_command(request, config, Path(request['voice_path']), Path(request['output_path']))
    assert isinstance(command, list)
    assert command[command.index('--reference-text') + 1] == transcript
    assert 'x_vector_only_mode=false' in command
    request['ref_text'] = ''
    command = nv.build_native_command(request, config, Path(request['voice_path']), Path(request['output_path']))
    assert '--reference-text' not in command
    assert 'x_vector_only_mode=true' in command


@pytest.mark.parametrize('field,value', [('speed', 1.2), ('emotion', 'happy'),
                                        ('device', 'cpu'), ('device', 'auto'), ('device', 'cuda')])
def test_unsupported_native_controls_are_rejected(native_case, field, value):
    nv, request, capture, _ = native_case
    config = nv.validate_native_configuration(request['engine'], request['model'], request)
    request[field] = value
    with pytest.raises(nv.NativeVulkanError):
        nv.build_native_command(request, config, Path(request['voice_path']), Path(request['output_path']))
    assert not capture.exists()


def test_selected_model_size_cannot_be_silently_substituted(native_case):
    nv, request, capture, _ = native_case
    with pytest.raises(nv.NativeVulkanError, match='(?i)base|size|model'):
        nv.validate_native_configuration('qwen3', oe.ENGINES['qwen3']['models'][1], request)
    assert not capture.exists()


def test_native_gpu_lock_is_exclusive_without_replacing_existing_file(native_case):
    import fcntl
    nv, request, capture, _ = native_case
    lock = Path(request['native_gpu_lock'])
    before = lock.stat().st_ino
    with lock.open('r') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(nv.NativeVulkanError, match='(?i)busy'):
            with nv.gpu_reservation(lock, timeout=0.01):
                pytest.fail('A second owner acquired an already held GPU lock')
    assert lock.stat().st_ino == before
    assert not capture.exists()


def running(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1][0] != 'Z'
    except FileNotFoundError:
        return False


def stop_stub_descendant(capture):
    """Safety cleanup only for the exact owned stdlib fixture process."""
    if capture.exists():
        for key in ('child', 'pid'):
            pid = json.loads(capture.read_text()).get(key)
            if pid and running(pid):
                os.kill(pid, signal.SIGKILL)


def test_native_cancellation_stops_owned_descendants_and_releases_lock(native_case):
    import fcntl
    nv, request, capture, configure = native_case
    request['native_sha256'] = configure('child_hang')
    flag, failures = Event(), []
    def run():
        try:
            nv.execute_native_generation(request, cancelled=flag, timeout_seconds=3)
        except BaseException as error:
            failures.append(error)
    thread = Thread(target=run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if capture.exists() and 'child' in json.loads(capture.read_text()):
                break
            time.sleep(0.01)
        assert capture.exists() and 'child' in json.loads(capture.read_text()), 'Stub descendant did not launch'
        flag.set()
        thread.join(timeout=4)
        assert not thread.is_alive()
        assert failures and isinstance(failures[0], nv.NativeVulkanCancelled)
        owned = json.loads(capture.read_text())
        assert not running(owned['pid']) and not running(owned['child'])
        with open(request['native_gpu_lock']) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not Path(request['output_path']).exists()
    finally:
        flag.set()
        thread.join(timeout=4)
        stop_stub_descendant(capture)


def test_launcher_exit_cannot_leave_owned_descendant_after_lock_release(native_case):
    nv, request, capture, configure = native_case
    request['native_sha256'] = configure('orphan')
    try:
        nv.execute_native_generation(request, timeout_seconds=3)
        owned = json.loads(capture.read_text())
        assert not running(owned['child']), 'Owned native descendant survived launcher success/GPU-lock release'
    finally:
        stop_stub_descendant(capture)


def test_declared_wav_frames_require_matching_payload(native_case):
    nv, request, capture, configure = native_case
    request['native_sha256'] = configure('truncated_wav')
    with pytest.raises(nv.NativeVulkanError, match='(?i)wav|audio|frame|payload'):
        nv.execute_native_generation(request, timeout_seconds=3)
    assert capture.exists()
    assert not Path(request['output_path']).exists()


def test_native_timeout_stops_owned_process_and_publishes_nothing(native_case):
    nv, request, capture, configure = native_case
    request['native_sha256'] = configure('hang')
    with pytest.raises(nv.NativeVulkanError, match='(?i)time'):
        nv.execute_native_generation(request, timeout_seconds=0.15)
    assert capture.exists()
    assert not running(json.loads(capture.read_text())['pid'])
    assert not Path(request['output_path']).exists()


def test_native_route_preserves_original_reference_and_literal_arguments(native_case, monkeypatch):
    nv, request, capture, _ = native_case
    manuscript = 'Meet at 9:05am. Say "hello"; $(literal) stays text.'
    request['text'] = manuscript
    def reject_python(*_args, **_kwargs):
        raise AssertionError('Native selection must not enter Python-engine configuration')
    monkeypatch.setattr(oe, 'check_configuration', reject_python)
    output = oe.execute_generation(request, '/not/a/python', timeout_seconds=3)
    actual = json.loads(capture.read_text())['args']
    prepared = 'Meet at nine oh five a.m. Say "hello"; $(literal) stays text.'
    assert actual[actual.index('--text') + 1] == prepared
    assert actual[actual.index('--backend') + 1] == 'vulkan'
    assert actual[actual.index('--device') + 1] == '0'
    sidecar = json.loads(output.with_suffix('.json').read_text())
    assert sidecar['text'] == sidecar['original_text'] == manuscript
    assert sidecar['prepared_text'] == prepared
    assert sidecar['ref_text'] == request['ref_text']
    assert sidecar['voice_path'] == request['voice_path']
    assert not (capture.parent / 'literal').exists()


@pytest.mark.parametrize('field,value', [
    ('native_sha256', '0' * 64), ('native_executable', '/not/present/native'),
    ('native_model_dir', '/not/present/model'), ('native_gpu_lock', '/not/present/lock'),
])
def test_native_configuration_failure_never_spawns(native_case, field, value):
    nv, request, capture, _ = native_case
    request[field] = value
    with pytest.raises((nv.NativeVulkanError, oe.EngineError)):
        oe.execute_generation(request, '/not/a/python', timeout_seconds=3)
    assert not capture.exists()
    assert not Path(request['output_path']).exists()


def test_qwen_customvoice_is_not_silently_loaded_as_base(native_case):
    nv, request, capture, _ = native_case
    config = Path(request['native_model_dir']) / 'config.json'
    config.write_text(json.dumps({'tts_model_type': 'custom_voice', 'tts_model_size': '0b6'}))
    with pytest.raises((nv.NativeVulkanError, oe.EngineError), match='(?i)base|variant|model.type'):
        oe.execute_generation(request, '/not/a/python', timeout_seconds=3)
    assert not capture.exists()


@pytest.mark.parametrize('mode', ['missing_gpu', 'invalid_wav', 'missing_device',
                                 'software_device', 'wrong_device', 'contradictory_device'])
def test_success_exit_without_gpu_proof_or_valid_audio_is_not_accepted(native_case, mode):
    nv, request, capture, configure = native_case
    request['native_sha256'] = configure(mode)
    with pytest.raises((nv.NativeVulkanError, oe.EngineError)):
        oe.execute_generation(request, '/not/a/python', timeout_seconds=3)
    assert capture.exists()
    assert not Path(request['output_path']).exists()
    assert not Path(request['output_path']).with_suffix('.json').exists()


@pytest.mark.parametrize('evidence', [
    '',
    'ggml_vulkan: 1 = AMD Radeon RX 7600 XT (RADV NAVI33)',
    'ggml_vulkan: 0 = llvmpipe (LLVM 19.1, 256 bits)',
    'ggml_vulkan: 0 = lavapipe (Mesa software ICD)',
    'ggml_vulkan: 0 = SwiftShader Device (Subzero)',
    'ggml_vulkan: 0 = Microsoft Basic Render Driver (software)',
    AMD_DEVICE_ZERO + ' | driver: SwiftShader',
    AMD_DEVICE_ZERO + '\nggml_vulkan: 0 = llvmpipe (LLVM software renderer)',
    AMD_DEVICE_ZERO + '\nggml_vulkan: 0 = NVIDIA GeForce RTX 4090',
])
def test_weight_buffers_alone_cannot_override_bad_physical_device_evidence(tmp_path, evidence):
    from chatterbox_studio import native_vulkan as nv
    logfile = tmp_path / 'synthetic-placement.log'
    logfile.write_text(evidence + '\nqwen3_tts.talker.weights.buffer_name Vulkan0\n'
                       'qwen3_tts.speech_tokenizer_decoder.weights.buffer_name Vulkan0\n')
    with pytest.raises(nv.NativeVulkanError):
        nv._placement(logfile, 'qwen3')


def test_physical_device_and_required_buffers_have_explicit_limited_scope(tmp_path):
    from chatterbox_studio import native_vulkan as nv
    logfile = tmp_path / 'synthetic-placement.log'
    logfile.write_text(AMD_DEVICE_ZERO + '\nqwen3_tts.talker.weights.buffer_name Vulkan0\n'
                       'qwen3_tts.speech_tokenizer_decoder.weights.buffer_name Vulkan0\n')
    placement = nv._placement(logfile, 'qwen3')
    assert placement['actual_backend'] == 'vulkan' and placement['actual_device'] == 'Vulkan0'
    assert placement['physical_device_name'] == 'AMD Radeon RX 7600 XT (RADV NAVI33)'
    assert placement['device_identity_scope']
    assert any('AMD Radeon RX 7600 XT' in line for line in placement['device_evidence'])
    assert placement['gpu_weight_buffers'] == ['speech_tokenizer_decoder', 'talker']
    assert 'CPU' in placement['placement_scope'] and 'weight' in placement['placement_scope'].lower()


def test_native_precancel_does_not_spawn(native_case):
    nv, request, capture, _ = native_case
    flag = Event(); flag.set()
    with pytest.raises((nv.NativeVulkanCancelled, oe.EngineCancelled)):
        oe.execute_generation(request, '/not/a/python', cancelled=flag, timeout_seconds=3)
    assert not capture.exists()


def test_native_reference_limit_does_not_truncate_or_modify_original(native_case):
    nv, request, capture, _ = native_case
    reference = Path(request['voice_path'])
    pcm(reference, seconds=30.1)
    original = reference.read_bytes()
    with pytest.raises((nv.NativeVulkanError, oe.EngineError), match='30|long|duration'):
        oe.execute_generation(request, '/not/a/python', timeout_seconds=3)
    assert reference.read_bytes() == original
    assert not capture.exists()


def test_native_cancel_while_gpu_lock_busy_never_launches(native_case):
    import fcntl
    nv, request, capture, _ = native_case
    flag, failures = Event(), []
    def run():
        try:
            oe.execute_generation(request, '/not/a/python', cancelled=flag, timeout_seconds=3)
        except BaseException as error:
            failures.append(error)
    with open(request['native_gpu_lock'], 'r+b') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        thread = Thread(target=run, daemon=True)
        thread.start()
        flag.set()
        thread.join(timeout=2)
        stopped_while_locked = not thread.is_alive()
        fcntl.flock(held, fcntl.LOCK_UN)
    thread.join(timeout=3)
    assert stopped_while_locked, 'Cancellation must not wait for the GPU lock holder'
    assert failures and isinstance(failures[0], (nv.NativeVulkanCancelled, oe.EngineCancelled))
    assert not capture.exists()


def test_reference_a_to_b_to_embedding_keeps_exact_conditioning_and_metadata(native_case):
    _, request, capture, _ = native_case
    reference_a = Path(request['voice_path'])
    reference_b = reference_a.with_name('reference B.wav')
    pcm(reference_b, sample=2)
    original_a, original_b = reference_a.read_bytes(), reference_b.read_bytes()
    hashes = []
    for suffix, reference, transcript, mode in [
        ('a', reference_a, '  Reference A says 9:05am.\nExactly.  ', 'reference_transcript'),
        ('b', reference_b, 'Reference B says 10:30pm.', 'reference_transcript'),
        ('embedding', reference_a, '', 'embedding_only'),
    ]:
        current = request | {'voice_path': str(reference), 'ref_text': transcript,
                             'output_path': str(reference.parent / (suffix + '.wav'))}
        output = oe.execute_generation(current, '/not/a/python', timeout_seconds=3)
        actual = json.loads(capture.read_text())
        argv = actual['args']
        metadata = json.loads(output.with_suffix('.json').read_text())
        runtime = metadata['runtime']
        conditioning = runtime['conditioning']
        expected_sha = hashlib.sha256(reference.read_bytes()).hexdigest()
        hashes.append(expected_sha)
        assert metadata['voice_path'] == str(reference) and metadata['ref_text'] == transcript
        assert metadata['original_text'] == metadata['text'] == request['text']
        assert metadata['prepared_text'] == 'Meet at nine oh five a.m.'
        assert conditioning['source_sha256'] == conditioning['prepared_sha256'] == expected_sha
        assert actual['reference_sha256'] == expected_sha
        assert Path(argv[argv.index('--voice-ref') + 1]) != reference
        assert conditioning['mode'] == mode
        assert conditioning['exact_transcript_used'] == bool(transcript)
        if transcript:
            assert argv[argv.index('--reference-text') + 1] == transcript
            assert 'x_vector_only_mode=false' in argv
        else:
            assert '--reference-text' not in argv and 'x_vector_only_mode=true' in argv
        assert runtime['actual_backend'] == 'vulkan' and runtime['actual_device'] == 'Vulkan0'
        assert runtime['physical_device_name'] == 'AMD Radeon RX 7600 XT (RADV NAVI33)'
        assert runtime['executable_sha256'] == request['native_sha256']
        assert runtime['model_config_sha256'] == hashlib.sha256(
            (Path(request['native_model_dir']) / 'config.json').read_bytes()).hexdigest()
        assert runtime['gpu_weight_buffers'] == ['speech_tokenizer_decoder', 'talker']
        assert runtime['audio_seconds'] == pytest.approx(0.2)
    assert hashes[0] != hashes[1] and hashes[2] == hashes[0]
    assert reference_a.read_bytes() == original_a and reference_b.read_bytes() == original_b


@pytest.mark.parametrize('mode', ['missing_gpu', 'invalid_wav', 'hang'])
def test_failure_retains_diagnostic_evidence_without_publishing(native_case, mode):
    _, request, capture, configure = native_case
    request['native_sha256'] = configure(mode)
    diagnostics = capture.parent / 'diagnostics'
    messages = []
    with pytest.raises(oe.EngineError) as failure:
        oe.execute_generation(request, '/not/a/python', timeout_seconds=0.2,
                              diagnostic_dir=diagnostics, log=messages.append)
    logs = list(diagnostics.glob('*.log'))
    assert len(logs) == 1 and '[stdlib native stub]' in logs[0].read_text()
    assert str(logs[0]) in str(failure.value) + '\n'.join(messages), 'User cannot locate retained failure evidence'
    assert not Path(request['output_path']).exists()
    assert not Path(request['output_path']).with_suffix('.json').exists()


def test_legacy_cpu_registry_and_character_profiles_preserve_unknown_fields(tmp_path):
    registry = oe.EngineRegistry(tmp_path)
    legacy = {
        'qwen3': {'python': str(sys.executable), 'repo': '', 'user_note': 'keep qwen'},
        'index25': {'python': str(sys.executable), 'repo': str(tmp_path / 'old repo')},
        'kokoro': {'python': str(sys.executable), 'model_dir': str(tmp_path / 'old kokoro')},
        'future_extension': {'keep': ['a', 'b']},
    }
    registry.path.write_text(json.dumps(legacy))
    before = registry.path.read_bytes()
    loaded = registry.read()
    assert registry.path.read_bytes() == before, 'Reading old configuration must not migrate it implicitly'
    assert loaded['qwen3']['backend'] == loaded['index25']['backend'] == 'python'
    for engine, values in legacy.items():
        assert all(loaded[engine][key] == value for key, value in values.items())
    registry.save({'native': {'native_executable': str(tmp_path / 'reviewed executable')}})
    saved = registry.read()
    for engine, values in legacy.items():
        assert all(saved[engine][key] == value for key, value in values.items())
    store = oe.CharacterStore(tmp_path)
    cpu = {'preferred_engine': 'index25', 'voice_id': 'original-a', 'ref_text': 'Exact A.',
           'custom_notes': {'keep': True}, 'engines': {'index25': {
               'model': oe.ENGINES['index25']['models'][0], 'backend': 'python', 'device': 'cpu',
               'emotion': 'happy', 'speed': 1.2}}}
    store.save_profile('Existing CPU', cpu)
    store.save_profile('New Native', {'engines': {'qwen3': {'backend': 'native_vulkan'}}})
    assert store.read()['Existing CPU'] == cpu


def test_legacy_python_cpu_route_keeps_controls_and_never_calls_native(native_case, monkeypatch):
    nv, request, capture, _ = native_case
    folder = capture.parent
    runner = folder / 'cpu_protocol_stub.py'
    received = folder / 'cpu-request.json'
    runner.write_text(textwrap.dedent(f'''\
        import json, sys, wave
        from pathlib import Path
        request = json.loads(Path(sys.argv[2]).read_text())
        Path({str(received)!r}).write_text(json.dumps(request))
        with wave.open(request['output_path'], 'wb') as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(24000)
            output.writeframes(b'\\x01\\x00' * 100)
        Path(sys.argv[3]).write_text(json.dumps({{'ok': True}}))
        '''))
    repo = folder / 'cpu index repository'
    (repo / 'indextts').mkdir(parents=True)
    (repo / 'indextts/infer_v2_5.py').write_text('# metadata-only fixture')
    (repo / 'checkpoints').mkdir()
    (repo / 'checkpoints/config.yaml').write_text('# metadata-only fixture')
    current = request | {'engine': 'index25', 'model': oe.ENGINES['index25']['models'][0],
                         'backend': 'python', 'device': 'cpu', 'language': 'EN',
                         'emotion': 'happy', 'speed': 1.2, 'repo': str(repo)}
    original = current.copy()
    monkeypatch.setattr(oe, 'runtime_script_path', lambda: runner)
    monkeypatch.setattr(nv, 'execute_native_generation', lambda *_a, **_k: pytest.fail('CPU route called native backend'))
    output = oe.execute_generation(current, str(sys.executable), timeout_seconds=3)
    actual = json.loads(received.read_text())
    assert (actual['backend'], actual['device'], actual['emotion'], actual['speed']) == ('python', 'cpu', 'happy', 1.2)
    assert actual['ref_text'] == current['ref_text'] and actual['voice_path'] == current['voice_path']
    assert output.is_file() and not capture.exists()
    assert current == original


@pytest.mark.parametrize('backend,device', [('python', 'vulkan'), ('native_vulkan', 'cpu'),
                                          ('automatic', 'vulkan')])
def test_invalid_backend_device_combinations_do_not_spawn(native_case, backend, device):
    _, request, capture, _ = native_case
    with pytest.raises(oe.EngineError):
        oe.execute_generation(request | {'backend': backend, 'device': device}, '/not/a/python', timeout_seconds=3)
    assert not capture.exists()


def test_index_generation_fails_closed_before_config_reference_or_cli_access(monkeypatch, tmp_path):
    from chatterbox_studio import native_vulkan as nv
    def forbidden(*_args, **_kwargs):
        pytest.fail('Unqualified Index generation inspected assets or started a process')
    monkeypatch.setattr(nv, 'validate_native_configuration', forbidden)
    monkeypatch.setattr(nv, '_prepare_reference', forbidden)
    monkeypatch.setattr(nv, '_run_owned', forbidden)
    with pytest.raises(nv.NativeVulkanError, match='(?i)index.*qualif|qualif.*index'):
        nv.execute_native_generation({'engine': 'index25'})
    with pytest.raises(nv.NativeVulkanError, match='(?i)index.*qualif|qualif.*index'):
        nv._placement(tmp_path / 'absent.log', 'index25')


def test_index_path_probe_does_not_claim_generation_support(native_case, monkeypatch):
    nv, request, capture, _ = native_case
    folder = capture.parent / 'index fixture'
    for name in nv.INDEX_FILES:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    settings = request | {'native_model_dir': str(folder)}
    monkeypatch.setattr(nv.subprocess, 'Popen', lambda *_a, **_k: pytest.fail('Path probe started native process'))
    result = oe.execute_probe('index25', '/not/a/python', backend='native_vulkan',
                              native_settings=settings, model=oe.ENGINES['index25']['models'][0])
    assert result['ready'] and result['generation_supported'] is False
    assert 'qualif' in result['status'].lower()
    assert not capture.exists()


_QA_APPLICATION = None


@pytest.fixture
def qa_lab(private_homes, tmp_path, monkeypatch):
    # A strong process-lifetime reference avoids repeatedly destroying and
    # recreating QApplication between tests. This scope uses no media player.
    global _QA_APPLICATION
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    widgets = pytest.importorskip('PyQt6.QtWidgets')
    from PyQt6.QtCore import QCoreApplication, QEvent, QSettings
    from chatterbox_studio.engine_lab import EngineLab
    _QA_APPLICATION = widgets.QApplication.instance() or widgets.QApplication([])
    host = widgets.QWidget()
    host.storage = tmp_path / 'application'
    host.storage.mkdir()
    host.settings = QSettings(str(tmp_path / 'isolated.ini'), QSettings.Format.IniFormat)
    host.settings.setFallbacksEnabled(False)
    host.player = SimpleNamespace(stop=lambda: None)
    host.bethesda_tab = None
    host.thread = None
    host.model_manager = SimpleNamespace(is_busy=False)
    host.editor = widgets.QPlainTextEdit()
    references = {key: tmp_path / ('UI reference ' + key + '.wav') for key in ('a', 'b')}
    for path in references.values():
        path.touch()
    host.voices = SimpleNamespace(
        list_voices=lambda: [{'id': key, 'name': 'Reference ' + key} for key in references],
        resolve=lambda key: str(references.get(key, '')),
    )
    lab = EngineLab(host)
    yield lab
    lab.close()
    host.close()
    host.deleteLater()
    host.editor.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    _QA_APPLICATION.processEvents()


def test_ui_native_discovery_only_suggests_empty_fields_until_explicit_save(qa_lab, monkeypatch):
    from chatterbox_studio import native_vulkan as nv
    lab = qa_lab
    registry = lab.registry.path
    assert not registry.exists()
    assert lab.backend.currentData() == 'python'
    lab.native_fields['native_executable'].setText('user retained text')
    suggestions = {key: str(lab.host.storage / ('suggested ' + key)) for key in lab.native_fields}
    suggestions['native_sha256'] = 'e' * 64
    inspected = []
    def discover(path):
        inspected.append(path)
        return suggestions
    monkeypatch.setattr(nv, 'discover_native_settings', discover)
    lab._discover_native_paths()
    assert inspected == [lab.host.storage]
    assert lab.native_fields['native_executable'].text() == 'user retained text'
    assert lab.native_fields['qwen_06_model_dir'].text() == suggestions['qwen_06_model_dir']
    assert not registry.exists() and lab.backend.currentData() == 'python'
    assert lab.thread is None
    lab.save_runtimes()
    assert lab.registry.read()['native']['native_executable'] == 'user retained text'


def test_ui_python_controls_survive_native_backend_round_trip(qa_lab):
    lab = qa_lab
    lab.engine.setCurrentIndex(lab.engine.findData('index25'))
    lab.speed.setValue(1.25)
    lab.emotion.setCurrentIndex(lab.emotion.findData('happy'))
    assert lab.speed.isEnabled() and lab.emotion.isEnabled()
    lab.backend.setCurrentIndex(lab.backend.findData('native_vulkan'))
    assert lab.device.currentData() == 'vulkan' and not lab.device.isEnabled()
    assert not lab.speed.isEnabled() and not lab.emotion.isEnabled()
    assert lab.speed.value() == 1.0 and lab.emotion.currentData() == 'neutral'
    lab.backend.setCurrentIndex(lab.backend.findData('python'))
    assert lab.speed.value() == 1.25 and lab.emotion.currentData() == 'happy'
    assert lab.device.currentData() == 'cpu'


def test_ui_native_profile_retains_paths_unknown_fields_voice_and_exact_transcript(qa_lab, native_case):
    lab = qa_lab
    _, request, _, _ = native_case
    lab.profiles.save_profile('Native A', {'custom_notes': {'keep': True},
        'engines': {'qwen3': {'future_control': 'preserve'}}})
    lab.character.setEditText('Native A')
    lab.engine.setCurrentIndex(lab.engine.findData('qwen3'))
    lab.model.setCurrentIndex(lab.model.findData(request['model']))
    lab.language.setCurrentIndex(lab.language.findData('English'))
    lab.voice.setCurrentIndex(lab.voice.findData('a'))
    transcript = '  Reference A says 9:05am.\nExactly.  '
    lab.ref_text.setPlainText(transcript)
    for key in ('native_executable', 'native_sha256', 'native_gpu_lock'):
        lab.native_fields[key].setText(request[key])
    lab.native_fields['qwen_06_model_dir'].setText(request['native_model_dir'])
    lab.backend.setCurrentIndex(lab.backend.findData('native_vulkan'))
    lab.save_profile()
    saved = lab.profiles.read()['Native A']
    assert saved['custom_notes'] == {'keep': True}
    assert saved['engines']['qwen3']['future_control'] == 'preserve'
    assert saved['engines']['qwen3']['backend'] == 'native_vulkan'
    assert saved['engines']['qwen3']['native_settings']['native_model_dir'] == request['native_model_dir']
    for field in lab.native_fields.values():
        field.clear()
    lab.backend.setCurrentIndex(lab.backend.findData('python'))
    lab.voice.setCurrentIndex(lab.voice.findData('b'))
    lab.ref_text.setPlainText('Reference B must not leak.')
    lab._profile_selected()
    assert lab.backend.currentData() == 'native_vulkan'
    assert lab.voice.currentData() == 'a' and lab.ref_text.toPlainText() == transcript
    assert lab.native_fields['native_executable'].text() == request['native_executable']
    assert lab.native_fields['qwen_06_model_dir'].text() == request['native_model_dir']
    assert lab.profiles.read()['Native A'] == saved


def test_ui_unqualified_index_generation_is_disabled(qa_lab):
    lab = qa_lab
    lab.engine.setCurrentIndex(lab.engine.findData('index25'))
    lab.backend.setCurrentIndex(lab.backend.findData('native_vulkan'))
    assert not lab.generate.isEnabled()
    assert lab.test.isEnabled(), 'Index path validation may remain available without a generation claim'


@pytest.mark.parametrize('duration,rate,channels,accepted', [
    (30, 24000, 1, True),
    (31, 24000, 1, False),
    (1, 16000, 2, False),
])
def test_reference_conversion_bounds_preserve_original_without_effects(
        tmp_path, monkeypatch, duration, rate, channels, accepted):
    from chatterbox_studio import native_vulkan as nv
    source = tmp_path / 'synthetic-container.mp3'
    original = b'private synthetic container; not actual encoded user audio'
    source.write_bytes(original)
    work = tmp_path / 'private work'
    work.mkdir()
    executable = tmp_path / 'never-executed-ffmpeg'
    commands = []
    monkeypatch.setitem(sys.modules, 'imageio_ffmpeg', SimpleNamespace(get_ffmpeg_exe=lambda: str(executable)))
    def synthetic_conversion(command, *_args, **_kwargs):
        commands.append(command)
        assert command[0] == str(executable)
        with wave.open(command[-1], 'wb') as result:
            result.setnchannels(channels)
            result.setsampwidth(2)
            result.setframerate(rate)
            result.writeframes(b'\x01\x00' * int(duration * rate * channels))
    monkeypatch.setattr(nv, '_run_owned', synthetic_conversion)
    if accepted:
        prepared, detail = nv._prepare_reference(source, work, work / 'conversion.log', Event(), timeout=2)
        assert prepared.parent == work and detail['seconds'] == 30
    else:
        with pytest.raises(nv.NativeVulkanError, match='30|mono|24kHz|PCM'):
            nv._prepare_reference(source, work, work / 'conversion.log', Event(), timeout=2)
    assert source.read_bytes() == original and len(commands) == 1
    assert '-ss' not in commands[0] and not any('atempo' in value for value in commands[0])
    assert commands[0][commands[0].index('-t') + 1] == '31'
    assert not (work / 'raw.wav').exists()


def test_sidecar_publication_race_preserves_other_metadata_and_removes_only_own_wav(native_case, monkeypatch):
    nv, request, _, _ = native_case
    output = Path(request['output_path'])
    metadata = output.with_suffix('.json')
    original_link = nv.os.link
    other_owner = b'{"owner": "another process", "preserve": true}\n'
    def race_link(source, target, *_args, **_kwargs):
        if Path(target) == metadata:
            metadata.write_bytes(other_owner)
        return original_link(source, target, *_args, **_kwargs)
    monkeypatch.setattr(nv.os, 'link', race_link)
    with pytest.raises(oe.EngineError):
        oe.execute_generation(request, '/not/a/python', timeout_seconds=3)
    assert metadata.read_bytes() == other_owner
    assert not output.exists()
