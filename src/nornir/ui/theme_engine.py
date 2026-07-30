"""Dark purple / cyan theme engine for Nornir.

Applies a comprehensive QSS stylesheet and application-wide font.  Call
:func:`apply_theme` once before building the main window.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# ── Palette ──────────────────────────────────────────────────────────────────
_BG = "#1a1625"  # deepest background (main window)
_SURFACE = "#252035"  # cards, docks, panels
_SURFACE_ALT = "#2e2840"  # alternate rows, subtle panels
_BORDER = "#3d3555"  # dividers, frames
_ACCENT_CYAN = "#00e5ff"  # primary accent
_ACCENT_PURPLE = "#b388ff"  # secondary accent
_TEXT = "#e0e0e0"  # primary text
_TEXT_DIM = "#a0a0a0"  # secondary / disabled text
_SELECTION = "#3d2f5a"  # selection background
_HOVER = "#342a4a"  # hover background
_BUTTON_BG = "#2d2640"
_BUTTON_HOVER = "#3d3555"
_BUTTON_PRESSED = "#4a4060"
_INPUT_BG = "#1e1a2b"
_SCROLLBAR = "#3d3555"
_SCROLLBAR_HOVER = "#5a4f75"

_FONT_FAMILY = "Hack Nerd Font"
_FONT_FALLBACK = ["JetBrains Mono", "Fira Code", "Consolas", "monospace"]

_QSS = f"""
/* ── Global ─────────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: "{_FONT_FAMILY}", {', '.join(f'"{f}"' for f in _FONT_FALLBACK)};
    font-size: 11pt;
    selection-background-color: {_SELECTION};
    selection-color: {_TEXT};
}}

/* ── Main Window / Dock ───────────────────────────────────────────────────── */
QMainWindow {{
    background-color: {_BG};
}}

QDockWidget {{
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
}}

QDockWidget::title {{
    background-color: {_SURFACE};
    padding: 6px;
    border-bottom: 1px solid {_BORDER};
}}

QDockWidget::close-button, QDockWidget::float-button {{
    background-color: transparent;
    border-radius: 2px;
    padding: 2px;
}}

QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background-color: {_HOVER};
}}

