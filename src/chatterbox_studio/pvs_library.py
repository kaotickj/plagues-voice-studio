"""v0.3 writable library with read-only access to v0.2.x and v0.1.x.

Never writes to or removes any file belonging to the older application.
"""
from __future__ import annotations
from pathlib import Path
import os
import re
import sys
from datetime import datetime
from .voices import VoiceLibrary
from .paths import legacy_v030_dir
from .paths import canonical_data_dir
from plagued_ai import root as shared_ai_root


def legacy_data_dir() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'ChatterboxStudio'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'ChatterboxStudio'


def stable_data_dir() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'PlaguesVoiceStudio-v021'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'PlaguesVoiceStudio-v021'


def old_export_directories() -> list[Path]:
    return [Path.home() / 'Music' / 'Chatterbox Studio',
            Path.home() / 'Music' / "Plague's Voice Studio 0.2",
            Path.home() / 'Music' / "Plague's Voice Studio Experimental",
            legacy_data_dir() / 'exports', stable_data_dir() / 'exports',
            legacy_v030_dir() / 'exports']


def new_export_directory(storage: Path) -> Path:
    music = Path.home() / 'Music'
    return music / "Plague's Voice Studio" if music.is_dir() else storage / 'exports'


def safe_voice_name(name: str) -> str:
    """Conservative file stem, based on the user's selected voice display name."""
    name = re.sub(r'[^A-Za-z0-9_-]+', '_', name.strip())
    return name.strip('_-')[:64] or 'default'


def narration_basename(voice_name: str | None, at: datetime | None = None) -> str:
    at = at or datetime.now()
    prefix = safe_voice_name(voice_name or 'default')
    return f'{prefix}_narration_{at:%Y%m%d-%H%M%S}'


class CompatibleVoiceLibrary:
    """Current writable library + stable/legacy read-only references.

    Legacy/stable identifiers are prefixed to avoid accidental conflicts. New
    imports go only to v0.3 storage. Removal of old voices is prohibited.
    """
    def __init__(self, storage: Path):
        if Path(storage) == canonical_data_dir() and not (shared_ai_root()/'voices.json').exists():
            from plagued_ai.voices import sources
            if not any((folder/'voices.json').is_file() for folder, prefix in sources()):
                shared_ai_root().mkdir(parents=True,exist_ok=True)
                try:
                    with (shared_ai_root()/'voices.json').open('x',encoding='utf-8') as index:
                        index.write('[]')
                except FileExistsError:
                    pass
        self.shared = Path(storage) == canonical_data_dir() and (shared_ai_root()/'voices.json').is_file()
        self.current = VoiceLibrary(shared_ai_root() if self.shared else storage)
        # Read metadata and reference paths without touching legacy storage.
        old = legacy_data_dir()
        self.legacy = VoiceLibrary(old, read_only=True) if old.is_dir() else None
        stable = stable_data_dir()
        self.stable = VoiceLibrary(stable, read_only=True) if stable.is_dir() else None

    def list_voices(self) -> list[dict]:
        current = self.current.list_voices()
        if self.shared:
            return current
        previous = [dict(item, id='legacy:' + item['id'], name=item['name'] + ' (v0.1.x)')
                    for item in (self.legacy.list_voices() if self.legacy else [])]
        stable_items = [dict(item, id='stable:' + item['id'], name=item['name'] + ' (stable v0.2.x)')
                        for item in (self.stable.list_voices() if self.stable else [])]
        return current + stable_items + previous

    def resolve(self, voice_id: str) -> str:
        if self.shared:
            return self.current.resolve(voice_id)
        if voice_id.startswith('legacy:'):
            return self.legacy.resolve(voice_id[7:]) if self.legacy else ""
        if voice_id.startswith('stable:'):
            return self.stable.resolve(voice_id[7:]) if self.stable else ""
        return self.current.resolve(voice_id)

    def import_voice(self, name: str, source: Path) -> dict:
        return self.current.import_voice(name, source)

    def remove_voice(self, voice_id: str) -> bool:
        if self.shared:
            return self.current.remove_voice(voice_id)
        if voice_id.startswith(('legacy:', 'stable:')):
            raise ValueError('This voice belongs to an earlier release and is read-only. Import a copy to edit.')
        return self.current.remove_voice(voice_id)
