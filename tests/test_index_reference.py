"""Reference conditioning stays independent of speaker identity and cache state."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('reference_runner', Path(__file__).parents[1] / 'optional_engine_runner.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class Tensor:
    def __init__(self, value): self.value = np.asarray(value)
    @property
    def shape(self): return self.value.shape
    @property
    def ndim(self): return self.value.ndim
    def numel(self): return self.value.size
    def __getitem__(self, key): return Tensor(self.value[key])
    def __sub__(self, value): return Tensor(self.value - value)
    def new_zeros(self, shape): return Tensor(np.zeros(shape))

def cat(values, dim): return Tensor(np.concatenate([v.value for v in values], axis=dim))

@pytest.fixture
def model():
    calls = []
    def inference(mu, x_lens, prompt, style, f0, n_timesteps, **kwargs):
        calls.append((mu, x_lens, prompt, style, n_timesteps, kwargs))
        return Tensor(mu.value[:, :, :1].transpose(0, 2, 1))
    cfm = SimpleNamespace(inference=inference)
    m = SimpleNamespace(s2mel=SimpleNamespace(models={'cfm':cfm}),
        cfg=SimpleNamespace(s2mel={'preprocess_params':{'sr':22050,'spect_params':{'hop_length':256}}}),
        cache_spk_cond=object(), cache_s2mel_style=object(), cache_mel=object())
    return m, cfm, inference, calls

@pytest.mark.parametrize('full', [200, 1292])
def test_fast_output_exactly_matches_truncated_prompt_and_keeps_identity(model, full):
    m, cfm, original, calls = model
    identity, style, mel = m.cache_spk_cond, m.cache_s2mel_style, m.cache_mel
    mu=Tensor(np.arange(full+100).reshape(1,-1,1));prompt=Tensor(np.ones((1,80,full)));length=Tensor([full+100])
    with r.index_reference_conditioning(m,5,SimpleNamespace(cat=cat)):
        out=cfm.inference(mu,length,prompt,style,None,25,inference_cfg_rate=.7)
        # Upstream discards the original full prompt before vocoding.
        assert np.array_equal(out.value[:,:,full:], mu.value[:,full:,:].transpose(0,2,1))
    used=min(full,int(5*22050/256))
    assert calls[0][0].shape[1]==used+100
    assert calls[0][1].value.tolist()==[used+100]
    assert calls[0][2].shape[-1]==used
    assert calls[0][3] is style and calls[0][4]==25
    assert calls[0][5]=={'inference_cfg_rate':.7}
    assert m.cache_spk_cond is identity and m.cache_s2mel_style is style and m.cache_mel is mel
    assert cfm.inference is original


def test_fast_full_fast_does_not_mutate_cached_prompts(model):
    m,cfm,original,calls=model
    for seconds, expected in [(5,430),(0,1000),(5,430)]:
        with r.index_reference_conditioning(m,seconds,SimpleNamespace(cat=cat)):
            cfm.inference(Tensor(np.zeros((1,1100,2))),Tensor([1100]),Tensor(np.ones((1,80,1000))),None,None,25)
        assert calls[-1][2].shape[-1]==expected
        assert cfm.inference is original


def test_incompatible_runtime_uses_original_full_reference(model):
    m,cfm,original,calls=model
    m.cfg.s2mel['preprocess_params']['sr']=24000
    with r.index_reference_conditioning(m,5,SimpleNamespace(cat=cat)):
        assert cfm.inference is original
    assert m._pvs_reference_seconds==0
    assert 'using full reference' in m._pvs_reference_note


def test_exception_restores_method(model):
    m,cfm,original,calls=model
    with pytest.raises(RuntimeError):
        with r.index_reference_conditioning(m,5,SimpleNamespace(cat=cat)):
            raise RuntimeError('test')
    assert cfm.inference is original


def test_same_path_replacement_and_new_voice_invalidate_all_speaker_caches(tmp_path):
    path=tmp_path/'voice.wav';path.write_bytes(b'first')
    m=SimpleNamespace()
    r.refresh_index_reference(m,path)
    names=('cache_spk_cond','cache_s2mel_style','cache_s2mel_prompt','cache_spk_audio_prompt','cache_mel')
    for name in names: setattr(m,name,'cached')
    r.refresh_index_reference(m,path)
    assert m.cache_spk_cond=='cached'
    path.write_bytes(b'replacement')
    r.refresh_index_reference(m,path)
    assert all(getattr(m,name) is None for name in names)
    for name in names: setattr(m,name,'cached')
    other=tmp_path/'other.wav';other.write_bytes(b'new')
    r.refresh_index_reference(m,other)
    assert all(getattr(m,name) is None for name in names)

@pytest.mark.parametrize('seconds',[-1,1,15,True,'5',float('nan')])
def test_unsupported_reference_setting_rejected_before_model_import(seconds):
    with pytest.raises(ValueError,match='5-second'):
        r.index_run({'reference_seconds':seconds})
