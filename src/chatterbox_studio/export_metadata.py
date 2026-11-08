"""Read the exact narration script from the JSON stored beside an audio export.

Read-only by design: importing older recordings must never alter their metadata.
"""
from __future__ import annotations

import json
import os
from pathlib import Path



def write_export_metadata(audio_path: Path, metadata: dict) -> Path:
    """Atomically write <audio>.json using the exact original script snapshot."""
    sidecar = Path(audio_path).with_suffix('.json')
    if not isinstance(metadata.get('text'), str):
        raise ValueError('Export metadata must contain the original narration text')
    temp = sidecar.with_name(sidecar.name + '.tmp')
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    try:
        temp.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, sidecar)
    finally:
        temp.unlink(missing_ok=True)
    return sidecar


def read_export_script(audio_path: Path, *, original: bool = False) -> tuple[str | None, str]:
    """Return (render input or original manuscript, preview status).

    New exports keep the prepared render input separate from ``text``, the
    original manuscript. Older exports use ``text`` for both views. Values are
    shown verbatim, including bracketed vocal tags and line breaks.
    Never substitute reference-audio transcripts or currently
    edited script text when an export does not have its own metadata.
    """
    sidecar = Path(audio_path).with_suffix('.json')
    if not sidecar.is_file():
        return None, 'No saved script for this recording (older or imported audio).'
    try:
        metadata = json.loads(sidecar.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, ValueError):
        return None, 'The matching JSON metadata could not be read.'
    if not isinstance(metadata, dict):
        return None, 'The matching JSON metadata is not an object.'
    script = metadata.get('text')
    prepared = metadata.get('prepared_text')
    if not original and isinstance(prepared, str):
        script = prepared
    if not isinstance(script, str) or not script.strip():
        return None, 'This recording has no saved script in its JSON metadata.'

    # Older and optional-engine sidecars may contain different metadata keys.
    engine = metadata.get('engine')
    model = metadata.get('model')
    details = [str(v) for v in (engine, model) if isinstance(v, str) and v.strip()]
    if metadata.get('render_scope') == 'selection':
        details.append('Original manuscript; recording contains selected passage' if original
                       else 'Selected passage; original manuscript saved separately')
    elif isinstance(prepared, str) and prepared != metadata.get('text'):
        details.append('Original manuscript' if original else 'Prepared render input')
    return script, ' | '.join(details) if details else 'Script loaded from matching JSON metadata.'
