"""Brand palette + small stylesheet helpers (DSI Redline).

Centralises the colours used by the splash screen and the iLovePDF-style PDF
Tools workspace so the dark-navy / orange look stays consistent.
"""

from __future__ import annotations

# Brand palette (from the DSI Redline icon)
NAVY = "#16233F"          # primary dark background
NAVY_PANEL = "#1E2E4F"    # raised panel
NAVY_LIGHT = "#27395E"    # hover / row
ORANGE = "#E8772E"        # accent
ORANGE_DIM = "#C96523"    # accent pressed
WHITE = "#FFFFFF"
TEXT = "#E8EDF6"
TEXT_DIM = "#9FB0CF"
LINE = "#2E4068"          # subtle borders


def workspace_qss() -> str:
    """Stylesheet for the PDF Tools workspace (file bar, rail, grid, options)."""
    return f"""
    QWidget#ToolsWorkspace {{
        background: {NAVY};
        color: {TEXT};
    }}
    QFrame#FileBar {{
        background: {NAVY_PANEL};
        border-bottom: 1px solid {LINE};
    }}
    QLabel#FileName {{ color: {WHITE}; font-size: 14px; font-weight: bold; }}
    QLabel#FileHint {{ color: {TEXT_DIM}; }}
    QFrame#Rail {{ background: {NAVY_PANEL}; border-right: 1px solid {LINE}; }}
    QFrame#Options {{ background: {NAVY_PANEL}; border-left: 1px solid {LINE}; }}
    QLabel#OptTitle {{ color: {WHITE}; font-size: 15px; font-weight: bold; }}
    QLabel#OptDesc {{ color: {TEXT_DIM}; }}
    QLabel {{ color: {TEXT}; }}

    /* operation rail buttons */
    QPushButton#RailBtn {{
        text-align: left;
        padding: 9px 12px;
        border: none;
        border-radius: 6px;
        background: transparent;
        color: {TEXT};
    }}
    QPushButton#RailBtn:hover {{ background: {NAVY_LIGHT}; }}
    QPushButton#RailBtn:checked {{ background: {ORANGE}; color: {WHITE}; font-weight: bold; }}

    /* primary action button */
    QPushButton#ActionBtn {{
        background: {ORANGE};
        color: {WHITE};
        border: none;
        border-radius: 6px;
        padding: 10px 16px;
        font-weight: bold;
        font-size: 14px;
    }}
    QPushButton#ActionBtn:hover {{ background: {ORANGE_DIM}; }}
    QPushButton#ActionBtn:disabled {{ background: {NAVY_LIGHT}; color: {TEXT_DIM}; }}

    /* secondary buttons */
    QPushButton {{
        background: {NAVY_LIGHT};
        color: {TEXT};
        border: 1px solid {LINE};
        border-radius: 5px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{ border-color: {ORANGE}; }}

    QLineEdit, QSpinBox, QComboBox {{
        background: {NAVY};
        color: {TEXT};
        border: 1px solid {LINE};
        border-radius: 5px;
        padding: 5px 7px;
        selection-background-color: {ORANGE};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ORANGE}; }}
    QCheckBox, QRadioButton {{ color: {TEXT}; spacing: 6px; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {ORANGE};
    }}
    QProgressBar {{
        background: {NAVY}; border: 1px solid {LINE}; border-radius: 4px;
        text-align: center; color: {TEXT};
    }}
    QProgressBar::chunk {{ background: {ORANGE}; border-radius: 3px; }}
    """


def grid_qss() -> str:
    """Stylesheet for the thumbnail grid (orange selection highlight)."""
    return f"""
    QListWidget#ThumbGrid {{
        background: {NAVY};
        border: none;
        outline: 0;
    }}
    QListWidget#ThumbGrid::item {{
        color: {TEXT_DIM};
        border: 2px solid transparent;
        border-radius: 6px;
        margin: 4px;
        padding: 4px;
    }}
    QListWidget#ThumbGrid::item:hover {{
        border-color: {LINE};
        background: {NAVY_PANEL};
    }}
    QListWidget#ThumbGrid::item:selected {{
        color: {WHITE};
        border-color: {ORANGE};
        background: {NAVY_LIGHT};
    }}
    """
