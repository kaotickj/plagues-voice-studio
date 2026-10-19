"""Forest-green desktop theme for the standalone Writer."""
def apply_theme(app):
    """Use one explicit palette for native popups, viewports and dialogs too."""
    from PyQt6.QtGui import QColor, QPalette
    app.setStyle('Fusion')
    palette = QPalette()
    colors = {
        'Window': '#111a16', 'WindowText': '#e8e6d9', 'Base': '#0e1712',
        'AlternateBase': '#203124', 'Text': '#ecece0', 'Button': '#263b2c',
        'ButtonText': '#e3e9d9', 'Highlight': '#567346', 'HighlightedText': '#ffffff',
        'ToolTipBase': '#203124', 'ToolTipText': '#ecece0', 'Link': '#bdd597',
        'PlaceholderText': '#a0afa2',
    }
    for name, value in colors.items():
        palette.setColor(getattr(QPalette.ColorRole, name), QColor(value))
    for name in ('Text', 'WindowText', 'ButtonText'):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, name), QColor('#82917e'))
    app.setPalette(palette)
    app.setStyleSheet(THEME)

THEME = '''
QWidget { background:#111a16; color:#e8e6d9; font-family:"Segoe UI"; font-size:13px; }
QMainWindow, QDialog { background:#111a16; }
QFrame#masthead { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #233a2a,stop:1 #14221b); border:1px solid #415a3c; border-radius:12px; }
QFrame#masthead QLabel { background:transparent; }
QLabel#brand { font-size:28px; font-weight:700; letter-spacing:3px; color:#e9ecd8; }
QLabel#eyebrow { color:#b4cb8d; font-size:10px; font-weight:600; letter-spacing:2px; }
QLabel#muted, QLabel#scriptStats { color:#a0afa2; font-size:12px; }
QLabel#badge { background:#263d2b; border:1px solid #506543; border-radius:9px; padding:5px 10px; color:#ccdcad; font-size:11px; }
QLabel#sectionTitle { color:#c6d99e; font-size:12px; font-weight:700; letter-spacing:2px; }
QGroupBox { background:#17241d; border:1px solid #354b3b; border-radius:9px; margin-top:15px; padding:15px 12px 10px; }
QGroupBox::title { subcontrol-origin:margin; left:14px; color:#c3d79f; font-weight:600; }
QGroupBox QLabel { background:transparent; }
QLineEdit,QTextEdit,QTextBrowser,QComboBox,QSpinBox { background:#0e1712; color:#ecece0; border:1px solid #3d5240; border-radius:6px; padding:7px; selection-background-color:#567346; }
QTextEdit#scriptEditor { background:#142019; border:1px solid #536748; border-radius:10px; padding:18px; font-size:15px; font-family:"Segoe UI"; }
QTextEdit:focus,QLineEdit:focus { border:1px solid #acc783; }
QComboBox { padding-right:32px; }
QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right; border-left:1px solid #506543; background:#263b2c; width:28px; }
QComboBox::down-arrow { image:url("__DROPDOWN_ICON__"); width:12px; height:8px; }
QPushButton,QToolButton { background:#263b2c; color:#e3e9d9; border:1px solid #465e45; border-radius:6px; padding:8px 12px; }
QPushButton:hover,QToolButton:hover { background:#36503a; border-color:#90ac6c; }
QPushButton#primary { background:#a9c17c; color:#152015; font-weight:700; border:1px solid #bdcf94; }
QPushButton#primary:hover { background:#bfd596; }
QPushButton:disabled { background:#1a281f; color:#728271; border-color:#2b3e30; }
QLineEdit:disabled,QComboBox:disabled { color:#758575; background:#17231c; }
QToolButton#disclosure { text-align:left; background:#1b2c21; border-color:#354b3a; padding:9px; color:#bdd198; }
QFrame#reviewCard { background:#203124; border:1px solid #526447; border-radius:9px; }
QFrame#reviewCard QLabel,QFrame#reviewCard QCheckBox { background:transparent; }
QFrame#reviewCard[approved="true"] { border:1px solid #b7cf86; background:#2a402b; }
QCheckBox { spacing:9px; padding:3px; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #7a916c; border-radius:4px; background:#122018; }
QCheckBox::indicator:checked { background:#afca80; border:2px solid #d4e3b6; image:none; }
QLabel#reviewNotes { color:#aab8a7; font-size:12px; padding:5px 2px; }
QMenuBar,QMenu { background:#17251c; color:#dce6d2; }
QMenu { border:1px solid #506543; padding:5px; }
QMenuBar::item { background:transparent; color:#dce6d2; padding:5px 10px; }
QMenu::item { background:transparent; color:#dce6d2; padding:7px 28px 7px 12px; }
QMenuBar::item:selected,QMenu::item:selected { background:#38513a; color:#ffffff; }
QMenu::item:disabled { color:#82917e; }
QMenu::separator { height:1px; background:#415a3c; margin:5px; }
QComboBox QAbstractItemView,QListView,QListWidget,QTreeView,QTableView { background:#142019; color:#ecece0; selection-background-color:#567346; selection-color:#ffffff; }
QToolTip { background:#203124; color:#ecece0; border:1px solid #7a916c; }
QStatusBar { background:#101913; color:#94a48e; font-size:11px; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:#111a16; width:9px; margin:0; }
QScrollBar::handle:vertical { background:#405940; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QSplitter::handle { background:#293c2c; }
QSplitter::handle:hover { background:#6d8659; }
'''

from pathlib import Path
THEME = THEME.replace('__DROPDOWN_ICON__', (Path(__file__).resolve().parent / 'assets/dropdown.svg').as_posix())
