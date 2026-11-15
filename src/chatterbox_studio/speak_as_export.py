"""Save exact converted audio and a matching snapshot without overwriting files."""
import json
import shutil
from pathlib import Path


def save_recording(source: Path, target: Path, metadata: dict) -> Path:
    source, target = Path(source), Path(target)
    sidecar = target.with_suffix('.json')
    # Serialize before creating anything, and never use replace/overwrite semantics.
    payload = json.dumps(metadata, indent=2, ensure_ascii=False)
    if not source.is_file():
        raise FileNotFoundError('Converted WAV is no longer available')
    if target.exists() or sidecar.exists():
        raise FileExistsError('WAV or matching JSON already exists; choose another filename')
    target.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with sidecar.open('x', encoding='utf-8') as stream:
            created.append(sidecar)
            stream.write(payload)
        with source.open('rb') as original, target.open('xb') as output:
            created.append(target)
            shutil.copyfileobj(original, output)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return target
