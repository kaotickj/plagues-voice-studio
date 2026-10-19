"""User-owned advertiser campaigns; no modifications to bundled dialogue data."""
import json
import re
import uuid
from pathlib import Path

PROFILES = ('blues', 'plague')
LENGTHS = ('Short', 'Medium', 'Long')
MOODS = ('Comforting', 'Melancholy', 'Wry', 'Reflective', 'Atmospheric', 'Suspicious', 'Ominous')


def validate_campaigns(campaigns):
    if not isinstance(campaigns, list):
        raise ValueError('Campaign file must contain an advertisers list.')
    seen = set()
    for c in campaigns:
        if not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name'].strip():
            raise ValueError('Each advertiser needs a name.')
        name = c['name'].strip().casefold()
        if name in seen:
            raise ValueError('Duplicate advertiser name: ' + c['name'])
        seen.add(name)
        if not isinstance(c.get('enabled', True), bool):
            raise ValueError('Enabled must be a boolean.')
        for field in ('slogan', 'description'):
            if not isinstance(c.get(field, ''), str):
                raise ValueError(f'Advertiser {field} must be text.')
        if not isinstance(c.get('scripts', []), list):
            raise ValueError('Scripts must be a list.')
        for script in c['scripts']:
            if (not isinstance(script, dict) or script.get('profile') not in PROFILES
                    or script.get('length') not in LENGTHS or script.get('mood') not in MOODS
                    or not isinstance(script.get('text'), str) or not script['text'].strip()):
                raise ValueError('Each script needs valid station profile, length, mood, and text.')
            if re.search(r'\{[^{}]*\}', script['text']):
                raise ValueError('Ad scripts must contain complete text, not template placeholders.')


def load_campaigns(path):
    path = Path(path)
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding='utf-8'))
    result = obj.get('advertisers') if isinstance(obj, dict) else None
    validate_campaigns(result)
    return result


def save_campaigns(path, campaigns):
    validate_campaigns(campaigns)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'schema': 1, 'advertisers': campaigns}, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def new_campaign(name):
    return {'id': uuid.uuid4().hex, 'name': name.strip(), 'enabled': True,
            'slogan': '', 'description': '', 'scripts': []}


def scripts_for(campaigns, sponsor, profile, mood, length):
    return [s['text'].strip() for c in campaigns
            if c.get('enabled', True) and c['name'].casefold() == sponsor.strip().casefold()
            for s in c.get('scripts', []) if s['profile'] == profile and s['length'] == length
            and (mood == 'Any' or s['mood'] == mood)]
