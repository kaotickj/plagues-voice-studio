"""Conservative, model-independent preparation of English render text.

The manuscript stays unchanged. Only unambiguous twelve-hour clocks with an
AM/PM suffix are expanded, before an engine can discard the colon. This is also
used by Script Prep, so applying its review workflow first does not cascade.
"""
from __future__ import annotations

import re
from collections.abc import Callable


_ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
_TENS = 'zero ten twenty thirty forty fifty'.split()
_ENGLISH = frozenset(('en', 'english', 'english (us)', 'english (uk)'))

# Protect complete address/markup tokens before looking for clocks. A colon in
# a URL, reference, direction or version must never become spoken clock text.
_PROTECTED = re.compile(
    r'(?<![\w.+-])(?:[a-z][a-z0-9+.-]*://|www\.)\S+'
    r'|(?<![^\s<>\[\]])[^\s<>\[\]]+@[^\s<>\[\]]+'
    r'|<[^<>]*>|\[[^\[\]\r\n]*\]'
    r'|(?<!\w)\d+(?:[ \t]*:[ \t]*\d+){2,}(?:[ \t]*[ap]\.?m\.?)?', re.IGNORECASE,
)
_CLOCK = re.compile(
    r'(?<![\w.:/\\@+\-])(?P<hour>0?[1-9]|1[0-2]):(?P<minute>[0-5][0-9])'
    # Possessive final dot prevents backtracking around the token boundary:
    # e.g. a.m./file must not become a.m../file after a partial match.
    r'[ \t]*(?P<meridiem>[ap])\.?m\.?+(?![\w:/\\@+\-]|\.\w)',
    re.IGNORECASE,
)


def _number(value: int) -> str:
    if value < 20:
        return _ONES[value]
    return _TENS[value // 10] + (' ' + _ONES[value % 10] if value % 10 else '')


def normalize_english_times(text: str, on_change: Callable[[str, str], None] | None = None) -> str:
    """Expand valid AM/PM clocks once, preserving protected spans verbatim.

    Zero minutes omit the minute words; 01–09 use "oh". Twelve a.m./p.m.
    retain their explicit meridiem rather than inferring a date boundary.
    Bare ratios, twenty-four-hour clocks and invalid clocks are untouched.
    """
    if ':' not in text:
        return text

    def replace(match: re.Match) -> str:
        hour, minute = int(match['hour']), int(match['minute'])
        spoken = _number(hour)
        if minute:
            spoken += (' oh ' if minute < 10 else ' ') + _number(minute)
        spoken += ' ' + match['meridiem'].lower() + '.m.'
        if on_change is not None:
            on_change(match.group(), spoken)
        return spoken

    result, start = [], 0
    for protected in _PROTECTED.finditer(text):
        result.append(_CLOCK.sub(replace, text[start:protected.start()]))
        result.append(protected.group())
        start = protected.end()
    result.append(_CLOCK.sub(replace, text[start:]))
    return ''.join(result)


def prepare_render_text(text: str, language: str = 'en') -> str:
    """Use English clock wording only for an explicitly English render."""
    return normalize_english_times(text) if language.lower() in _ENGLISH else text
