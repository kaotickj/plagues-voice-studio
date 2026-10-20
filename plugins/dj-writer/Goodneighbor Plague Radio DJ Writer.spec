# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import copy_metadata
license_data = [('../../BINARY_LICENSE.md', '.'), ('../../THIRD_PARTY_NOTICES.md', '.'),
                ('../../LICENSES/GPL-3.0.txt', 'LICENSES')]
for distribution in ('PyQt6', 'PyQt6-Qt6', 'PyQt6-sip'):
    license_data += copy_metadata(distribution)

a = Analysis(
    ['goodneighbor_dj.py'],
    pathex=['..', '../../src'],
    binaries=[],
    datas=license_data+[('LORE_LIBRARY_LICENSE.md', '.'), ('lore_curation_report.json', '.'), ('lore_starter.json', '.'), ('dialogue.json', '.'), ('stories.json', '.'), ('assets/dj-writer.ico', 'assets'), ('assets/dj-writer.png', 'assets'), ('assets/dropdown.svg', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Goodneighbor Plague Radio DJ Writer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/dj-writer.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Goodneighbor Plague Radio DJ Writer',
)
