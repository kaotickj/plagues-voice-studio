"""End-to-end deterministic speech-output smoke tests (no GPU/PyQt needed)."""
import json
import re
import unittest
from speech_director import CHATTERBOX_TAGS, clean_spoken_text, render, export_json

SAMPLE = (
    'The wind’s howling through the old Boston streets, and your pack’s heavier than it should be.\n\n'
    'You’re out there, scavenging, walking, fighting the cold with nothing but grit and a stubborn hope.\n\n'
    'That’s where Chleo’s Guns comes in—hand-patched, rusted, but still sharp.\n\n'
    'They don’t sell fancy steel, they sell survival.\n\n'
    'Old rifles, bolt-action, one-shot, patched with salvaged parts.\n\n'
    'No promises, just honest tools for a tough world.\n\n'
    'You don’t need a badge to feel safe.\n\n'
    'Just a good gun in your hands.\n\n'
    'Ask about Chleo’s Guns.'
)

class SpeechOutputTests(unittest.TestCase):
    def test_19_exact_native_tokens(self):
        self.assertEqual(len(CHATTERBOX_TAGS), 19)
        self.assertEqual(len(set(CHATTERBOX_TAGS)), 19)
        self.assertIn('clear throat', CHATTERBOX_TAGS)
        self.assertIn('advertisement', CHATTERBOX_TAGS)
        self.assertIn('sarcastic', CHATTERBOX_TAGS)
        self.assertNotIn('dialog', CHATTERBOX_TAGS)
        self.assertNotIn('clear_throat', CHATTERBOX_TAGS)

    def test_demo_commercial_uses_contextual_tags_not_repeated(self):
        for engine in ('Chatterbox Turbo', 'Chatterbox Nano'):
            with self.subTest(engine=engine):
                output, _ = render(SAMPLE, engine, 'Mister The Plague', 'Ad / promo')
                self.assertIn('[narration]', output)
                self.assertIn('[advertisement]', output)
                self.assertIn('[sarcastic]', output)
                self.assertEqual(output.count('[advertisement]'), 1)
                self.assertNotIn('[dialog]', output)
                self.assertEqual(clean_spoken_text(output), SAMPLE)
                self.assertEqual(render(output, engine, 'Mister The Plague', 'Ad / promo')[0], output)

    def test_other_engines_receive_no_chatterbox_tokens(self):
        turbo, _ = render(SAMPLE, 'Chatterbox Nano', 'Tal Conroy', 'Ad / promo')
        for engine in ('Plain text', 'IndexTTS 2.5', 'Qwen3-TTS (official)'):
            speech, _ = render(turbo, engine, 'Tal Conroy', 'Ad / promo')
            self.assertEqual(speech, SAMPLE)
        idx = json.loads(export_json(turbo, 'IndexTTS 2.5', 'Tal Conroy', 'Ad / promo'))
        self.assertEqual(idx['clean_text'], SAMPLE)
        self.assertEqual(len(idx['direction']['segments'][0]['emo_vector']), 8)

    def test_native_tag_manual_preservation(self):
        src = '[sarcastic] Well, of course.\n\n[clear throat] Now listen closely.'
        speech, _ = render(src, 'Chatterbox Nano', 'Tal Conroy', 'Station break')
        self.assertEqual(speech, src)
        self.assertEqual(clean_spoken_text(speech), 'Well, of course.\n\nNow listen closely.')

    def test_unsupported_dialog_does_not_go_to_speech(self):
        original = '[dialog] This is a script.\n\n[advertisement] Come buy a rifle.'
        speech, _ = render(original, 'Chatterbox Turbo', 'Tal Conroy', 'Ad / promo')
        self.assertNotIn('[dialog]', speech)
        self.assertTrue(speech.startswith('This is a script.'))

    def test_no_added_spoken_words_or_lore_fixes(self):
        result, _ = render(SAMPLE, 'Chatterbox Turbo', 'Tal Conroy', 'Ad / promo')
        self.assertEqual(clean_spoken_text(result), SAMPLE)
        self.assertIn('Chleo’s Guns', result)  # no silent substitution of custom shop names

    def test_all_auto_added_tags_exact_and_in_inventory(self):
        long_script = (SAMPLE + '\n\nListen close, they are watching you.\n\n'
                       'Incoming fire!\n\nThat joke was funny.')
        result, _ = render(long_script, 'Chatterbox Turbo', 'Mister The Plague', 'Ad / promo', 'Expressive')
        tags = re.findall(r'\[([^\]]+)\]', result)
        self.assertTrue(tags)
        self.assertTrue(all(tag in CHATTERBOX_TAGS for tag in tags))

if __name__ == '__main__':
    unittest.main()
