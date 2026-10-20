"""Verify complete local Chatterbox model directories for an offline Windows bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from download_models import REQUIRED
from chatterbox_studio.tokenizer_assets import pkuseg_ready

MARKER = 'offline-bundle.json'


def verify(root: Path, require_marker: bool = False, write_marker: bool = False) -> None:
    root = Path(root)
    failures: list[str] = []
    for model, required_files in REQUIRED.items():
        for filename in required_files:
            f = root / model / filename
            if not f.is_file() or f.stat().st_size == 0:
                failures.append(f'{model}/{filename}')
    if not pkuseg_ready(root/'tokenizers'/'pkuseg'/'spacy_ontonotes'):
        failures.append('tokenizers/pkuseg/spacy_ontonotes (missing or incomplete tokenizer files)')
    if failures:
        raise RuntimeError('Missing or empty model files:\n' + '\n'.join(failures))
    marker = root / MARKER
    expected = {'bundle': "Plague's Voice Studio", 'offline': True, 'models': sorted(REQUIRED)}
    if require_marker:
        if not marker.is_file():
            raise RuntimeError(f'Missing offline release marker: {marker}')
        try:
            data = json.loads(marker.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError('Invalid offline bundle marker') from exc
        if data != expected:
            raise RuntimeError('Offline bundle marker does not match the expected model set')
    if write_marker:
        root.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(expected, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--all', action='store_true', help='Verify all four models (the only supported policy)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write-marker', action='store_true')
    group.add_argument('--require-marker', action='store_true')
    args = parser.parse_args()
    if not args.all:
        parser.error('--all is required')
    verify(args.root, require_marker=args.require_marker, write_marker=args.write_marker)
    print(f'All four models verified at: {args.root}')


if __name__ == '__main__':
    main()
