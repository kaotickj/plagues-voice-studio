"""Model manager correctness without PyQt, torch or network downloads."""
from pathlib import Path
from threading import Event
import sys
import types
import pytest

from chatterbox_studio import model_downloads as md
from chatterbox_studio.optional_engines import EngineCancelled


def chatterbox_fixture_files(item, tokenizer_format='split'):
    files = list(item.required)
    if item.key in ('nano', 'turbo'):
        files += ['tokenizer.json'] if tokenizer_format == 'self-contained' else ['vocab.json', 'merges.txt']
    return files


def test_catalog_contains_production_engines_only():
    assert len(md.CATALOG) == 6
    assert {m.key for m in md.CATALOG if m.family == 'qwen3'} == {'qwen-0.6b', 'qwen-1.7b'}
    assert not any('index' in m.key for m in md.CATALOG)
    assert md.MODELS['qwen-0.6b'].repo.endswith('0.6B-Base')


@pytest.mark.parametrize('key', ['qwen-0.6b', 'qwen-1.7b'])
@pytest.mark.parametrize('operation', ['check', 'download'])
def test_qwen_task_launches_and_reads_completion(tmp_path, monkeypatch, key, operation):
    python = tmp_path / 'python.exe'
    python.write_bytes(b'python')
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs['stderr']))
        kwargs['stdout'].write(b'PVS_CACHE_FOUND\nPVS_DOWNLOAD_COMPLETE model\n')
        return types.SimpleNamespace(returncode=0, poll=lambda: 0)

    monkeypatch.setattr(md, '_spawn_optional_interpreter', spawn)
    monkeypatch.setattr(md, '_watch_engine_process', lambda *args: None)
    assert md.qwen_task(md.MODELS[key], str(python), operation, Event(),
                        lambda *_: None, tmp_path / 'logs')
    assert calls[0][0][-2:] == [md.MODELS[key].repo, operation]
    assert calls[0][1] == md.subprocess.STDOUT


def test_chatterbox_status_only_accepts_nonempty_required_files(tmp_path, monkeypatch):
    item = md.MODELS['nano']
    monkeypatch.setattr(md, 'bundled_models_dir', lambda: tmp_path / 'no-bundle')
    assert md.chatterbox_status(tmp_path, item) == 'Download available'
    folder = md.user_model_directory(tmp_path, 'nano')
    folder.mkdir(parents=True)
    for name in chatterbox_fixture_files(item):
        (folder / name).write_bytes(b'x')
    assert md.chatterbox_status(tmp_path, item) == 'Installed (user data)'
    (folder / item.required[0]).write_bytes(b'')
    assert md.chatterbox_status(tmp_path, item) == 'Download available'


def test_download_checks_cancel_between_hf_files(tmp_path, monkeypatch):
    item = md.MODELS['nano']
    event = Event()
    observed = []
    def download(**kwargs):
        observed.append(kwargs['filename'])
        target = Path(kwargs['local_dir']) / kwargs['filename']
        target.write_bytes(b'good')
        if len(observed) == 1:
            event.set()
    hub = types.SimpleNamespace(list_repo_files=lambda repo: chatterbox_fixture_files(item),
                                hf_hub_download=download)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    with pytest.raises(EngineCancelled):
        md.download_chatterbox(item, tmp_path, event, lambda *_: None)
    assert len(observed) == 1
    assert md.chatterbox_status(tmp_path, item) != 'Installed (user data)'


def test_download_verifies_model_and_uses_user_data(tmp_path, monkeypatch):
    item = md.MODELS['turbo']
    def download(**kwargs):
        (Path(kwargs['local_dir']) / kwargs['filename']).write_bytes(b'weight')
    hub = types.SimpleNamespace(list_repo_files=lambda repo: chatterbox_fixture_files(item),
                                hf_hub_download=download)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    folder = md.download_chatterbox(item, tmp_path, Event(), lambda *_: None)
    assert folder == tmp_path / 'models' / 'turbo'
    assert md.has_required_files(folder, item)


def test_qwen_download_is_whitelisted_and_uses_isolated_python(tmp_path):
    python = tmp_path / 'python.exe'; python.write_bytes(b'python')
    cmd = md.qwen_command(str(python), md.MODELS['qwen-0.6b'], 'download')
    assert cmd[:4] == [str(python), '-I', '-u', '-c']
    assert cmd[-2:] == ['Qwen/Qwen3-TTS-12Hz-0.6B-Base', 'download']
    with pytest.raises(ValueError):
        md.qwen_command(str(python), md.MODELS['nano'], 'download')
    with pytest.raises(ValueError):
        md.qwen_command(str(python), md.MODELS['qwen-0.6b'], 'arbitrary-command')

