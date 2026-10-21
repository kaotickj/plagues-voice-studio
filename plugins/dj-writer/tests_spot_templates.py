"""Reusable commercial terms, website isolation and real Qt spot selection."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
import goodneighbor_dj as gui
from ai_writer import ScriptRequest, build_messages, default_settings, validate_script
from ai_writer import LocalWriter
from dj_engine import CATEGORIES
from spot_templates import checked_terms, context, load_terms, prepared_copy, resolve_template, save_terms, templates_for


class SpotTemplateTests(unittest.TestCase):
    def test_all_formats_have_a_tailored_default(self):
        for category in CATEGORIES:
            template = resolve_template(category)
            self.assertIn(template, templates_for(category))
            if category != 'Stories From the Commonwealth':
                copy = prepared_copy(category, '', {}, context('Tal Conroy', 'Goodneighbor Blues, 95.77'))
                self.assertTrue(copy)
                self.assertNotIn('{', copy)
                self.assertIn('goodneighborblues.com' if category == 'Website Promo' else 'Goodneighbor Blues', copy)

    def test_percentage_offer_is_exact_and_omits_unsupplied_conditions(self):
        text = prepared_copy('Website Promo', 'percent-off', dict(percent='12.5%', offer='the selected album'), {})
        self.assertEqual(text, 'Save 12.5 percent on the selected album at goodneighborblues.com.')
        self.assertNotIn('ends', text)
        self.assertNotIn('code', text)

    def test_subscription_preserves_introductory_and_renewal_terms(self):
        terms = dict(plan='Blues Club', price='$5', billing='per month', duration='the first three months',
                     renewal='$9 per month', code='BLUE3', eligibility='New members only')
        text = prepared_copy('Website Promo', 'subscription', terms, {})
        for supplied in ('$5', 'per month', 'the first three months', '$9 per month', 'BLUE3', 'New members only'):
            self.assertIn(supplied, text)
        self.assertNotIn('exclusive', text)
        self.assertNotIn('cancel', text)
        self.assertNotIn('free', text)

    def test_missing_terms_and_invalid_percentages_fail_before_inference(self):
        template = resolve_template('Website Promo', 'percent-off')
        for value in ('0', '-5', '101', 'NaN', 'Infinity', 'lots'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                checked_terms(template, dict(percent=value, offer='albums'))
        with self.assertRaisesRegex(ValueError, 'renewal'):
            checked_terms(resolve_template('Website Promo', 'subscription'), dict(plan='Club', price='$5', billing='per month', duration='three months'))

    def test_website_prompt_excludes_fiction_and_unrelated_slogans(self):
        settings = default_settings()
        settings['lore'] = 'SECRET FICTION LORE'
        settings['continuity']['Mister The Plague'] = 'SECRET CONTINUITY'
        request = ScriptRequest('Mister The Plague', 'Ad / promo', template_id='percent-off',
                                template_values=dict(percent='25', offer='albums'),
                                advertiser_slogan='AN UNRELATED SLOGAN')
        prompt = '\n'.join(message['content'] for message in build_messages(request, settings, references='SECRET WIKI', character_notes='SECRET CHARACTER NOTES'))
        for secret in ('SECRET FICTION LORE', 'SECRET CONTINUITY', 'SECRET WIKI', 'SECRET CHARACTER NOTES', 'AN UNRELATED SLOGAN'):
            self.assertNotIn(secret, prompt)
        self.assertIn('goodneighborblues.com', prompt)
        self.assertIn('"percent": "25"', prompt)
        self.assertNotIn('one complete in-world radio commercial', prompt)

    def test_changed_offer_or_code_is_flagged_for_review(self):
        request = ScriptRequest('Tal Conroy', 'Website Promo', template_id='percent-off',
                                template_values=dict(percent='25', offer='albums', code='BLUE25'))
        warnings = validate_script('Save 15 percent on albums at goodneighborblues.com. Use code BLUE15.', request)
        self.assertTrue(any('discount' in item for item in warnings))
        self.assertTrue(any('promo code' in item for item in warnings))

    def test_saved_terms_are_separate_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'terms.json'
            values = {'percent-off': dict(percent='20', offer='albums', code='ABC')}
            save_terms(path, values)
            self.assertEqual(load_terms(path)['percent-off']['code'], 'ABC')
            self.assertNotIn('subscription', load_terms(path))

    def test_price_substrings_and_unsupplied_urgency_are_not_accepted(self):
        request = ScriptRequest('Tal Conroy', 'Website Promo', template_id='price-offer',
                                template_values=dict(offer='albums', price='$5'))
        warnings = validate_script('Albums for $15 at goodneighborblues.com. Today only.', request)
        self.assertTrue(any('exact price' in item for item in warnings))
        self.assertTrue(any('deadline' in item for item in warnings))

    def test_song_copy_uses_only_supplied_metadata(self):
        supplied = context('Tal Conroy', 'Goodneighbor Blues, 95.77', 'Test Song', 'Test Artist')
        self.assertEqual(prepared_copy('Song introduction', '', {}, supplied), 'Here’s “Test Song” by Test Artist.')
        self.assertNotIn('Test Song', prepared_copy('Song introduction', '', {}, context('Tal Conroy', 'Goodneighbor Blues, 95.77')))

    def test_website_generation_never_requests_lore_or_character_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = LocalWriter(default_settings(), directory)
            with patch('ai_writer.LoreLibrary.context') as lore, patch('ai_writer.CharacterLibrary.context') as character, \
                    patch.object(writer, '_paths', side_effect=RuntimeError('Stop before loading')):
                with self.assertRaisesRegex(RuntimeError, 'Stop before loading'):
                    writer.generate(ScriptRequest('Tal Conroy', 'Website Promo'))
            lore.assert_not_called(); character.assert_not_called()


class SpotControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        root = Path(self.home.name)
        self.paths = patch.multiple(gui, DATA=root, HISTORY=root/'history.json', CAMPAIGNS=root/'advertisers.json')
        self.paths.start()
        self.window = gui.Window()

    def tearDown(self):
        self.window.close(); self.window.deleteLater(); self.app.processEvents()
        self.paths.stop(); self.home.cleanup()

    def select(self, key):
        self.window.cat.setCurrentText('Website Promo')
        self.window.ai.template_combo.setCurrentIndex(self.window.ai.template_combo.findData(key))

    def test_prepared_id_does_not_load_a_model_or_apply_the_ai_brief(self):
        window = self.window
        window.cat.setCurrentText('Station ID')
        window.ai.brief.setPlainText('Unapplied custom direction')
        with patch('ai_studio.LocalWriter') as writer:
            window.ai.prepared_button.click()
        writer.assert_not_called()
        self.assertIn('Goodneighbor Blues', window.output.toPlainText())
        self.assertNotIn('Unapplied', window.output.toPlainText())
        self.assertFalse(window.reviewed.isChecked())

    def test_missing_offer_blocks_before_setup_or_writer_start(self):
        self.select('percent-off')
        with patch.object(self.window.ai, 'open_setup') as setup, patch('ai_studio.LocalWriter') as writer:
            self.window.ai.generate()
        setup.assert_not_called(); writer.assert_not_called()
        self.assertIn('discount', self.window.ai.state.text().lower())

    def test_changing_type_preserves_brief_and_keeps_terms_per_template(self):
        self.select('percent-off')
        ai = self.window.ai
        ai.brief.setPlainText('My custom brief')
        ai.template_values['percent-off'] = dict(percent='20', offer='albums')
        self.select('subscription')
        self.assertEqual(ai.current_request().template_values, {})
        self.window.cat.setCurrentText('Station ID')
        self.select('percent-off')
        self.assertEqual(ai.current_request().template_values['percent'], '20')
        self.assertEqual(ai.brief.toPlainText(), 'My custom brief')

    def test_story_has_no_canned_copy_and_template_controls_follow_busy_state(self):
        self.window.cat.setCurrentText('Stories From the Commonwealth')
        self.assertFalse(self.window.ai.prepared_button.isEnabled())
        self.select('subscription')
        self.window.ai.set_busy(True)
        self.assertFalse(self.window.ai.template_combo.isEnabled())
        self.assertFalse(self.window.ai.terms_button.isEnabled())
        self.window.ai.set_busy(False)
        self.assertTrue(self.window.ai.terms_button.isEnabled())

    def test_edit_terms_save_and_reload_without_changing_the_brief(self):
        self.select('percent-off')
        ai = self.window.ai
        ai.brief.setPlainText('Keep this custom direction')
        with patch('ai_studio.TermsDialog') as dialog:
            dialog.return_value.exec.return_value = 1
            dialog.return_value.values = dict(percent='15', offer='selected albums', code='BLUES15')
            ai.edit_terms()
        self.assertEqual(load_terms(Path(self.home.name)/'spot_template_terms.json')['percent-off']['code'], 'BLUES15')
        self.assertEqual(ai.brief.toPlainText(), 'Keep this custom direction')
