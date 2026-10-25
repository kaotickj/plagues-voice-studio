"""Real rule behavior, durable dictionaries and plugin review lifecycle."""
import importlib.util
import importlib
import json
import os
from pathlib import Path
import sys
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'plugins' / 'script-prep'
spec = importlib.util.spec_from_file_location('_script_prep_tests', FOLDER / '__init__.py', submodule_search_locations=[str(FOLDER)])
package = importlib.util.module_from_spec(spec); sys.modules[spec.name] = package; spec.loader.exec_module(package)
from _script_prep_tests.preparation import prepare
from _script_prep_tests.library import Library


@pytest.mark.parametrize('source,expected', [
    ('$12.50', 'twelve dollars and fifty cents'), ('$1.01', 'one dollar and one cent'),
    ('$0.05', 'zero dollars and five cents'), ('$1,250.00', 'one thousand two hundred fifty dollars'),
    ('25.5%', 'twenty five point five percent'), ('95.77 FM', 'ninety five point seven seven F M'),
    ('1020 AM', 'one thousand twenty A M'), ('8:05 p.m.', 'eight oh five p.m.'),
    ('12:00 AM', 'twelve a.m.'), ('2026-10-21', 'October twenty first, two thousand twenty six'),
    ('2026-02-30', '2026-02-30'), ('Dr. Wright vs. Mr. Jones', 'Doctor Wright versus Mister Jones'),
    ('$1,000,000', '$1,000,000'), ('$12.345', '$12.345'), ('13:99 PM', '13:99 PM'),
    ('$12.50.', 'twelve dollars and fifty cents.'), ('$12.50, please', 'twelve dollars and fifty cents, please'),
])
def test_spoken_forms(source, expected):
    assert prepare(source).text == expected


def test_dictionary_priority_boundaries_longest_and_no_cascade():
    entries = [{'term': 'Dr. Rex', 'spoken': 'Doc Reks'}, {'term':'Rex','spoken':'King'},
               {'term':'King','spoken':'Royal'}, {'term':'95.77 FM','spoken':'ninety five seven seven'}]
    assert prepare('DR. REX, Rexford, Rex and King at 95.77 FM', entries).text == 'Doc Reks, Rexford, King and Royal at ninety five seven seven'


def test_protected_addresses_tags_and_ambiguity():
    source = 'https://example.com/$12.50 [pause 25%] <break time="8:05 pm"/> a25@example.com 10/11/2026'
    result = prepare(source)
    assert result.text == source
    assert len(result.warnings) == 3


def test_controls_preserve_original_and_optional_pauses():
    source = 'Dr. Jones — $12.50 at 95.77 FM'
    assert prepare(source, numbers=False, abbreviations=False).text == source
    assert prepare(source, numbers=False, abbreviations=False, pauses=True).text == 'Dr. Jones, $12.50 at 95.77 FM'
    with pytest.raises(ValueError): prepare('x'*100001)


def test_clock_rules_are_shared_reviewable_and_do_not_cascade():
    from chatterbox_studio.text_preparation import prepare_render_text
    source = 'Meet at 9:05 a.m. See https://example.test/9:05am.'
    prepared = prepare(source)
    assert prepared.text == prepare_render_text(source)
    assert prepared.changes == ['Time: 9:05 a.m. → nine oh five a.m.']
    assert prepare(prepared.text).text == prepared.text
    assert prepare(source, numbers=False).text == source
    assert prepare('9:05am', [{'term': '9:05am', 'spoken': 'the scheduled time'}]).text == 'the scheduled time'


def test_atomic_profiles_validation_and_corruption(tmp_path):
    library = Library(tmp_path); data = library.load()
    data['profiles']['Advertisers'] = [{'term':'Acme', 'spoken':'Ack mee'}]
    library.save(data); assert library.load() == data
    data['profiles']['Advertisers'].append({'term':'ACME','spoken':'Other'})
    with pytest.raises(ValueError): library.save(data)
    assert len(library.load()['profiles']['Advertisers']) == 1
    library.path.write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError): library.load()
    assert library.path.read_text() == '{broken'


def test_gui_menu_handoff_and_review_invalidation(tmp_path):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PyQt6')
    from PyQt6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit
    from chatterbox_studio.plugin_manager import PluginManager
    from types import SimpleNamespace
    app = QApplication.instance() or QApplication([])
    host = QMainWindow(); host.storage = tmp_path; host.thread = None
    host.engine_lab = host.model_manager = host.bethesda_tab = SimpleNamespace(is_busy=False)
    host.editor = QPlainTextEdit(); host.editor.setPlainText('Dr. Jones paid $12.50.')
    received = []; host._accept_plugin_text = lambda text: received.append(text) or True
    manager = PluginManager(host, [ROOT/'plugins'])
    action = next(a for a in manager.menu.actions() if a.data() == 'script-prep'); action.trigger()
    panel = manager.dialogs['script-prep'].panel
    panel.load_studio(); panel.preview()
    assert panel.source.toPlainText() == host.editor.toPlainText()
    assert panel.output.toPlainText() == 'Doctor Jones paid twelve dollars and fifty cents.'
    panel.send(); assert not received
    panel.reviewed.setChecked(True); panel.send()
    assert received == [panel.output.toPlainText()]
    panel.output.insertPlainText('Hello '); assert not panel.reviewed.isChecked()
    panel.reviewed.setChecked(True); panel.numbers.setChecked(False)
    assert not panel.output.toPlainText() and not panel.send_button.isEnabled()
    panel.preview(); panel.reviewed.setChecked(True); host.thread = object(); panel.send()
    assert len(received) == 1
    host.thread = None; panel.save(); assert (tmp_path/'plugins/script-prep/dictionaries.json').exists()
    action.trigger(); assert manager.dialogs['script-prep'].panel is panel
    manager.close_all(); host.close(); app.processEvents()


def test_plugin_package_contains_only_necessary_files(tmp_path, monkeypatch):
    module_spec = importlib.util.spec_from_file_location('_prep_builder', FOLDER/'build_plugin.py')
    builder = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(builder)
    archive = builder.build(tmp_path)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert 'plugins/script-prep/plugin.json' in bundle.namelist()
        assert 'plugins/script-prep/LICENSE' in bundle.namelist()
        assert bundle.read('plugins/script-prep/time_preparation.py') == (ROOT/'src/chatterbox_studio/text_preparation.py').read_bytes()
        assert not any(name.endswith(('.exe', '.gguf')) or '/artifacts/' in name for name in bundle.namelist())
        bundle.extractall(tmp_path / 'expanded')
    # API-1 hosts predating the shared core helper can still load this archive.
    folder = tmp_path / 'expanded/plugins/script-prep'
    name = '_script_prep_older_host'
    archived_spec = importlib.util.spec_from_file_location(name, folder/'__init__.py', submodule_search_locations=[str(folder)])
    archived = importlib.util.module_from_spec(archived_spec)
    monkeypatch.setitem(sys.modules, name, archived)
    monkeypatch.setitem(sys.modules, 'chatterbox_studio.text_preparation', None)
    archived_spec.loader.exec_module(archived)
    archived_preparation = importlib.import_module(name + '.preparation')
    assert archived_preparation.prepare('9:05am').text == 'nine oh five a.m.'
