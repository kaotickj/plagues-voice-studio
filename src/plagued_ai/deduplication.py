"""Explicit SHA-256 deduplication of immutable model files using hard links."""
from collections import defaultdict
import json
import os
from pathlib import Path
from uuid import uuid4
from . import root
from .voices import digest


def plan(model_root=None, minimum_size=16*1024*1024):
    model_root=Path(model_root) if model_root else root()/'models'
    sizes=defaultdict(list)
    for directory, folders, files in os.walk(model_root, followlinks=False):
        folders[:] = [name for name in folders if not (Path(directory)/name).is_symlink()
                      and not getattr(Path(directory)/name,'is_junction',lambda:False)()]
        for name in files:
            path=Path(directory)/name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(model_root.resolve()):continue
            size=path.stat().st_size
            if size >= minimum_size:sizes[size].append(path)
    moves=[]
    for size, paths in sizes.items():
        if len(paths)<2:continue
        by_hash={}
        for path in sorted(paths):
            hashed=digest(path)
            keeper=by_hash.setdefault(hashed,path)
            if path != keeper and not path.samefile(keeper):
                moves.append({'keep':str(keeper),'replace':str(path),'sha256':hashed,'bytes':size})
    return moves


def apply(moves, model_root=None):
    model_root=Path(model_root) if model_root else root()/'models'
    saved=0
    for move in moves:
        keeper, duplicate=Path(move['keep']),Path(move['replace'])
        if not all(p.resolve().is_relative_to(model_root.resolve()) for p in (keeper,duplicate)):
            raise ValueError('Deduplication must stay inside the shared model directory.')
        if digest(keeper)!=move['sha256'] or digest(duplicate)!=move['sha256']:
            raise ValueError('Model contents changed after preflight.')
        if duplicate.samefile(keeper):continue
        temporary=duplicate.with_name(duplicate.name+'.dedupe-'+uuid4().hex)
        try:
            os.link(keeper,temporary)
            temporary.replace(duplicate)
        finally:
            if temporary.exists():temporary.unlink()
        if not duplicate.samefile(keeper):raise ValueError('Model hard-link verification failed.')
        saved += move['bytes']
    return {'status':'complete','files_linked':len(moves),'bytes_reclaimed':saved,'files':moves}
