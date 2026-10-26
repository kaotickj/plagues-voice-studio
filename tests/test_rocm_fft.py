"""CPU equivalence with independent Torch FFT references; no model/GPU loads."""
import ast
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import torch

from chatterbox_studio.rocm_fft import install_rocm_fft_compat


torch.set_num_threads(2)


class HiFT:
    def __init__(self, dtype=torch.float32):
        self.istft_params = {'n_fft': 16, 'hop_len': 4}
        self.stft_window = torch.hann_window(16, periodic=True, dtype=dtype)

    def _stft(self, value):
        return 'unmodified stft'

    def _istft(self, magnitude, phase):
        return 'unmodified istft'


def installed(dtype=torch.float32):
    target = HiFT(dtype)
    model = SimpleNamespace(s3gen=SimpleNamespace(mel2wav=target))
    metadata = install_rocm_fft_compat(model)
    return target, model, metadata


def reference_stft(value, window):
    return torch.stft(value, 16, 4, 16, window=window, center=True, pad_mode='reflect',
                      normalized=False, onesided=True, return_complex=True)


def reference_istft(magnitude, phase, window):
    clipped = torch.clip(magnitude, max=100)
    spectrum = torch.complex(clipped * torch.cos(phase), clipped * torch.sin(phase))
    return torch.istft(spectrum, 16, 4, 16, window=window, center=True, normalized=False,
                       onesided=True, return_complex=False)


