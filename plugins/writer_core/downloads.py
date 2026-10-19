"""Shared verified model/runtime installers. No product prompting."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile

MODEL_NAME = 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
MODEL_REVISION = '4edb920b6f14e3b9284d4502a6485103d72cde05'
MODEL_URL = ('https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF/'
             f'resolve/{MODEL_REVISION}/{MODEL_NAME}')
MODEL_SHA256 = '8cdb57cbb880d313736a9bc4e3d3d2485f145b5e19cf33783746e753e82641fc'
MODEL_SIZE = 2497280448
MODELS = {
    'gemma-writer': {
        'label': 'Gemma The Writer, Mighty Sword 9B (quality, higher memory)',
        'repo': 'DavidAU/Gemma-The-Writer-Mighty-Sword-9B-GGUF',
        'revision': '9fbe618c90ddeb88694d6159d3f7e0fd548fc670',
        'filename': 'Gemma-The-Writer-Mighty-Sword-9B-D_AU-Q4_k_m.gguf',
        'size': 5639201696,
        'sha256': 'c1b1671c878806743d37b8ede29dd626533eef7f9e5266170c7b41bd75c266b0',
        'context': 8192, 'single_user': True,
    },
    'qwen-small': {
        'label': 'Qwen3 4B Instruct (smaller fallback)',
        'repo': 'lmstudio-community/Qwen3-4B-Instruct-2507-GGUF',
        'revision': MODEL_REVISION, 'filename': MODEL_NAME, 'size': MODEL_SIZE,
        'sha256': MODEL_SHA256, 'context': 16384, 'single_user': False,
        'sampling': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'min_p': 0.0, 'repeat_penalty': 1.0},
    },
}
RUNTIME_VERSION = 'b11703'
RUNTIMES = {
    'windows-cpu': ('llama-b11703-bin-win-cpu-x64.zip', 19610655,
                    'cf3050ac140fb9d8c726cdea5e3c16b1879c86e41443aabb84c948e9e100b9de'),
    'windows-vulkan': ('llama-b11703-bin-win-vulkan-x64.zip', 32258906,
                       '93b7db0f380a0c021007d6df35a48460fbedd27be7f9b76db9238cb5c6f03ffe'),
    'linux-cpu': ('llama-b11703-bin-ubuntu-x64.tar.gz', 17914276,
                  'c0691ec3876c2e47a213a37822d894fd5b8c38dfccb9977138b097435663cbb0'),
}

class Cancelled(Exception):
    """A user stopped the current download or generation."""


class KVCacheAllocationError(RuntimeError):
    """The llama.cpp KV cache did not fit into allocatable memory."""


KV_CACHE_MODES = {
    'standard': ('f16', 'f16'),
    'balanced': ('q8_0', 'f16'),
    'compact': ('q8_0', 'q8_0'),
}


def context_retry_sizes(start):
    """Keep configured context first; reduce only after an allocation failure."""
    return [start] + [ctx for ctx in (16384, 8192, 4096, 2048, 1024) if ctx < start]


def check_cancel(cancel):
    if cancel.is_set():
        raise Cancelled('Cancelled.')


def download_verified(url, destination, size, sha256, cancel, progress):
    """Download with resumable partials. A final filename always has a verified hash."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + '.partial')

    def verify(path):
        if path.stat().st_size != size:
            return False
        digest = hashlib.sha256()
        progress(0, 0, 'Verifying SHA-256, please wait...')
        with path.open('rb') as stream:
            while chunk := stream.read(4 * 1024 * 1024):
                check_cancel(cancel)
                digest.update(chunk)
        return digest.hexdigest() == sha256

    if destination.exists():
        if verify(destination):
            return destination
        raise ValueError(f'{destination.name} failed verification. Move that file aside and retry.')
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > size:
        partial.unlink()
        offset = 0
    if offset < size:
        headers = {'User-Agent': 'PVS-Local-Writer/1.0'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        request = urllib.request.Request(url, headers=headers)
        check_cancel(cancel)
        with urllib.request.urlopen(request, timeout=30) as response:
            resume = offset > 0 and response.status == 206
            if resume and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                raise ValueError('Download server returned an unexpected byte range. Please retry.')
            done = offset if resume else 0
            with partial.open('ab' if resume else 'wb') as output:
                while chunk := response.read(1024 * 1024):
                    check_cancel(cancel)
                    output.write(chunk)
                    done += len(chunk)
                    if done > size:
                        raise ValueError('Download exceeded the expected size.')
                    progress(done, size, f'Downloading {destination.name}')
    check_cancel(cancel)
    if partial.stat().st_size < size:
        raise ConnectionError('Download ended before the expected size. Retry to resume the partial file.')
    if not verify(partial):
        partial.unlink(missing_ok=True)
        raise ValueError('Download failed its size or SHA-256 check. Please retry.')
    check_cancel(cancel)
    partial.replace(destination)
    return destination


def extract_runtime(archive, destination, cancel):
    """Extract only files/directories inside destination, never archive links."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    def target(name):
        if '\\' in name or ':' in name:
            raise ValueError('Unsafe runtime archive path.')
        path = (destination / name).resolve()
        if path == destination or not path.is_relative_to(destination):
            raise ValueError('Unsafe runtime archive path.')
        return path

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                check_cancel(cancel)
                path = target(member.filename.rstrip('/'))
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Runtime ZIP contains an unsupported symbolic link.')
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, path.open('wb') as output:
                        shutil.copyfileobj(source, output)
    else:
        with tarfile.open(archive, 'r:gz') as bundle:
            for member in bundle.getmembers():
                check_cancel(cancel)
                if member.name in ('.', './'):
                    continue
                path = target(member.name)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                elif member.isfile() or member.issym() or member.islnk():
                    # Dereference only links to files inside this signed archive.
                    if member.issym() or member.islnk():
                        base = Path(member.name).parent if member.issym() else Path()
                        target(str(base / member.linkname))
                    source = bundle.extractfile(member)
                    if source is None:
                        raise ValueError('Runtime archive contains an unreadable file.')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with source, path.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    path.chmod(0o755 if member.mode & 0o111 else 0o644)
                else:
                    raise ValueError('Runtime archive contains an unsupported entry.')


def install_runtime(data_dir, variant, cancel, progress):
    if variant not in RUNTIMES:
        raise ValueError('No bundled installer for this operating system. Choose a llama-server executable manually.')
    filename, size, digest = RUNTIMES[variant]
    root = Path(data_dir) / 'ai_writer'
    archive = download_verified(
        f'https://github.com/ggml-org/llama.cpp/releases/download/{RUNTIME_VERSION}/{filename}',
        root / 'downloads' / filename, size, digest, cancel, progress)
    install = root / 'runtime' / f'{RUNTIME_VERSION}-{variant}'
    executable = 'llama-server.exe' if variant.startswith('windows') else 'llama-server'
    if install.exists():
        matches = list(install.rglob(executable))
        if len(matches) == 1:
            return str(matches[0])
        raise ValueError('Existing runtime is incomplete. Move its folder aside and reinstall.')
    install.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='extract-', dir=install.parent) as stage:
        progress(0, 0, 'Extracting verified llama.cpp runtime...')
        extract_runtime(archive, Path(stage) / 'runtime', cancel)
        matches = list((Path(stage) / 'runtime').rglob(executable))
        if len(matches) != 1:
            raise ValueError('llama-server was not found in the runtime package.')
        check_cancel(cancel)
        (Path(stage) / 'runtime').replace(install)
    return str(next(install.rglob(executable)))


def install_model(data_dir, cancel, progress, preset='qwen-small'):
    model = MODELS[preset]
    url = f'https://huggingface.co/{model["repo"]}/resolve/{model["revision"]}/{model["filename"]}'
    return str(download_verified(url, Path(data_dir) / 'ai_writer' / 'models' / model['filename'],
                                 model['size'], model['sha256'], cancel, progress))
