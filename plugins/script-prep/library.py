"""Atomic per-plugin dictionary persistence; corrupt libraries are never overwritten."""
import json
import os
import tempfile
from pathlib import Path


def validate(data):
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('profiles'), dict):
        raise ValueError('Unsupported dictionary format.')
    if not 1 <= len(data['profiles']) <= 100:
        raise ValueError('Keep between 1 and 100 profiles.')
    for name, entries in data['profiles'].items():
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or not isinstance(entries, list) or len(entries) > 1000:
            raise ValueError('Invalid profile name or dictionary size.')
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or any(not isinstance(entry.get(k), str) or not entry[k].strip() or len(entry[k]) > 200 or '\n' in entry[k] for k in ('term', 'spoken')):
                raise ValueError('Each entry needs a term and spoken form (at most 200 characters).')
            key = entry['term'].casefold()
            if key in seen:
                raise ValueError('Duplicate pronunciation: '+entry['term'])
            seen.add(key)
    return data


class Library:
    def __init__(self, directory):
        self.path = Path(directory) / 'dictionaries.json'

    def load(self):
        if not self.path.exists():
            return {'version': 1, 'profiles': {'General': [], 'Fallout broadcasts': [], 'Advertisers': []}}
        if self.path.stat().st_size > 2000000:
            raise ValueError('Dictionary file is too large.')
        return validate(json.loads(self.path.read_text(encoding='utf-8')))

    def save(self, data):
        validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
