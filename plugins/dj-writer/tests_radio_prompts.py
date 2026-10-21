import unittest
from ai_writer import ScriptRequest, build_messages, default_settings, validate_script, clean_radio_edit_draft
from script_prompts import DEFAULT_WORDS, DJ_IDENTITIES, FORMAT_PROMPTS, SHARED_WRITING_RULES
from dj_engine import CATEGORIES, DJS

class RadioPromptTests(unittest.TestCase):
    def test_every_format_and_host_receive_new_voice_and_editorial_rules(self):
        settings = default_settings()
        for host in DJS:
            for category in CATEGORIES:
                with self.subTest(host=host, category=category):
                    text = '\n'.join(m['content'] for m in build_messages(
                        ScriptRequest(host, category), settings))
                    self.assertIn(SHARED_WRITING_RULES, text)
                    self.assertIn(DJ_IDENTITIES[host], text)
                    self.assertIn(FORMAT_PROMPTS[category], text)
                    self.assertIn('standard spelling', text)
                    if category != 'Website Promo':
                        self.assertIn('Treat lore as a constraint', text)

    def test_formats_have_distinct_broadcast_jobs(self):
        self.assertIn('One or two clean sentences', FORMAT_PROMPTS['Station ID'])
        self.assertIn('Do not introduce a new anecdote', FORMAT_PROMPTS['Broadcast closer'])
        self.assertIn('No invented local story', FORMAT_PROMPTS['Broadcast opener'])
        self.assertIn('within an ongoing broadcast', FORMAT_PROMPTS['Station break'])
        for category in ('Song introduction', 'Song outro'):
            self.assertIn('metadata', FORMAT_PROMPTS[category])
        self.assertLess(DEFAULT_WORDS['Station ID'], DEFAULT_WORDS['Broadcast closer'])
        self.assertLess(DEFAULT_WORDS['Broadcast closer'], DEFAULT_WORDS['Broadcast opener'])

    def test_custom_profiles_are_preserved_and_do_not_remove_shared_rules(self):
        settings = default_settings()
        settings['profiles']['Tal Conroy'] = 'My custom measured host notes.'
        before = dict(settings['profiles'])
        text = '\n'.join(m['content'] for m in build_messages(
            ScriptRequest('Tal Conroy', 'Broadcast closer'), settings))
        self.assertIn('My custom measured host notes.', text)
        self.assertIn('standard spelling', text)
        self.assertEqual(settings['profiles'], before)

    def test_unsupplied_record_and_time_claims_are_flagged_for_review(self):
        request = ScriptRequest('Tal Conroy', 'Broadcast opener')
        warnings = validate_script("Tonight, let's hear 'The Weight' by The Band.", request)
        self.assertTrue(any('named record' in item for item in warnings))
        self.assertTrue(any('programme claims' in item for item in warnings))

    def test_short_link_cleanup_removes_inventions_but_keeps_supplied_metadata(self):
        request = ScriptRequest('Tal Conroy', 'Broadcast opener')
        text = "Welcome in. This is Tal Conroy on Goodneighbor Blues 95.77. Let's hear 'The Weight' by The Band. Thanks for tonight."
        clean = clean_radio_edit_draft(text, request)
        self.assertEqual(clean, 'Welcome in. This is Tal Conroy on Goodneighbor Blues 95.77.')
        supplied = ScriptRequest('Tal Conroy', 'Song introduction', title='The Weight', artist='The Band', brief='Tonight.')
        self.assertEqual(clean_radio_edit_draft(text, supplied), text)

if __name__ == '__main__':
    unittest.main()
