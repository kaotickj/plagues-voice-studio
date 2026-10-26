"""Scoped reference-frontend transforms, without FFT runtime calls.

Only one model's prepare_conditionals method is wrapped. The mode is thread
local and replaces CUDA/HIP STFT/RFFT calls only during that invocation. CPU
calls and all other Torch functions retain their original implementation.
"""
from __future__ import annotations

from collections import OrderedDict
from functools import wraps
import math
from threading import RLock


_SIZES = (16, 400, 512, 1920)
_STFT = {16: (4, True), 400: (160, True), 1920: (480, False)}


class ReferenceFFTCompatibilityError(ValueError):
    """An intercepted call falls outside the qualified reference contract."""


class _BasisCache:
    """LRU constants only; never retains reference waveforms or their outputs."""
    def __init__(self, cpu_limit=40 * 1024 ** 2, device_limit=64 * 1024 ** 2):
        self.cpu_limit, self.device_limit = cpu_limit, device_limit
        self.cpu, self.device = OrderedDict(), OrderedDict()
        self.lock = RLock()

    @staticmethod
    def _bytes(tables):
        return sum(value.numel() * value.element_size() for value in tables)

    def get(self, n, value):
        import torch
        key = (n, value.device, value.dtype)
        with self.lock:
            if key in self.device:
                self.device.move_to_end(key)
                return self.device[key]
            if 2 * (n // 2 + 1) * n * 8 > self.cpu_limit:
                raise ReferenceFFTCompatibilityError('Reference DFT constants exceed the CPU constant-cache bound.')
            needed = 2 * (n // 2 + 1) * n * value.element_size()
            if needed > self.device_limit:
                raise ReferenceFFTCompatibilityError('Reference DFT constants exceed the device constant-cache bound.')
            if n not in self.cpu:
                while self.cpu and sum(self._bytes(t) for t in self.cpu.values()) + 2 * (n // 2 + 1) * n * 8 > self.cpu_limit:
                    self.cpu.popitem(last=False)
                # Host-generated data are fixed DFT constants, never inputs.
                bins = torch.arange(n // 2 + 1, dtype=torch.float64, device='cpu')
                samples = torch.arange(n, dtype=torch.float64, device='cpu')
                angle = torch.outer(bins, samples) * (2 * math.pi / n)
                cosine, sine = angle.cos(), angle.sin()
                sine[0].zero_()
                sine[-1].zero_()
                cosine[0].fill_(1)
                cosine[-1] = 1 - 2 * (samples.remainder(2))
                self.cpu[n] = (cosine, sine)
            self.cpu.move_to_end(n)
            while self.device and sum(self._bytes(t) for t in self.device.values()) + needed > self.device_limit:
                self.device.popitem(last=False)
            self.device[key] = tuple(table.to(device=value.device, dtype=value.dtype) for table in self.cpu[n])
            return self.device[key]

    def stats(self):
        with self.lock:
            return {'cpu_constant_bytes': sum(self._bytes(t) for t in self.cpu.values()),
                    'device_constant_bytes': sum(self._bytes(t) for t in self.device.values()),
                    'cpu_limit_bytes': self.cpu_limit, 'device_limit_bytes': self.device_limit,
                    'resident_sizes': sorted(self.cpu), 'device_entries': len(self.device)}


def _direct_rfft(input, n=None, dim=-1, norm=None, *, out=None, _cache=None):
    import torch
    import torch.nn.functional as functional
    if not isinstance(input, torch.Tensor) or input.ndim < 1 or input.dtype not in (torch.float32, torch.float64):
        raise ReferenceFFTCompatibilityError('Reference RFFT requires a real float32/float64 tensor.')
    if dim not in (-1, input.ndim - 1) or out is not None:
        raise ReferenceFFTCompatibilityError('Reference RFFT supports the last dimension and no out tensor only.')
    length = input.shape[-1] if n is None else n
    if type(length) is not int or length not in _SIZES:
        raise ReferenceFFTCompatibilityError('Reference RFFT supports lengths 16, 400, 512 and 1920 only.')
    if norm not in (None, 'backward', 'forward', 'ortho'):
        raise ReferenceFFTCompatibilityError('Unsupported reference RFFT normalization.')
    value = input[..., :length]
    if value.shape[-1] < length:
        value = functional.pad(value, (0, length - value.shape[-1]))
    cosine, sine = (_cache or _BasisCache()).get(length, value)
    real = value @ cosine.transpose(0, 1)
    imaginary = -(value @ sine.transpose(0, 1))
    scale = 1 / length if norm == 'forward' else 1 / math.sqrt(length) if norm == 'ortho' else 1
    return torch.complex(real * scale, imaginary * scale)


def _direct_stft(input, n_fft, hop_length=None, win_length=None, window=None, center=True,
                 pad_mode='reflect', normalized=False, onesided=None, return_complex=None,
                 *, align_to_window=None, _cache=None):
    import torch
    import torch.nn.functional as functional
    if (not isinstance(input, torch.Tensor) or input.ndim not in (1, 2)
            or input.dtype not in (torch.float32, torch.float64)):
        raise ReferenceFFTCompatibilityError('Reference STFT requires real one/two-dimensional float32/float64 input.')
    if type(n_fft) is not int or n_fft not in _STFT:
        raise ReferenceFFTCompatibilityError('Reference STFT supports the known 16/400/1920 frontend contracts only.')
    hop = n_fft // 4 if hop_length is None else hop_length
    width = n_fft if win_length is None else win_length
    if ((hop, center) != _STFT[n_fft] or width != n_fft or type(hop) is not int
            or type(center) is not bool or type(normalized) is not bool
            or pad_mode != 'reflect' or onesided not in (None, True)
            or return_complex is not True or align_to_window not in (None, False)):
        raise ReferenceFFTCompatibilityError('Unsupported reference STFT hop/window/center/pad/normalization/output contract.')
    if (not isinstance(window, torch.Tensor) or window.shape != (n_fft,)
            or window.device != input.device or window.dtype not in (torch.float32, torch.float64)):
        raise ReferenceFFTCompatibilityError('Reference STFT requires the full periodic Hann on the input device.')
    expected = torch.hann_window(n_fft, periodic=True, dtype=window.dtype, device=window.device)
    if not torch.allclose(window, expected, atol=2e-6 if window.dtype == torch.float32 else 2e-12, rtol=0):
        raise ReferenceFFTCompatibilityError('Reference STFT window is not the qualified periodic Hann.')
    value = input.unsqueeze(0) if input.ndim == 1 else input
    if center:
        if value.shape[-1] <= n_fft // 2:
            raise ReferenceFFTCompatibilityError('Reference STFT input is too short for reflect centering.')
        value = functional.pad(value.unsqueeze(1), (n_fft // 2, n_fft // 2), mode='reflect').squeeze(1)
    elif value.shape[-1] < n_fft:
        raise ReferenceFFTCompatibilityError('Reference STFT input is shorter than its uncentered window.')
    frames = value.unfold(-1, n_fft, hop) * window
    spectrum = _direct_rfft(frames, n=n_fft, norm='ortho' if normalized else None, _cache=_cache).transpose(-1, -2)
    return spectrum.squeeze(0) if input.ndim == 1 else spectrum


def _make_mode(cache, metadata, *, device_types=('cuda',)):
    import torch
    from torch.overrides import TorchFunctionMode

    class ReferenceFFTMode(TorchFunctionMode):
        def __torch_function__(self, func, types, args=(), kwargs=None):
            kwargs = kwargs or {}
            # HIP's complex abs kernel crashes on this qualified runtime.
            # Keep the same magnitude on-device using real component arithmetic.
            if func in (torch.abs, torch.absolute, torch.Tensor.abs, torch.Tensor.absolute):
                value = args[0] if args else kwargs.get('input')
                if (isinstance(value, torch.Tensor) and value.is_complex()
                        and value.device.type in device_types):
                    if kwargs.get('out') is not None:
                        raise ReferenceFFTCompatibilityError('Complex magnitude out tensors are unsupported.')
                    parts = torch.view_as_real(value)
                    # Scale first, matching hypot and avoiding overflow/underflow.
                    scale = torch.maximum(parts[..., 0].abs(), parts[..., 1].abs())
                    safe = torch.where(scale == 0, torch.ones_like(scale), scale)
                    result = scale * torch.sqrt((parts / safe.unsqueeze(-1)).square().sum(-1))
                    metadata['counters']['complex_abs_replaced'] = metadata['counters'].get('complex_abs_replaced', 0) + 1
                    return result
            if func is torch.stft or func is torch.fft.rfft:
                value = args[0] if args else kwargs.get('input')
                if isinstance(value, torch.Tensor) and value.device.type in device_types:
                    kind = 'stft_replaced' if func is torch.stft else 'rfft_replaced'
                    try:
                        result = (_direct_stft if func is torch.stft else _direct_rfft)(*args, **kwargs, _cache=cache)
                    except (ReferenceFFTCompatibilityError, TypeError):
                        metadata['counters']['unsupported_fft_calls'] += 1
                        raise
                    metadata['counters'][kind] += 1
                    return result
                metadata['counters']['cpu_fft_forwarded'] += 1
            return func(*args, **kwargs)

    return ReferenceFFTMode()


def install_rocm_reference_fft_compat(model) -> dict:
    """Return live JSON provenance/counters for this instance's scoped wrapper.

    The returned dictionary updates after each conditioning invocation. Record
    it after preparation. No tensor/reference content is stored in that state.
    """
    original = getattr(model, 'prepare_conditionals', None)
    if not callable(original):
        raise ReferenceFFTCompatibilityError('Reference FFT compatibility requires model.prepare_conditionals.')
    existing = getattr(original, '_rocm_reference_fft_metadata', None)
    if existing is not None:
        return existing
    cache = _BasisCache()
    metadata = {'method': 'thread_local_direct_reference_dft',
                'scope': 'GPU STFT/RFFT/complex magnitude inside this instance.prepare_conditionals',
                'supported_rfft_sizes': list(_SIZES),
                'supported_stft': {str(n): {'hop': hop, 'center': center} for n, (hop, center) in _STFT.items()},
                'cpu_fallback': False,
                'counters': dict.fromkeys(('prepare_calls', 'prepare_completed', 'prepare_failures',
                                          'stft_replaced', 'rfft_replaced', 'cpu_fft_forwarded',
                                          'unsupported_fft_calls', 'complex_abs_replaced'), 0),
                'cache': cache.stats()}

    @wraps(original)
    def prepare(*args, **kwargs):
        metadata['counters']['prepare_calls'] += 1
        try:
            with _make_mode(cache, metadata):
                result = original(*args, **kwargs)
        except BaseException:
            metadata['counters']['prepare_failures'] += 1
            raise
        else:
            metadata['counters']['prepare_completed'] += 1
            return result
        finally:
            metadata['cache'] = cache.stats()

    prepare._rocm_reference_fft_metadata = metadata
    model.prepare_conditionals = prepare
    return metadata
