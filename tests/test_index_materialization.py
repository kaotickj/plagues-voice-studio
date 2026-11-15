"""Worker-local semantic checkpoint mitigation: no real models or GPU."""
from contextlib import nullcontext
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
spec=importlib.util.spec_from_file_location('materialization_runner',Path(__file__).parents[1]/'optional_engine_runner.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class Tensor:
    def __init__(self, value, device='cpu'):
        self.value=value;self.device=SimpleNamespace(type=device)
    def clone(self):return Tensor(self.value,self.device.type)

class Model:
    def __init__(self,tensors):self.tensors=tensors
    def _apply(self,operation):self.tensors=[operation(t) for t in self.tensors];return self

def test_copies_exact_values_and_restores_loader():
    originals=[Tensor(1),Tensor(-3)];model=Model(originals);calls=[]
    def load(*args,**kwargs):calls.append((args,kwargs));return model
    loader=SimpleNamespace(from_pretrained=load);upstream=SimpleNamespace(Wav2Vec2BertModel=loader)
    with r.materialized_index_semantic_model(upstream,SimpleNamespace(no_grad=nullcontext)):
        assert upstream.Wav2Vec2BertModel.from_pretrained('local/model',local_files_only=True) is model
        assert calls==[(('local/model',),{'local_files_only':True})]
        assert [t.value for t in model.tensors]==[1,-3]
        assert all(a is not b for a,b in zip(originals,model.tensors))
    assert upstream.Wav2Vec2BertModel is loader

@pytest.mark.parametrize('failure',['load','non_cpu'])
def test_failure_restores_original_alias(failure):
    def load(*args,**kwargs):
        if failure=='load':raise ValueError('bad checkpoint')
        return Model([Tensor(1,'cuda')])
    loader=SimpleNamespace(from_pretrained=load);upstream=SimpleNamespace(Wav2Vec2BertModel=loader)
    with pytest.raises((ValueError,RuntimeError)):
        with r.materialized_index_semantic_model(upstream,SimpleNamespace(no_grad=nullcontext)):
            upstream.Wav2Vec2BertModel.from_pretrained('model')
    assert upstream.Wav2Vec2BertModel is loader

@pytest.mark.parametrize('enabled,device,hip,expected', [
    (False,'cuda:0','6.4',True), (True,'cpu','6.4',False),
    (True,'cuda:0',None,False), (True,'cuda:0','6.4',True)])
def test_mitigation_is_automatic_rocm_gpu_only(monkeypatch,enabled,device,hip,expected):
    import sys
    original=SimpleNamespace(from_pretrained=lambda *a,**kw:Model([Tensor(7)]))
    upstream=SimpleNamespace(Wav2Vec2BertModel=original)
    observed=[]
    def build(**kwargs):
        observed.append(upstream.Wav2Vec2BertModel is not original)
        model=upstream.Wav2Vec2BertModel.from_pretrained('local')
        return SimpleNamespace(infer=lambda **kw:None)
    upstream.IndexTTS2=build
    torch=SimpleNamespace(version=SimpleNamespace(hip=hip),__version__='test',
        get_num_threads=lambda:2,no_grad=nullcontext)
    monkeypatch.setitem(sys.modules,'torch',torch)
    monkeypatch.setitem(sys.modules,'indextts.infer_v2_5',upstream)
    monkeypatch.setattr(r,'_device',lambda *args:device)
    monkeypatch.setattr(r,'windows_cpu_tensor_reader',lambda:None)
    monkeypatch.setenv('PVS_INDEX_EAGER_SEMANTIC','1' if enabled else '0')
    r.index_run(dict(repo='.',voice_path='reference',text='test',language='en',output_path='unused'))
    assert observed==[expected]
    assert upstream.Wav2Vec2BertModel is original
