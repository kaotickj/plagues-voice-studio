"""Regression coverage for Windows checkpoint reading and offline Qwen processors."""
import importlib.util
from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def runner():
    spec=importlib.util.spec_from_file_location('speech_runner_test',Path(__file__).resolve().parents[1]/'optional_engine_runner.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_cpu_reader_patches_only_process_aliases(runner,monkeypatch):
    calls=[]
    def safe_open(filename,framework,device='cpu',*,backend='mmap'):
        calls.append((filename,framework,device,backend))
        return 'reader'
    tensors=types.ModuleType('safetensors');tensors.__path__=[]
    torch=types.ModuleType('safetensors.torch')
    tensors.safe_open=safe_open;tensors.torch=torch;torch.safe_open=safe_open
    transformers=types.ModuleType('transformers.modeling_utils');transformers.safe_open=safe_open
    for name,mod in [('safetensors',tensors),('safetensors.torch',torch),('transformers.modeling_utils',transformers)]:
        monkeypatch.setitem(sys.modules,name,mod)
    monkeypatch.setattr(sys,'platform','win32')
    runner.windows_cpu_tensor_reader()
    wrapper=tensors.safe_open
    runner.windows_cpu_tensor_reader()
    assert tensors.safe_open is wrapper  # idempotent; no recursive wrapper
    assert torch.safe_open is wrapper and transformers.safe_open is wrapper
    assert wrapper('weights',framework='pt',device='cpu')=='reader'
    assert calls==[('weights','pt','cpu','pread')]


def test_old_windows_reader_reports_required_setup(runner,monkeypatch):
    tensors=types.ModuleType('safetensors');tensors.__path__=[]
    torch=types.ModuleType('safetensors.torch');tensors.torch=torch
    tensors.safe_open=lambda filename,framework,device='cpu':None
    monkeypatch.setitem(sys.modules,'safetensors',tensors)
    monkeypatch.setitem(sys.modules,'safetensors.torch',torch)
    monkeypatch.setattr(sys,'platform','win32')
    with pytest.raises(RuntimeError,match='safetensors 0.8.0'):
        runner.windows_cpu_tensor_reader()


def test_non_windows_reader_unchanged(runner,monkeypatch):
    monkeypatch.setattr(sys,'platform','linux')
    runner.windows_cpu_tensor_reader()  # no dependency import required


def test_cached_qwen_includes_offline_processor_assets(runner,monkeypatch,tmp_path):
    names=['config.json','tokenizer_config.json','vocab.json','merges.txt','generation_config.json',
           'preprocessor_config.json','model.safetensors','speech_tokenizer/config.json',
           'speech_tokenizer/model.safetensors','speech_tokenizer/preprocessor_config.json']
    for name in names:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'x')
    calls=[]
    def cached(**kwargs):calls.append(kwargs);return str(tmp_path)
    monkeypatch.setitem(sys.modules,'huggingface_hub',types.SimpleNamespace(snapshot_download=cached))
    assert runner.qwen_model_source('Qwen/model')==str(tmp_path)
    assert calls==[{'repo_id':'Qwen/model','local_files_only':True}]
    (tmp_path/'speech_tokenizer/model.safetensors').unlink()
    assert runner.qwen_model_source('Qwen/model')=='Qwen/model'


def test_qwen_missing_cache_and_explicit_path(runner,monkeypatch,tmp_path):
    def missing(**kwargs):raise FileNotFoundError('not cached')
    monkeypatch.setitem(sys.modules,'huggingface_hub',types.SimpleNamespace(snapshot_download=missing))
    assert runner.qwen_model_source('Qwen/model')=='Qwen/model'
    assert runner.qwen_model_source(str(tmp_path))==str(tmp_path)
