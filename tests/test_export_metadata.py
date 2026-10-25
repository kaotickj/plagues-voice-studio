"""Script-preview regression tests without requiring a GUI environment."""
import json
from chatterbox_studio.export_metadata import read_export_script


def test_exact_script_roundtrip(tmp_path):
    sound = tmp_path / 'Mama_Mire.wav'
    text = '[narration] The river\u2019s quiet.\n\n[whispering] But not for long.  '
    sound.with_suffix('.json').write_text(json.dumps({'text': text, 'engine': 'chatterbox', 'model': 'turbo'}), encoding='utf-8')
    found, status = read_export_script(sound)
    assert found == text
    assert 'chatterbox' in status and 'turbo' in status


def test_optional_engine_sidecar_preview(tmp_path):
    sound = tmp_path / 'Qwen-001.wav'
    text = 'Buenos d\u00edas.\n[advertisement] Goodneighbor Records.'
    sound.with_suffix('.json').write_text(json.dumps({'engine': 'qwen3', 'text': text}), encoding='utf-8')
    assert read_export_script(sound)[0] == text


def test_missing_sidecar_avoids_stale_script(tmp_path):
    assert read_export_script(tmp_path / 'legacy.wav')[0] is None


def test_bad_metadata_is_handled(tmp_path):
    sound = tmp_path / 'bad.wav'
    meta = sound.with_suffix('.json')
    for value in ('bad-json', '[]', '{"text": null}', '{"text": "   "}'):
        meta.write_text(value, encoding='utf-8')
        script, status = read_export_script(sound)
        assert script is None
        assert status


def test_numbered_export_uses_matching_json(tmp_path):
    first = tmp_path / 'story.wav'
    second = tmp_path / 'story_2.wav'
    first.with_suffix('.json').write_text('{"text":"First recording"}', encoding='utf-8')
    second.with_suffix('.json').write_text('{"text":"Second recording"}', encoding='utf-8')
    assert read_export_script(first)[0] == 'First recording'
    assert read_export_script(second)[0] == 'Second recording'


def test_selection_preview_keeps_render_input_and_manuscript_distinct(tmp_path):
    sound = tmp_path / 'passage.wav'
    manuscript = 'The entire original manuscript.\n\nSecond passage.'
    selected = 'Second passage.'
    sound.with_suffix('.json').write_text(json.dumps({
        'text': manuscript, 'prepared_text': selected, 'render_scope': 'selection',
        'engine': 'chatterbox', 'profile': 'clear_narration',
    }), encoding='utf-8')
    rendered, status = read_export_script(sound)
    assert rendered == selected
    assert 'Selected passage' in status
    original, status = read_export_script(sound, original=True)
    assert original == manuscript
    assert 'recording contains selected passage' in status


def test_older_null_prepared_text_keeps_original_preview(tmp_path):
    sound = tmp_path / 'older.wav'
    sound.with_suffix('.json').write_text(json.dumps({
        'text': 'Legacy script.', 'prepared_text': None,
    }), encoding='utf-8')
    assert read_export_script(sound)[0] == 'Legacy script.'
    assert read_export_script(sound, original=True)[0] == 'Legacy script.'

def test_atomic_writer_and_orphaned_metadata(tmp_path):
    from chatterbox_studio.export_metadata import write_export_metadata
    from chatterbox_studio.engine import unique_output_path
    audio = tmp_path / 'example.wav'
    text = '[narration] Goodneighbor.\n\n[whispering] The Third Rail.'
    write_export_metadata(audio, {'text': text, 'engine': 'chatterbox'})
    assert read_export_script(audio)[0] == text
    # A missing WAV must never allow a later render to overwrite existing JSON.
    assert unique_output_path(audio).name == 'example_2.wav'
    assert not list(tmp_path.glob('*.tmp'))
