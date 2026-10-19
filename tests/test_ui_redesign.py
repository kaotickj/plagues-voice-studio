"""Review the redesigned UI without importing native Qt in headless CI."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SRC = ROOT / 'src' / 'chatterbox_studio'
sys.path.insert(0, str(ROOT / 'src'))


def test_about_dialog_imports_qdialog_and_uses_nonmodal_show():
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    module = (SRC / 'about_dialog.py').read_text(encoding='utf-8')
    assert 'QDialog' in module and 'class AboutDialog(QDialog)' in module
    assert 'self._about_dialog.show()' in app
    assert '.exec()' not in module
    assert "'plagues_about_dialog'" in module
    assert "'about_logo'" in module
    assert 'Copy diagnostics' in module
    assert 'Voice Engines' in module
    assert 'IndexTTS 2.5' in module
    assert 'has been verified working on the creator' in module
    assert 'separate Python environment' in module


def test_help_topics_are_searchable_without_models_or_network():
    module = ast.parse((SRC / 'help_center.py').read_text(encoding='utf-8'))
    declaration = next(node for node in module.body if isinstance(node, ast.AnnAssign)
                       and isinstance(node.target, ast.Name) and node.target.id == 'TOPICS')
    topics = ast.literal_eval(declaration.value)
    def matches(query):
        words = query.lower().strip().split()
        return [i for i, (name, keywords, content) in enumerate(topics)
                if all(w in (name+' '+keywords+' '+content).lower() for w in words)]
    assert len(topics) >= 6
    assert len(matches('')) == len(topics)
    assert any('Bethesda' in topics[i][0] for i in matches('fuz'))
    assert any('Script' in topics[i][0] for i in matches('pause'))
    sponsorship = next(html for title, _keywords, html in topics
                       if title == 'Support Project Development')
    assert 'https://github.com/sponsors/kaotickj' in sponsorship
    assert 'https://www.patreon.com/KaotickJay' in sponsorship
    assert 'https://paypal.me/kaotickj' in sponsorship
    assert any('Qwen3-TTS' in topics[i][0] for i in matches('qwen'))
    assert any('Voice Engines' in html for _, _, html in topics)
    assert not any('Optional Engine Lab' in html for _, _, html in topics)
    assert matches('thereisnomatchingtopicname') == []


def test_engine_lab_promotes_qwen_without_changing_settings_paths():
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    engine = (SRC / 'engine_lab.py').read_text(encoding='utf-8')
    assert 'self.tabs.addTab(self.engine_lab, "Voice Engines")' in app
    assert 'VOICE ENGINES' in engine
    assert 'Chatterbox, Qwen3-TTS and IndexTTS 2.5 are supported speech engines' in engine
    assert 'independent Python runtimes' in engine
    assert 'PlaguesVoiceStudio030Experimental' in app
    assert "self.setObjectName('engine_lab')" in engine


def test_model_manager_is_available_and_preserves_existing_views():
    app = (SRC / 'app.py').read_text(encoding='utf-8')
    manager = (SRC / 'model_manager.py').read_text(encoding='utf-8')
    smoke = (SRC / 'ui_smoke_test.py').read_text(encoding='utf-8')
    engine = (SRC / 'engine.py').read_text(encoding='utf-8')
    assert 'self.tabs.addTab(self.model_manager, "Model Manager")' in app
    assert 'or self.model_manager.is_busy' in app
    assert "self.setObjectName('model_manager')" in manager
    assert 'Download selected model' in manager
    assert 'Check Qwen cache' in manager
    assert 'model_manager.model.count() != 6' in smoke
    assert 'installed_model_directory(user_data_dir(), spec)' in engine
    assert 'has_required_files(path, spec)' in engine


def test_packaged_smoke_exercises_about_and_help():
    source = (SRC / 'ui_smoke_test.py').read_text(encoding='utf-8')
    assert 'about_button.click()' in source
    assert 'help_search.setText' in source
    assert 'about_tabs' in source
    assert "about_dialog.close()" in source


def test_source_compiles_and_assets_are_packaged():
    for p in SRC.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    spec = (ROOT / 'ChatterboxStudio.spec').read_text()
    for name in ('plagues-voice-studio-icon.png', 'plagues-voice-studio-logo.png'):
        assert name in spec
        assert (ROOT / 'assets' / name).is_file()


def test_legacy_library_constructor_remains_read_only(tmp_path):
    from chatterbox_studio.voices import VoiceLibrary
    older = tmp_path / 'old-library'
    older.mkdir()
    reader = VoiceLibrary(older, read_only=True)
    assert not (older / 'voices').exists()
    assert reader.list_voices() == []
    try:
        reader.remove_voice('anything')
    except ValueError:
        pass
    else:
        raise AssertionError('Read-only library must reject mutation')
