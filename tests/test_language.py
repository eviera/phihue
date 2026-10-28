import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from phihue.__main__ import Window
from phihue.model import State


class LanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.json'
        self.window = Window(self.path)
        self.addCleanup(self.window.close)
        self.addCleanup(self.app.removeTranslator, self.window.qt_translator)

    def test_switch_persists_with_scenes_and_survives_reopen(self):
        self.window.state.current.name = 'Mi ambiente'
        self.window.state.current.set_color(1, '#123456')
        self.window.settings_button.click()
        self.window.language_selector.setCurrentIndex(1)
        self.assertEqual(self.window.pages.currentIndex(), 1)
        self.assertEqual(self.window.back_button.text(), '← Back')
        self.assertEqual(self.window.settings_button.toolTip(), 'Settings')
        self.assertTrue(self.window.color_buttons[0].text().startswith('Light 1'))
        saved = State.load(self.path)
        self.assertEqual(saved.language, 'en')
        self.assertEqual(saved.current.name, 'Mi ambiente')
        self.assertEqual(saved.current.colors[1], '#123456')
        reopened = Window(self.path)
        self.addCleanup(reopened.close)
        self.addCleanup(self.app.removeTranslator, reopened.qt_translator)
        self.assertEqual(reopened.language_selector.currentData(), 'en')
        self.assertEqual(reopened.reset_button.text(), 'Restore defaults')
        reopened.language_selector.setCurrentIndex(0)
        self.assertEqual(reopened.back_button.text(), '← Volver')
        self.assertEqual(State.load(self.path).language, 'es')

    def test_failed_language_save_restores_selection(self):
        with patch.object(State, 'save', side_effect=OSError('Read only')), patch.object(QMessageBox, 'warning') as warning:
            self.window.language_selector.setCurrentIndex(1)
        warning.assert_called_once()
        self.assertEqual(self.window.state.language, 'es')
        self.assertEqual(self.window.language_selector.currentData(), 'es')

    def test_reset_keeps_language_and_saves_defaults(self):
        self.window.state.current.name = 'Custom'
        self.window.language_selector.setCurrentIndex(1)

        def confirm(dialog):
            self.assertEqual(dialog.text(), 'Reset your saved scene settings?')
            next(button for button in dialog.buttons()
                 if dialog.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole).click()
            return 0

        with patch.object(QMessageBox, 'exec', confirm):
            self.window.reset_settings()
        saved = State.load(self.path)
        self.assertEqual(saved.language, 'en')
        self.assertEqual(saved.current.name, 'Lectura')
        self.assertTrue(all(not scheme.linked for scheme in saved.schemes))
