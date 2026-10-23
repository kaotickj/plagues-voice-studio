"""Versioned local QWidget plugin discovery and lifecycle.

Manifests are inspected without executing code; entry points run only on selection.
Plugins are trusted Python code installed with the application, not a sandbox.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout, QWidget

API_VERSION = 1


@dataclass(frozen=True)
class PluginSpec:
    plugin_id: str
    name: str
    version: str
    directory: Path
    entry_point: Path


@dataclass(frozen=True)
class PluginContext:
    parent: QWidget
    data_dir: Path
    can_generate: object
    handoff: object


def plugin_roots():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    roots = [base / 'plugins']
    if getattr(sys, 'frozen', False):
        external = Path(sys.executable).resolve().parent / 'plugins'
        if external != roots[0]:
            roots.append(external)
    return roots


def discover_plugins(roots):
    found, errors = {}, []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for directory in sorted(root.iterdir()):
            manifest = directory / 'plugin.json'
            if not directory.is_dir() or not manifest.is_file():
                continue
            try:
                if manifest.stat().st_size > 65536:
                    raise ValueError('Manifest is too large.')
                data = json.loads(manifest.read_text(encoding='utf-8'))
                plugin_id = data.get('id', '')
                if not isinstance(plugin_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', plugin_id):
                    raise ValueError('Invalid plugin id.')
                if type(data.get('api_version')) is not int or data['api_version'] != API_VERSION:
                    raise ValueError('Unsupported plugin API version.')
                name, version = data.get('name'), data.get('version')
                if not isinstance(name, str) or not name.strip() or len(name) > 80 or not isinstance(version, str):
                    raise ValueError('Missing plugin name/version.')
                entry = (directory / data.get('entry_point', '')).resolve()
                if not entry.is_relative_to(directory.resolve()) or entry.suffix != '.py' or not entry.is_file():
                    raise ValueError('Entry point must be a Python file inside the plugin folder.')
                if plugin_id in found and found[plugin_id].directory.parent == directory.parent:
                    raise ValueError('Duplicate plugin id in the same folder.')
                found[plugin_id] = PluginSpec(plugin_id, name, version, directory.resolve(), entry)
            except (ValueError, OSError, TypeError, AttributeError) as exc:
                errors.append(f'{directory.name}: {exc}')
    return sorted(found.values(), key=lambda item: item.name), errors


def load_factory(spec):
    # Unique package namespace supports relative imports and avoids plugin collisions.
    digest = hashlib.sha256(str(spec.directory).encode()).hexdigest()[:12]
    name = f'_pvs_plugin_{spec.plugin_id.replace("-", "_")}_{digest}'
    if name in sys.modules:
        module = sys.modules[name]
    else:
        module_spec = importlib.util.spec_from_file_location(name, spec.entry_point,
                            submodule_search_locations=[str(spec.directory)])
        if module_spec is None or module_spec.loader is None:
            raise ValueError('Cannot load plugin entry point.')
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[name] = module
        try:
            module_spec.loader.exec_module(module)
        except Exception:
            for key in list(sys.modules):
                if key == name or key.startswith(name + '.'):
                    sys.modules.pop(key, None)
            raise
    factory = getattr(module, 'create_plugin', None)
    if not callable(factory):
        raise ValueError('Plugin does not export create_plugin(context).')
    return factory


class PluginDialog(QDialog):
    def __init__(self, panel, name, parent):
        super().__init__(parent)
        self.setWindowTitle(name); self.resize(1100, 850); self.setMinimumSize(900, 680)
        self.panel = panel
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        layout = QVBoxLayout(self); layout.addWidget(panel)

    def reject(self):
        if getattr(self.panel, 'is_busy', False):
            self.panel.cancel()
            return
        super().reject()

    def closeEvent(self, event):
        if getattr(self.panel, 'is_busy', False):
            self.panel.cancel()
            event.ignore()
        else:
            super().closeEvent(event)


class PluginManager:
    def __init__(self, host, roots=None):
        self.host = host
        self.roots = plugin_roots() if roots is None else roots
        # Shared runtime is bundled by PyInstaller; source runs locate plugins/ here.
        if not getattr(sys, 'frozen', False):
            shared = Path(__file__).resolve().parents[2] / 'plugins'
            if str(shared) not in sys.path:
                sys.path.insert(0, str(shared))
        self.dialogs = {}
        self.specs, self.errors = discover_plugins(self.roots)
        self.menu = host.menuBar().addMenu('Plugins')
        self.refresh_menu()

    @property
    def is_busy(self):
        return any(getattr(dialog.panel, 'is_busy', False) for dialog in self.dialogs.values())

    def refresh_menu(self):
        self.menu.clear()
        for spec in self.specs:
            action = self.menu.addAction(spec.name + '…')
            action.setData(spec.plugin_id)
            action.triggered.connect(lambda checked=False, selected=spec: self.open(selected))
        if not self.specs:
            self.menu.addAction('No plugins installed').setEnabled(False)
        if self.errors:
            self.menu.addSeparator()
            action = self.menu.addAction('Plugin loading details…')
            action.triggered.connect(lambda: QMessageBox.warning(self.host, 'Plugin loading details', '\n'.join(self.errors)))

    def can_generate(self):
        if self.host.thread is not None or any(
                getattr(getattr(self.host, name, None), 'is_busy', False)
                for name in ('engine_lab', 'model_manager', 'bethesda_tab')):
            return 'Finish Voice Studio generation or model operations before starting the writer.'
        if self.is_busy:
            return 'Another plugin operation is still running.'
        return ''

    def open(self, spec):
        if spec.plugin_id in self.dialogs:
            dialog = self.dialogs[spec.plugin_id]
            dialog.show(); dialog.raise_(); dialog.activateWindow()
            return dialog
        try:
            context = PluginContext(self.host, self.host.storage / 'plugins' / spec.plugin_id,
                                    self.can_generate, self.host._accept_plugin_text)
            panel = load_factory(spec)(context)
            if not isinstance(panel, QWidget):
                raise ValueError('Plugin factory must return a QWidget.')
            if not hasattr(panel, 'is_busy') or not callable(getattr(panel, 'cancel', None)):
                panel.deleteLater()
                raise ValueError('Plugin must expose is_busy and cancel().')
            dialog = PluginDialog(panel, spec.name, self.host)
            self.dialogs[spec.plugin_id] = dialog
            dialog.show()
            return dialog
        except Exception as exc:
            QMessageBox.warning(self.host, 'Plugin could not open', f'{spec.name}: {exc}')
            return None

    def cancel_all(self):
        for dialog in self.dialogs.values():
            if dialog.panel.is_busy:
                dialog.panel.cancel()

    def close_all(self):
        for dialog in self.dialogs.values():
            dialog.close()
