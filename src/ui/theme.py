"""
theme.py — Runtime theme/accent/animation system for Quadrogent.

Call apply_theme(app, db) after loading settings to update styles.
"""
from __future__ import annotations

_ACCENTS = {
    "mono":   {"accent": "#e0e0e0", "accent_dim": "#606060", "accent_bg": "#181818", "accent_bd": "#2a2a2a"},
    "blue":   {"accent": "#5a9fd8", "accent_dim": "#2a5070", "accent_bg": "#0a1420", "accent_bd": "#1a3050"},
    "green":  {"accent": "#5a9a6a", "accent_dim": "#2a5030", "accent_bg": "#0a1610", "accent_bd": "#1a3820"},
    "orange": {"accent": "#d8843a", "accent_dim": "#704020", "accent_bg": "#1a1008", "accent_bd": "#402808"},
    "pink":   {"accent": "#c87ab0", "accent_dim": "#703060", "accent_bg": "#180c18", "accent_bd": "#381830"},
    "red":    {"accent": "#d84848", "accent_dim": "#702020", "accent_bg": "#180808", "accent_bd": "#381818"},
}

_DARK_BASE = {
    "bg":       "#0a0a0a",
    "bg2":      "#070707",
    "bg3":      "#050505",
    "surface":  "#0d0d0d",
    "border":   "#181818",
    "border2":  "#1e1e1e",
    "text":     "#e8e8e8",
    "text_dim": "#999999",
    "text_mute":"#555555",
}

_LIGHT_BASE = {
    "bg":       "#f5f5f5",
    "bg2":      "#eeeeee",
    "bg3":      "#e8e8e8",
    "surface":  "#ffffff",
    "border":   "#d0d0d0",
    "border2":  "#c0c0c0",
    "text":     "#111111",
    "text_dim": "#555555",
    "text_mute":"#888888",
}


