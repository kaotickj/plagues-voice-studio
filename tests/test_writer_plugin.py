"""Plugin discovery, neutral prompts, owned-runtime failures and Qt handoff."""
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6')
from PyQt6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QTabWidget, QLabel, QMessageBox
from chatterbox_studio.plugin_manager import (PluginContext, PluginManager, discover_plugins, load_factory)
from writer_core.runtime import WriterRuntime
from writer_core.downloads import Cancelled
from writer_core.settings import default_settings, existing_runtime_settings, save_settings, load_settings


@pytest.fixture(scope='module')
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def plugin(qt_app, tmp_path):
    host = QMainWindow()
    transfers = []
    spec = discover_plugins([ROOT/'plugins'])[0][0]
    context = PluginContext(host, tmp_path, lambda: '', lambda text: transfers.append(text) or True)
    with patch('writer_core.settings.Path.home', return_value=tmp_path):
        panel = load_factory(spec)(context)
    yield panel, transfers
    if panel.is_busy:
        panel.cancel()
        pump(qt_app, lambda: not panel.is_busy)
    host.close(); panel.deleteLater(); qt_app.processEvents()


def pump(app, condition):
    deadline = time.monotonic()+5
    while not condition() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    assert condition()


def test_plugin_has_generic_recipes_and_no_radio_context(plugin):
    panel, _ = plugin
    module = sys.modules[panel.__module__.rsplit('.', 1)[0] + '.prompts']
    assert panel.category.count() == 7
    assert 'profiles' not in panel.settings and 'lore' not in panel.settings
    for category in module.RECIPES:
        request = module.CopyRequest(category=category, product='Desk lamp', facts='USB powered', call_to_action='Visit our shop')
        text = '\n'.join(message['content'] for message in module.build_messages(request))
        assert 'USB powered' in text and 'Visit our shop' in text
        for forbidden in ('Goodneighbor', 'Commonwealth', 'Fallout', 'Tal Conroy', 'DJ voice', '[narration]'):
            assert forbidden not in text
        assert 'Never invent prices' in text
    with pytest.raises(ValueError):
        module.build_messages(module.CopyRequest())
    with pytest.raises(ValueError):
        module.build_messages(module.CopyRequest(instructions='x'*17000))


def test_runtime_import_copies_only_model_preferences(tmp_path):
    server, model = tmp_path/'llama-server.exe', tmp_path/'writer.gguf'
    server.touch(); model.touch()
    old = dict(default_settings(), server_path=str(server), model_path=str(model),
               profiles={'DJ': 'fictional character'}, lore='fiction', continuity={'DJ': 'old story'})
    source = tmp_path/'old.json'; source.write_text(json.dumps(old))
    data = existing_runtime_settings(source)
    assert data['model_path'] == str(model)
    assert not {'profiles', 'lore', 'continuity'} & data.keys()
    target = tmp_path/'new.json'; save_settings(target, data)
    assert load_settings(target) == data
    assert json.loads(source.read_text()) == old


def test_discovery_rejects_incompatible_and_escaping_entries_without_execution(tmp_path):
    folder = tmp_path/'bad'; folder.mkdir()
    outside = tmp_path/'outside.py'; outside.write_text('raise RuntimeError("must not execute")')
    manifest = dict(id='bad', name='Bad', version='1', api_version=1, entry_point='../outside.py')
    (folder/'plugin.json').write_text(json.dumps(manifest))
    found, errors = discover_plugins([tmp_path])
    assert not found and 'inside the plugin' in errors[0]
    manifest.update(api_version=2, entry_point='__init__.py')
    (folder/'plugin.json').write_text(json.dumps(manifest))
    assert 'API version' in discover_plugins([tmp_path])[1][0]