/* ── Menu Bar ───────────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {_SURFACE};
    border-bottom: 1px solid {_BORDER};
    padding: 4px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border-radius: 3px;
}}

QMenuBar::item:selected {{
    background-color: {_HOVER};
}}

QMenuBar::item:pressed {{
    background-color: {_SELECTION};
}}

QMenu {{
    background-color: {_SURFACE};
    border: 1px solid {_BORDER};
    padding: 4px;
}}

QMenu::item {{
    padding: 5px 24px;
    border-radius: 3px;
}}

QMenu::item:selected {{
    background-color: {_SELECTION};
    color: {_ACCENT_CYAN};
}}

QMenu::separator {{
    height: 1px;
    background-color: {_BORDER};
    margin: 4px 8px;
}}

QMenu::icon {{
    padding-left: 8px;
}}

/* ── Push Button ──────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {_BUTTON_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 6px 14px;
    min-height: 22px;
}}

QPushButton:hover {{
    background-color: {_BUTTON_HOVER};
    border-color: {_ACCENT_PURPLE};
}}

QPushButton:pressed {{
    background-color: {_BUTTON_PRESSED};
}}

QPushButton:default {{
    background-color: {_SELECTION};
    border-color: {_ACCENT_CYAN};
    color: {_ACCENT_CYAN};
}}

QPushButton:disabled {{
    background-color: {_SURFACE};
    color: {_TEXT_DIM};
    border-color: {_BORDER};
}}

/* ── Tool Button ──────────────────────────────────────────────────────────── */
QToolButton {{
    background-color: {_BUTTON_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}

QToolButton:hover {{
    background-color: {_BUTTON_HOVER};
    border-color: {_ACCENT_PURPLE};
}}

QToolButton:pressed {{
    background-color: {_BUTTON_PRESSED};
}}

/* ── Line Edit / Plain Text Edit ──────────────────────────────────────────── */
QLineEdit, QPlainTextEdit {{
    background-color: {_INPUT_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {_SELECTION};
}}

QLineEdit:focus, QPlainTextEdit:focus {{
    border-color: {_ACCENT_CYAN};
}}

QLineEdit:disabled, QPlainTextEdit:disabled {{
    background-color: {_SURFACE};
    color: {_TEXT_DIM};
}}

/* ── Combo Box ────────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {_INPUT_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}}

QComboBox:hover {{
    border-color: {_ACCENT_PURPLE};
}}

QComboBox:focus {{
    border-color: {_ACCENT_CYAN};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {_BORDER};
}}

QComboBox QAbstractItemView {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    selection-background-color: {_SELECTION};
    selection-color: {_ACCENT_CYAN};
}}

/* ── Spin Box / Date Edit ─────────────────────────────────────────────────── */
QSpinBox, QDateEdit {{
    background-color: {_INPUT_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}

QSpinBox:focus, QDateEdit:focus {{
    border-color: {_ACCENT_CYAN};
}}

QSpinBox::up-button, QSpinBox::down-button,
QDateEdit::up-button, QDateEdit::down-button {{
    background-color: {_BUTTON_BG};
    border: 1px solid {_BORDER};
    width: 18px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDateEdit::up-button:hover, QDateEdit::down-button:hover {{
    background-color: {_BUTTON_HOVER};
}}

/* ── Calendar Widget ──────────────────────────────────────────────────────── */
QCalendarWidget QTableView {{
    background-color: {_SURFACE};
    color: {_TEXT};
    selection-background-color: {_SELECTION};
    gridline-color: {_BORDER};
}}

QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background-color: {_SURFACE_ALT};
    padding: 4px;
}}

QCalendarWidget QToolButton {{
    background-color: transparent;
    border: none;
    color: {_ACCENT_CYAN};
    font-weight: bold;
}}

QCalendarWidget QMenu {{
    background-color: {_SURFACE};
    color: {_TEXT};
}}

/* ── Check Box ────────────────────────────────────────────────────────────── */
QCheckBox {{
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {_BORDER};
    border-radius: 3px;
    background-color: {_INPUT_BG};
}}

QCheckBox::indicator:checked {{
    background-color: {_ACCENT_CYAN};
    border-color: {_ACCENT_CYAN};
}}

QCheckBox::indicator:hover {{
    border-color: {_ACCENT_PURPLE};
}}

/* ── Table View ───────────────────────────────────────────────────────────── */
QTableView {{
    background-color: {_BG};
    alternate-background-color: {_SURFACE_ALT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    gridline-color: {_BORDER};
    selection-background-color: {_SELECTION};
    selection-color: {_TEXT};
}}

QTableView::item:selected {{
    background-color: {_SELECTION};
    color: {_ACCENT_CYAN};
}}

QTableView::item:hover {{
    background-color: {_HOVER};
}}

QHeaderView::section {{
    background-color: {_SURFACE};
    color: {_ACCENT_CYAN};
    padding: 6px 10px;
    border: none;
    border-bottom: 2px solid {_ACCENT_PURPLE};
    font-weight: bold;
}}

QHeaderView::section:hover {{
    background-color: {_HOVER};
}}

/* ── Tree View / Tree Widget ──────────────────────────────────────────────── */
QTreeView, QTreeWidget {{
    background-color: {_BG};
    alternate-background-color: {_SURFACE_ALT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    selection-background-color: {_SELECTION};
    selection-color: {_TEXT};
    outline: none;
}}

QTreeView::item:selected, QTreeWidget::item:selected {{
    background-color: {_SELECTION};
    color: {_ACCENT_CYAN};
}}

QTreeView::item:hover, QTreeWidget::item:hover {{
    background-color: {_HOVER};
}}

QTreeView::branch:has-siblings:!adjoins-item {{
    border-image: none;
}}

QTreeView::branch:has-siblings:adjoins-item {{
    border-image: none;
}}

/* ── List Widget ──────────────────────────────────────────────────────────── */
QListWidget {{
    background-color: {_BG};
    alternate-background-color: {_SURFACE_ALT};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    selection-background-color: {_SELECTION};
    selection-color: {_TEXT};
    outline: none;
    padding: 4px;
}}

QListWidget::item {{
    padding: 4px 6px;
    border-radius: 3px;
}}

QListWidget::item:selected {{
    background-color: {_SELECTION};
    color: {_ACCENT_CYAN};
}}

QListWidget::item:hover {{
    background-color: {_HOVER};
}}

/* ── Scroll Bar ───────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: {_BG};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {_SCROLLBAR};
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {_SCROLLBAR_HOVER};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {_BG};
    height: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal {{
    background-color: {_SCROLLBAR};
    border-radius: 6px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {_SCROLLBAR_HOVER};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ── Dialog ───────────────────────────────────────────────────────────────── */
QDialog {{
    background-color: {_BG};
}}

QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

/* ── Group Box / Frame ────────────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {_BORDER};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: {_ACCENT_PURPLE};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
}}

QFrame {{
    border: 1px solid {_BORDER};
}}

/* ── Label ────────────────────────────────────────────────────────────────── */
QLabel {{
    color: {_TEXT};
    background: transparent;
}}

/* ── Tab Widget (if used later) ───────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {_BORDER};
    background-color: {_SURFACE};
}}

QTabBar::tab {{
    background-color: {_BUTTON_BG};
    color: {_TEXT_DIM};
    border: 1px solid {_BORDER};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
}}

QTabBar::tab:selected {{
    background-color: {_SURFACE};
    color: {_ACCENT_CYAN};
    border-bottom: 2px solid {_ACCENT_CYAN};
}}

QTabBar::tab:hover {{
    background-color: {_HOVER};
}}

/* ── Tooltip ──────────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1px solid {_ACCENT_PURPLE};
    padding: 4px 8px;
    border-radius: 3px;
}}

/* ── Splitter ─────────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {_BORDER};
}}

QSplitter::handle:hover {{
    background-color: {_ACCENT_PURPLE};
}}
"""


def _load_font() -> QFont | None:
    """Try to load Hack Nerd Font; fall back through the list."""
    db = QFontDatabase()
    for family in [_FONT_FAMILY, *_FONT_FALLBACK]:
        if family in db.families():
            font = QFont(family)
            font.setPointSize(10)
            font.setStyleHint(QFont.StyleHint.Monospace)
            return font
    return None


def apply_theme(app: QApplication) -> None:
    """Apply the dark purple/cyan stylesheet and monospace font to *app*."""
    app.setStyleSheet(_QSS)
    font = _load_font()
    if font is not None:
        app.setFont(font)
