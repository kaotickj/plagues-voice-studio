"""Curated, coherence-first offline radio dialogue engine. No generative model required."""
import json
import random
import re
import sys
from collections import deque
from difflib import SequenceMatcher
from pathlib import Path
from ad_manager import scripts_for

CATEGORIES = ['Broadcast opener', 'Station ID', 'Station break', 'Song introduction',
              'Song outro', 'Ad / promo', 'Website Promo', 'Broadcast closer', 'Stories From the Commonwealth', 'Random mix']
MOODS = ['Any', 'Comforting', 'Melancholy', 'Wry', 'Reflective', 'Atmospheric', 'Suspicious', 'Ominous']
LENGTHS = ['Short', 'Medium', 'Long']
DJS = ['Tal Conroy', 'Hattie Boggs', 'Mister The Plague']
DJ_NAME_VARIANTS = {
    'Tal Conroy': ('Tal Conroy',),
    'Hattie Boggs': ('Hattie Boggs', 'Mama Mire', 'Hattie “Mama Mire” Boggs'),
    'Mister The Plague': ('Mister The Plague', 'The Plague'),
    # Backward compatibility with the v0.2.0 display name.
    'Hattie “Mama Mire” Boggs': ('Hattie Boggs', 'Mama Mire', 'Hattie “Mama Mire” Boggs'),
}
STATION = 'Goodneighbor Blues, 95.77'
PLAGUE_STATION = 'Plague Radio'

def dj_profile(dj):
    return 'plague' if dj.strip() in DJ_NAME_VARIANTS.get('Mister The Plague', ()) or dj.strip() == 'Mister The Plague' else 'blues'


def resource_path(filename):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return root / filename


