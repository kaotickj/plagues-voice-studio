"""Explicit folder relocation preserving old application paths via links."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from . import root, app_dir
from .voices import directory_link


def locations():
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData'/'Local')))
    dj = Path.home()/'.goodneighbor_blues_dj'
    old = local/'PlaguesVoiceStudio-v030-Experimental'
    return [(dj/'ai_writer/models',root()/'models/text'),
            (dj/'ai_writer/runtime',root()/'runtimes/llama.cpp'),
            (dj/'ai_writer/downloads',root()/'downloads/llama.cpp'),
            (old/'models',root()/'models/chatterbox'),
            (old/'engines/index-tts/checkpoints',root()/'models/index-tts/2.5'),
            (Path(os.environ.get('HF_HOME',str(Path.home()/'.cache/huggingface'))),root()/'models/huggingface'),
            (dj,app_dir('dj-writer')),
            (local/'PlaguesVoiceStudio',app_dir('voice-studio'))]


def plan(pairs=None):
    moves = []
    for source, target in locations() if pairs is None else pairs:
        source,target=Path(source).absolute(),Path(target).absolute()
        if not source.exists() or source.resolve() == target.resolve():continue
        if target.exists():
            raise ValueError('Destination already exists; refusing to merge or overwrite: '+str(target))
        if target.is_relative_to(source) or source.is_relative_to(target):
            raise ValueError('Source and destination trees overlap.')
        if source.drive.casefold() != target.drive.casefold():
            raise ValueError('This migration requires the same volume; no multi-GB copy will be started.')
        moves.append({'source':str(source),'destination':str(target)})
    return moves


def apply(moves, destination=None, link=directory_link):
    destination = Path(destination) if destination else root()
    destination.mkdir(parents=True,exist_ok=True)
    journal=destination/'storage-consolidation.json'
    report={'status':'in progress','started_utc':datetime.now(timezone.utc).isoformat(),'moves':[]}
    for move in moves:
        source,target=Path(move['source']),Path(move['destination'])
        if target.exists() or not source.is_dir():raise ValueError('Migration locations changed; run the audit again.')
        target.parent.mkdir(parents=True,exist_ok=True)
        before = dict(move,status='prepared')
        report['moves'].append(before)
        journal.write_text(json.dumps(report,indent=2),encoding='utf-8')
        # Same-volume rename preserves every byte and filesystem identity.
        source.rename(target)
        try:
            link(source,target)
        except Exception:
            target.rename(source)
            before['status']='rolled back'
            journal.write_text(json.dumps(report,indent=2),encoding='utf-8')
            raise
        before['status']='complete'
        journal.write_text(json.dumps(report,indent=2),encoding='utf-8')
    report['status']='complete'
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    journal.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
