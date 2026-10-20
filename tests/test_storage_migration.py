"""Permanent AppData migration tests, no GUI or large model downloads."""
import json
from pathlib import Path

import pytest

from chatterbox_studio import paths
from chatterbox_studio import model_downloads as md
from chatterbox_studio.settings_migration import copy_legacy_settings


def _windows_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("PLAGUES_VOICE_STUDIO_HOME", raising=False)
    monkeypatch.delenv("PLAGUES_VOICE_STUDIO_030_HOME", raising=False)
    monkeypatch.delenv('PLAGUED_AI_HOME', raising=False)
    current = tmp_path/'PlaguedAI/apps/voice-studio'
    current.parent.mkdir(parents=True, exist_ok=True)
    return tmp_path / "PlaguesVoiceStudio-v030-Experimental", current


def test_appdata_migration_preserves_profiles_and_voice_references(monkeypatch, tmp_path):
    old, new = _windows_paths(monkeypatch, tmp_path)
    (old / "voices").mkdir(parents=True)
    (old / "voices" / "ref.wav").write_bytes(b"original voice")
    (old / "voices.json").write_text('[{"id":"id1","file":"ref.wav","name":"Tal"}]', encoding="utf-8")
    (old / "optional_engines.json").write_text(json.dumps({
        "qwen3": {"python": str(old / "engines/qwen3/Scripts/python.exe"), "repo": ""},
    }), encoding="utf-8")
    (old / "character_profiles.json").write_text('{"Tal": {"voice_id":"id1"}}', encoding="utf-8")
    (old / "bethesda_projects.json").write_text('{"test":"keep"}', encoding="utf-8")
    for folder in ("models", "engines", "engine_logs", "exports"):
        (old / folder).mkdir()
        (old / folder / "untouched.bin").write_bytes(b"x" * 100)
    assert paths.user_data_dir() == new
    assert (new / "voices/ref.wav").read_bytes() == b"original voice"
    assert (new / "voices.json").read_text() == (old / "voices.json").read_text()
    assert (new / "character_profiles.json").read_text() == (old / "character_profiles.json").read_text()
    assert (new / "bethesda_projects.json").read_text() == '{"test":"keep"}'
    assert json.loads((new / "optional_engines.json").read_text())["qwen3"]["python"].startswith(str(old))
    for folder in ("models", "engines", "engine_logs", "exports"):
        assert not (new / folder).exists(), f"{folder} should remain in legacy directory"
        assert (old / folder / "untouched.bin").is_file()
    assert json.loads((new / "migration.json").read_text())["method"] == "non-destructive copy"
    assert (old / "voices/ref.wav").is_file()


def test_existing_new_data_is_authoritative_and_never_overwritten(monkeypatch, tmp_path):
    old, new = _windows_paths(monkeypatch, tmp_path)
    old.mkdir(); new.mkdir()
    (old / "voices.json").write_text("old", encoding="utf-8")
    (new / "voices.json").write_text("new", encoding="utf-8")
    assert paths.user_data_dir() == new
    assert (new / "voices.json").read_text() == "new"
    assert (old / "voices.json").read_text() == "old"


def test_override_bypasses_migration(monkeypatch, tmp_path):
    old, new = _windows_paths(monkeypatch, tmp_path)
    old.mkdir()
    custom = tmp_path / "isolated-app"
    monkeypatch.setenv("PLAGUES_VOICE_STUDIO_HOME", str(custom))
    assert paths.user_data_dir() == custom
    assert custom.is_dir() and not new.exists()


def test_failed_migration_does_not_create_partial_canonical_directory(monkeypatch, tmp_path):
    old, new = _windows_paths(monkeypatch, tmp_path)
    old.mkdir()
    (old / "voices.json").write_text("source", encoding="utf-8")
    def fail(*args, **kwargs):
        stage = Path(args[1])
        stage.mkdir()
        (stage / "partial").write_text("partial")
        raise OSError("simulated disk failure")
    monkeypatch.setattr(paths.shutil, "copytree", fail)
    with pytest.raises(OSError, match="simulated"):
        paths.migrate_v030_data(old, new)
    assert not new.exists()
    assert (old / "voices.json").read_text() == "source"
    assert not list(tmp_path.glob("PlaguesVoiceStudio.migration-*"))


def test_old_chatterbox_weights_are_reused_without_download(monkeypatch, tmp_path):
    old, new = _windows_paths(monkeypatch, tmp_path)
    item = md.MODELS["nano"]
    folder = old / "models" / "nano"
    folder.mkdir(parents=True)
    for fn in item.required:
        (folder / fn).write_bytes(b"valid")
    monkeypatch.setattr(md, "canonical_data_dir", lambda: new)
    monkeypatch.setattr(md, "legacy_v030_dir", lambda: old)
    monkeypatch.setattr(md, "bundled_models_dir", lambda: tmp_path / "bundle")
    assert md.installed_model_directory(new, item) == folder
    assert md.chatterbox_status(new, item) == "Installed (previous v0.3 data)"
    messages = []
    from threading import Event
    assert md.download_chatterbox(item, new, Event(), messages.append) == folder
    assert not (new / "models").exists()
    assert "No download needed" in messages[-1]


def test_new_chatterbox_weights_take_precedence(monkeypatch, tmp_path):
    old, new = _windows_paths(monkeypatch, tmp_path)
    item = md.MODELS["nano"]
    monkeypatch.setattr(md, "canonical_data_dir", lambda: new)
    monkeypatch.setattr(md, "legacy_v030_dir", lambda: old)
    for target in (old, new):
        folder = target / "models" / "nano"
        folder.mkdir(parents=True)
        for fn in item.required:
            (folder / fn).write_bytes(b"valid")
    assert md.installed_model_directory(new, item) == new / "models" / "nano"


class FakeSettings:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.sync_calls = 0
    def allKeys(self):
        return list(self.data)
    def value(self, key):
        return self.data[key]
    def setValue(self, key, value):
        self.data[key] = value
    def sync(self):
        self.sync_calls += 1


def test_old_settings_are_copied_but_never_overwrite_new_values():
    old = FakeSettings({"last_voice": "tal", "model": "turbo", "pause_ms": 180})
    new = FakeSettings({"model": "nano"})
    assert copy_legacy_settings(new, old) == 2
    assert new.data == {"model": "nano", "last_voice": "tal", "pause_ms": 180}
    assert copy_legacy_settings(new, old) == 0
    assert old.data["model"] == "turbo"
    assert new.sync_calls == 1


def test_legacy_audio_folders_remain_browsable_and_new_exports_are_unversioned(monkeypatch, tmp_path):
    from chatterbox_studio import pvs_library
    old, new = _windows_paths(monkeypatch, tmp_path)
    old_exports = pvs_library.old_export_directories()
    assert old / "exports" in old_exports
    assert Path.home() / "Music" / "Plague's Voice Studio Experimental" in old_exports
    assert "Experimental" not in str(pvs_library.new_export_directory(new).name)
