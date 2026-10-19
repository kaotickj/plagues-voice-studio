"""Regression tests for live-ready human-stakes storytelling and exact preservation."""
import ast
import re
import unittest
from pathlib import Path

from speech_director import _sentences, CHATTERBOX_TAGS, clean_spoken_text, render

STORY = (
    'The wind’s been howling off the Charles River since dawn, and the mutfruit patch behind the Hotel Rexford '
    'hasn’t grown a single fruit in three days. I heard old Mr. Parnell say it was the water—damaged purifier '
    'again, just like last year. But that’s not what’s bothering Elsie. She’s been hauling sacks of caps '
    'from the Third Rail to the market every night, not for profit, not for pride—just to keep her daughter’s '
    'fever down. The little girl’s cough won’t stop, and the only thing that’s helped so far is a cup of tea '
    'made with mutfruit bark, which tastes like burnt sugar and hope.'
)


class StoryDirectionRegression(unittest.TestCase):
    def test_exact_storygets_context_cues_no_sound_event(self):
        for engine in ('Chatterbox Turbo', 'Chatterbox Nano'):
            with self.subTest(engine=engine):
                script, manifest = render(STORY, engine, 'Tal Conroy', 'Stories From the Commonwealth')
                self.assertTrue(script.startswith('[narration] The wind'))
                self.assertIn('[whispering] She’s been hauling sacks', script)
                self.assertNotIn('[cough]', script)
                self.assertNotIn('[crying]', script)
                self.assertEqual(clean_spoken_text(script), STORY)
                self.assertEqual(render(script, engine, 'Tal Conroy', 'Stories From the Commonwealth')[0], script)
                self.assertTrue(all(x in CHATTERBOX_TAGS for x in re.findall(r'\[([^]]+)\]', script)))

    def test_subtle_does_not_force_whisper(self):
        script, _ = render(STORY, 'Chatterbox Turbo', 'Tal Conroy', 'Stories From the Commonwealth', 'Subtle')
        self.assertTrue(script.startswith('[narration]'))
        self.assertNotIn('[whispering]', script)

    def test_abbreviations_not_split_into_fake_sentences(self):
        parts = list(_sentences(STORY))
        self.assertEqual(len(parts), 5)
        self.assertIn('Mr. Parnell', parts[1][1])

    def test_other_engines_get_compassion_without_tags(self):
        for eng in ('IndexTTS 2.5', 'Qwen3-TTS (official)'):
            raw, meta = render(STORY, eng, 'Tal Conroy', 'Stories From the Commonwealth')
            self.assertEqual(raw, STORY)
            self.assertEqual(len(meta['segments']), 5)
            self.assertIn('quiet compassion', str(meta['segments'][3]))

    def test_exact_multiline_whitespace_and_spoken_content_preserved(self):
        src = 'The rain fell hard.  She had nowhere to go.\n\nThe mother was sick,\nand the daughter had a fever.'
        directed, _ = render(src, 'Chatterbox Nano', 'Tal Conroy', 'Stories From the Commonwealth')
        self.assertEqual(clean_spoken_text(directed), src)
        self.assertEqual(directed.count('[narration]'), 1)

    def test_throttled_preview_wired_with_independent_raw_buffer(self):
        # Qt is absent on this build host, so validate the intended GUI wiring
        # statically without pretending this exercises a live Windows GUI.
        source = (Path(__file__).parent / 'ai_studio.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('self.live_timer.setInterval(350)', source)
        self.assertIn('self._live_text += fragment', source)
        self.assertIn('self.host.set_generated_script(self._live_text)', source)
        self.assertIn('self.live_timer.stop()', source)

if __name__ == '__main__':
    unittest.main()
