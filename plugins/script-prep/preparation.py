"""Conservative English speech preparation. No engine markup or model required."""
from dataclasses import dataclass
from datetime import date
import re

try:
    from chatterbox_studio.text_preparation import normalize_english_times
except ModuleNotFoundError as exc:
    if exc.name not in ('chatterbox_studio', 'chatterbox_studio.text_preparation'):
        raise
    # Portable API-1 archives include the exact shared helper for older hosts.
    from .time_preparation import normalize_english_times

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()


def number(value):
    n = int(value)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + (' ' + ONES[n % 10] if n % 10 else '')
    if n < 1000:
        return ONES[n // 100] + ' hundred' + (' ' + number(n % 100) if n % 100 else '')
    return number(n // 1000) + ' thousand' + (' ' + number(n % 1000) if n % 1000 else '')


def decimal(value):
    whole, dot, fraction = value.replace(',', '').partition('.')
    return number(whole) + (' point ' + ' '.join(ONES[int(c)] for c in fraction) if dot else '')


@dataclass
class Prepared:
    text: str
    changes: list
    warnings: list


def prepare(text, entries=(), numbers=True, abbreviations=True, pauses=False):
    if len(text) > 100000:
        raise ValueError('Prepare at most 100,000 characters at a time.')
    changes, warnings = [], []
    # Preserve addresses and existing markup verbatim; do not partially rewrite them.
    protected = re.compile(r'(https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.\w+|<[^>]+>|\[[^\]\n]+\])')
    if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', text):
        warnings.append('Numeric slash dates are ambiguous; write the month in words.')
    if re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+\.\w+', text):
        warnings.append('Addresses are preserved. Check how the voice reads them.')
    if re.search(r'<[^>]+>|\[[^\]\n]+\]', text):
        warnings.append('Existing tags are preserved; confirm that your engine supports them.')

    def replace(pattern, callback, source, label, flags=0):
        def apply(match):
            result = callback(match)
            if result != match.group():
                changes.append(f'{label}: {match.group()} → {result}')
            return result
        return re.sub(pattern, apply, source, flags=flags)

    def convert(source):
        if numbers:
            def money(m):
                dollars, _, cents = m[1].replace(',', '').partition('.')
                n = int(dollars)
                result = number(n) + (' dollar' if n == 1 else ' dollars')
                if cents and int(cents):
                    result += ' and ' + number(int(cents)) + (' cent' if int(cents) == 1 else ' cents')
                return result
            source = replace(r'(?<![\w$-])\$(\d{1,3}(?:,\d{3})?|\d{1,6})(?:\.(\d{2}))?(?!\d|[.,]\d)',
                lambda m: money(re.match(r'\$(.*)', m.group())), source, 'Price')
            source = replace(r'(?<![\w.-])(\d{1,6}(?:\.\d+)?)\s*%(?!\w)', lambda m: decimal(m[1])+' percent', source, 'Percent')
            source = replace(r'(?<![\w:.])(\d{1,4}(?:\.\d+)?)\s*(FM|AM|MHz)\b', lambda m: decimal(m[1])+' '+({'FM':'F M','AM':'A M','MHz':'megahertz'}[m[2]]), source, 'Frequency')
            source = normalize_english_times(source,
                lambda original, spoken: changes.append(f'Time: {original} → {spoken}'))
            def calendar(m):
                try:
                    d = date.fromisoformat(m.group())
                except ValueError:
                    warnings.append('Invalid calendar date preserved: '+m.group())
                    return m.group()
                day = number(d.day)
                irregular = {'one':'first','two':'second','three':'third','five':'fifth','eight':'eighth','nine':'ninth','twelve':'twelfth','twenty':'twentieth','thirty':'thirtieth'}
                words = day.split(); words[-1] = irregular.get(words[-1], words[-1]+'th')
                return d.strftime('%B')+' '+' '.join(words)+', '+number(d.year)
            source = replace(r'\b\d{4}-\d{2}-\d{2}\b', calendar, source, 'Date')
        if abbreviations:
            for token, spoken in [('Dr.', 'Doctor'), ('Mr.', 'Mister'), ('Mrs.', 'Missus'), ('vs.', 'versus')]:
                source = replace(r'(?<!\w)'+re.escape(token)+r'(?!\w)', lambda m, s=spoken: s, source, 'Abbreviation')
        if pauses:
            source = replace(r'\s*[—–]\s*', lambda m: ', ', source, 'Pause')
        return source

    # Dictionary applied once, longest phrases first; replacements never cascade.
    mapping = {item['term'].casefold(): item['spoken'] for item in entries}
    pattern = re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(mapping, key=len, reverse=True))+r')(?!\w)', re.I) if mapping else None
    chunks = protected.split(text)
    for i in range(0, len(chunks), 2):
        if pattern:
            parts, start = [], 0
            for match in pattern.finditer(chunks[i]):
                parts.append(convert(chunks[i][start:match.start()]))
                spoken = mapping[match.group().casefold()]
                parts.append(spoken)
                if spoken != match.group():
                    changes.append(f'Pronunciation: {match.group()} → {spoken}')
                start = match.end()
            parts.append(convert(chunks[i][start:])); chunks[i] = ''.join(parts)
        else:
            chunks[i] = convert(chunks[i])
    return Prepared(''.join(chunks), changes, list(dict.fromkeys(warnings)))
