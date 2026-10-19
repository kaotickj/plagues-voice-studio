"""Engine-specific speech direction for Fallout radio scripts.

The writing model produces spoken words. This module adds *only* documented
Chatterbox Turbo/Nano native token spellings, or supplies separate metadata
for IndexTTS/Qwen3. No speech engines are invoked here.
"""
import json
import re
from dataclasses import asdict, dataclass

# The 19 dedicated tokens in ResembleAI/chatterbox-turbo's added_tokens.json.
# The style tokens are tokenizer-recognized, but audible effects differ between
# runtimes/checkpoints; the event effects are comparatively better established.
CHATTERBOX_STYLES = (
    'angry', 'fear', 'surprised', 'whispering', 'advertisement',
    'dramatic', 'narration', 'crying', 'happy', 'sarcastic',
)
CHATTERBOX_EVENTS = (
    'clear throat', 'sigh', 'shush', 'cough', 'groan',
    'sniff', 'gasp', 'chuckle', 'laugh',
)
CHATTERBOX_TAGS = CHATTERBOX_STYLES + CHATTERBOX_EVENTS
# Unsupported prompts inserted by some writing models / older drafts.
NON_SPEECH_LABELS = ('dialog', 'dialogue', 'speaker', 'pause', 'sfx', 'music',
                     'clear_throat', 'whisper', 'shout')
TAG_RE = re.compile(r'\[(' + '|'.join(re.escape(x) for x in CHATTERBOX_TAGS + NON_SPEECH_LABELS)
                    + r')\]\s*', re.I)
EMOTIONS = ('happy', 'angry', 'sad', 'afraid', 'disgusted', 'melancholic', 'surprised', 'calm')


@dataclass
class Cue:
    text: str
    mood: str
    strength: float
    reason: str
    event: str = ''


def clean_spoken_text(text):
    """Remove *known* TTS directions without deleting arbitrary literal [text]."""
    lines = []
    for line in text.splitlines():
        # Native tags may be mid-sentence; remove only the controlled vocabulary.
        line = TAG_RE.sub('', line).rstrip()
        lines.append(line)
    return '\n'.join(lines).strip()


def base_voice(dj, category):
    low = dj.casefold()
    if 'plague' in low:
        return ('Deep, intimate midnight pirate-radio host, suspicious and sardonic; '
                'paranoid but intelligent, dry conspiratorial humor, never constant shouting.')
    if 'hattie' in low or 'mama mire' in low:
        return ('Mature gravelly female Chicago blues singer turned radio host; '
                'smoky, whiskey-weathered warmth, soulful understatement.')
    return ('Measured late-night Goodneighbor blues radio storyteller; warm, worn, reflective, '
            'patient and conversational, never a theatrical announcer.')


# Splitting must not mistake "Mr. Parnell" for a sentence boundary.
_HONORIFIC_END = re.compile(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St|Sgt|Capt|Lt|Gen|Jr|Sr)\.$', re.I)
_BOUNDARY = re.compile(r'\n[ \t]*\n|(?<=[.!?])[ \t\r\n]+(?=[A-Z“"\'‘\[0-9])')


def _sentence_spans(text):
    """(paragraph number, sentence, start offset), retaining original whitespace.

    We inject native tags into offsets rather than rebuilding paragraphs, so
    cleaning the tags produces *exactly* the original spoken manuscript.
    """
    cursor = 0
    paragraph = 0
    spans = []
    for m in _BOUNDARY.finditer(text):
        gap = m.group()
        is_paragraph = '\n' in gap and gap.count('\n') >= 2
        before = text[cursor:m.start()]
        if not is_paragraph and _HONORIFIC_END.search(before.rstrip()):
            continue
        if before.strip():
            first = cursor + len(before) - len(before.lstrip())
            spans.append((paragraph, text[first:m.start()].strip(), first))
        cursor = m.end()
        if is_paragraph:
            paragraph += 1
    tail = text[cursor:]
    if tail.strip():
        first = cursor + len(tail) - len(tail.lstrip())
        spans.append((paragraph, text[first:].strip(), first))
    return spans


def _sentences(text):
    """Yield paragraph number and exact sentence text for emotion metadata."""
    for paragraph, sentence, _ in _sentence_spans(text.strip()):
        yield paragraph, sentence


