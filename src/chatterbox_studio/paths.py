"""Long-lived writable user-data directory and safe one-time v0.3 migration.

The original v0.3 directory is never moved, deleted or modified by migration.
Independent Python environments (often non-relocatable), huge model weights,
logs and existing exports stay in place and remain discoverable separately.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone
from uuid import uuid4
from plagued_ai import app_dir, root as shared_ai_root

_APP_FOLDER = "PlaguesVoiceStudio"
_LEGACY_APP_FOLDER = "PlaguesVoiceStudio-v030-Experimental"
_MIGRATION_EXCLUDED = frozenset({"engines", "models", "engine_logs", "exports", "__pycache__"})


def _local_data_root() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))


def legacy_v030_dir() -> Path:
    """Older v0.3 location, retained for read-only compatibility."""
    return _local_data_root() / _LEGACY_APP_FOLDER


def canonical_data_dir() -> Path:
    """Fixed path that does not change when the application version changes."""
    return app_dir('voice-studio')


def _ignore_legacy_items(folder: str, names: list[str]) -> set[str]:
    """Do not duplicate model caches, Python venvs, large logs or linked paths."""
    ignored = set()
    for name in names:
        path = Path(folder) / name
        if name in ('voices', 'voices.json') and (shared_ai_root()/'voices.json').is_file():
            ignored.add(name)
            continue
        if path.is_symlink() or (name in _MIGRATION_EXCLUDED and path.is_dir()):
            ignored.add(name)
    return ignored


def migrate_v030_data(legacy: Path, current: Path) -> bool:
    """Copy portable user state safely, committing only a complete new directory.

    Old content is untouched. If current already exists, never merge over user
    changes or overwrite them. Partial copies are cleaned up after failures.
    Heavy model weights and independent environments remain in legacy storage
    and are resolved read-only by other modules.
    """
    legacy, current = Path(legacy), Path(current)
    if current.exists() or not legacy.is_dir():
        return False
    current.parent.mkdir(parents=True, exist_ok=True)
    stage = current.with_name(current.name + ".migration-" + uuid4().hex)
    try:
        shutil.copytree(legacy, stage, symlinks=False, ignore=_ignore_legacy_items)
        manifest = {
            "from": str(legacy),
            "date_utc": datetime.now(timezone.utc).isoformat(),
            "method": "non-destructive copy",
            "retained_in_legacy": sorted(_MIGRATION_EXCLUDED),
            "note": "Separate installed engine environments and model weights remain at their original paths.",
        }
        (stage / "migration.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        # Both directories are under the same parent, so committing the
        # completed staged tree is a single rename, never a partial copy.
        stage.rename(current)
        return True
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def user_data_dir() -> Path:
    """Resolve canonical writable storage; preserve historical test overrides."""
    override = (os.environ.get("PLAGUES_VOICE_STUDIO_HOME")
                or os.environ.get("PLAGUES_VOICE_STUDIO_030_HOME"))
    if override:
        root = Path(override).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return root
    root = canonical_data_dir()
    previous = _local_data_root() / _APP_FOLDER
    if not root.exists():
        for source in (previous, legacy_v030_dir()):
            if source.is_dir():
                migrate_v030_data(source, root)
                break
    root.mkdir(parents=True, exist_ok=True)
    return root


def bundled_models_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "models"
