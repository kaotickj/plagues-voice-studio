# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder package; models/ populated by download_models.py."""
from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

project = Path(SPECPATH)
models = project / 'models'
datas = [
    (str(project / 'assets' / 'plagues-voice-studio-icon.png'), 'assets'),
    (str(project / 'assets' / 'plagues-voice-studio-logo.png'), 'assets'),
    (str(project / 'THIRD_PARTY_NOTICES.md'), '.'),
    (str(project / 'LICENSE'), '.'),
    (str(project / 'BINARY_LICENSE.md'), '.'),
    (str(project / 'LICENSES' / 'GPL-3.0.txt'), 'LICENSES'),
    (str(project / 'optional_engine_runner.py'), '.'),
    (str(project / 'OPTIONAL_ENGINES.md'), '.'),
    (str(project / 'scripts' / 'setup_kokoro_windows.ps1'), 'scripts'),
]
if sys.platform == 'linux':
    datas.append((str(project / 'LINUX.md'), '.'))
# Ship generic plugins, never the branded DJ standalone or its builds.
for folder in ('promotional-writer', 'script-prep'):
    for path in (project / 'plugins' / folder).rglob('*'):
        if path.is_file() and path.suffix in ('.py', '.json', '.md', '.svg') and path.name != 'build_plugin.py' and '__pycache__' not in path.parts:
            datas.append((str(path), str(Path('plugins') / folder / path.relative_to(project / 'plugins' / folder).parent)))
# Slim installer intentionally ships no Chatterbox weights, even if models/
# already exists on the build machine. Model Manager handles on-demand installs.
if os.environ.get('PVS_SLIM_BUILD') != '1':
    for path in models.rglob('*'):
        if path.is_file() and '.cache' not in path.parts and path.name != '.gitkeep':
            datas.append((str(path), str(Path('models') / path.relative_to(models).parent)))

for package in ('chatterbox', 'imageio_ffmpeg', 's3tokenizer', 'perth', 'spacy_pkuseg', 'srsly'):
    pkg_datas, pkg_bins, pkg_hidden = collect_all(package, include_py_files=False)
    if package == 'imageio_ffmpeg' and sys.platform == 'linux':
        # Linux uses the distribution's FFmpeg (see LINUX.md). Avoid shipping a
        # second native binary with a different system/library/license baseline.
        pkg_datas = [(src, dst) for src, dst in pkg_datas
                     if not Path(src).name.startswith('ffmpeg-')]
        pkg_bins = [(src, dst) for src, dst in pkg_bins
                    if not Path(src).name.startswith('ffmpeg-')]
    datas += pkg_datas
    if package == 'chatterbox':
        hidden = pkg_hidden
        binaries = pkg_bins
    else:
        hidden += pkg_hidden
        binaries += pkg_bins
# Transformers (and other ML dependencies) call importlib.metadata.version() at
# runtime. PyInstaller gathers Python modules but does NOT automatically ship
# every *.dist-info directory. Without metadata for 'requests', transformers
# raises PackageNotFoundError, despite requests itself being present.
#
# These packages are already installed by `pip install -e '.[build]'`. Failing
# the build for a missing distribution is intentional: an incomplete EXE must
# not be published as a working offline package.
metadata_distributions = (
    'plagues-voice-studio-v030', 'chatterbox-tts', 'resemble-perth',
    'transformers', 'requests', 'regex', 'filelock', 'fsspec',
    'huggingface-hub', 'tokenizers', 'safetensors', 'packaging',
    'numpy', 'PyYAML', 'tqdm', 'torch', 'torchaudio',
    'diffusers', 'librosa', 'soundfile', 'imageio-ffmpeg',
    's3tokenizer', 'Pillow', 'charset-normalizer', 'idna',
    'urllib3', 'certifi', 'PyQt6', 'PyQt6-Qt6',
    'spacy_pkuseg', 'srsly',
)
for package in metadata_distributions:
    datas += copy_metadata(package)

hidden += collect_submodules('chatterbox')
hidden += ['writer_core', 'writer_core.downloads', 'writer_core.runtime',
           'writer_core.settings', 'writer_core.setup_dialog', 'PyQt6.QtSvg']
hidden += ['plagued_ai']
# Keep portable FUZ/container and project helpers on every platform. Only the
# complete Windows-tool-dependent production UI is excluded from Linux builds.
hidden += ['chatterbox_studio.bethesda_export', 'chatterbox_studio.mod_profiles']
hidden += ['PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'soundfile', 'imageio_ffmpeg',
           'librosa', 'transformers', 'diffusers', 'torch', 'torchaudio', 'safetensors']

excluded = ['gradio', 'gradio_client', 'streamlit', 'tensorflow', 'tensorboard']
if sys.platform != 'win32':
    excluded.append('chatterbox_studio.bethesda_widget')

analysis = Analysis(
    [str(project / 'launcher.py')],
    pathex=[str(project / 'src'), str(project / 'plugins')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    excludes=excluded,
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True,
    name='PlaguesVoiceStudio030Experimental',
    icon=str(project / 'assets' / 'plagues-voice-studio.ico') if sys.platform == 'win32' else None,
    version=str(project / 'assets' / 'version_info.txt') if sys.platform == 'win32' else None,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False,
               name='PlaguesVoiceStudio030Experimental')
