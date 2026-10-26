"""Child-only HIP validation and instrumentation around the shared core engine."""
from __future__ import annotations
from dataclasses import replace
import json
import hashlib
import os
from pathlib import Path
import shutil
import socket
import sys
import traceback
from types import ModuleType


def vram_budget(free, total):
    headroom = 2 * 1024**3
    if free <= headroom:
        raise RuntimeError('At most 2 GiB GPU headroom is available; existing work was not interrupted')
    budget = min(12 * 1024**3, total - headroom, free - headroom)
    if budget < 1024**3:
        raise RuntimeError('Less than 1 GiB remains in the guarded GPU allocator budget; retry when other GPU work is idle')
    return budget


def gpu_activity(sysfs=Path('/sys/class/drm')):
    """Read the unique AMD card's existing sysfs counters; never reset a GPU."""
    cards = []
    for folder in sysfs.glob('card[0-9]*/device'):
        try:
            if (folder / 'vendor').read_text().strip().lower() != '0x1002':
                continue
            data = dict(pci_device=folder.resolve().name,
                        vendor=(folder / 'vendor').read_text().strip(),
                        device=(folder / 'device').read_text().strip(),
                        busy_percent=int((folder / 'gpu_busy_percent').read_text().strip()))
            cards.append(data)
        except FileNotFoundError:
            continue
    if len(cards) != 1:
        raise RuntimeError('Cannot identify one AMD GPU with readable activity counters; no external render started')
    card = cards[0]
    if not 0 <= card['busy_percent'] <= 20:
        raise RuntimeError(f'AMD GPU is busy ({card["busy_percent"]}%); retry after other GPU work is idle')
    return card


def attach_reference_fft(model, record):
    """Keep the helper's live state, checkpointed after conditioning finishes."""
    from .rocm_reference_fft import install_rocm_reference_fft_compat
    metadata = install_rocm_reference_fft_compat(model)
    prepare = model.prepare_conditionals
    def observed_prepare(*args, **kwargs):
        try:
            return prepare(*args, **kwargs)
        finally:
            record(metadata)
    model.prepare_conditionals = observed_prepare
    return metadata


