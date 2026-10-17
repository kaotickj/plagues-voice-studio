"""Catch the Export Library regression without a Qt display dependency."""
import ast
from pathlib import Path

SOURCE = Path(__file__).parents[1] / 'src' / 'chatterbox_studio' / 'export_browser.py'


def test_export_browser_references_instance_host_in_build():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ExportBrowser')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_build')
    # A bare `host` is not a local variable or argument in _build; it caused the v0.2.0 crash.
    assert not any(isinstance(n, ast.Name) and n.id == 'host' and isinstance(n.ctx, ast.Load)
                   for n in ast.walk(method))
    source = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), method)
    assert 'self.host.player.stop' in source


def test_full_logo_included_in_pyinstaller():
    root = SOURCE.parents[2]
    spec = (root / 'ChatterboxStudio.spec').read_text(encoding='utf-8')
    assert "'plagues-voice-studio-logo.png'" in spec
    assert (root / 'assets' / 'plagues-voice-studio-logo.png').is_file()


def test_about_action_is_nonmodal_and_exercised_by_frozen_smoke_test():
    root = SOURCE.parents[2]
    app_source = (root / 'src' / 'chatterbox_studio' / 'app.py').read_text(encoding='utf-8')
    ui_smoke = (root / 'src' / 'chatterbox_studio' / 'ui_smoke_test.py').read_text(encoding='utf-8')
    about_source = app_source.split('    def _about(self):', 1)[1].split('    def _restore_settings(self):', 1)[0]
    assert 'dialog.exec()' not in about_source
    assert 'self._about_dialog.show()' in app_source
    assert 'about_button.click()' in ui_smoke
    assert "about_dialog.close()" in ui_smoke
    assert "plagues_about_dialog" in ui_smoke


def test_release_candidate_exercises_export_library_script_preview():
    root = SOURCE.parents[2]
    smoke = (root / 'src' / 'chatterbox_studio' / 'ui_smoke_test.py').read_text(encoding='utf-8')
    assert 'write_export_metadata(audio_path' in smoke
    assert 'browser.script_preview.toPlainText() != script' in smoke
    assert 'browser.copy_script.click()' in smoke
    assert 'browser.copy_script.isEnabled()' in smoke
