"""Apply the measured Windows dependency overrides to an explicit IndexTTS checkout.

Only two requirement strings change. Inference source and model weights are
untouched; the original project file and a hash manifest remain recoverable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import tomllib
from uuid import uuid4

OVERRIDES = {'safetensors':('0.5.2','0.8.0'), 'opencv-python':('4.9.0.80','4.12.0.88')}


def apply(repository: Path) -> bool:
    repository=Path(repository).resolve()
    project=repository/'pyproject.toml'
    original=project.read_bytes()
    text=original.decode('utf-8')
    data=tomllib.loads(text)
    if data.get('project',{}).get('name')!='indextts':
        raise RuntimeError('Compatibility patch requires an IndexTTS project directory')
    dependencies=data['project']['dependencies']
    for package,(old,new) in OVERRIDES.items():
        if package+'=='+new in dependencies:
            continue
        requirement=package+'=='+old
        if requirement not in dependencies or text.count('"'+requirement+'"')!=1:
            raise RuntimeError('Unrecognized IndexTTS requirement for '+package+'; review this upstream revision first.')
        text=text.replace('"'+requirement+'"','"'+package+'=='+new+'"',1)
    updated=text.encode('utf-8')
    if updated==original:return False
    backup=repository/'.pvs-windows-compat'
    backup.mkdir(exist_ok=True)
    initial=backup/'pyproject.original.toml'
    if not initial.exists():
        with initial.open('xb') as f:f.write(original)
    manifest={'purpose':'Windows CPU bounded checkpoint reads and NumPy 2 compatible OpenCV',
        'before_sha256':hashlib.sha256(original).hexdigest(),
        'after_sha256':hashlib.sha256(updated).hexdigest(), 'overrides':OVERRIDES}
    temporary=project.with_name('pyproject.'+uuid4().hex+'.tmp')
    try:
        temporary.write_bytes(updated)
        os.replace(temporary,project)
    finally:
        temporary.unlink(missing_ok=True)
    (backup/'applied.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return True


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    args=parser.parse_args()
    print('IndexTTS Windows compatibility requirements '+('updated' if apply(args.repo) else 'already applied'))