def _qwen_check_script(monkeypatch, tmp_path, *, complete, missing=None, operation="check", small_metadata=False):
    """Run the lightweight embedded script with a fake local Hub snapshot."""
    import contextlib
    import io
    hub = types.ModuleType('huggingface_hub')
    hub.snapshot_download = lambda **kwargs: tmp_path
    constants = types.ModuleType('huggingface_hub.constants')
    constants.HF_HUB_CACHE = str(tmp_path)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    monkeypatch.setitem(sys.modules, 'huggingface_hub.constants', constants)
    monkeypatch.setattr(sys, 'argv', ['-c', 'Qwen/Qwen3-TTS-12Hz-1.7B-Base', operation])
    (tmp_path / 'speech_tokenizer').mkdir(exist_ok=True)
    required = [
        'config.json', 'model.safetensors', 'speech_tokenizer/config.json',
        'speech_tokenizer/model.safetensors',
        'tokenizer_config.json', 'vocab.json', 'merges.txt',
        'generation_config.json', 'preprocessor_config.json',
        'speech_tokenizer/preprocessor_config.json',
    ]
    for fn in (required if complete else required[:2]):
        target = tmp_path / fn
        target.write_bytes(b'{}' if small_metadata and not fn.endswith('.safetensors')
                           else b'synthetic model data' * 100)
    if missing:
        (tmp_path / missing).unlink()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(md._QWEN_SCRIPT, 'qwen-check-script', 'exec'), {'__name__': '__main__'})
    return output.getvalue()


def test_qwen_cache_check_rejects_incomplete_snapshot(monkeypatch, tmp_path):
    result = _qwen_check_script(monkeypatch, tmp_path, complete=False)
    assert 'PVS_CACHE_INCOMPLETE' in result
    assert 'PVS_CACHE_MISSING' in result
    assert 'PVS_CACHE_FOUND' not in result


def test_qwen_cache_check_accepts_complete_snapshot(monkeypatch, tmp_path):
    result = _qwen_check_script(monkeypatch, tmp_path, complete=True)
    assert 'PVS_MODEL_VERIFIED' in result
    assert 'PVS_CACHE_FOUND' in result
    assert 'PVS_CACHE_MISSING' not in result


def test_qwen_script_avoids_revision_only_cache_check():
    assert 'scan_cache_dir' not in md._QWEN_SCRIPT
    assert 'local_files_only=True' in md._QWEN_SCRIPT
    assert 'speech_tokenizer/model.safetensors' in md._QWEN_SCRIPT


@pytest.mark.parametrize('missing', [
    'tokenizer_config.json', 'vocab.json', 'merges.txt',
    'generation_config.json', 'preprocessor_config.json',
    'speech_tokenizer/preprocessor_config.json',
])
@pytest.mark.parametrize('operation', ['check', 'download'])
def test_qwen_readiness_requires_offline_processor_files(monkeypatch, tmp_path, missing, operation):
    if operation == 'download':
        with pytest.raises(RuntimeError, match=missing):
            _qwen_check_script(monkeypatch, tmp_path, complete=True,
                               missing=missing, operation=operation)
    else:
        output = _qwen_check_script(monkeypatch, tmp_path, complete=True, missing=missing)
        assert 'PVS_CACHE_MISSING' in output
        assert 'PVS_CACHE_FOUND' not in output
        assert missing in output


def test_qwen_readiness_accepts_nonempty_small_metadata(monkeypatch, tmp_path):
    output = _qwen_check_script(monkeypatch, tmp_path, complete=True, small_metadata=True)
    assert 'PVS_CACHE_FOUND' in output
    assert 'PVS_CACHE_INCOMPLETE' not in output


@pytest.mark.parametrize('failure', [ConnectionError('network unavailable'),
                                     OSError(28, 'No space left on device')])
def test_failed_chatterbox_install_retains_partial_files_and_can_retry(tmp_path, monkeypatch, failure):
    item = md.MODELS['nano']
    destination = md.user_model_directory(tmp_path, item.key)
    unrelated = tmp_path / 'existing-voice.wav'
    unrelated.write_bytes(b'existing user recording')
    interrupted = {'active': True}
    transferred = []
    def download(**kwargs):
        target = Path(kwargs['local_dir']) / kwargs['filename']
        if target.is_file():
            return str(target)  # Simulate the Hub's reuse of a completed file.
        if interrupted['active'] and len(transferred) == 1:
            raise failure
        target.write_bytes(b'fixture model content')
        transferred.append(kwargs['filename'])
        return str(target)
    hub = types.SimpleNamespace(list_repo_files=lambda repo: chatterbox_fixture_files(item),
                                hf_hub_download=download)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    with pytest.raises(type(failure), match=str(failure).replace('[', r'\[').replace(']', r'\]')):
        md.download_chatterbox(item, tmp_path, Event(), lambda *_: None)
    assert not md.has_required_files(destination, item)
    first = destination / item.required[0]
    assert first.read_bytes() == b'fixture model content'
    assert unrelated.read_bytes() == b'existing user recording'
    interrupted['active'] = False
    assert md.download_chatterbox(item, tmp_path, Event(), lambda *_: None) == destination
    assert transferred == chatterbox_fixture_files(item)
    assert md.has_required_files(destination, item)
    assert unrelated.read_bytes() == b'existing user recording'


