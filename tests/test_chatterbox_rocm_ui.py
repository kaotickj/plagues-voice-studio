"""Isolated Qt settings/snapshot checks, with no model runtime or audio device."""
from test_narration_profile_ui import windows


def test_model_device_and_runtime_fields_survive_restart(windows, monkeypatch):
    from chatterbox_studio import app, rocm
    monkeypatch.setattr(rocm, 'known_runtime_defaults', lambda: {'python': '', 'overlay': ''})
    first = windows()
    first.settings.setValue('unrelated/retained', 'keep this')
    first.model.setCurrentIndex(first.model.findData('turbo'))
    first.device.setCurrentIndex(first.device.findData('rocm'))
    first.rocm_python.setText('/approved/python')
    first.rocm_overlay.setText('/approved/overlay')
    first.rocm_overlay.editingFinished.emit()
    first.close()
    second = app.MainWindow()
    try:
        assert second.model.currentData() == 'turbo'
        assert second.device.currentData() == 'rocm'
        assert second.rocm_python.text() == '/approved/python'
        assert second.rocm_overlay.text() == '/approved/overlay'
        assert second.settings.value('unrelated/retained') == 'keep this'
    finally:
        second.close()


def test_runtime_fields_are_captured_in_immutable_job(windows, monkeypatch):
    from chatterbox_studio import rocm
    monkeypatch.setattr(rocm, 'known_runtime_defaults', lambda: {'python': '', 'overlay': ''})
    window = windows()
    window.device.setCurrentIndex(window.device.findData('rocm'))
    window.rocm_python.setText('/approved/python')
    window.rocm_overlay.setText('/approved/overlay')
    candidate = window._snapshot()
    assert candidate.device == 'rocm'
    assert (candidate.rocm_python, candidate.rocm_overlay) == ('/approved/python', '/approved/overlay')
    window.device.setCurrentIndex(window.device.findData('cpu'))
    window.rocm_python.setText('/different/python')
    assert candidate.device == 'rocm' and candidate.rocm_python == '/approved/python'


def test_about_discovers_all_shared_chatterbox_models(monkeypatch, tmp_path):
    from chatterbox_studio import about_dialog, model_downloads
    monkeypatch.setattr(model_downloads, 'installed_model_directory', lambda storage, model: tmp_path / model.key)
    text = about_dialog.diagnostics_text()
    for model in ('nano', 'turbo', 'english', 'multilingual-v3'):
        assert str(tmp_path / model) in text
    assert 'core Vulkan is unsupported' in text and 'external AMD ROCm' in text