def test_menu_reuses_dialog_and_cancel_prevents_busy_close(qt_app, tmp_path):
    host = QMainWindow(); host.storage = tmp_path; host.thread = None
    host.engine_lab = host.bethesda_tab = host.model_manager = SimpleNamespace(is_busy=False)
    host._accept_plugin_text = lambda text: True
    manager = PluginManager(host, [ROOT/'plugins'])
    with patch('writer_core.settings.Path.home', return_value=tmp_path):
        manager.menu.actions()[0].trigger()
    dialog = manager.dialogs['promotional-writer']
    assert dialog.isVisible() and not dialog.panel.is_busy
    manager.menu.actions()[0].trigger()
    assert manager.dialogs['promotional-writer'] is dialog
    dialog.panel.thread = object()
    with patch.object(dialog.panel, 'cancel') as cancel:
        dialog.close(); assert dialog.isVisible(); cancel.assert_called_once()
    dialog.panel.thread = None
    manager.close_all()
    assert not dialog.isVisible()
    manager.menu.actions()[0].trigger()
    assert dialog.isVisible()
    dialog.reject()
    assert not dialog.isVisible()
    host.close()


def test_review_gate_edit_reset_and_exact_plain_text_handoff(plugin):
    panel, transfers = plugin
    panel.output.setPlainText('A useful desk lamp. Visit our shop.')
    assert not panel.send_button.isEnabled()
    panel.send_to_studio(); assert not transfers
    panel.reviewed.setChecked(True); panel.send_to_studio()
    assert transfers == ['A useful desk lamp. Visit our shop.']
    panel.output.insertPlainText(' Revised.')
    assert not panel.reviewed.isChecked() and not panel.send_button.isEnabled()


def test_host_handoff_preserves_existing_script_until_confirmed(qt_app):
    from chatterbox_studio.app import MainWindow
    host = QMainWindow(); host.thread = None; host.editor = QPlainTextEdit('Existing script')
    host.tabs = QTabWidget(); host.status_label = QLabel()
    with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
        assert not MainWindow._accept_plugin_text(host, 'New copy')
    assert host.editor.toPlainText() == 'Existing script'
    with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
        assert MainWindow._accept_plugin_text(host, 'New copy')
    assert host.editor.toPlainText() == 'New copy' and host.thread is None
    host.close()


class Response(io.BytesIO):
    pass