def classify(text, dj='', category='', intensity='Balanced'):
    """Create sentence-level emotion metadata without modifying spoken words."""
    cues = []
    host = dj.casefold()
    for _, sentence in _sentences(clean_spoken_text(text)):
        low = sentence.casefold()
        mood, reason, strength, event = 'calm', 'natural conversational delivery', .32, ''
        if (re.search(r'\b(child|daughter|son|little girl|little boy|mother|father|family)\b', low)
                and re.search(r'\b(fever|sick|illness|cough|hungry|hunger|starving|medicine|dying|hurt)\b', low)):
            mood, strength, reason = 'melancholic', .48, 'quiet compassion for someone in hardship'
        elif re.search(r'\b(died|funeral|buried|never came back|lost her|lost him|grief|mourning)\b', low):
            mood, strength, reason = 'melancholic', .48, 'grief or loss'
        elif re.search(r'\b(listen close|keep this between us|don.t tell|not a soul|hush|whisper)\b', low):
            mood, strength, reason = 'calm', .25, 'confidential aside'
        elif re.search(r'\b(ambush|gunfire|run for|exploded|incoming|danger|shooting)\b', low):
            mood, strength, reason = 'afraid', .49, 'danger or urgency'
        elif re.search(r'\b(laughing|joke|funny|ridiculous|ha ha|hilarious)\b', low):
            mood, strength, reason, event = 'happy', .4, 'lightly amused delivery', 'chuckle'
        elif re.search(r'\b(victory|celebrate|congratulations|we made it|good news)\b', low):
            mood, strength, reason = 'happy', .50, 'hopeful or celebratory moment'
        elif re.search(r'\b(disgusting|filthy liar|betrayed|outrage|furious)\b', low):
            mood, strength, reason = 'angry', .43, 'controlled indignation'
        elif '?' in sentence and ('plague' in host or 'conspiracy' in low):
            mood, strength, reason = 'surprised', .35, 'skeptical rhetorical question'
        if category == 'Ad / promo':
            strength = min(strength, .43)
        if 'plague' in host and mood == 'afraid':
            strength = min(strength, .4)
        if intensity == 'Subtle':
            strength *= .65
        elif intensity == 'Expressive':
            strength = min(.70, strength * 1.25)
        cues.append(Cue(sentence, mood, round(strength, 2), reason, event))
    return cues


def vector(cue):
    out = [0.] * len(EMOTIONS)
    out[EMOTIONS.index(cue.mood)] = cue.strength
    return out


def _style_for(sentence, category, dj, index, intensity):
    """Only mark a genuine delivery shift; don't classify each line as an ad."""
    low = sentence.casefold()
    # Tal and Hattie use a confidential, softer delivery when ordinary people's
    # suffering becomes the point of the story. An illness mentioned in narration
    # NEVER triggers a [cough] or [crying] sound from the DJ.
    if (category == 'Stories From the Commonwealth' and intensity != 'Subtle'
            and 'plague' not in dj.casefold()
            and re.search(r'\b(child|daughter|son|little girl|little boy|mother|father|family)\b', low)
            and re.search(r'\b(fever|sick|illness|cough|hunger|hungry|starving|medicine|dying|hurt)\b', low)):
        return 'whispering'
    if re.search(r'\b(oh sure|yeah right|as if|of course you could|what could possibly|because that.s a great|you don.t need a badge)\b', low):
        return 'sarcastic'
    if re.search(r'\b(listen close|between you and me|nobody.s supposed to know|keep this between us|don.t tell a soul)\b', low):
        return 'whispering'
    if re.search(r'\b(hold on|wait a minute|would you believe|you won.t believe)\b', low):
        return 'surprised'
    if re.search(r'\b(incoming fire|gunfire erupted|the door exploded|ambush|a deathclaw (?:charged|roared))\b', low):
        return 'dramatic' if 'plague' in dj.casefold() else 'fear'
    if re.search(r'\b(here.s the good news|we made it|you survived|congratulations)\b', low):
        return 'happy'
    if re.search(r'\b(that.s outrageous|filthy liar|betrayed us|i.m furious)\b', low):
        return 'angry'
    if re.search(r'\b(i can.t stop crying|tears streamed down my face)\b', low):
        return 'crying'
    return ''


def _intro_style(sentences, category, dj):
    if category != 'Ad / promo':
        if category == 'Station ID' and 'plague' in dj.casefold():
            return 'dramatic'
        return 'narration'
    # A scene-setting hook is narrated before the actual pitch begins.
    first = sentences[0].casefold() if sentences else ''
    atmospheric = bool(re.search(r'\b(wind|rain|storm|streets|night|road|walking|cold|scaveng|fog|dark|wasteland)\b', first))
    pitch = bool(re.search(r'\b(buy|visit|ask about|now selling|come to|stop by|for sale|offers|presents)\b', first))
    return 'narration' if atmospheric and not pitch and len(sentences) > 1 else 'advertisement'


def _pitch_boundary(sentence):
    return bool(re.search(r'\b(comes in|come to|visit|ask about|shop|offers|sell|selling|buy|need a|try|available|introducing|look no further)\b',
                          sentence.casefold()))


def _event_for(sentence, intensity):
    low = sentence.casefold()
    if re.search(r'\b(joke|funny|hilarious|ha ha|laughing)\b', low):
        return 'chuckle' if intensity != 'Expressive' else 'laugh'
    if re.search(r'\b(i (?:had to )?sigh(?:ed)?|with a sigh)\b', low):
        return 'sigh'
    if re.search(r'\b(i gasped|i couldn.t believe my eyes)\b', low):
        return 'gasp'
    if re.search(r'\b(ahem|cleared my throat|clear my throat)\b', low):
        return 'clear throat'
    if re.search(r'\b(i coughed|i cough|coughing fit)\b', low):
        return 'cough'
    if re.search(r'\b(i sniffed|sniffed back tears)\b', low):
        return 'sniff'
    if re.search(r'\b(i (?:let out a )?groan(?:ed)?)\b', low):
        return 'groan'
    if re.search(r'\b(shh|be quiet now)\b', low):
        return 'shush'
    return ''


