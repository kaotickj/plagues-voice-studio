"""Shared storage contract for Plagued AI applications; standard library only."""
from pathlib import Path
import os
import sys
import json
import shutil
from uuid import uuid4


def root():
    override = os.environ.get('PLAGUED_AI_HOME')
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local'))) if sys.platform == 'win32' else Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local'/'share')))
    return base/'PlaguedAI'


def app_dir(name):
    return root()/'apps'/name


def huggingface_home():
    destination = root()/'models'/'huggingface'
    # Reuse preexisting caches until explicit consolidation; never silently
    # create a second multi-GB cache during an upgrade.
    legacy = Path(os.environ.get('HF_HOME', str(Path.home()/'.cache'/'huggingface')))
    return destination if destination.exists() or not legacy.exists() else legacy


def writer_assets(data_dir):
    """Custom/test application homes remain isolated unless explicitly shared."""
    data_dir = Path(data_dir)
    if data_dir.is_relative_to(root()/'apps') or data_dir == Path.home()/'.goodneighbor_blues_dj':
        return root()
    return data_dir/'ai_writer'


def writer_models(data_dir):
    assets = writer_assets(data_dir)
    return assets/'models'/'text' if assets == root() else assets/'models'


def writer_runtime(data_dir):
    assets = writer_assets(data_dir)
    return assets/'runtimes'/'llama.cpp' if assets == root() else assets/'runtime'


def find_writer_model(data_dir, filename):
    candidates = [writer_models(data_dir)/filename, Path(data_dir)/'ai_writer'/'models'/filename]
    if writer_assets(data_dir) == root():
        candidates.append(Path.home()/'.goodneighbor_blues_dj'/'ai_writer'/'models'/filename)
    return next((p for p in candidates if p.is_file()), candidates[0])


def previous_studio_dir():
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local'))) if sys.platform=='win32' else Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local'/'share')))
    return local/'PlaguesVoiceStudio'


def dj_data_dir():
    override = os.environ.get('GOODNEIGHBOR_DJ_HOME')
    if override:
        return Path(override)
    destination = app_dir('dj-writer')
    legacy = Path.home()/'.goodneighbor_blues_dj'
    if not destination.exists() and legacy.is_dir():
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = destination.with_name(destination.name+'.migration-'+uuid4().hex)
        try:
            shutil.copytree(legacy, stage, ignore=shutil.ignore_patterns('models','runtime','downloads','__pycache__','*.log'))
            (stage/'migration.json').write_text(json.dumps({'source':str(legacy),'method':'state only; model/runtime paths retained'}),encoding='utf-8')
            stage.rename(destination)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
    return destination


def resolve_writer_settings(settings, data_dir):
    result = dict(settings)
    for key in ('model_path', 'server_path'):
        path = Path(result.get(key, ''))
        if path.is_file() and path.resolve().is_relative_to(root().resolve()):
            result[key] = str(path.resolve())
    return result
