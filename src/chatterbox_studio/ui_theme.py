"""Palette and typography for Plague's Voice Studio.

One stylesheet across Qt, with targeted object names for branded surfaces.
Native widget layout remains in charge of scaling, focus and accessibility.
"""

CSS = r"""
QWidget { background-color: #101719; color: #e4f0e8; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 13px; }
QMainWindow, QDialog, QTabWidget::pane { background-color: #0e1516; }
QToolTip { background: #182b25; color: #edf9ef; border: 1px solid #508960; padding: 7px; }
QMenuBar, QMenu { background:#15231e; color:#e4f0e8; }
QMenu { border:1px solid #4b7255; padding:5px; }
QMenuBar::item { background:transparent; color:#e4f0e8; padding:5px 10px; }
QMenu::item { background:transparent; color:#e4f0e8; padding:7px 26px 7px 12px; }
QMenuBar::item:selected, QMenu::item:selected { background:#355b3d; color:#ffffff; }
QMenu::item:disabled { color:#8a9d90; }
QLabel { background: transparent; }
QLabel#sectionTitle { color: #b1ffc0; font-size: 17px; font-weight: 700; }
QLabel#mutedText { color: #adc5b3; }
QLabel#warningText { color: #f5d59c; background: #31281b; border: 1px solid #8d7441; border-radius: 7px; padding: 9px; }
QFrame#brandHeader { background: #15231e; border: 1px solid #314c3d; border-radius: 12px; }
QFrame#heroCard, QFrame#infoCard { background: #17231f; border: 1px solid #334a3d; border-radius: 10px; }
QFrame#helpSidebar { background: #13201b; border: 1px solid #304839; border-radius: 10px; }
QGroupBox { background: #15201c; border: 1px solid #344e3e; border-radius: 10px; margin-top: 17px; padding: 14px 11px 12px; font-weight: 600; }
QGroupBox::title { color: #b6f8bd; subcontrol-origin: margin; left: 13px; padding: 0 6px; }
QPushButton { background: #273d30; color: #edf8ed; border: 1px solid #4b7255; border-radius: 7px; padding: 8px 12px; min-height: 19px; }
QPushButton:hover { background: #355b3d; border-color: #7baa80; }
QPushButton:pressed { background: #1a3626; }
QPushButton:focus { border: 2px solid #a0f6ad; }
QPushButton:disabled { background: #1e2924; border-color: #37483c; color: #8a9d90; }
QPushButton#primary { background: #8ceba0; color: #0e2614; border: 1px solid #8ceba0; font-weight: 700; }
QPushButton#primary:hover { background: #b4ffc3; }
QPushButton#quietButton { background: #1a2822; border: 1px solid #36533d; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QTreeWidget, QListWidget, QTextBrowser {
    background: #0e1716; color: #e8f4eb; selection-background-color: #326d47;
    border: 1px solid #3d5948; border-radius: 7px; padding: 7px;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QTextBrowser:focus, QListWidget:focus, QTreeWidget:focus {
    border: 1px solid #9cecac;
}
QComboBox::drop-down { border: 0; width: 22px; }
QComboBox QAbstractItemView { background: #13211b; selection-background-color: #315b3c; }
QTabWidget::pane { border: 1px solid #334b3c; border-radius: 8px; top: -1px; }
QTabBar::tab { background: #1b2c23; border: 1px solid #344b3a; border-bottom: 0; border-top-left-radius: 7px; border-top-right-radius: 7px; padding: 10px 16px; margin-right: 3px; color: #c6dbc9; }
QTabBar::tab:selected { background: #386744; color: #ffffff; font-weight: 700; }
QTabBar::tab:hover:!selected { background: #2c4935; }
QListWidget::item { padding: 10px 9px; border-radius: 5px; }
QListWidget::item:selected { background: #315c41; color: #ffffff; }
QListWidget::item:hover { background: #233e2d; }
QHeaderView::section { background: #22372a; color: #e4f3e7; padding: 8px; border: 0; border-bottom: 1px solid #405946; }
QTableWidget, QTreeWidget { alternate-background-color: #15211a; }
QSlider::groove:horizontal { background: #3d5945; height: 7px; border-radius: 3px; }
QSlider::handle:horizontal { background: #a7f3b5; width: 15px; margin: -5px 0; border-radius: 7px; }
QProgressBar { background: #182b1d; color: #e9f9e8; border: 1px solid #426247; border-radius: 6px; text-align: center; }
QProgressBar::chunk { background: #70d889; border-radius: 5px; }
QScrollBar:vertical { background: #18231d; width: 13px; margin: 0; }
QScrollBar::handle:vertical { background: #4e785b; border-radius: 5px; min-height: 25px; }
QScrollBar:horizontal { background: #18231d; height: 13px; }
QScrollBar::handle:horizontal { background: #4e785b; border-radius: 5px; min-width: 25px; }
QStatusBar { background: #101b15; color: #bad3bf; }
QSplitter::handle { background: #304b36; }
"""