def _build_stylesheet(colors: dict, a: dict, animations: bool) -> str:
    bg   = colors["bg"]
    bg2  = colors["bg2"]
    bg3  = colors["bg3"]
    surf = colors["surface"]
    brd  = colors["border"]
    brd2 = colors["border2"]
    txt  = colors["text"]
    dim  = colors["text_dim"]
    mute = colors["text_mute"]
    acc  = a["accent"]
    adim = a["accent_dim"]
    abg  = a["accent_bg"]
    abd  = a["accent_bd"]

    trans = "all 0.15s ease" if animations else "none"

    return f"""
QMainWindow, QDialog {{
    background-color: {bg};
    color: {txt};
}}
QWidget {{
    background-color: {bg};
    color: {txt};
    font-family: "Roboto", "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
}}

/* ── Sidebar ─────────────────────────── */
#sidebar {{
    background-color: {bg2};
    border-right: 1px solid {brd};
}}
#newChatBtn {{
    background-color: transparent;
    color: {txt};
    border: 1px solid {brd2};
    font-size: 12px;
    font-weight: 500;
    padding: 9px 12px;
    margin: 6px 10px 4px 10px;
    border-radius: 7px;
    text-align: left;
}}
#newChatBtn:hover {{ background-color: {surf}; border-color: {brd2}; }}
#chatList {{ background-color: {bg2}; border: none; outline: none; }}
#chatList::item {{
    padding: 9px 12px; border-radius: 6px;
    color: {dim}; margin: 1px 6px; font-size: 12px;
    border-left: 2px solid transparent;
}}
#chatList::item:selected {{
    background-color: {surf}; color: {txt};
    border-left: 2px solid {acc};
}}
#chatList::item:hover:!selected {{ background-color: {bg3}; color: {txt}; }}
#settingsBtn {{
    background-color: transparent; color: {dim};
    border: none; border-top: 1px solid {brd};
    font-size: 12px; padding: 11px 16px; margin: 0;
    border-radius: 0; text-align: left;
}}
#settingsBtn:hover {{ background-color: {bg3}; color: {txt}; }}
#clearBtn {{
    background-color: transparent; color: #cc3333;
    border: none; border-top: 1px solid {brd};
    font-size: 11px; padding: 9px 16px; margin: 0;
    border-radius: 0; text-align: left;
}}
#clearBtn:hover {{ background-color: {bg3}; color: #ee5555; }}

/* ── Top bar ─────────────────────────── */
#chatTopBar {{
    background-color: {bg2};
    border-bottom: 1px solid {brd};
    min-height: 46px; max-height: 46px;
}}
#modelLabel {{ color: {dim}; font-size: 11px; background: transparent; }}
#modelCombo {{
    background-color: transparent; border: 1px solid {brd2};
    border-radius: 5px; padding: 3px 8px; color: {txt}; font-size: 11px;
    min-width: 190px; text-align: left;
}}
#modelCombo:hover {{ border-color: {acc}; color: {txt}; }}

#exportBtn {{
    background-color: transparent; border: 1px solid {brd};
    border-radius: 5px; color: {dim}; font-size: 11px; padding: 4px 10px;
}}
#exportBtn:hover {{ background-color: {surf}; border-color: {brd2}; color: {txt}; }}
#logToggleTopBtn {{
    background-color: transparent; border: 1px solid {brd};
    border-radius: 5px; color: {dim}; font-size: 11px; padding: 4px 10px;
}}
#logToggleTopBtn:hover {{ background: {surf}; border-color: {brd2}; color: {txt}; }}
#logToggleTopBtn[active="true"] {{
    background: {abg}; border-color: {abd}; color: {acc};
}}

/* ── Chat area ───────────────────────── */
#chatArea {{ background-color: {bg}; }}
QTextBrowser {{
    background-color: {bg}; border: none;
    color: {txt}; padding: 0;
    selection-background-color: {surf};
}}

/* ── Input area ──────────────────────── */
#inputArea {{
    background-color: {bg2};
    border-top: 1px solid {brd};
}}
#messageInput {{
    background-color: {surf}; border: 1px solid {brd2};
    border-radius: 10px; padding: 10px 14px;
    color: {txt}; font-size: 13px; line-height: 1.5;
    font-family: "Roboto", sans-serif;
}}
#messageInput:focus {{ border-color: {acc}; }}

/* ── Buttons ─────────────────────────── */
QPushButton {{
    background-color: {surf}; color: {dim};
    border: 1px solid {brd2}; border-radius: 7px;
    padding: 7px 14px; font-size: 12px;
}}
QPushButton:hover {{ background-color: {bg3}; border-color: {brd}; color: {txt}; }}
QPushButton:pressed {{ background-color: {bg2}; }}

#sendBtn {{
    background-color: {acc}; color: {bg};
    border: none; border-radius: 10px;
    font-weight: 800; font-size: 16px; padding: 0;
}}
#sendBtn:hover {{ background-color: {txt}; }}
#sendBtn:pressed {{ background-color: {adim}; }}

#attachBtn {{
    background-color: transparent; color: {mute};
    border: 1px solid {brd}; border-radius: 10px;
    font-size: 17px; padding: 0;
}}
#attachBtn:hover {{ background-color: {surf}; color: {dim}; border-color: {brd2}; }}

/* ── Status ──────────────────────────── */
#statusLabel {{ color: {dim}; font-size: 11px; padding: 1px 0; }}
#agentStatusBar {{
    background: {bg2}; border-top: 1px solid {brd};
    padding: 0 16px; min-height: 26px; max-height: 26px;
}}
#agentStatusLabel {{
    color: {dim}; font-size: 11px; background: transparent;
    letter-spacing: 0.5px;
    font-family: "JetBrains Mono", monospace;
}}

/* ── Scrollbar ───────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 4px; margin: 2px 0; }}
QScrollBar::handle:vertical {{ background: {brd2}; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {brd}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}

/* ── ComboBox ────────────────────────── */
QComboBox {{
    background-color: {surf}; border: 1px solid {brd};
    border-radius: 6px; padding: 5px 10px; color: {txt}; font-size: 12px;
}}
QComboBox:hover {{ border-color: {acc}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {surf}; border: 1px solid {brd2};
    color: {txt}; selection-background-color: {bg3}; outline: none;
}}

/* ── Labels ──────────────────────────── */
QLabel {{ color: {txt}; background: transparent; }}
QCheckBox {{ color: {txt}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px; border: 1px solid {brd2};
    border-radius: 3px; background: {surf};
}}
QCheckBox::indicator:checked {{ background: {acc}; border-color: {acc}; }}

/* ── Menu ────────────────────────────── */
QMenu {{
    background-color: {surf}; border: 1px solid {brd2};
    border-radius: 8px; padding: 4px;
}}
QMenu::item {{ padding: 7px 16px; border-radius: 5px; color: {txt}; font-size: 12px; }}
QMenu::item:selected {{ background-color: {bg3}; color: {txt}; }}
QMenu::separator {{ height: 1px; background: {brd}; margin: 4px 8px; }}

/* ── Splitter ────────────────────────── */
QSplitter::handle {{ background: {brd}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
QSplitter::handle:horizontal:hover {{ background: {adim}; }}

/* ── LineEdit ────────────────────────── */
QLineEdit {{
    background-color: {surf}; border: 1px solid {brd};
    border-radius: 6px; padding: 7px 12px; color: {txt}; font-size: 12px;
    font-family: "Roboto", sans-serif;
}}
QLineEdit:focus {{ border-color: {acc}; }}

/* ── Tab ─────────────────────────────── */
QTabWidget::pane {{ border: 1px solid {brd}; background: {bg}; }}
QTabBar::tab {{
    background: transparent; color: {mute};
    padding: 8px 16px; border-bottom: 2px solid transparent; font-size: 12px;
}}
QTabBar::tab:selected {{ color: {txt}; border-bottom: 2px solid {acc}; }}
QTabBar::tab:hover:!selected {{ color: {dim}; }}

/* ── Right log panel ─────────────────── */
#logPanel {{ background-color: {bg3}; border-left: 1px solid {brd}; }}
#logPanelHeader {{
    background: {bg2}; border-bottom: 1px solid {brd};
    min-height: 38px; max-height: 38px;
}}
#logPanelTitle {{
    color: {mute}; font-size: 10px; font-weight: 600;
    letter-spacing: 1.2px; background: transparent;
    font-family: "JetBrains Mono", monospace;
}}
#logCloseBtn {{
    background: transparent; border: 1px solid {brd};
    border-radius: 4px; color: {mute}; font-size: 12px; padding: 1px 7px;
}}
#logCloseBtn:hover {{ background: {surf}; color: {dim}; border-color: {brd2}; }}

/* ── Dialog ──────────────────────────── */
QDialog {{ background: {bg2}; }}
QDialog QLabel {{ color: {txt}; font-size: 12px; }}
QTextEdit {{
    background-color: {surf}; border: 1px solid {brd};
    border-radius: 5px; color: {txt}; font-size: 12px; padding: 4px;
}}

/* ── Quick panel ─────────────────────── */
#quickPanel {{
    background: {bg2}; border-top: 1px solid {brd};
}}
"""


def apply_theme(app, db):
    """Read theme/accent/animations from DB and apply to the QApplication."""
    theme   = db.get_setting("theme", "dark")
    accent  = db.get_setting("accent", "mono")
    anims   = db.get_setting("animations", "1") == "1"

    colors = _LIGHT_BASE if theme == "light" else _DARK_BASE
    a      = _ACCENTS.get(accent, _ACCENTS["mono"])

    stylesheet = _build_stylesheet(colors, a, anims)
    app.setStyleSheet(stylesheet)

    # Store animations flag globally for animated widgets to check
    import builtins
    builtins._quadrogent_animations = anims