def compare(actual, expected, record_property, kind, precision=None):
    error = actual - expected
    record_property(kind + '_max_abs', error.abs().max().item())
    record_property(kind + '_rms', error.square().mean().sqrt().item())
    comparison_dtype = precision or actual.dtype
    record_property(kind + '_precision', str(comparison_dtype))
    atol, rtol = (1e-5, 2e-6) if comparison_dtype == torch.float32 else (2e-12, 2e-12)
    torch.testing.assert_close(actual, expected, atol=atol, rtol=rtol)
    assert actual.dtype == expected.dtype and actual.device == expected.device


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64])
@pytest.mark.parametrize('batch,length', [(1, 9), (2, 16), (3, 19), (2, 64), (1, 257), (2, 1024)])
def test_stft_matches_cpu_reference(dtype, batch, length, record_property):
    target, _, _ = installed(dtype)
    generator = torch.Generator().manual_seed(8123 + length)
    value = torch.randn(batch, length, generator=generator, dtype=dtype)
    expected = reference_stft(value, target.stft_window)
    real, imaginary = target._stft(value)
    assert real.shape == imaginary.shape == expected.shape == (batch, 9, length // 4 + 1)
    compare(real, expected.real, record_property, 'real')
    compare(imaginary, expected.imag, record_property, 'imaginary')


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64])
@pytest.mark.parametrize('batch,frames', [(1, 2), (2, 3), (3, 17), (2, 64)])
def test_arbitrary_spectra_and_clipping_match_cpu_reference(dtype, batch, frames, record_property):
    target, _, _ = installed(dtype)
    generator = torch.Generator().manual_seed(938 + frames)
    magnitude = torch.rand(batch, 9, frames, generator=generator, dtype=dtype) * 300 - 80
    phase = (torch.rand(batch, 9, frames, generator=generator, dtype=dtype) * 2 - 1) * torch.pi
    expected = reference_istft(magnitude, phase, target.stft_window)
    actual = target._istft(magnitude, phase)
    assert actual.shape == (batch, 4 * (frames - 1))
    compare(actual, expected, record_property, 'inverse')


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64])
@pytest.mark.parametrize('length', [12, 64, 259, 1024])
def test_roundtrip_matches_default_center_trim_and_original_prefix(dtype, length, record_property):
    target, _, _ = installed(dtype)
    value = torch.randn(2, length, generator=torch.Generator().manual_seed(length), dtype=dtype) * 0.2
    real, imaginary = target._stft(value)
    magnitude = torch.sqrt(real.square() + imaginary.square())
    phase = torch.atan2(imaginary, real)
    actual = target._istft(magnitude, phase)
    spectrum = reference_stft(value, target.stft_window)
    expected = reference_istft(spectrum.abs(), spectrum.angle(), target.stft_window)
    compare(actual, expected, record_property, 'roundtrip_reference')
    compare(actual, value[:, :length // 4 * 4], record_property, 'roundtrip_original')


@pytest.mark.parametrize('dtype', [torch.float32, torch.float64])
def test_noncontiguous_input_with_original_float32_window(dtype, record_property):
    # HiFT stores a double-calculated periodic Hann rounded to float32, even
    # when a caller uses float64 input. Match that retained window's values.
    target = HiFT()
    target.stft_window = torch.hann_window(16, periodic=True, dtype=torch.float64).float()
    install_rocm_fft_compat(SimpleNamespace(s3gen=SimpleNamespace(mel2wav=target)))
    value = torch.randn(2, 194, generator=torch.Generator().manual_seed(458), dtype=dtype)[:, ::2]
    assert not value.is_contiguous()
    expected = reference_stft(value, target.stft_window)
    real, imaginary = target._stft(value)
    compare(real, expected.real, record_property, 'source_window_real')
    compare(imaginary, expected.imag, record_property, 'source_window_imaginary')
    actual = target._istft(expected.abs(), expected.angle())
    # The retained float32 window also produces a float32 normalization
    # envelope. fold and Torch ISTFT may add its overlaps in different orders;
    # a float64 signal does not restore precision lost in that envelope.
    compare(actual, reference_istft(expected.abs(), expected.angle(), target.stft_window),
            record_property, 'source_window_inverse', precision=target.stft_window.dtype)


def test_only_one_instance_methods_are_bound_and_reinstallation_is_not_a_wrapper():
    target = HiFT()
    untouched = HiFT()
    original_window = target.stft_window
    original_keys = set(vars(target))
    model = SimpleNamespace(s3gen=SimpleNamespace(mel2wav=target))
    first = install_rocm_fft_compat(model)
    second = install_rocm_fft_compat(model)
    assert json.loads(json.dumps(first)) == second
    assert set(vars(target)) - original_keys == {'_stft', '_istft'}
    assert target.stft_window is original_window
    assert untouched._stft(None) == 'unmodified stft'
    assert HiFT._stft(target, None) == 'unmodified stft'
    assert target._stft.__self__ is target and target._istft.__self__ is target


@pytest.mark.parametrize('change', ['nfft', 'hop', 'extra', 'symmetric', 'changed_window', 'shape', 'missing_method'])
def test_unsupported_configuration_fails_before_changing_either_method(change):
    target = HiFT()
    if change == 'nfft': target.istft_params['n_fft'] = 32
    elif change == 'hop': target.istft_params['hop_len'] = 8
    elif change == 'extra': target.istft_params['center'] = False
    elif change == 'symmetric': target.stft_window = torch.hann_window(16, periodic=False)
    elif change == 'changed_window': target.stft_window[3] += 0.01
    elif change == 'shape': target.stft_window = target.stft_window.unsqueeze(0)
    elif change == 'missing_method': target._istft = None
    before = vars(target).copy()
    with pytest.raises(ValueError, match='HiFT'):
        install_rocm_fft_compat(SimpleNamespace(s3gen=SimpleNamespace(mel2wav=target)))
    assert vars(target).keys() == before.keys()
    assert all(vars(target)[key] is value for key, value in before.items())


def test_input_dtype_shape_and_pair_contracts_are_explicit():
    target, _, _ = installed()
    with pytest.raises(ValueError): target._stft(torch.zeros(1, 8))
    with pytest.raises(ValueError): target._stft(torch.zeros(1, 32, dtype=torch.float16))
    with pytest.raises(ValueError): target._istft(torch.ones(1, 8, 3), torch.ones(1, 8, 3))
    with pytest.raises(ValueError): target._istft(torch.ones(1, 9, 3), torch.ones(1, 9, 3, dtype=torch.float64))
    double_window, _, _ = installed(torch.float64)
    with pytest.raises(ValueError): double_window._stft(torch.zeros(1, 32, dtype=torch.float32))


def test_import_is_lazy_and_helper_contains_no_fft_or_cpu_transfer_calls():
    source = Path(__file__).resolve().parents[1] / 'src/chatterbox_studio/rocm_fft.py'
    tree = ast.parse(source.read_text())
    forbidden = {'stft', 'istft', 'rfft', 'irfft', 'fft', 'ifft', 'cpu', 'numpy'}
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr in forbidden]
    code = 'import sys; sys.path.insert(0,' + repr(str(source.parents[1])) + '); import chatterbox_studio.rocm_fft; assert "torch" not in sys.modules'
    result = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
