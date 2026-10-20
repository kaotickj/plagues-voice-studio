"""The optional Index setup patch changes only known dependency constraints."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('index_compat_test',Path(__file__).resolve().parents[1]/'scripts/patch_index_windows_compat.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_preserves_source_and_original_project_and_is_idempotent(tmp_path):
    original=b'[project]\nname="indextts"\nversion="2.0.0"\ndependencies=["safetensors==0.5.2", "opencv-python==4.9.0.80", "numpy==2.2.6"]\n'
    project=tmp_path/'pyproject.toml';project.write_bytes(original)
    source=tmp_path/'model.py';source.write_bytes(b'unchanged')
    assert module.apply(tmp_path)
    assert b'safetensors==0.8.0' in project.read_bytes()
    assert b'opencv-python==4.12.0.88' in project.read_bytes()
    assert (tmp_path/'.pvs-windows-compat/pyproject.original.toml').read_bytes()==original
    assert source.read_bytes()==b'unchanged'
    assert not module.apply(tmp_path)


def test_unknown_constraints_fail_without_modifying_project(tmp_path):
    original=b'[project]\nname="indextts"\ndependencies=["safetensors==0.9.0", "opencv-python==4.9.0.80"]\n'
    project=tmp_path/'pyproject.toml';project.write_bytes(original)
    with pytest.raises(RuntimeError,match='Unrecognized'):
        module.apply(tmp_path)
    assert project.read_bytes()==original
