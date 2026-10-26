"""Independent CPU FFT references and temporary thread-local mode contracts."""
import ast
import json
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread

import pytest
import torch
from torch.overrides import _get_current_function_mode_stack

from chatterbox_studio.rocm_reference_fft import (
    _BasisCache, _direct_rfft, _direct_stft, _make_mode,
    ReferenceFFTCompatibilityError, install_rocm_reference_fft_compat,
)

torch.set_num_threads(2)


@pytest.fixture(scope='module')
def cache():
    return _BasisCache()


def check(actual, expected, record_property, dtype):
    difference = actual - expected
    record_property('max_abs', difference.abs().max().item())
    record_property('rms', difference.abs().square().mean().sqrt().item())
    torch.testing.assert_close(actual, expected, atol=2e-4 if dtype == torch.float32 else 2e-9,
                               rtol=2e-5 if dtype == torch.float32 else 2e-10)
    assert actual.device == expected.device and actual.dtype == expected.dtype


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64])
@pytest.mark.parametrize('n', [16, 400, 512, 1920])
@pytest.mark.parametrize('norm', [None, 'forward', 'ortho'])
def test_rfft_matches_trim_pad_last_dimension_and_norm(cache, dtype, n, norm, record_property):
    value = torch.randn(2, 3, n + 13, dtype=dtype, generator=torch.Generator().manual_seed(n))
    value = value[..., ::2]  # Noncontiguous and shorter than the explicit FFT size.
    actual = _direct_rfft(value, n=n, dim=2, norm=norm, _cache=cache)
    expected = torch.fft.rfft(value, n=n, dim=2, norm=norm)
    check(actual, expected, record_property, dtype)
    long = torch.cat((value, value, value), dim=-1)
    check(_direct_rfft(long, n=n, _cache=cache), torch.fft.rfft(long, n=n), record_property, dtype)


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64])
@pytest.mark.parametrize('n,hop,center', [(16, 4, True), (400, 160, True), (1920, 480, False)])
@pytest.mark.parametrize('normalized', [False, True])
def test_stft_matches_known_reference_frontends(cache, dtype, n, hop, center, normalized, record_property):
    value = torch.randn(2, n * 3 + 23, dtype=dtype, generator=torch.Generator().manual_seed(n + 89))
    if not center:
        # Match the upstream mel extractor's pre-existing manual reflect pad.
        value = torch.nn.functional.pad(value.unsqueeze(1), ((n-hop)//2, (n-hop)//2), mode='reflect').squeeze(1)
    window = torch.hann_window(n, dtype=dtype, periodic=True)
    kwargs = dict(n_fft=n, hop_length=hop, window=window, center=center, pad_mode='reflect',
                  normalized=normalized, onesided=True, return_complex=True)
    check(_direct_stft(value, _cache=cache, **kwargs), torch.stft(value, **kwargs), record_property, dtype)
    check(_direct_stft(value[0], _cache=cache, **kwargs), torch.stft(value[0], **kwargs), record_property, dtype)


def metadata():
    return {'counters': dict.fromkeys(('stft_replaced', 'rfft_replaced', 'cpu_fft_forwarded', 'unsupported_fft_calls'), 0)}


def test_mode_dispatches_keyword_calls_and_forwards_unrelated_functions(cache):
    state = metadata()
    value = torch.randn(2, 512)
    expected = torch.fft.rfft(value, norm='backward')
    with _make_mode(cache, state, device_types=('cpu',)):
        actual = torch.fft.rfft(input=value, norm='backward')
        torch.testing.assert_close(torch.sin(value), value.sin())
    torch.testing.assert_close(actual, expected, atol=2e-4, rtol=2e-5)
    assert state['counters']['rfft_replaced'] == 1
    assert _get_current_function_mode_stack() == []


def test_mode_dispatches_stft_keyword_contract(cache):
    state = metadata()
    value, window = torch.randn(2, 1300), torch.hann_window(400)
    kwargs = dict(input=value, n_fft=400, hop_length=160, window=window, return_complex=True)
    expected = torch.stft(**kwargs)
    with _make_mode(cache, state, device_types=('cpu',)):
        actual = torch.stft(**kwargs)
    torch.testing.assert_close(actual, expected, atol=2e-4, rtol=2e-5)
    assert state['counters']['stft_replaced'] == 1 and state['counters']['rfft_replaced'] == 0
    assert _get_current_function_mode_stack() == []


def test_replacement_exception_escapes_and_restores_mode_stack(cache):
    state = metadata()
    value, window = torch.ones(1200), torch.hann_window(400)
    with pytest.raises(ReferenceFFTCompatibilityError):
        with _make_mode(cache, state, device_types=('cpu',)):
            torch.stft(value, 400, 100, window=window, return_complex=True)
    assert state['counters']['unsupported_fft_calls'] == 1
    assert _get_current_function_mode_stack() == []
    # This is a valid native CPU call outside the known scoped GPU contract.
    assert torch.stft(value, 400, 100, window=window, return_complex=True).shape[0] == 201


def test_thread_local_cleanup_on_error_and_no_global_function_or_thread_leak(cache):
    original_rfft, original_stft = torch.fft.rfft, torch.stft
    state = metadata()
    entered, release, done = Event(), Event(), Event()
    failures = []
    def worker():
        try:
            with _make_mode(cache, state, device_types=('cpu',)):
                entered.set()
                assert release.wait(3)
                with pytest.raises(ReferenceFFTCompatibilityError):
                    torch.fft.rfft(torch.ones(128))
            assert _get_current_function_mode_stack() == []
        except BaseException as error:
            failures.append(error)
        finally:
            done.set()
    thread = Thread(target=worker)
    thread.start()
    try:
        assert entered.wait(3)
        # The other thread's unsupported FFT size must still use native Torch.
        assert torch.fft.rfft(torch.ones(128)).shape == (65,)
        assert _get_current_function_mode_stack() == []
    finally:
        release.set()
        thread.join(3)
    assert done.is_set() and not failures
    assert torch.fft.rfft is original_rfft and torch.stft is original_stft
    assert state['counters']['unsupported_fft_calls'] == 1


def test_installer_preserves_original_controls_and_only_wraps_one_instance():
    class Model:
        def __init__(self): self.calls = []
        def prepare_conditionals(self, value, exaggeration=0.5, norm_loudness=True):
            self.calls.append((value, exaggeration, norm_loudness))
            return torch.fft.rfft(value)
    model, other = Model(), Model()
    original_class = Model.prepare_conditionals
    original_rfft = torch.fft.rfft
    state = install_rocm_reference_fft_compat(model)
    assert install_rocm_reference_fft_compat(model) is state
    value = torch.randn(512)
    torch.testing.assert_close(model.prepare_conditionals(value, exaggeration=0.31, norm_loudness=False),
                               torch.fft.rfft(value))
    assert model.calls == [(value, 0.31, False)]
    assert state['counters']['prepare_completed'] == state['counters']['prepare_calls'] == 1
    assert state['counters']['cpu_fft_forwarded'] == 1 and state['counters']['rfft_replaced'] == 0
    assert Model.prepare_conditionals is original_class and other.prepare_conditionals.__func__ is original_class
    assert torch.fft.rfft is original_rfft and _get_current_function_mode_stack() == []
    json.dumps(state)


def test_installer_mode_is_removed_when_original_method_raises():
    class Model:
        def prepare_conditionals(self, value):
            torch.fft.rfft(value)
            raise RuntimeError('original reference error')
    state = install_rocm_reference_fft_compat(model := Model())
    with pytest.raises(RuntimeError, match='original reference error'):
        model.prepare_conditionals(torch.ones(512))
    assert _get_current_function_mode_stack() == []
    assert state['counters']['prepare_failures'] == 1


@pytest.mark.parametrize('kwargs', [dict(n=128), dict(n=512, dim=0), dict(n=512, norm='bad'), dict(n=512, out=torch.empty(257, dtype=torch.complex64))])
def test_rfft_unsupported_calls_fail_without_fallback(cache, kwargs):
    with pytest.raises(ReferenceFFTCompatibilityError):
        _direct_rfft(torch.ones(2, 512), _cache=cache, **kwargs)


@pytest.mark.parametrize('changed', [dict(hop_length=100), dict(center=False), dict(pad_mode='constant'),
                                    dict(win_length=200), dict(onesided=False), dict(return_complex=False)])
def test_stft_unsupported_contract_fails(cache, changed):
    kwargs = dict(n_fft=400, hop_length=160, window=torch.hann_window(400), return_complex=True)
    with pytest.raises(ReferenceFFTCompatibilityError):
        _direct_stft(torch.ones(2, 1200), _cache=cache, **(kwargs | changed))


def test_constant_cache_is_bounded_and_excludes_input_data(cache):
    stats = cache.stats()
    assert stats['cpu_constant_bytes'] <= stats['cpu_limit_bytes']
    assert stats['device_constant_bytes'] <= stats['device_limit_bytes']
    assert set(stats['resident_sizes']) <= {16, 400, 512, 1920}
    with pytest.raises(ReferenceFFTCompatibilityError, match='bound'):
        _direct_rfft(torch.ones(512), _cache=_BasisCache(cpu_limit=1024))


def test_import_is_lazy_and_source_has_no_global_torch_patch_or_input_cpu_transfer():
    source = Path(__file__).resolve().parents[1] / 'src/chatterbox_studio/rocm_reference_fft.py'
    tree = ast.parse(source.read_text())
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr in ('cpu', 'numpy')]
    code = 'import sys; sys.path.insert(0,' + repr(str(source.parents[1])) + '); import chatterbox_studio.rocm_reference_fft; assert "torch" not in sys.modules'
    result = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


def test_scoped_complex_magnitude_matches_hypot():
    import torch
    from chatterbox_studio.rocm_reference_fft import _make_mode, _BasisCache
    value = torch.complex(torch.tensor([0., 3., 1e20, 1e-20]), torch.tensor([0., 4., 1e20, 1e-20]))
    expected = value.abs()
    metadata = {'counters': {}}
    with _make_mode(_BasisCache(), metadata, device_types=('cpu',)):
        actual = value.abs()
        other = torch.abs(value)
    torch.testing.assert_close(actual, expected)
    torch.testing.assert_close(other, expected)
    assert metadata['counters']['complex_abs_replaced'] == 2