def run(request, response):
    handles = []
    evidence = {'phase': 'starting', 'audio_accepted': False,
                'parent_death_guard': request.get('parent_death_guard', {})}
    def checkpoint():
        destination = Path(request['proof_path'])
        temporary = destination.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(evidence, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, destination)
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        checkpoint()
        original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
        def offline_connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                raise RuntimeError('External Chatterbox is offline; network/model downloads are forbidden')
            return original_connect(sock, address)
        def offline_connect_ex(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                raise RuntimeError('External Chatterbox is offline; network/model downloads are forbidden')
            return original_connect_ex(sock, address)
        socket.socket.connect, socket.socket.connect_ex = offline_connect, offline_connect_ex
        hardware = gpu_activity()
        evidence.update(phase='AMD activity guard passed; model not loaded', hardware=hardware)
        checkpoint()
        import torch
        import chatterbox
        overlay = Path(request['overlay']).resolve()
        if not Path(chatterbox.__file__).resolve().is_relative_to(overlay):
            raise RuntimeError('Chatterbox was not imported from the explicitly approved overlay')
        if not torch.version.hip or not torch.cuda.is_available():
            raise RuntimeError('This runtime cannot execute AMD ROCm; CPU fallback is forbidden')
        if torch.cuda.device_count() != 1:
            raise RuntimeError('This bounded route requires one visible HIP GPU; device mapping needs review')
        # On this approved ROCm runtime, MIOpen and rocFFT compilation crash.
        # Keep convolutions on CUDA/HIP tensors using PyTorch's native GPU path.
        # This flag changes this fresh child only; the host CPU route is untouched.
        torch.backends.cudnn.enabled = False
        name = torch.cuda.get_device_name(0)
        if not any(v in name.lower() for v in ('amd', 'radeon', 'instinct')):
            raise RuntimeError('ROCm did not report an AMD GPU')
        print(f'Chatterbox external AMD GPU: {name}; Torch {torch.__version__}; HIP {torch.version.hip}; cuda:0 is the ROCm API device.', flush=True)
        torch.set_num_threads(6); torch.set_num_interop_threads(6)
        torch.manual_seed(731); torch.cuda.manual_seed_all(731)
        properties = torch.cuda.get_device_properties(0)
        evidence.update(phase='HIP device available; synthesis not yet proved', hip_version=str(torch.version.hip),
            torch_version=str(torch.__version__), device_name=name,
            gcn_arch=str(getattr(properties, 'gcnArchName', 'unavailable')),
            total_gpu_bytes=int(properties.total_memory), module_parameters={}, forward_evidence={})
        checkpoint()
        free, total = torch.cuda.mem_get_info(0)
        budget = vram_budget(free, total)
        torch.cuda.set_per_process_memory_fraction(budget / total, 0)
        ffmpeg = Path(request['ffmpeg'])
        if not ffmpeg.is_file() or shutil.which(str(ffmpeg)) is None:
            raise RuntimeError('Existing system FFmpeg is required for unchanged core audio export/effects')
        shim = ModuleType('imageio_ffmpeg'); shim.get_ffmpeg_exe = lambda: str(ffmpeg)
        sys.modules['imageio_ffmpeg'] = shim
        from .engine import Engine, load_model
        from .jobs import NarrationJob
        original = NarrationJob(**request['job']); original.validate()
        job = replace(original, device='cuda', voice_path=request['child_voice_path'],
            output_path=str(Path(request['work']) / ('render.' + original.format)))
        parameters, forwards, dsp = {}, {}, {}
        fft_compat = {}
        reference_fft = {}
        def tensors(value):
            if torch.is_tensor(value):
                yield value
            elif isinstance(value, dict):
                for child in value.values(): yield from tensors(child)
            elif isinstance(value, (tuple, list)):
                for child in value: yield from tensors(child)
        def observe(component):
            def hook(module, args, output):
                if forwards.get(component, {}).get('gpu_tensor_seen'): return
                seen = [t for t in tensors(output) if t.device.type == 'cuda' and t.device.index in (None, 0)]
                if seen:
                    forwards[component] = {'gpu_tensor_seen': True, 'device': 'cuda:0',
                        'evidence': 'CUDA output tensor from parameterized module forward', 'dtype': str(seen[0].dtype)}
                    evidence.update(phase='GPU forward observed; audio acceptance pending', forward_evidence=forwards)
                    checkpoint()
                if torch.cuda.memory_reserved(0) > budget:
                    raise RuntimeError('ROCm exceeded its GPU allocator budget')
            return hook
        def loader(model_id, device):
            nonlocal budget, reference_fft
            hardware.update(gpu_activity())
            current_free, current_total = torch.cuda.mem_get_info(0)
            current_budget = vram_budget(current_free, current_total)
            budget = min(budget, current_budget)
            torch.cuda.set_per_process_memory_fraction(budget / current_total, 0)
            evidence.update(engine_source_sha256=hashlib.sha256(Path(__file__).with_name('engine.py').read_bytes()).hexdigest(),
                gpu_allocator_budget_bytes=budget, model_construct_free_gpu_bytes=current_free)
            checkpoint()
            model = load_model(model_id, device, local_only=True, model_path=request['model_dir'])
            from .rocm_fft import install_rocm_fft_compat
            fft_compat.update(install_rocm_fft_compat(model))
            evidence['fft_compatibility'] = fft_compat
            def record_reference(metadata):
                evidence.update(phase='Reference conditioning reported; audio acceptance pending',
                                reference_fft_compatibility=metadata)
                checkpoint()
            reference_fft = attach_reference_fft(model, record_reference)
            evidence['reference_fft_compatibility'] = reference_fft
            vocoder = model.s3gen.mel2wav
            for method in ('_stft', '_istft'):
                operation = getattr(vocoder, method)
                def observed_dsp(*args, _operation=operation, _method=method, **kwargs):
                    result = _operation(*args, **kwargs)
                    outputs = list(tensors(result))
                    if not outputs or any(t.device.type != 'cuda' or t.device.index not in (None, 0) for t in outputs):
                        raise RuntimeError('ROCm vocoder DSP returned a non-GPU tensor: ' + _method)
                    dsp[_method] = dict(device='cuda:0', gpu_outputs=len(outputs), dtype=str(outputs[0].dtype),
                                        calls=dsp.get(_method, {}).get('calls', 0) + 1)
                    evidence.update(phase='GPU vocoder DSP observed; audio acceptance pending', dsp_evidence=dsp)
                    checkpoint()
                    return result
                setattr(vocoder, method, observed_dsp)
            for component in ('t3', 's3gen', 've'):
                module = getattr(model, component)
                gpu = other = 0
                for param in module.parameters():
                    if param.device.type == 'cuda' and param.device.index in (None, 0): gpu += param.numel()
                    else: other += param.numel()
                parameters[component] = {'gpu_parameters': gpu, 'non_gpu_parameters': other}
                evidence.update(phase='GPU model parameters inspected; synthesis pending', module_parameters=parameters)
                checkpoint()
                if not gpu or other:
                    raise RuntimeError('Non-GPU model parameters detected in ' + component)
                for child in module.modules():
                    if any(True for _ in child.parameters(recurse=False)):
                        handles.append(child.register_forward_hook(observe(component)))
            return model
        output = Engine(model_loader=loader, local_only=True, output_peak_limit=0.891250938).render(job, lambda text: print(text, flush=True),
            lambda n, total: print(f'Progress {n}/{total}', flush=True), lambda: False)
        torch.cuda.synchronize(0)
        runtime = dict(actual_backend='rocm', actual_device='cuda:0', hip_version=str(torch.version.hip),
            torch_version=str(torch.__version__), python_version=sys.version.split()[0], device_name=name,
            gcn_arch=str(getattr(torch.cuda.get_device_properties(0), 'gcnArchName', 'unavailable')),
            module_parameters=parameters, forward_evidence=forwards, cpu_fallback=False,
            peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(0), gpu_allocator_budget_bytes=budget,
            initial_free_gpu_bytes=free, gpu_headroom_bytes=2 * 1024**3,
            hardware=hardware, initial_gpu_busy_limit_percent=20,
            seed=731, cpu_threads=6, model_dir=request['model_dir'],
            chatterbox_source=str(chatterbox.__file__), overlay=str(overlay),
            engine_source=str(Path(__file__).with_name('engine.py')))
        runtime['engine_source_sha256'] = hashlib.sha256(Path(__file__).with_name('engine.py').read_bytes()).hexdigest()
        runtime['fft_compatibility'] = fft_compat
        runtime['reference_conditioning_used'] = bool(original.voice_path)
        runtime['reference_fft_compatibility'] = reference_fft
        runtime['parent_death_guard'] = request.get('parent_death_guard', {})
        runtime['dsp_evidence'] = dsp
        runtime['convolution_compatibility'] = dict(torch_cudnn_enabled=False, backend='native_gpu_convolution',
            scope='ROCm child only; CUDA/HIP tensors and GPU model parameters retained')
        runtime['proof_scope'] = 'HIP backend, GPU module parameters and CUDA output tensors observed; CPU preprocessing/watermarking remains.'
        from .rocm import validate_proof
        validate_proof(runtime)
        evidence.update(phase='synthesis completed; parent acceptance pending', runtime=runtime)
        checkpoint()
        response.write_text(json.dumps(dict(ok=True, runtime=runtime, output=str(output))), encoding='utf-8')
    except BaseException:
        evidence.update(phase='failed', error=traceback.format_exc())
        checkpoint()
        response.write_text(json.dumps(dict(ok=False, error=traceback.format_exc())), encoding='utf-8')
        raise
    finally:
        for handle in handles: handle.remove()