def test_generic_runtime_checks_completion_and_always_stops_owned_server(tmp_path):
    server, model = tmp_path/'server', tmp_path/'copy.gguf'
    server.touch(); model.touch()
    settings = dict(default_settings(), server_path=str(server), model_path=str(model))
    writer = WriterRuntime(settings, tmp_path)
    messages = [{'role':'system', 'content':'Write copy'}, {'role':'user','content':'USB lamp'}]
    def response(route, payload=None, timeout=5):
        if route == '/apply-template': return Response(b'{"prompt":"copy"}')
        if route == '/tokenize': return Response(b'{"tokens":[1,2]}')
        assert payload['messages'] == [{'role':'user', 'content':'Write copy\n\nUSB lamp'}]
        assert payload['model'] == 'local-writer'
        return Response(b'data: {"choices":[{"delta":{"content":"A desk lamp."},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
    with patch.object(writer, '_load_with_memory_recovery', return_value=8192), patch.object(writer, '_request', side_effect=response), patch.object(writer, '_stop_server') as stop:
        assert writer.generate_messages(messages)['text'] == 'A desk lamp.'
        stop.assert_called_once()

    def incomplete(route, payload=None, timeout=5):
        return Response(b'data: {"choices":[{"delta":{"content":"Incomplete"},"finish_reason":"length"}]}\ndata: [DONE]\n') if route == '/v1/chat/completions' else response(route,payload,timeout)
    with patch.object(writer, '_load_with_memory_recovery', return_value=8192), patch.object(writer, '_request', side_effect=incomplete), patch.object(writer, '_stop_server') as stop:
        with pytest.raises(RuntimeError, match='did not finish'):
            writer.generate_messages(messages)
        stop.assert_called_once()



def test_generic_runtime_startup_uses_its_own_model_alias(tmp_path):
    runtime = WriterRuntime(default_settings(), tmp_path)
    runtime._process = SimpleNamespace(poll=lambda: None)
    def reply(route):
        if route == '/health':
            return Response(b'{"status":"ok"}')
        return Response(json.dumps({'data':[{'id':runtime.alias,'meta':{'n_ctx_train':8192}}]}).encode())
    with patch.object(runtime, '_request', side_effect=reply):
        runtime._wait_ready(lambda status: None)


def test_failed_or_cancelled_job_restores_prior_text_and_review(plugin, qt_app, tmp_path):
    panel, _ = plugin
    server, model = tmp_path/'server', tmp_path/'test.gguf'; server.touch(); model.touch()
    panel.settings.update(server_path=str(server), model_path=str(model))
    panel.product.setText('Desk lamp'); panel.output.setPlainText('Previous draft'); panel.reviewed.setChecked(True)
    def fail(*args, **kwargs):
        kwargs['on_text']('Partial new draft')
        raise RuntimeError('Test server failure')
    with patch.object(WriterRuntime, 'generate_messages', side_effect=fail):
        panel.generate(); assert panel.is_busy
        pump(qt_app, lambda: not panel.is_busy)
    assert panel.output.toPlainText() == 'Previous draft' and panel.reviewed.isChecked()
    def wait_cancel(runtime, *args, **kwargs):
        assert runtime.cancelled.wait(3)
        raise Cancelled('Cancelled')
    with patch.object(WriterRuntime, 'generate_messages', wait_cancel):
        panel.generate(); panel.cancel(); pump(qt_app, lambda: not panel.is_busy)
    assert panel.output.toPlainText() == 'Previous draft' and panel.reviewed.isChecked()


def test_success_returns_editable_unapproved_copy_and_host_block_prevents_start(plugin, qt_app, tmp_path):
    panel, _ = plugin
    server, model = tmp_path/'server', tmp_path/'test.gguf'; server.touch(); model.touch()
    panel.settings.update(server_path=str(server), model_path=str(model))
    panel.product.setText('Desk lamp')
    result = dict(text='USB light for your desk.', model='test.gguf', elapsed_seconds=1)
    with patch.object(WriterRuntime, 'generate_messages', return_value=result):
        panel.generate(); pump(qt_app, lambda: not panel.is_busy)
    assert panel.output.toPlainText() == result['text']
    assert not panel.output.isReadOnly() and not panel.reviewed.isChecked()
    object.__setattr__(panel.context, 'can_generate', lambda: 'Narration running')
    with patch.object(WriterRuntime, 'generate_messages') as generate:
        panel.generate(); generate.assert_not_called()
    assert 'Narration running' in panel.status.text()


def test_shipping_spec_excludes_dj_standalone():
    spec = (ROOT/'ChatterboxStudio.spec').read_text()
    assert "for folder in ('promotional-writer',)" in spec
    assert "'writer_core.setup_dialog'" in spec
    assert "project / 'plugins' / 'dj-writer'" not in spec


def test_host_model_operations_wait_for_writer(qt_app):
    from chatterbox_studio.app import MainWindow
    from chatterbox_studio.engine_lab import EngineLab
    from chatterbox_studio.model_manager import ModelManager
    host = SimpleNamespace(plugins=SimpleNamespace(is_busy=True))
    with patch.object(QMessageBox, 'information') as notice:
        MainWindow._start_jobs(host, [])
        EngineLab._start(SimpleNamespace(host=host))
        ModelManager._start(SimpleNamespace(host=host), 'check')
    assert notice.call_count == 3


def test_packaged_plugin_has_no_dj_shell_or_model_weights(tmp_path):
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('_plugin_builder_test', ROOT/'plugins/promotional-writer/build_plugin.py')
    module = module_from_spec(spec); spec.loader.exec_module(module)
    archive = module.build(tmp_path)
    import zipfile
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        names = bundle.namelist()
        assert 'plugins/promotional-writer/plugin.json' in names
        assert 'plugins/promotional-writer/dropdown.svg' in names
        assert 'plugins/writer_core/runtime.py' in names
        assert not any('dj-writer/' in name or name.endswith(('.gguf', '.exe')) for name in names)
