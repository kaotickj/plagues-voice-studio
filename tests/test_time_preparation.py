"""Clock preparation and shared render inputs; no audio or model inference."""
from dataclasses import replace
import json

import pytest

from chatterbox_studio.jobs import NarrationJob
from chatterbox_studio.text_preparation import normalize_english_times, prepare_render_text


@pytest.mark.parametrize('source,expected', [
    ('9:05am', 'nine oh five a.m.'),
    ('9:05 a.m.', 'nine oh five a.m.'),
    ('09:05AM', 'nine oh five a.m.'),
    ('12:00pm', 'twelve p.m.'),
    ('12:00 a.m.', 'twelve a.m.'),
    ('12:01AM', 'twelve oh one a.m.'),
    ('12:59pm', 'twelve fifty nine p.m.'),
    ('1:09 pm', 'one oh nine p.m.'),
    ('11:10 p.m.', 'eleven ten p.m.'),
    ('At 9:05am, then 10:30 P.M.!', 'At nine oh five a.m., then ten thirty p.m.!'),
    ('(9:05am)', '(nine oh five a.m.)'),
])
def test_valid_twelve_hour_clocks(source, expected):
    changes = []
    assert normalize_english_times(source, lambda *change: changes.append(change)) == expected
    assert changes
    assert normalize_english_times(expected) == expected


@pytest.mark.parametrize('source', [
    '0:05am', '00:05am', '13:05pm', '24:00pm', '9:60am', '9:99pm',
    '9:5am', '9:005am', '009:05am', '9:05', '09:05', '21:05',
    '9:05 a.missing', '9:05amp', '9:05am_suffix', 'x9:05am',
    'ratio 9:05', '1:9:05am', '9:05:30am', 'v1.9:05am', 'v9:05am',
    'ratio 1: 9:05am', 'ratio 1 : 9 : 05am',
    '9:05 a.m./10:30 p.m.', '9:05a.m.:x', '9:05a.m.-1', '9:05a.m..org',
    '9:05am.2', '9:05am/path', '/9:05am', r'C:\9:05am',
    'https://example.test/9:05am www.example.test/9:05am',
    'ftp://example.test/9:05am?next=10:30pm',
    '9:05am@example.test someone@example.test/9:05am',
    '<break time="9:05am"/> [direction 9:05 a.m.]',
])
def test_invalid_ambiguous_and_protected_text_is_unchanged(source):
    changes = []
    assert normalize_english_times(source, lambda *change: changes.append(change)) == source
    assert not changes


def test_protected_spans_do_not_hide_other_valid_clocks():
    source = 'https://example.test/9:05am at 9:05am [rate:0.9]10:30pm[/rate]'
    assert normalize_english_times(source) == (
        'https://example.test/9:05am at nine oh five a.m. [rate:0.9]ten thirty p.m.[/rate]')


def test_long_non_address_token_does_not_mask_separate_clock():
    token = 'a' * 100000 + ':9:05am'
    assert normalize_english_times(token + ' at 9:05am') == token + ' at nine oh five a.m.'


@pytest.mark.parametrize('language', ['en', 'English', 'EN', 'English (US)', 'English (UK)'])
def test_explicit_english_language_aliases(language):
    assert prepare_render_text('9:05am', language) == 'nine oh five a.m.'


@pytest.mark.parametrize('language', ['fr', 'French', 'Auto', 'zh', ''])
def test_other_languages_are_not_given_english_words(language):
    assert prepare_render_text('9:05am', language) == '9:05am'


def narration(**kwargs):
    values = dict(text='Meet at 9:05 a.m.', model='english', device='cpu', language='en',
                  voice_path='', output_path='clock.wav')
    return NarrationJob(**(values | kwargs))


@pytest.mark.parametrize('model', ['nano', 'turbo', 'english', 'multilingual-v3'])
def test_all_english_narration_models_share_clock_preparation(model):
    job = narration(model=model)
    assert job.text == 'Meet at 9:05 a.m.'
    assert job.render_text == 'Meet at nine oh five a.m.'
    assert [step.text for step in job.render_steps() if step.kind == 'speech'] == [job.render_text]
    restored = NarrationJob(**json.loads(json.dumps(job.as_json())))
    assert restored.text == job.text and restored.render_text == job.render_text
    if model == 'multilingual-v3':
        assert replace(job, language='fr').render_text == job.text


def test_selection_preparation_preserves_full_manuscript_and_directions():
    source = 'First at 8:00am. [rate:0.9]Meet at 9:05am.[/rate] Later at 10:00pm.'
    job = narration(text=source, prepared_text='[rate:0.9]Meet at 9:05am.[/rate]', render_scope='selection')
    job.validate()
    assert job.text == source
    assert job.render_text == '[rate:0.9]Meet at nine oh five a.m.[/rate]'
    speech = [step for step in job.render_steps() if step.kind == 'speech']
    assert [(step.text, step.rate) for step in speech] == [('Meet at nine oh five a.m.', 0.9)]


def test_clock_expansion_and_chunking_preserve_all_prepared_words():
    job = narration(text=('Meet at 9:05am and return at 10:30pm. ' * 20).strip(), max_chars=60)
    speech = [step.text for step in job.render_steps() if step.kind == 'speech']
    assert len(speech) > 1
    assert ' '.join(speech).split() == job.render_text.split()
    assert job.render_text.count('nine oh five a.m.') == 20
    assert job.render_text.count('ten thirty p.m.') == 20
