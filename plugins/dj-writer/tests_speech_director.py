import json
import unittest
from speech_director import render, export_json, classify, EMOTIONS

class SpeechTests(unittest.TestCase):
    def test_plain_preserves_source(self):
        src = 'The fog came in.\n\nNobody spoke.'
        self.assertEqual(render(src, 'Plain text', 'Tal Conroy')[0], src)
    def test_vectors_have_eight_bounded_entries(self):
        result = json.loads(export_json('Someone died. Run for cover!', 'IndexTTS 2.5', 'Mister The Plague'))
        for segment in result['direction']['segments']:
            self.assertEqual(len(segment['emo_vector']), len(EMOTIONS))
            self.assertTrue(0 <= sum(segment['emo_vector']) <= .8)
        self.assertEqual(result['direction']['use_emo_text'], False)
    def test_qwen_instruct_not_speech(self):
        original = 'This is just a test.'
        result = json.loads(export_json(original, 'Qwen3-TTS (official)', 'Hattie Boggs'))
        self.assertEqual(result['spoken_text'], original)
        self.assertIn('gravelly', result['direction']['segments'][0]['instruct'])
    def test_nano_native_tags(self):
        rendered, manifest = render('The joke was funny.', 'Chatterbox Nano', 'Tal Conroy')
        self.assertIn('[chuckle]', rendered)
        self.assertEqual(manifest['engine'], 'Chatterbox Nano')
    def test_turbo_minimal(self):
        rendered, _ = render('The joke was funny.', 'Chatterbox Turbo', 'Tal Conroy')
        self.assertIn('[chuckle]', rendered)
        self.assertIn('The joke was funny.', rendered)

if __name__ == '__main__': unittest.main()
