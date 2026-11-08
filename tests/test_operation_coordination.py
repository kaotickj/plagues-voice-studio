"""Exercise real operation entry points without starting threads or AI work."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip('PyQt6')
from chatterbox_studio import app, engine_lab, model_manager, bethesda_widget


STARTERS = {
    'narration': (app, app.MainWindow._start_jobs),
    'engine': (engine_lab, engine_lab.EngineLab._start),
    'model': (model_manager, model_manager.ModelManager._start),
    'export': (bethesda_widget, bethesda_widget.BethesdaExportTab._start),
}


def operation(starter, tmp_path):
    host = SimpleNamespace(
        thread=None, storage=tmp_path / 'data',
        plugins=SimpleNamespace(is_busy=False),
        engine_lab=SimpleNamespace(is_busy=False),
        model_manager=SimpleNamespace(is_busy=False),
        bethesda_tab=SimpleNamespace(is_busy=False))
    if starter == 'narration':
        caller, args = host, ([],)
    else:
        caller = SimpleNamespace(
            host=host, thread=None, is_busy=False,
            model=SimpleNamespace(currentData=lambda: 'qwen-0.6b'),
            _config=lambda: SimpleNamespace(validate=lambda: None),
            _save_tools=lambda: None, cancel_event=Mock(),
            cancel_button=Mock(), diagnose_button=Mock(), status=Mock(),
            run_button=SimpleNamespace(setEnabled=lambda _: None))
        args = ('check',) if starter == 'model' else ()
        field = {'engine': 'engine_lab', 'model': 'model_manager',
                 'export': 'bethesda_tab'}[starter]
        setattr(host, field, caller)
    return host, caller, args


@pytest.mark.parametrize(('starter', 'active'), [
    (starter, active) for starter in STARTERS
    for active in ['narration', 'engine', 'model', 'export', 'plugin']
    if (starter == 'export') == (active == 'export')
])
def test_gpu_operations_coordinate_and_export_blocks_only_itself(
        tmp_path, monkeypatch, starter, active):
    module, start = STARTERS[starter]
    host, caller, args = operation(starter, tmp_path)
    if active == 'narration':
        host.thread = object()
    else:
        field = {'engine': 'engine_lab', 'model': 'model_manager',
                 'export': 'bethesda_tab', 'plugin': 'plugins'}[active]
        current = getattr(host, field)
        current.is_busy = True
        current.thread = object()
    before = caller.thread
    notices = []
    monkeypatch.setattr(module.QMessageBox, 'information', lambda *args: notices.append(args))
    monkeypatch.setattr(module, 'QThread', lambda *_: pytest.fail('Blocked operation created a thread'))
    monkeypatch.setattr(model_manager, 'qwen_python', lambda _: '/usr/bin/python3')
    start(caller, *args)
    assert caller.thread is before
    assert not (host.storage / 'bethesda_source').exists()
    if active != starter:
        assert len(notices) == 1


@pytest.mark.parametrize('starter', STARTERS)
def test_idle_host_can_reach_worker_creation(tmp_path, monkeypatch, starter):
    """A shared guard must not reject its own idle tab or block everything."""
    module, start = STARTERS[starter]
    host, caller, args = operation(starter, tmp_path)

    class ReachedWorkerCreation(Exception):
        pass

    def stop_before_thread(*args):
        raise ReachedWorkerCreation

    monkeypatch.setattr(module, 'QThread', stop_before_thread)
    monkeypatch.setattr(module.QMessageBox, 'information', lambda *args: pytest.fail('Idle operation was blocked'))
    monkeypatch.setattr(model_manager, 'qwen_python', lambda _: '/usr/bin/python3')
    monkeypatch.setattr(bethesda_widget, 'expected_fuz_path', lambda _: tmp_path / 'new.fuz')
    with pytest.raises(ReachedWorkerCreation):
        start(caller, *args)


@pytest.mark.parametrize(('starter', 'active'), [
    ('export', 'narration'), ('export', 'engine'), ('export', 'model'),
    ('export', 'plugin'), ('narration', 'export'), ('engine', 'export'),
    ('model', 'export'),
])
def test_existing_audio_export_is_independent_of_gpu_operations(
        tmp_path, monkeypatch, starter, active):
    module, start = STARTERS[starter]
    host, caller, args = operation(starter, tmp_path)
    if active == 'narration':
        host.thread = object()
    else:
        field = {'engine': 'engine_lab', 'model': 'model_manager',
                 'export': 'bethesda_tab', 'plugin': 'plugins'}[active]
        getattr(host, field).is_busy = True
        getattr(host, field).thread = object()

    class ReachedWorkerCreation(Exception):
        pass

    def stop_before_thread(*args):
        raise ReachedWorkerCreation

    monkeypatch.setattr(module, 'QThread', stop_before_thread)
    monkeypatch.setattr(module.QMessageBox, 'information',
                        lambda *args: pytest.fail('Independent operation was blocked'))
    monkeypatch.setattr(model_manager, 'qwen_python', lambda _: '/usr/bin/python3')
    monkeypatch.setattr(bethesda_widget, 'expected_fuz_path', lambda _: tmp_path / 'new.fuz')
    with pytest.raises(ReachedWorkerCreation):
        start(caller, *args)
