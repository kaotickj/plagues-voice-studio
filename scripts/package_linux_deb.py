"""Build a model-free amd64 Debian installer from the tested Linux onedir."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'plagues-voice-studio'
EXECUTABLE = 'PlaguesVoiceStudio030Experimental'
INSTALL_PATH = Path('usr/lib') / PACKAGE
DEPENDENCIES = (
    'libc6 (>= 2.39)', 'libgcc-s1', 'libstdc++6', 'zlib1g',
    'ffmpeg', 'libsndfile1', 'libegl1', 'libgl1', 'libopengl0',
    'libpulse0', 'libasound2t64', 'libglib2.0-0t64', 'libdbus-1-3',
    'libfontconfig1', 'libfreetype6', 'libx11-6', 'libx11-xcb1',
    'libxext6', 'libxrender1', 'libsm6', 'libice6',
    'libxkbcommon-x11-0', 'libxcb-cursor0', 'libxcb-icccm4',
    'libxcb-keysyms1', 'libxcb-shape0', 'libxcb-xinerama0',
    'libxcb-xkb1', 'libxcb-randr0', 'libxcb-render-util0', 'libxcb-image0',
)
DESKTOP = '''[Desktop Entry]
Type=Application
Name=Plague's Voice Studio
Comment=Local AI voice production and narration
Exec=plagues-voice-studio
TryExec=plagues-voice-studio
Icon=plagues-voice-studio
Terminal=false
Categories=AudioVideo;Audio;
Keywords=voice;speech;narration;TTS;
'''


def debian_version(version: str) -> str:
    """Keep alpha/beta/RC packages older than the corresponding final release."""
    match = re.fullmatch(r'(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?', version)
    if not match:
        raise ValueError('Unsupported release version: ' + version)
    base, stage, number = match.groups()
    return base + (f'~{stage}{number}' if stage else '') + '-1'


def validate_app(app: Path) -> None:
    executable = app / EXECUTABLE
    if not executable.is_file():
        raise ValueError('Expected a native amd64 Linux ELF executable')
    with executable.open('rb') as stream:
        header = stream.read(64)
    if (len(header) < 20 or header[:6] != b'\x7fELF\x02\x01'
            or struct.unpack_from('<H', header, 18)[0] != 62):
        raise ValueError('Expected a native amd64 Linux ELF executable')
    if not executable.stat().st_mode & 0o111:
        raise ValueError('Application executable must retain its execute permission')
    for path in app.rglob('*'):
        if path.is_symlink() and (os.path.isabs(os.readlink(path))
                                  or not path.resolve().is_relative_to(app)):
            raise ValueError('Application symlink escapes the payload: ' + str(path))
        if path.is_file() and path.suffix.lower() in {
                '.safetensors', '.pt', '.pth', '.ckpt', '.gguf', '.onnx'}:
            raise ValueError('Model weights are not allowed in the Debian slim package')


def write_file(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')
    path.chmod(mode)


def package(app: Path, output: Path) -> Path:
    app, output = app.resolve(), output.resolve()
    validate_app(app)
    if output.is_relative_to(app):
        raise ValueError('Output directory must be outside the application payload')
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    version_deb = debian_version(version)
    provenance = app / 'BUILD-INFO.json'
    if not provenance.is_file():
        raise ValueError('Package the tested portable onedir with BUILD-INFO.json first')
    if json.loads(provenance.read_text(encoding='utf-8')).get('version') != version:
        raise ValueError('Application build version does not match the package source')
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f'{PACKAGE}_{version_deb}_amd64.deb'
    with tempfile.TemporaryDirectory(prefix='pvs-deb-', dir=output) as temporary:
        stage = Path(temporary)
        payload = stage / INSTALL_PATH
        payload.parent.mkdir(parents=True)
        shutil.copytree(app, payload, symlinks=True)
        # dpkg installs only program files. No models, runtime environments,
        # /home files, /var data, conffiles, or maintainer scripts are generated.
        write_file(stage / 'usr/bin' / PACKAGE,
                   '#!/bin/sh\nset -eu\ncd /usr/lib/plagues-voice-studio\n'
                   f'exec ./{EXECUTABLE} "$@"\n', 0o755)
        write_file(stage / 'usr/share/applications' / (PACKAGE + '.desktop'), DESKTOP)
        icon = stage / 'usr/share/pixmaps' / (PACKAGE + '.png')
        icon.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'assets/plagues-voice-studio-icon.png', icon)
        docs = stage / 'usr/share/doc' / PACKAGE
        docs.mkdir(parents=True)
        for name in ('BINARY_LICENSE.md', 'THIRD_PARTY_NOTICES.md', 'LINUX.md', 'LICENSE'):
            shutil.copyfile(ROOT / name, docs / name)
        shutil.copytree(ROOT / 'LICENSES', docs / 'LICENSES')
        write_file(docs / 'copyright',
                   'Plague\'s Voice Studio, created by Kaotick Jay.\n'
                   'Source: https://github.com/kaotickj/plagues-voice-studio\n'
                   'The combined GUI binary is distributed under GNU GPL v3.\n'
                   'Original project source retains its MIT license.\n'
                   'See BINARY_LICENSE.md, LICENSES/GPL-3.0.txt and component notices.\n')
        size = sum(p.stat().st_size for p in stage.rglob('*')
                   if p.is_file() and not p.is_symlink())
        write_file(stage / 'DEBIAN/control',
                   f'Package: {PACKAGE}\nVersion: {version_deb}\nArchitecture: amd64\n'
                   'Maintainer: Kaotick Jay <kaotickj@users.noreply.github.com>\n'
                   'Section: sound\nPriority: optional\n'
                   f'Installed-Size: {(size + 1023)//1024}\n'
                   'Homepage: https://github.com/kaotickj/plagues-voice-studio\n'
                   f'Depends: {", ".join(DEPENDENCIES)}\n'
                   'Description: local AI voice production studio\n'
                   ' Native Linux CPU application with narration and optional speech engines.\n'
                   ' Model weights and optional runtimes are configured separately.\n')
        # Archive ownership is root:root without running the builder as root.
        for folder in [stage, *(p for p in stage.rglob('*') if p.is_dir() and not p.is_symlink())]:
            folder.chmod(0o755)
        subprocess.run(['dpkg-deb', '--root-owner-group', '--uniform-compression',
                        '-Zxz', '-z6', '--threads-max=2', '--build', str(stage), str(destination)], check=True)
    with destination.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {destination.name}\n', encoding='utf-8')
    print(destination)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.app, args.output)