def _render_chatterbox(text, dj, category, intensity):
    # If the author deliberately supplied native Chatterbox directions, trust
    # them and preserve them rather than silently duplicating or replacing them.
    valid_existing = re.search(r'\[(' + '|'.join(re.escape(t) for t in CHATTERBOX_TAGS) + r')\]', text, re.I)
    if valid_existing:
        return re.sub(r'\[(?:dialog|dialogue|clear_throat|whisper|shout)\]\s*', '', text.strip(), flags=re.I)

    plain = clean_spoken_text(text)
    segments = _sentence_spans(plain)
    if not segments:
        return ''
    sentence_text = [sentence for _, sentence, _ in segments]
    intro = _intro_style(sentence_text, category, dj)
    budget = (max(3, min(6, 3 + len(plain.split()) // 150)) if category == 'Ad / promo'
              else max(2, min(20, 1 + len(plain.split()) // 140)))
    if intensity == 'Subtle':
        budget = max(1, budget - 1)
    # Separate style tags from sound events, which are used sparingly.
    insertions = []
    used_styles = 0
    last_style = ''
    ad_pitched = intro == 'advertisement'
    last_block = None
    last_switch = -3
    events_used = 0
    max_events = max(1, min(4, len(plain.split()) // 300 + 1))
    for i, (block, sentence, offset) in enumerate(segments):
        style = ''
        if i == 0:
            style = intro
        elif (category == 'Ad / promo' and not ad_pitched and
              _pitch_boundary(sentence) and used_styles < budget):
            style = 'advertisement'
            ad_pitched = True
        else:
            candidate = _style_for(sentence, category, dj, i, intensity)
            if (candidate and candidate != last_style and
                    i - last_switch >= 1 and used_styles < budget):
                style = candidate
        # Reset temporary styles at a new paragraph, rather than letting one
        # whispered line change the narrator for the rest of the story.
        if (not style and category != 'Ad / promo' and block != last_block and
                last_style not in ('', 'narration') and used_styles < budget):
            style = 'narration'
        event = _event_for(sentence, intensity) if events_used < max_events else ''
        if event:
            events_used += 1
        if style:
            used_styles += 1
            last_style = style
            last_switch = i
        marks = ''.join(f'[{tag}] ' for tag in (style, event) if tag)
        if marks:
            insertions.append((offset, marks))
        last_block = block
    # Insert from the end so that text offsets do not shift; this preserves
    # line breaks and punctuation in the original manuscript byte for byte.
    for offset, marks in reversed(insertions):
        plain = plain[:offset] + marks + plain[offset:]
    return plain



def render(text, engine, dj, category='', intensity='Balanced', experimental=False):
    """Produce paste-ready Chatterbox text or metadata for non-Chatterbox TTS.

    `experimental` is retained for old callers; the canonical full 19-token
    vocabulary is available, but auto-selection never inserts random effects.
    """
    plain = clean_spoken_text(text)
    instructions = base_voice(dj, category)
    if engine == 'Plain text':
        return plain, None
    if engine in ('Chatterbox Turbo', 'Chatterbox Nano'):
        speech = _render_chatterbox(text, dj, category, intensity)
        return speech, {
            'engine': engine,
            'voice_direction': instructions,
            'supported_tag_vocabulary': list(CHATTERBOX_TAGS),
            'note': ('Speech contains exact native Chatterbox token spellings. Styles and events are '
                     'contextual, not repeated every sentence. Audibility varies by backend.'),
        }
    cues = classify(plain, dj, category, intensity)
    if engine == 'IndexTTS 2.5':
        return plain, {
            'engine': engine, 'voice_direction': instructions,
            'emotion_order': list(EMOTIONS), 'use_random': False, 'use_emo_text': False,
            'note': 'Send each clean segment and emo_vector to IndexTTS; never speak the JSON.',
            'segments': [{'text': c.text, 'emo_vector': vector(c), 'reason': c.reason} for c in cues],
        }
    if engine == 'Qwen3-TTS (official)':
        return plain, {
            'engine': engine, 'voice_direction': instructions,
            'note': 'Use instruct with an instruction-capable Qwen3-TTS variant; cloning may ignore it.',
            'segments': [{'text': c.text,
                          'instruct': instructions + ' Deliver this segment with ' + c.mood +
                          ' undertones, ' + c.reason + ', remaining natural.'} for c in cues],
        }
    raise ValueError('Unsupported TTS engine: ' + engine)


def export_json(text, engine, dj, category='', intensity='Balanced', experimental=False):
    speech, metadata = render(text, engine, dj, category, intensity, experimental)
    return json.dumps({
        'schema_version': 2,
        'clean_text': clean_spoken_text(text),
        'spoken_text': speech,
        'direction': metadata,
    }, ensure_ascii=False, indent=2)
