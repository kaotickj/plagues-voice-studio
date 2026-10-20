"""Test migration against isolated copies of real metadata and reference audio.

No model weights are copied and no real profile, registry key or audio is
modified. Private fixtures/reports stay in ignored artifacts.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    from plagued_ai import root
    from chatterbox_studio.paths import legacy_v030_dir,user_data_dir
    from chatterbox_studio.pvs_library import CompatibleVoiceLibrary
    source=legacy_v030_dir()
    shared=root()
    run=ROOT/'artifacts/release-speech-repair/real-profile-migration'/uuid4().hex
    copied=run/'local/PlaguesVoiceStudio-v030-Experimental'
    copied.mkdir(parents=True)
    originals={}
    for path in list(source.glob('*.json'))+list((source/'plugins').rglob('*.json')):
        if path.name=='migration.json':continue
        if path.stat().st_size>10*1024*1024:raise RuntimeError('Unexpectedly large metadata fixture')
        relative=path.relative_to(source)
        target=copied/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);originals[path]=digest(path)
    legacy_voices=json.loads((source/'voices.json').read_text(encoding='utf-8'))
    (copied/'voices').mkdir()
    for voice in legacy_voices:
        original=source/'voices'/voice['file']
        os.link(original,copied/'voices'/voice['file'])
        originals[original]=digest(original)
    with patch.dict(os.environ,LOCALAPPDATA=str(run/'local'),PLAGUED_AI_HOME=str(run/'shared')):
        current=user_data_dir()
        for original,expected in originals.items():
            relative=original.relative_to(source)
            if digest(current/relative)!=expected:raise RuntimeError('Migrated fixture changed: '+str(relative))
        library=CompatibleVoiceLibrary(current)
        assert len(library.current.list_voices())==len(legacy_voices)
        for voice in legacy_voices:assert Path(library.resolve(voice['id'])).is_file()
        # Repeated startup must preserve an edit made after migration.
        edited=current/'migration-acceptance-note.json';edited.write_text('{"retained":true}')
        assert user_data_dir()==current and json.loads(edited.read_text())['retained']
        assert not (current/'models').exists() and not (current/'engines').exists()
        shared_index=shared/'voices.json'
        central_voices=json.loads(shared_index.read_text(encoding='utf-8'))
        root().mkdir(exist_ok=True)
        shutil.copy2(shared_index,root()/'voices.json');(root()/'voices').mkdir()
        originals[shared_index]=digest(shared_index)
        for voice in central_voices:
            original=shared/'voices'/voice['file']
            os.link(original,root()/'voices'/voice['file']);originals[original]=digest(original)
        central=CompatibleVoiceLibrary(current)
        assert len(central.list_voices())==len(central_voices)
        assert all(Path(central.resolve(v['id'])).is_file() for v in central_voices)
    assert all(digest(path)==expected for path,expected in originals.items())
    report=dict(status='passed',legacy_voices=len(legacy_voices),shared_voices=len(central_voices),
        original_files_unchanged=len(originals),models_copied=0,registry_modified=False,
        note='Real metadata and reference-file fixtures; isolated profile migration, repeated startup and shared-library resolution.')
    (run/'result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(report,report=str(run/'result.json'))))


if __name__=='__main__':main()
