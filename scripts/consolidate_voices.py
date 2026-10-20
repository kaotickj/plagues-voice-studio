"""Audit by default; --apply moves voice audio and creates compatibility links."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from plagued_ai.voices import plan, apply

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    options = parser.parse_args()
    prepared = plan()
    if options.apply:
        result = apply(prepared)
        print(json.dumps({'status':result['status'], 'voices':result['voice_count'],
                          'audio':str(Path(result['destination'])/'voices'),
                          'report':str(Path(result['destination'])/'voice-consolidation.json')}, indent=2))
    else:
        print(json.dumps({'voices':len(prepared['records']), 'files_to_relocate':len(prepared['moves']),
                          'destination':prepared['destination'], 'compatibility_folders':prepared['folders']}, indent=2))
