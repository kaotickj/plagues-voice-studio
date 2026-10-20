"""The Windows -FullOffline builder must not invoke a missing verification script."""
import importlib.util
from pathlib import Path
import sys
import pytest

scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
from verify_models import verify, REQUIRED


def test_required_model_files_and_marker(tmp_path, monkeypatch):
    monkeypatch.setattr('verify_models.pkuseg_ready', lambda folder: True)
    for model, names in REQUIRED.items():
        (tmp_path / model).mkdir()
        for name in names:
            (tmp_path / model / name).write_bytes(b'header')
    verify(tmp_path, write_marker=True)
    verify(tmp_path, require_marker=True)
    (tmp_path / 'nano' / REQUIRED['nano'][0]).unlink()
    with pytest.raises(RuntimeError, match='Missing or empty'):
        verify(tmp_path, require_marker=True)


def test_offline_bundle_rejects_missing_tokenizer(tmp_path):
    for model, names in REQUIRED.items():
        (tmp_path/model).mkdir()
        for name in names:
            (tmp_path/model/name).write_bytes(b'header')
    with pytest.raises(RuntimeError, match='tokenizers/pkuseg'):
        verify(tmp_path, write_marker=True)
    assert not (tmp_path/'offline-bundle.json').exists()
