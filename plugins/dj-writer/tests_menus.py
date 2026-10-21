"""Exercise real menu signals and modal dialogs without a writing model."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QDialog, QTextBrowser
import goodneighbor_dj as gui


class MenuTests(unittest.TestCase):
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
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.paths.stop()
        self.home.cleanup()

    def test_every_dialog_menu_opens_a_readable_dialog(self):
        for menu_action in self.window.menuBar().actions()[1:]:
            for action in menu_action.menu().actions():
                with self.subTest(action=action.text()):
                    seen = []
                    def dismiss():
                        dialog = self.app.activeModalWidget()
                        if dialog is not None:
                            seen.append(dialog)
                            palette = dialog.palette()
                            self.assertNotEqual(palette.color(QPalette.ColorRole.Window), palette.color(QPalette.ColorRole.WindowText))
                            for browser in dialog.findChildren(QTextBrowser):
                                self.assertLess(browser.viewport().palette().color(QPalette.ColorRole.Base).lightness(), 100)
                            dialog.reject()
                    QTimer.singleShot(20, dismiss)
                    action.trigger()
                    self.assertEqual(len(seen), 1, 'Menu action did not open its dialog')

    def test_file_actions_reflect_review_and_export(self):
        w = self.window
        self.assertFalse(w.copy_action.isEnabled())
        self.assertFalse(w.export_action.isEnabled())
        w.output.setPlainText('Test script')
        w.copy_action.trigger()
        self.assertEqual(self.app.clipboard().text(), 'Test script')
        self.assertFalse(w.export_action.isEnabled())
        w.reviewed.setChecked(True)
        self.assertTrue(w.export_action.isEnabled())
        target = Path(self.home.name)/'export.txt'
        with patch.object(gui.QFileDialog, 'getSaveFileName', return_value=(str(target), 'Text (*.txt)')):
            w.export_action.trigger()
        self.assertEqual(target.read_text(), 'Test script')
        w.output.insertPlainText(' revised')
        self.assertFalse(w.export_action.isEnabled())

    def test_advertisers_remain_available_with_custom_campaigns(self):
        w = self.window
        w.campaigns = [{'name': 'Custom shop', 'enabled': True}, {'name': 'Disabled shop', 'enabled': False}]
        w.refresh_advertisers()
        items = [w.sponsor.itemText(i) for i in range(w.sponsor.count())]
        self.assertEqual(items, gui.ADS + ['Custom shop'])
        for category in gui.CATS:
            w.cat.setCurrentText(category)
            self.assertTrue(w.sponsor.isEnabled())
        w.cat.setCurrentText('Ad / promo')
        w.sponsor.setCurrentText('The Third Rail')
        self.assertEqual(w.ai.current_request().sponsor, 'The Third Rail')
        w.sponsor.setEditText('New advertiser')
        self.assertEqual(w.ai.current_request().sponsor, 'New advertiser')

    def test_three_rows_keep_editor_and_export_visible_at_minimum_size(self):
        from PyQt6.QtCore import Qt
        w = self.window
        w.resize(1000, 720); w.show()
        w.direction_toggle.setChecked(True)
        self.app.processEvents()
        self.assertEqual(w.workspace_splitter.orientation(), Qt.Orientation.Vertical)
        self.assertEqual(w.workspace_splitter.count(), 3)
        editor_bottom = w.output.mapTo(w, w.output.rect().bottomRight()).y()
        review_top = w.reviewed.mapTo(w, w.reviewed.rect().topLeft()).y()
        self.assertLess(editor_bottom, review_top)
        for widget in (w.generate_button, w.output, w.reviewed, w.copy_button, w.save_button):
            self.assertTrue(w.rect().contains(widget.mapTo(w, widget.rect().bottomRight())))
        self.assertEqual(w.settings_scroll.horizontalScrollBar().maximum(), 0)
        viewport = w.settings_scroll.viewport()
        for widget in (w.ai.prepared_button, w.ai.template_combo):
            self.assertTrue(viewport.rect().contains(widget.mapTo(viewport, widget.rect().bottomRight())),
                            'Quick spot controls must be visible without scrolling.')