def load_content(path=None):
    path = Path(path) if path else resource_path('dialogue.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    validate_content(data)
    return data


def load_stories(path=None):
    data = json.loads((Path(path) if path else resource_path('stories.json')).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('stories'), list):
        raise ValueError('Unknown story library format.')
    identifiers = set()
    for story in data['stories']:
        if not isinstance(story, dict) or not all(isinstance(story.get(k), str) and story[k].strip() for k in ('id', 'title', 'text')):
            raise ValueError('Each story needs an id, title and complete text.')
        if story['id'] in identifiers:
            raise ValueError('Duplicate story id: ' + story['id'])
        identifiers.add(story['id'])
        if story.get('profile') not in ('blues', 'plague') or not isinstance(story.get('moods'), list) or not story['moods']:
            raise ValueError('Each story needs a station profile and moods.')
        if any(m not in MOODS[1:] for m in story['moods']):
            raise ValueError('Unknown story mood.')
        if set(re.findall(r'\{([^{}]+)\}', story['text'])) - {'dj', 'station'}:
            raise ValueError('Unknown story placeholder.')
    if not data['stories']:
        raise ValueError('The story library is empty.')
    return data['stories']


def validate_content(data):
    if not isinstance(data, dict) or not isinstance(data.get('scenes'), list):
        raise ValueError('Dialogue database must contain a scenes list.')
    identifiers = set()
    for scene in data['scenes']:
        if not isinstance(scene, dict) or not all(scene.get(k) for k in ('id','category','mood','setup','thought','landing')):
            raise ValueError('Each scene needs id, category, mood, setup, thought, and landing.')
        if scene['id'] in identifiers: raise ValueError('Duplicate scene id: ' + scene['id'])
        identifiers.add(scene['id'])
        if scene.get('profile', 'blues') not in ('blues', 'plague'): raise ValueError('Unknown DJ profile.')
        if scene['category'] not in CATEGORIES[:-1]: raise ValueError('Unknown category: ' + scene['category'])
        if scene['mood'] not in MOODS[1:]: raise ValueError('Unknown mood: ' + scene['mood'])
        for field in ('setup', 'thought', 'landing'):
            if not isinstance(scene[field], list) or not scene[field] or any(not isinstance(x, str) or not x.strip() for x in scene[field]):
                raise ValueError(f'{scene["id"]}: {field} must be a nonempty list of strings.')
            for phrase in scene[field]:
                tokens = set(re.findall(r'\{([^{}]+)\}', phrase))
                if tokens - {'dj', 'title', 'artist_phrase', 'sponsor', 'station'}:
                    raise ValueError(f'{scene["id"]}: unknown placeholder {tokens}')
    if not data['scenes']: raise ValueError('No scenes available.')


def similarity(a, b):
    # Two tests: normalized exact text proximity and vocabulary overlap.
    x = re.sub(r'[^\w ]', '', a.casefold())
    y = re.sub(r'[^\w ]', '', b.casefold())
    if x == y: return 1.0
    words_x, words_y = set(x.split()), set(y.split())
    overlap = len(words_x & words_y) / max(1, len(words_x | words_y))
    return max(SequenceMatcher(None, x, y).ratio(), overlap)


class DialogueEngine:
    def __init__(self, data=None, rng=None, campaigns=None):
        self.data = data if data is not None else load_content()
        validate_content(self.data)
        self.rng = rng or random.Random()
        self.recent_ids = deque(maxlen=80)
        self.campaigns = campaigns if campaigns is not None else []

    def generate_one(self, category, dj, title='', artist='', sponsor='Goodneighbor Blues',
                     mood='Any', length='Medium', history=()):
        """The desktop workflow returns exactly one complete script, never a list.

        Long-form stories are authored whole. They are not assembled from
        unrelated scene fragments or padded to meet an arbitrary word count.
        """
        if dj not in DJ_NAME_VARIANTS:
            raise ValueError('Select a known DJ.')
        if category == 'Stories From the Commonwealth':
            if mood not in MOODS:
                raise ValueError('Invalid mood.')
            stories = load_stories()
            available = [s for s in stories if s['profile'] == dj_profile(dj)
                         and (mood == 'Any' or mood in s['moods'])]
            if not available:
                return '', 'No complete story matches this DJ and mood. Try Any mood.'
            values = {'dj': dj, 'station': PLAGUE_STATION if dj_profile(dj) == 'plague' else STATION}
            choices = [s['text'].format(**values).strip() for s in available]
            fresh = [s for s in choices if s not in history]
            return self.rng.choice(fresh or choices), ('' if fresh else 'This story has appeared before. The story library is finite; no filler was added.')
        results, warning = self.generate_batch(category, dj, title, artist, sponsor,
                                                mood, length, quantity=1, history=history)
        return (results[0] if results else ''), warning

    def generate_batch(self, category, dj, title='', artist='', sponsor='Goodneighbor Blues',
                       mood='Any', length='Medium', quantity=5, history=()):
        if category not in CATEGORIES or mood not in MOODS or length not in LENGTHS:
            raise ValueError('Invalid category, mood or length.')
        if not 1 <= quantity <= 100: raise ValueError('Quantity must be 1–100.')
        if category == 'Website Promo':
            from spot_templates import prepared_copy, context
            line = prepared_copy(category, '', {}, context(dj, STATION))
            return [line], ('' if quantity == 1 else 'One prepared website invitation is available; use AI Studio quick templates for offers.')
        categories = CATEGORIES[:-1] if category == 'Random mix' else [category]
        # Custom scripts are complete, human-authored spots. They are never
        # intermixed with unrelated fragments from the bundled scene database.
        if 'Ad / promo' in categories:
            custom = scripts_for(self.campaigns, sponsor, dj_profile(dj), mood, length)
            if custom:
                self.rng.shuffle(custom)
                distinct = []
                for spot in custom:
                    if spot in distinct or any(similarity(spot, x) >= .9 for x in distinct): continue
                    if any(similarity(spot, x) >= .96 for x in list(history)[-150:]): continue
                    distinct.append(spot)
                    if len(distinct) >= quantity: break
                warning = '' if len(distinct) == quantity else f'Only {len(distinct)} distinct custom ad(s) available. Add more scripts for this station, mood and length.'
                return distinct, warning
            # Registered custom advertisers do not fall back to generic ads.
            if any(c['name'].casefold() == sponsor.strip().casefold() for c in self.campaigns):
                return [], 'No enabled custom ad scripts match this DJ, mood and length.'
        profile = dj_profile(dj)
        scenes = [s for s in self.data['scenes'] if s['category'] in categories and s.get('profile', 'blues') == profile and
                  (mood == 'Any' or s['mood'] == mood) and
                  (s['id'] != 'ad-custom' or sponsor.strip().casefold() not in ('the third rail', 'memory den', 'goodneighbor blues', 'plague radio')) and
                  (s.get('sponsor') is None or s['sponsor'].casefold() == sponsor.strip().casefold())]
        if not scenes:
            return [], 'No compatible dialogue scenes. Try Any mood or another advertiser.'
        # Prefer fresh scene families, but avoid an infinite search with limited libraries.
        by_preference = sorted(scenes, key=lambda s: (s['id'] in self.recent_ids, self.rng.random()))
        recent_text = list(history)[-150:]
        results = []
        used = set()
        for strictness in (0.73, 0.82, 0.93, 0.995):
            for scene in by_preference:
                if len(results) >= quantity: break
                for _ in range(10):
                    sample = self._render(scene, dj, title, artist, sponsor, length)
                    if sample in used: continue
                    if any(similarity(sample, old) >= strictness for old in results): continue
                    # Historical repetition threshold is slightly more forgiving.
                    if any(similarity(sample, old) >= min(.99, strictness + .1) for old in recent_text): continue
                    results.append(sample); used.add(sample)
                    self.recent_ids.append(scene['id'])
                    break
            if len(results) >= quantity: break
        warning = '' if len(results) == quantity else (f'Only {len(results)} sufficiently distinct line(s) available out of {quantity} requested. '
                  'The generator does not invent incoherent filler to meet the quota. Try Any mood, another type, or fewer lines.')
        return results, warning

    def _render(self, scene, dj, title, artist, sponsor, length):
        # All variation occurs *within* a curated scenario. The thought and landing
        # have been authored to follow the setup, no cross-theme sentence roulette.
        dj_choice = dj.strip() or DJS[0]
        # Resolve one name per generated line, not independently per sentence.
        display_name = self.rng.choice(DJ_NAME_VARIANTS.get(dj_choice, (dj_choice,)))
        values = {'dj': display_name, 'title': f'“{title.strip()}”' if title.strip() else 'the next record',
                  'artist_phrase': f' by {artist.strip()}' if artist.strip() else '',
                  'sponsor': sponsor.strip() or 'a local establishment', 'station': PLAGUE_STATION if dj_profile(dj) == 'plague' else STATION}
        setup = self.rng.choice(scene['setup']).format(**values)
        thought = self.rng.choice(scene['thought']).format(**values)
        landing = self.rng.choice(scene['landing']).format(**values)
        # All three pieces are independently meaningful within their thematic family;
        # short = scene punchline, medium = context + resolution, long = full arc.
        if length == 'Short': parts = [landing]
        elif length == 'Medium': parts = [setup, landing]
        else: parts = [setup, thought, landing]
        result = ' '.join(parts)
        result = re.sub(r'\s+', ' ', result).strip()
        return result
