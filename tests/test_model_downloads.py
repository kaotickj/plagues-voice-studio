"""Model manager correctness without PyQt, torch or network downloads."""
from pathlib import Path
from threading import Event
import sys
import types
import pytest

from chatterbox_studio import model_downloads as md
from chatterbox_studio.optional_engines import EngineCancelled


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
    for name in item.required:
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
    hub = types.SimpleNamespace(list_repo_files=lambda repo: list(item.required),
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
    hub = types.SimpleNamespace(list_repo_files=lambda repo: list(item.required),
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

def _qwen_check_script(monkeypatch, tmp_path, *, complete):
    """Run the lightweight embedded script with a fake local Hub snapshot."""
    import contextlib
    import io
    hub = types.ModuleType('huggingface_hub')
    hub.snapshot_download = lambda **kwargs: tmp_path
    constants = types.ModuleType('huggingface_hub.constants')
    constants.HF_HUB_CACHE = str(tmp_path)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
    monkeypatch.setitem(sys.modules, 'huggingface_hub.constants', constants)
    monkeypatch.setattr(sys, 'argv', ['-c', 'Qwen/Qwen3-TTS-12Hz-1.7B-Base', 'check'])
    (tmp_path / 'speech_tokenizer').mkdir(exist_ok=True)
    required = [
        'config.json', 'model.safetensors', 'speech_tokenizer/config.json',
        'speech_tokenizer/model.safetensors',
    ]
    for fn in (required if complete else required[:2]):
        target = tmp_path / fn
        target.write_bytes(b'synthetic model data' * 100)
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
