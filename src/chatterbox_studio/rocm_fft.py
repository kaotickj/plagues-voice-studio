"""Local HiFT 16-point transforms without invoking an FFT runtime.

Installation is explicit and affects only one model's mel2wav instance. Torch is
imported lazily. Tensor data, frame construction and overlap-add stay on the
input device; this does not supply a CPU fallback or modify Torch/upstream code.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from types import MethodType


_N, _H = 16, 4
_F = _N // 2 + 1


def _clean(value: float) -> float:
    return 0.0 if abs(value) < 1e-15 else value


_COS = tuple(tuple(_clean(math.cos(2 * math.pi * k * n / _N))
                   for n in range(_N)) for k in range(_F))
_SIN = tuple(tuple(0.0 if k in (0, _N // 2)
                   else _clean(math.sin(2 * math.pi * k * n / _N))
                   for n in range(_N)) for k in range(_F))
_HANN = tuple(0.5 - 0.5 * math.cos(2 * math.pi * n / _N) for n in range(_N))
_WEIGHTS = (1.0,) + (2.0,) * (_F - 2) + (1.0,)


def install_rocm_fft_compat(model) -> dict:
    """Bind only HiFT ``_stft``/``_istft`` after validating its exact contract.

    Supports the shipped N=16, hop=4, full periodic Hann, centered/reflect STFT
    and centered onesided inverse with no explicit output length. Float32 and
    float64 are qualified; unsupported configurations fail before either method
    is changed. The caller decides whether its ROCm runtime needs this hook.
    """
    import torch
    import torch.nn.functional as functional

    target = getattr(getattr(model, 's3gen', None), 'mel2wav', None)
    params = getattr(target, 'istft_params', None)
    if (not isinstance(params, Mapping) or set(params) != {'n_fft', 'hop_len'}
            or type(params['n_fft']) is not int or type(params['hop_len']) is not int
            or params['n_fft'] != _N or params['hop_len'] != _H):
        raise ValueError('HiFT FFT compatibility requires exactly n_fft=16 and hop_len=4.')
    window = getattr(target, 'stft_window', None)
    if (not isinstance(window, torch.Tensor) or window.shape != (_N,)
            or window.dtype not in (torch.float32, torch.float64)):
        raise ValueError('HiFT FFT compatibility requires a floating 16-sample periodic Hann window.')
    expected = torch.tensor(_HANN, dtype=window.dtype, device=window.device)
    tolerance = 5e-7 if window.dtype == torch.float32 else 1e-12
    if not torch.allclose(window, expected, rtol=0, atol=tolerance):
        raise ValueError('HiFT FFT compatibility requires the full periodic Hann window.')
    if not all(callable(getattr(target, name, None)) for name in ('_stft', '_istft')):
        raise ValueError('HiFT FFT compatibility requires both original transform methods.')

    # Cache only small constants per input device/dtype in these bound closures;
    # neither tensor inputs nor outputs ever leave that device.
    validated_window = window.detach().clone()
    constants = {}

    def basis(value):
        if value.dtype not in (torch.float32, torch.float64):
            raise ValueError('HiFT direct transforms support float32 or float64 inputs.')
        if validated_window.dtype == torch.float64 and value.dtype == torch.float32:
            raise ValueError('HiFT input precision must not be lower than the validated Hann window.')
        key = (value.device, value.dtype)
        if key not in constants:
            cosine = torch.tensor(_COS, device=value.device, dtype=value.dtype)
            sine = torch.tensor(_SIN, device=value.device, dtype=value.dtype)
            weights = torch.tensor(_WEIGHTS, device=value.device, dtype=value.dtype)[:, None] / _N
            constants[key] = (cosine, sine, cosine * weights, sine * weights,
                              validated_window.to(device=value.device, dtype=value.dtype),
                              validated_window.to(device=value.device))
        return constants[key]

    def stft(_self, value):
        if value.ndim != 2 or value.shape[0] < 1 or value.shape[-1] <= _N // 2:
            raise ValueError('HiFT STFT expects batch-by-samples input longer than the reflect padding (8).')
        cosine, sine, _, _, hann, _ = basis(value)
        padded = functional.pad(value.unsqueeze(1), (_N // 2, _N // 2), mode='reflect').squeeze(1)
        frames = padded.unfold(-1, _N, _H) * hann
        return ((frames @ cosine.transpose(0, 1)).transpose(1, 2),
                -(frames @ sine.transpose(0, 1)).transpose(1, 2))

    def istft(_self, magnitude, phase):
        if (magnitude.ndim != 3 or magnitude.shape[0] < 1 or magnitude.shape[1] != _F
                or magnitude.shape[-1] < 2 or phase.shape != magnitude.shape
                or phase.device != magnitude.device or phase.dtype != magnitude.dtype):
            raise ValueError('HiFT ISTFT expects matching batch-by-9-by-frames tensors on one device/dtype, with at least two frames.')
        _, _, inverse_cosine, inverse_sine, hann, envelope_window = basis(magnitude)
        limited = magnitude.clamp(max=100)
        real = (limited * phase.cos()).transpose(1, 2)
        imaginary = (limited * phase.sin()).transpose(1, 2)
        frames = (real @ inverse_cosine - imaginary @ inverse_sine) * hann
        count = frames.shape[1]
        length = _N + _H * (count - 1)
        # fold performs native overlap-add; normalize with the same window^2
        # envelope as centered torch.istft, then remove the 8-sample margins.
        signal = functional.fold(frames.transpose(1, 2), (1, length), (1, _N),
                                 stride=(1, _H)).flatten(1)
        # Upstream computes this envelope in the stored window dtype, even
        # when the signal is float64 and its retained window is float32.
        envelope = functional.fold(envelope_window.square()[None, :, None].expand(1, _N, count),
                                   (1, length), (1, _N), stride=(1, _H)).flatten(1)
        return signal[:, _N // 2:-_N // 2] / envelope[:, _N // 2:-_N // 2]

    target._stft = MethodType(stft, target)
    target._istft = MethodType(istft, target)
    return {'method': 'direct_dft16_fold', 'scope': 's3gen.mel2wav instance _stft/_istft only',
            'n_fft': _N, 'hop_len': _H, 'center': True, 'pad_mode': 'reflect',
            'onesided': True, 'normalized': False, 'magnitude_max': 100}
