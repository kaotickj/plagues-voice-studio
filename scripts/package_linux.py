"""Package a tested native Linux onedir tree, preserving modes and symlinks."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def package(app: Path, output: Path):
    executable = app / 'PlaguesVoiceStudio030Experimental'
    if not executable.is_file() or executable.read_bytes()[:4] != b'\x7fELF':
        raise ValueError('Expected a native Linux ELF executable')
    if any(p.suffix.lower() in {'.safetensors', '.pt', '.pth', '.ckpt', '.gguf', '.onnx'}
           for p in app.rglob('*') if p.is_file()):
        raise ValueError('Model weights are not allowed in the Linux slim package')
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    shutil.copyfile(ROOT / 'LINUX.md', app / 'START-HERE.md')
    # A relocatable entry point, including launch from a directory with spaces.
    launcher = app / 'start-voice-studio.sh'
    launcher.write_text('#!/usr/bin/env sh\nset -eu\ncd "$(dirname "$0")"\nexec ./PlaguesVoiceStudio030Experimental "$@"\n', encoding='utf-8', newline='\n')
    launcher.chmod(0o755)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (app / 'BUILD-INFO.json').write_text(json.dumps({
        'version': version, 'commit': commit, 'platform': platform.platform(),
        'python': platform.python_version(), 'libc': platform.libc_ver(),
        'edition': 'Linux x86-64 experimental; CPU Chatterbox; optional native engines unqualified',
    }, indent=2), encoding='utf-8')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'PlaguesVoiceStudio-{version}-Linux-x86_64-Portable.tar.gz'
    # tar preserves the ELF execute bit and PyInstaller's shared-library links.
    with tarfile.open(archive, 'w:gz', dereference=False) as bundle:
        bundle.add(app, arcname=app.name)
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(archive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.app.resolve(), args.output.resolve())
