"""Bounded story variety hints; past drafts never become facts or instructions."""
import random
import re
from collections import Counter

# Only these fixed labels can enter a prompt from unreviewed history. No raw
# sentences, names, invented lore or model-written instructions are forwarded.
MOTIFS = {
    'brahmin': r'\bbrahmin\b',
    'bridge tolls': r'\btolls?\b',
    'mutfruit': r'\bmutfruit\b',
    'bridges': r'\b(?:bridge|overpass)\b',
    'caravans': r'\bcaravans?\b',
    'robots': r'\b(?:robots?|protectrons?|mister handy|mr\.? handy)\b',
    'water equipment': r'\b(?:purifier|water pump|water filter)\b',
    'radio equipment': r'\b(?:transmitter|antenna|radio repair)\b',
    'missing possessions': r'\b(?:lost|missing|stolen)\s+(?:trinket|locket|lantern|watch|bag)\b',
    'mysterious signals': r'\b(?:signal|signals|secret frequency)\b',
    'Institute theories': r'\bInstitute\b',
    'Memory Den': r'\bMemory Den\b',
    'Third Rail': r'\bThird Rail\b',
    'train yards': r'\b(?:train yard|rail ties|railway|rail line)\b',
    'a walk interrupted by a stranger': r'\b(?:walking back|on my way back|stopped me|flagged me down)\b',
}


def story_motifs(text):
    return {label for label, pattern in MOTIFS.items()
            if re.search(pattern, str(text)[:12000], re.I)}


def recent_story_motifs(recent):
    counts = Counter(label for text in list(recent)[-6:] for label in story_motifs(text))
    return [label for label, count in counts.most_common(8)]


def story_variation(brief, seed=None):
    rng = random.Random(seed) if seed is not None else random
    return {
        'source': ('Follow the source specified in the brief; otherwise choose a plausible source.'
                   if brief.strip() else rng.choice((
                       'Firsthand: the selected DJ took part in or directly witnessed the incident.',
                       'Reported: someone told the selected DJ; keep that attribution throughout.'))),
        'payoff_direction': rng.choice((
            'An observable practical consequence.',
            'A comic reversal that follows from the characters\' actions.',
            'A small human decision with an observable result.',
            'A revealing discrepancy in the source\'s account.',
            'An earned escape from a concrete difficulty.')),
        'setting_type': rng.choice(('a roadside worksite', 'a shared cooking area',
            'a salvage sorting yard', 'an improvised clinic', 'a settlement gate',
            'a trading stall', 'a roof repair job', 'a communal water queue',
            'a public noticeboard', 'a caravan rest stop')),
        'conflict_type': rng.choice(('competing practical needs',
            'a misunderstanding with consequences', 'a bluff that gets tested',
            'a trade-off under pressure', 'an inconvenient obligation',
            'a disputed claim of ownership')),
        'instruction': 'Invent the incident yourself. These are structural choices, not a plot or a stock opening.',
    }


PLAN_KEYS = ('source', 'goal', 'obstacle', 'action', 'outcome', 'closing_aside', 'wasteland_cause')


def validate_story_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError('Story planner did not return an object. Try again.')
    clean = {}
    for key in PLAN_KEYS:
        value = plan.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 900:
            raise ValueError(f'Story planner returned an invalid {key}. Try again.')
        clean[key] = value.strip()
    return clean
