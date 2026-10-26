"""Isolated Qt settings/snapshot checks, with no model runtime or audio device."""
from test_narration_profile_ui import windows
from types import SimpleNamespace
import sys

import pytest


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
    assert 'Linux-only' in text and 'CPU-only Torch build does not provide AMD GPU acceleration' in text


@pytest.mark.parametrize('platform', ['win32', 'linux'])
def test_external_controls_only_show_for_selected_linux_backend(windows, monkeypatch, platform):
    from chatterbox_studio import app, engine_lab, rocm
    monkeypatch.setattr(app, 'sys', SimpleNamespace(platform=platform))
    monkeypatch.setattr(engine_lab, 'sys', SimpleNamespace(platform=platform))
    monkeypatch.setattr(rocm, 'known_runtime_defaults', lambda: {'python': '', 'overlay': ''})
    window = windows()
    window.device.setCurrentIndex(window.device.findData('cpu'))
    assert all(not window._rocm_form.isRowVisible(row) for row in window._rocm_rows)
    window.device.setCurrentIndex(window.device.findData('rocm'))
    assert window.rocm_python.isEnabled() is (platform == 'linux')
    assert all(window._rocm_form.isRowVisible(row) == (platform == 'linux') for row in window._rocm_rows)
    window.rocm_python.setText('/retained/linux/python')
    window.rocm_overlay.setText('/retained/linux/overlay')
    window._save_processor_settings()
    assert window.settings.value('rocm/python') == '/retained/linux/python'
    assert window.settings.value('rocm/overlay') == '/retained/linux/overlay'

    lab = window.engine_lab
    assert lab.backend.model().item(lab.backend.findData('native_vulkan')).isEnabled() is (platform == 'linux')
    for field in lab.native_fields.values():
        assert field.isEnabled() is (platform == 'linux')
        assert field.isHidden() is (platform != 'linux')
    lab.native_fields['native_executable'].setText('/retained/linux/audio-cli')
    lab.save_runtimes()
    assert lab.registry.read()['native']['native_executable'] == '/retained/linux/audio-cli'
    if platform == 'win32':
        from PyQt6.QtWidgets import QLabel
        assert any('available on Linux only' in label.text() for label in lab.findChildren(QLabel))


@pytest.mark.parametrize('cuda,hip,expected,enabled', [
    (None, None, 'CPU-only PyTorch', False),
    ('12.4', None, 'NVIDIA CUDA', True),
    (None, '6.4', 'AMD ROCm', True),
])
def test_host_processor_labels_follow_host_build_not_optional_runtimes(windows, monkeypatch, cuda, hip, expected, enabled):
    from chatterbox_studio import app
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(version=SimpleNamespace(cuda=cuda, hip=hip)))
    window = windows()
    index = window.device.findData('cuda')
    assert expected in window.device.itemText(index)
    assert window.device.model().item(index).isEnabled() is enabled
    if not enabled:
        assert 'Auto (CPU;' in window.device.itemText(window.device.findData('auto'))
