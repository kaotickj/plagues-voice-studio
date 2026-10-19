"""Single-result and long-form regressions, including real offscreen Qt widgets."""
import json
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication, QFileDialog, QSpinBox
from dj_engine import DialogueEngine, load_content, load_stories
import goodneighbor_dj as gui


class SingleScriptTests(unittest.TestCase):
    def setUp(self):
        self.engine = DialogueEngine(rng=random.Random(11))

    def test_classic_returns_one_string(self):
        result, warning = self.engine.generate_one('Station break', 'Tal Conroy')
        self.assertIsInstance(result, str)
        self.assertTrue(result)
        self.assertFalse(result.startswith('1.'))

    def test_full_expanded_database_preserved(self):
        self.assertEqual(len(load_content()['scenes']), 156)

    def test_stories_are_whole_and_long(self):
        for dj in ('Tal Conroy', 'Hattie Boggs', 'Mister The Plague'):
            story, warning = self.engine.generate_one('Stories From the Commonwealth', dj, length='Short')
            self.assertGreaterEqual(len(story.split()), 500)
            self.assertIn('\n\n', story)
            self.assertNotIn('{dj}', story)
            self.assertNotIn('{station}', story)
            expected = 'Plague Radio' if dj == 'Mister The Plague' else 'Goodneighbor Blues'
            self.assertIn(expected, story)
            self.assertFalse(warning)

    def test_story_station_separation_and_freshness(self):
        first, _ = self.engine.generate_one('Stories From the Commonwealth', 'Mister The Plague')
        second, _ = self.engine.generate_one('Stories From the Commonwealth', 'Mister The Plague', history=[first])
        self.assertNotEqual(first, second)
        self.assertNotIn('Goodneighbor Blues', second)
        repeated, warning = self.engine.generate_one('Stories From the Commonwealth', 'Mister The Plague', history=[first, second])
        self.assertIn(repeated, (first, second))
        self.assertIn('appeared before', warning)

    def test_no_story_for_incompatible_mood(self):
        story, warning = self.engine.generate_one('Stories From the Commonwealth', 'Tal Conroy', mood='Ominous')
        self.assertEqual(story, '')
        self.assertIn('Try Any mood', warning)

    def test_invalid_story_database_is_actionable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'stories.json'
            path.write_text('{"version":1,"stories":[{}]}')
            with self.assertRaises(ValueError): load_stories(path)

    def test_custom_ad_returns_one_complete_spot(self):
        ads = [{'name':'Test shop', 'scripts':[
            {'profile':'blues','length':'Long','mood':'Wry','text':'A complete first commercial.'},
            {'profile':'blues','length':'Long','mood':'Wry','text':'A different complete commercial.'}]}]
        engine = DialogueEngine(campaigns=ads, rng=random.Random(11))
        text, _ = engine.generate_one('Ad / promo', 'Tal Conroy', sponsor='Test shop', length='Long')
        self.assertIn(text, ('A complete first commercial.', 'A different complete commercial.'))


class SingleScriptGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.patch = patch.multiple(gui, DATA=root, HISTORY=root/'history.json', CAMPAIGNS=root/'advertisers.json')
        self.patch.start()
        self.window = gui.Window()
        self.window.mode.setCurrentText('Classic Generator')

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.patch.stop()
        self.folder.cleanup()

    def test_no_quantity_control_or_numbered_output(self):
        self.assertEqual([w.objectName() for w in self.window.findChildren(QSpinBox)], ['target_words'])
        self.window.on_generate()
        self.assertTrue(self.window.output.toPlainText())
        self.assertEqual(len(self.window.records), 1)

    def test_story_uses_one_whole_result_and_disables_short_length(self):
        w = self.window
        w.cat.setCurrentText('Stories From the Commonwealth')
        self.assertFalse(w.length.isEnabled())
        w.on_generate()
        self.assertGreaterEqual(len(w.output.toPlainText().split()), 500)
        self.assertEqual(len(w.records), 1)
        self.assertIn('words', w.script_stats.text())
        w.cat.setCurrentText('Station ID')
        self.assertTrue(w.length.isEnabled())

    def test_previous_result_never_concatenates_scripts(self):
        w = self.window
        w.records = ['First complete result.', 'Second complete result.']
        w.history_index = 2
        w.restore_history()
        self.assertEqual(gui.clean_spoken_text(w.output.toPlainText()), 'Second complete result.')
        w.restore_history()
        self.assertEqual(gui.clean_spoken_text(w.output.toPlainText()), 'First complete result.')

    def test_review_is_invalidated_by_edits(self):
        w = self.window
        w.output.setPlainText('A draft.')
        self.assertFalse(w.save_button.isEnabled())
        w.reviewed.setChecked(True)
        self.assertTrue(w.save_button.isEnabled())
        w.output.setPlainText('A changed draft.')
        self.assertFalse(w.reviewed.isChecked())
        self.assertFalse(w.save_button.isEnabled())

    def test_utf8_handoff_preserves_complete_paragraphs(self):
        w = self.window
        script = 'A little café in Goodneighbor.\n\nA second paragraph, still the same script.'
        w.output.setPlainText(script)
        w.reviewed.setChecked(True)
        target = Path(self.folder.name) / 'radio.txt'
        with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(target), 'Text (*.txt)')):
            w.save_txt()
        self.assertEqual(target.read_text(encoding='utf-8'), script)

    def test_legacy_history_survives_and_loads_individually(self):
        gui.HISTORY.write_text(json.dumps(['First old result.', 'Second old result.']))
        self.window.close()
        self.window = gui.Window()
        self.window.restore_history()
        self.assertEqual(gui.clean_spoken_text(self.window.output.toPlainText()), 'Second old result.')


if __name__ == '__main__':
    unittest.main()
