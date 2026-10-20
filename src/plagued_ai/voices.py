"""Explicit, hash-checked consolidation of imported voice references."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from . import root, app_dir


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(4*1024*1024):
            result.update(chunk)
    return result.hexdigest()


def sources():
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local')))
    return [(app_dir('voice-studio'), ''), (local/'PlaguesVoiceStudio', ''),
            (local/'PlaguesVoiceStudio-v030-Experimental', ''),
            (local/'PlaguesVoiceStudio-v021', 'stable:'),
            (local/'ChatterboxStudio', 'legacy:')]


def directory_link(source, destination):
    if os.name == 'nt':
        env = dict(os.environ, PVS_LINK_SOURCE=str(source), PVS_LINK_TARGET=str(destination))
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                        'New-Item -ItemType Junction -Path $env:PVS_LINK_SOURCE -Target $env:PVS_LINK_TARGET -ErrorAction Stop | Out-Null'],
                       env=env, check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        source.symlink_to(destination, target_is_directory=True)


def plan(destination=None, libraries=None):
    destination = Path(destination) if destination else root()
    audio = destination/'voices'
    index = destination/'voices.json'
    records = json.loads(index.read_text(encoding='utf-8')) if index.exists() else []
    if not isinstance(records, list): raise ValueError('Invalid central voice index.')
    by_id = {item['id']: item for item in records}
    filenames, moves, folders = {}, [], []
    for base, prefix in sources() if libraries is None else libraries:
        base = Path(base); folder = base/'voices'; old_index = base/'voices.json'
        if not old_index.is_file(): continue
        items = json.loads(old_index.read_text(encoding='utf-8'))
        if not isinstance(items, list): raise ValueError('Invalid voice index: '+str(old_index))
        for item in items:
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k] for k in ('id', 'file', 'name')):
                raise ValueError('Invalid voice entry in '+str(old_index))
            filename = item['file']
            if Path(filename).name != filename or '/' in filename or '\\' in filename:
                raise ValueError('Voice filename escapes its library: '+filename)
            source = folder/filename
            if not source.is_file() and not (audio/filename).is_file():
                raise ValueError('Missing voice reference: '+str(source))
            record = dict(item, id=prefix+item['id'])
            previous = by_id.get(record['id'])
            if previous and (previous['file'] != record['file'] or previous['name'] != record['name']):
                raise ValueError('Conflicting voice identity: '+record['id'])
            by_id[record['id']] = record
        if not folder.exists():
            folders.append(folder)
        elif folder.resolve() != audio.resolve():
            folders.append(folder)
            for source in folder.iterdir():
                if not source.is_file() or source.is_symlink():
                    raise ValueError('Unexpected nested or linked voice item: '+str(source))
                file_hash = digest(source)
                if source.name in filenames and filenames[source.name] != file_hash:
                    raise ValueError('Different voice contents share a filename: '+source.name)
                target = audio/source.name
                if target.exists() and digest(target) != file_hash:
                    raise ValueError('Central voice conflict: '+source.name)
                filenames[source.name] = file_hash
                moves.append({'source': str(source), 'destination': str(target), 'sha256': file_hash,
                              'bytes': source.stat().st_size})
    return {'destination': str(destination), 'records': list(by_id.values()), 'moves': moves,
            'folders': [str(p) for p in folders]}


def apply(prepared, link=directory_link):
    destination = Path(prepared['destination']); audio = destination/'voices'
    audio.mkdir(parents=True, exist_ok=True)
    journal = destination/'voice-consolidation.json'
    report = dict(prepared, status='in progress', started_utc=datetime.now(timezone.utc).isoformat())
    journal.write_text(json.dumps(report, indent=2), encoding='utf-8')
    for move in prepared['moves']:
        source, target = Path(move['source']), Path(move['destination'])
        if not source.is_file() or digest(source) != move['sha256']:
            raise ValueError('Voice changed after preflight: '+str(source))
        if target.exists():
            if digest(target) != move['sha256']: raise ValueError('Central file changed: '+str(target))
            # Only remove the redundant source after proving the retained file
            # contains exactly the same audio bytes.
            source.unlink()
        else:
            os.rename(source, target)  # Same volume: no temporary audio copy.
        if digest(target) != move['sha256']: raise ValueError('Post-move verification failed: '+str(target))
    for folder in map(Path, prepared['folders']):
        if folder.resolve() == audio.resolve(): continue
        if folder.exists():
            folder.rmdir()  # Refuses nonempty directories; never recursive deletion.
        link(folder, audio)
    stage = destination/'voices.json.tmp'
    stage.write_text(json.dumps(prepared['records'], indent=2, ensure_ascii=False), encoding='utf-8')
    stage.replace(destination/'voices.json')
    report.update(status='complete', voice_count=len(prepared['records']),
                  finished_utc=datetime.now(timezone.utc).isoformat())
    journal.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