@pytest.mark.parametrize('key', ['nano', 'turbo'])
def test_meanflow_install_does_not_fetch_unused_s3gen_weights(tmp_path, monkeypatch, key):
    item = md.MODELS[key]
    available = [*chatterbox_fixture_files(item), 's3gen.safetensors', 'conds.pt']
    observed = []
    def download(**kwargs):
        observed.append(kwargs['filename'])
        (Path(kwargs['local_dir']) / kwargs['filename']).write_bytes(b'fixture')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', types.SimpleNamespace(
        list_repo_files=lambda repo: available, hf_hub_download=download))
    md.download_chatterbox(item, tmp_path, Event(), lambda *_: None)
    assert 's3gen.safetensors' not in observed
    assert set(item.required).issubset(observed)
    assert {'tokenizer_config.json', 'vocab.json', 'merges.txt', 'conds.pt'}.issubset(observed)


@pytest.mark.parametrize('key', ['nano', 'turbo'])
@pytest.mark.parametrize('tokenizer_format', ['split', 'self-contained'])
def test_complete_nano_turbo_tokenizer_reused_offline(tmp_path, monkeypatch, key, tokenizer_format):
    item = md.MODELS[key]
    folder = md.user_model_directory(tmp_path, key); folder.mkdir(parents=True)
    for name in chatterbox_fixture_files(item, tokenizer_format):
        (folder / name).write_bytes(b'synthetic complete file')
    monkeypatch.setattr(md, 'bundled_models_dir', lambda: tmp_path / 'no-bundle')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', types.SimpleNamespace(
        list_repo_files=lambda *_: pytest.fail('Complete offline tokenizer must not start download'),
        hf_hub_download=lambda **_: pytest.fail('Complete files must be reused')))
    assert md.has_required_files(folder, item)
    assert md.installed_model_directory(tmp_path, item) == folder
    assert md.chatterbox_status(tmp_path, item) == 'Installed (user data)'
    assert md.download_chatterbox(item, tmp_path, Event(), lambda *_: None) == folder


@pytest.mark.parametrize('key', ['nano', 'turbo'])
@pytest.mark.parametrize('tokenizer_format, missing', [
    ('split', 'tokenizer_config.json'), ('split', 'vocab.json'), ('split', 'merges.txt'),
    ('self-contained', 'tokenizer_config.json'), ('self-contained', 'tokenizer.json'),
])
@pytest.mark.parametrize('empty', [False, True], ids=['missing', 'zero-byte'])
def test_incomplete_tokenizer_is_not_installed_and_retry_repairs_only_fixture_files(
        tmp_path, monkeypatch, key, tokenizer_format, missing, empty):
    item = md.MODELS[key]
    folder = md.user_model_directory(tmp_path, key); folder.mkdir(parents=True)
    files = chatterbox_fixture_files(item, tokenizer_format)
    for name in files:
        (folder / name).write_bytes(b'original synthetic file')
    if empty:
        (folder / missing).write_bytes(b'')
    else:
        (folder / missing).unlink()
    weights = {name: (folder / name).read_bytes() for name in item.required if name.endswith('.safetensors')}
    user_audio = tmp_path / 'existing-user-audio.wav'; user_audio.write_bytes(b'untouched synthetic user audio')
    monkeypatch.setattr(md, 'bundled_models_dir', lambda: tmp_path / 'no-bundle')
    assert not md.has_required_files(folder, item)
    assert md.installed_model_directory(tmp_path, item) is None
    assert md.chatterbox_status(tmp_path, item) == 'Download available'
    calls = []
    def download(**kwargs):
        calls.append(kwargs['filename'])
        path = Path(kwargs['local_dir']) / kwargs['filename']
        if not path.is_file() or path.stat().st_size == 0:
            path.write_bytes(b'repaired synthetic tokenizer file')
        return str(path)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', types.SimpleNamespace(
        list_repo_files=lambda repo: files, hf_hub_download=download))
    assert md.download_chatterbox(item, tmp_path, Event(), lambda *_: None) == folder
    assert missing in calls  # Readiness did not take the old "already installed" path.
    assert md.has_required_files(folder, item)
    assert md.chatterbox_status(tmp_path, item) == 'Installed (user data)'
    assert {name: (folder / name).read_bytes() for name in weights} == weights
    assert user_audio.read_bytes() == b'untouched synthetic user audio'


@pytest.mark.parametrize('key', ['nano', 'turbo'])
def test_failed_tokenizer_repair_names_both_supported_representations(tmp_path, monkeypatch, key):
    item = md.MODELS[key]
    def download(**kwargs):
        (Path(kwargs['local_dir']) / kwargs['filename']).write_bytes(b'synthetic file')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', types.SimpleNamespace(
        list_repo_files=lambda repo: list(item.required), hf_hub_download=download))
    with pytest.raises(md.EngineError, match='missing/empty') as failure:
        md.download_chatterbox(item, tmp_path, Event(), lambda *_: None)
    message = str(failure.value)
    assert all(name in message for name in ('tokenizer.json', 'vocab.json', 'merges.txt'))
    assert md.chatterbox_status(tmp_path, item) != 'Installed (user data)'
