"""
chat_widget.py — Quadrogent redesigned chat UI.

KEY CONSTRAINT: QTextBrowser uses Qt's limited HTML engine.
- NO display:flex / justify-content / gap  → use <table> layout
- CSS <style> classes are unreliable        → use inline style=""
- All message bubbles built as inline-styled tables
"""
import html
import json
import os
import re
import shutil
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QLabel, QFileDialog,
    QSizePolicy, QMenu, QComboBox, QApplication,
    QDialog, QListWidget, QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import QGraphicsOpacityEffect
from PyQt5.QtGui import QDesktopServices, QKeyEvent

from src.ui.styles import MESSAGE_CSS as _MESSAGE_CSS_DARK
from src.ui.icon_helper import apply_icon, get_icon


def _message_css() -> str:
    """Return MESSAGE_CSS tuned to current theme."""
    import builtins
    if getattr(builtins, "_quadrogent_theme", "dark") == "light":
        return """
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #f5f5f5;
    color: #222222;
    font-family: "Roboto", "Inter", system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.7;
    padding: 16px 0 12px 0;
}
table { border-collapse: collapse; }
a { color: #1a5fa8; text-decoration: none; }
a:hover { text-decoration: underline; }
code {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12.5px; color: #7c6020;
    background: #e4e4e4; border: 1px solid #cccccc;
    padding: 2px 5px; border-radius: 4px;
}
pre {
    background: #eeeeee; border: 1px solid #cccccc;
    padding: 12px 14px; border-radius: 7px;
    font-size: 12.5px; white-space: pre-wrap; word-wrap: break-word;
    font-family: "JetBrains Mono", "Consolas", monospace; color: #334155;
    margin: 8px 0;
}
pre code { background: none; border: none; padding: 0; }
h1,h2,h3,h4,h5,h6 { color: #111111; font-weight: 600; margin: 14px 0 5px 0; }
h1 { font-size: 18px; } h2 { font-size: 16px; } h3 { font-size: 14px; }
strong { color: #111111; font-weight: 600; }
em { font-style: italic; color: #555555; }
ul, ol { padding-left: 20px; margin: 5px 0; }
li { margin: 3px 0; color: #333333; }
hr { border: none; border-top: 1px solid #cccccc; margin: 10px 0; }
blockquote {
    border-left: 2px solid #aaaaaa; padding: 4px 12px;
    color: #666666; margin: 8px 0; font-style: italic;
}
</style>
"""
    return _MESSAGE_CSS_DARK
from PyQt5.QtCore import QSize as _QSize


# ─────────────────────────────────────────────────────────────────────────────
#  HTML message builders — all inline styles, table-based layout
# ─────────────────────────────────────────────────────────────────────────────

# Palette constants
# Theme-aware palettes for chat HTML rendering
_DARK_PALETTE = {
    "user_bg":       "#181818",
    "user_border":   "#2a2a2a",
    "user_text":     "#ededed",
    "asst_text":     "#c4c4c4",
    "body_bg":       "#0a0a0a",
    "body_text":     "#c4c4c4",
    "avatar_bg":     "#0e0e0e",
    "avatar_border": "#1e1e1e",
    "avatar_text":   "#303030",
    "tool_name":     "#444444",
    "tool_ok":       "#2a5530",
    "tool_err":      "#632020",
    "tool_body_bg":  "#080808",
    "tool_body_bd":  "#131313",
    "tool_body_txt": "#555555",
    "ec_ok_bg":      "#0a160b",
    "ec_ok_bd":      "#143418",
    "ec_ok_txt":     "#27502c",
    "ec_err_bg":     "#140707",
    "ec_err_bd":     "#370f0f",
    "ec_err_txt":    "#621e1e",
    "error_text":    "#c84040",
    "error_border":  "#9a2e2e",
    "error_bg":      "#0c0505",
    "code_bg":       "#0b0b0b",
    "code_bd":       "#161616",
    "code_lang_bg":  "#0e0e0e",
    "code_lang_txt": "#555555",
    "code_txt":      "#9ca3af",
    "inline_code_bg": "#141414",
    "inline_code_bd": "#1e1e1e",
    "inline_code_txt": "#b5a46a",
    "fc_bg":         "#0c0c0c",
    "fc_bd":         "#181818",
    "fc_name":       "#c4c4c4",
    "fc_meta":       "#2c2c2c",
    "fc_link":       "#5788b8",
    "chip_bg":       "#111111",
    "chip_bd":       "#1e1e1e",
    "chip_name":     "#b8b8b8",
    "chip_ext":      "#343434",
    "cursor":        "#363636",
    "dot1":          "#333333",
    "dot_active":    "#999999",
}

_LIGHT_PALETTE = {
    "user_bg":       "#e8e8e8",
    "user_border":   "#cccccc",
    "user_text":     "#111111",
    "asst_text":     "#222222",
    "body_bg":       "#f5f5f5",
    "body_text":     "#222222",
    "avatar_bg":     "#e0e0e0",
    "avatar_border": "#bbbbbb",
    "avatar_text":   "#666666",
    "tool_name":     "#555555",
    "tool_ok":       "#1a6b28",
    "tool_err":      "#8b2020",
    "tool_body_bg":  "#eeeeee",
    "tool_body_bd":  "#cccccc",
    "tool_body_txt": "#444444",
    "ec_ok_bg":      "#d4f0d8",
    "ec_ok_bd":      "#88c890",
    "ec_ok_txt":     "#1a5c22",
    "ec_err_bg":     "#fce8e8",
    "ec_err_bd":     "#e08080",
    "ec_err_txt":    "#8b2020",
    "error_text":    "#cc2020",
    "error_border":  "#cc6060",
    "error_bg":      "#fff0f0",
    "code_bg":       "#eeeeee",
    "code_bd":       "#cccccc",
    "code_lang_bg":  "#e0e0e0",
    "code_lang_txt": "#888888",
    "code_txt":      "#334155",
    "inline_code_bg": "#e4e4e4",
    "inline_code_bd": "#cccccc",
    "inline_code_txt": "#7c6020",
    "fc_bg":         "#f0f0f0",
    "fc_bd":         "#cccccc",
    "fc_name":       "#222222",
    "fc_meta":       "#666666",
    "fc_link":       "#1a5fa8",
    "chip_bg":       "#e8e8e8",
    "chip_bd":       "#cccccc",
    "chip_name":     "#333333",
    "chip_ext":      "#888888",
    "cursor":        "#aaaaaa",
    "dot1":          "#cccccc",
    "dot_active":    "#555555",
}


def _get_palette() -> dict:
    """Return current theme palette."""
    try:
        import builtins
        if getattr(builtins, "_quadrogent_theme", "dark") == "light":
            return _LIGHT_PALETTE
    except Exception:
        pass
    return _DARK_PALETTE


# C is now a dynamic proxy — always reads from current theme
class _Palette:
    def __getitem__(self, key):
        return _get_palette()[key]
    def get(self, key, default=None):
        return _get_palette().get(key, default)


C = _Palette()

FONT = '"Inter","Segoe UI",system-ui,sans-serif'
MONO = '"JetBrains Mono","Consolas",monospace'

# User avatar path — set at runtime by MainWindow
_USER_AVATAR_PATH: str = ""

def set_user_avatar(path: str):
    global _USER_AVATAR_PATH
    _USER_AVATAR_PATH = path


_LOGO_PATH: str = ""


def _init_logo_path():
    global _LOGO_PATH
    try:
        from src.utils.static_paths import image as _img
        p = _img("logo.png")
    except Exception:
        here = os.path.dirname(os.path.abspath(__file__))
        p = os.path.normpath(os.path.join(here, "..", "..", "static", "images", "logo.png"))
    if os.path.exists(p):
        _LOGO_PATH = p


_init_logo_path()


def _avatar():
    if _LOGO_PATH:
        url = "file:///" + _LOGO_PATH.replace("\\", "/").lstrip("/")
        return (
            f'<div style="width:26px;height:26px;min-width:26px;'
            f'border-radius:6px;overflow:hidden;margin-top:2px;">'
            f'<img src="{url}" width="26" height="26" '
            f'style="border-radius:6px;object-fit:cover;display:block;"/>'
            f'</div>'
        )
    return (
        f'<div style="width:26px;height:26px;min-width:26px;'
        f'background:{C["avatar_bg"]};border:1px solid {C["avatar_border"]};'
        f'border-radius:6px;text-align:center;font-family:{MONO};'
        f'font-size:11px;color:{C["avatar_text"]};line-height:26px;'
        f'margin-top:2px;">◈</div>'
    )


def _user_avatar_html() -> str:
    """User avatar: image if path set, else generic icon."""
    if _USER_AVATAR_PATH and os.path.exists(_USER_AVATAR_PATH):
        import urllib.request as _ur
        url = "file:///" + _USER_AVATAR_PATH.replace("\\", "/").lstrip("/")
        return (
            f'<div style="width:26px;height:26px;min-width:26px;'
            f'border-radius:6px;overflow:hidden;margin-top:2px;">'
            f'<img src="{url}" width="26" height="26" '
            f'style="border-radius:6px;object-fit:cover;"/>'
            f'</div>'
        )
    return (
        f'<div style="width:26px;height:26px;min-width:26px;'
        f'background:{C["avatar_bg"]};border:1px solid {C["avatar_border"]};'
        f'border-radius:6px;text-align:center;font-family:{MONO};'
        f'font-size:11px;color:{C["avatar_text"]};line-height:26px;'
        f'margin-top:2px;">👤</div>'
    )


def _user_bubble(content_html: str) -> str:
    """Right-aligned user bubble with avatar via table."""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:3px 0;">'
        f'<tr>'
        f'<td width="25%"></td>'
        f'<td align="right" valign="top" style="padding-top:2px;">'
        f'<div style="display:inline-block;background:{C["user_bg"]};'
        f'border:1px solid {C["user_border"]};'
        f'border-radius:16px 16px 3px 16px;'
        f'padding:10px 14px;color:{C["user_text"]};'
        f'font-family:{FONT};font-size:14px;line-height:1.62;'
        f'word-wrap:break-word;max-width:100%;">'
        f'{content_html}</div>'
        f'</td>'
        f'<td width="8" valign="top" style="padding-top:2px;">{_user_avatar_html()}</td>'
        f'<td width="10"></td>'
        f'</tr>'
        f'</table>'
    )


def _asst_bubble(content_html: str) -> str:
    """Left-aligned assistant bubble with avatar via table."""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:3px 0;">'
        f'<tr>'
        f'<td width="18"></td>'
        f'<td width="36" valign="top">{_avatar()}</td>'
        f'<td valign="top" style="padding-top:3px;">'
        f'<div style="color:{C["asst_text"]};font-family:{FONT};'
        f'font-size:14px;line-height:1.7;word-wrap:break-word;">'
        f'{content_html}</div>'
        f'</td>'
        f'<td width="25%"></td>'
        f'</tr>'
        f'</table>'
    )


def _tool_row(tool_name: str, exit_code, body: str) -> str:
    if exit_code is None:
        name_color = C["tool_name"]
    elif exit_code == 0:
        name_color = C["tool_ok"]
    else:
        name_color = C["tool_err"]

    badge = ""
    if exit_code is not None:
        if exit_code == 0:
            badge = (
                f' <span style="font-size:9px;font-family:{MONO};'
                f'color:{C["ec_ok_txt"]};background:{C["ec_ok_bg"]};'
                f'border:1px solid {C["ec_ok_bd"]};border-radius:3px;'
                f'padding:0 5px;">exit 0</span>'
            )
        else:
            badge = (
                f' <span style="font-size:9px;font-family:{MONO};'
                f'color:{C["ec_err_txt"]};background:{C["ec_err_bg"]};'
                f'border:1px solid {C["ec_err_bd"]};border-radius:3px;'
                f'padding:0 5px;">exit {exit_code}</span>'
            )

    escaped_body = html.escape(body) if body else "(нет вывода)"

    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:2px 0;">'
        f'<tr>'
        f'<td width="62"></td>'
        f'<td>'
        f'<div style="font-size:9.5px;text-transform:uppercase;letter-spacing:1.4px;'
        f'font-family:{MONO};color:{name_color};margin-bottom:3px;">'
        f'{html.escape(str(tool_name or "tool"))}{badge}</div>'
        f'<div style="background:{C["tool_body_bg"]};border:1px solid {C["tool_body_bd"]};'
        f'border-radius:5px;padding:7px 12px;font-family:{MONO};font-size:11.5px;'
        f'color:{C["tool_body_txt"]};white-space:pre-wrap;word-wrap:break-word;'
        f'max-width:94%;line-height:1.5;">'
        f'{escaped_body}</div>'
        f'</td>'
        f'<td width="25%"></td>'
        f'</tr>'
        f'</table>'
    )


def _error_row(content_html: str) -> str:
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:3px 0;">'
        f'<tr>'
        f'<td width="18"></td>'
        f'<td>'
        f'<div style="color:{C["error_text"]};background:{C["error_bg"]};'
        f'border-left:2px solid {C["error_border"]};border-radius:0 6px 6px 0;'
        f'padding:8px 14px;font-size:13px;line-height:1.6;">'
        f'{content_html}</div>'
        f'</td>'
        f'<td width="18"></td>'
        f'</tr>'
        f'</table>'
    )


_BRAIN_COLORS = ["#333333", "#888888", "#dddddd", "#888888"]


def _brain_avatar(frame: int = 0) -> str:
    """Pulsing academic-cap icon during thinking."""
    color = _BRAIN_COLORS[frame % len(_BRAIN_COLORS)]
    try:
        from src.utils.static_paths import icon as _icon_path
        icon_path = _icon_path("academic-cap")
        if not __import__("os").path.exists(icon_path):
            icon_path = _icon_path("cpu-chip")
    except Exception:
        icon_path = ""
    if os.path.exists(icon_path):
        svg = open(icon_path).read().replace("currentColor", color)
        # Encode as data URI for QTextBrowser
        import base64
        b64 = base64.b64encode(svg.encode()).decode()
        return (
            f'<div style="width:26px;height:26px;min-width:26px;'
            f'background:{C["avatar_bg"]};border:1px solid {C["avatar_border"]};'
            f'border-radius:6px;text-align:center;line-height:26px;margin-top:2px;">'
            f'<img src="data:image/svg+xml;base64,{b64}" width="16" height="16" '
            f'style="margin-top:5px;vertical-align:middle;"/>'
            f'</div>'
        )
    return _avatar()


def _thinking_row(frame: int = 0) -> str:
    """Pulsing academic-cap animation during thinking."""
    color = _BRAIN_COLORS[frame % len(_BRAIN_COLORS)]
    # Build 3 animated dots that cycle
    dot_colors = ["#555", "#999", "#ddd"]
    dots = "".join(
        f'<span style="color:{dot_colors[(frame + i) % 3]};font-size:20px;'
        f'letter-spacing:1px;margin-right:2px;">&#8226;</span>'
        for i in range(3)
    )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:6px 0;">'
        f'<tr>'
        f'<td width="18"></td>'
        f'<td width="36" valign="middle">{_brain_avatar(frame)}</td>'
        f'<td valign="middle" style="padding:4px 0 0 6px;">{dots}</td>'
        f'</tr>'
        f'</table>'
    )


def _file_card_row(icon: str, safe_name: str, safe_meta: str, file_url: str) -> str:
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0;">'
        f'<tr>'
        f'<td width="62"></td>'
        f'<td>'
        f'<table cellpadding="0" cellspacing="0" style="background:{C["fc_bg"]};'
        f'border:1px solid {C["fc_bd"]};border-radius:8px;max-width:340px;">'
        f'<tr>'
        f'<td style="padding:10px 9px 10px 12px;font-size:20px;">{icon}</td>'
        f'<td style="padding:10px 7px;">'
        f'<div style="color:{C["fc_name"]};font-size:12.5px;font-weight:500;">{safe_name}</div>'
        f'<div style="color:{C["fc_meta"]};font-size:10.5px;text-transform:uppercase;'
        f'letter-spacing:0.4px;font-family:{MONO};margin-top:2px;">{safe_meta}</div>'
        f'</td>'
        f'<td style="padding:10px 12px 10px 7px;" align="right">'
        f'<a href="{file_url}" style="color:{C["fc_link"]};font-size:12px;'
        f'text-decoration:none;white-space:nowrap;">⬇ Скачать</a>'
        f'</td>'
        f'</tr>'
        f'</table>'
        f'</td>'
        f'<td width="18"></td>'
        f'</tr>'
        f'</table>'
    )


# ─────────────────────────────────────────────────────────────────────────────
#  LaTeX + Markdown rendering
# ─────────────────────────────────────────────────────────────────────────────

def _latex_to_html(expr: str) -> str:
    import re as _re
    GREEK = {
        r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
        r'\epsilon': 'ε', r'\theta': 'θ', r'\lambda': 'λ', r'\mu': 'μ',
        r'\pi': 'π', r'\sigma': 'σ', r'\phi': 'φ', r'\omega': 'ω',
        r'\Sigma': 'Σ', r'\Delta': 'Δ', r'\Omega': 'Ω',
    }
    SYMBOLS = {
        r'\times': '×', r'\cdot': '·', r'\leq': '≤', r'\geq': '≥',
        r'\neq': '≠', r'\approx': '≈', r'\infty': '∞', r'\rightarrow': '→',
        r'\leftarrow': '←', r'\in': '∈', r'\notin': '∉', r'\to': '→',
    }
    s = expr.strip()
    def _frac(m):
        return f'<sup>{_latex_to_html(m.group(1))}</sup>&#8260;<sub>{_latex_to_html(m.group(2))}</sub>'
    s = _re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', _frac, s)
    s = _re.sub(r'\^\{([^{}]*)\}', lambda m: f'<sup>{m.group(1)}</sup>', s)
    s = _re.sub(r'_\{([^{}]*)\}', lambda m: f'<sub>{m.group(1)}</sub>', s)
    for tex, uni in {**GREEK, **SYMBOLS}.items():
        s = s.replace(tex, uni)
    s = _re.sub(r'\\([A-Za-z]+)', r'\1', s)
    return s


def _render_latex(text: str) -> str:
    import re as _re
    cc = C["inline_code_bg"]
    cb = C["inline_code_bd"]
    ct = C["inline_code_txt"]
    style = f'display:inline-block;background:{cc};border:1px solid {cb};padding:3px 10px;border-radius:5px;font-family:{MONO};font-size:13px;color:{ct};margin:6px 0;'
    def _block(m):
        return f'<div style="{style}">{_latex_to_html(m.group(1))}</div>'
    def _inline(m):
        return f'<code style="background:{cc};border:1px solid {cb};color:{ct};font-family:{MONO};font-size:12.5px;padding:1px 4px;border-radius:3px;">{_latex_to_html(m.group(1))}</code>'
    text = _re.sub(r'\\\[(.+?)\\\]', _block, text, flags=_re.DOTALL)
    text = _re.sub(r'\\\((.+?)\\\)', _inline, text, flags=_re.DOTALL)
    text = _re.sub(r'\$\$(.+?)\$\$', _block, text, flags=_re.DOTALL)
    text = _re.sub(r'(?<!\$)\$([^\$\n]+?)\$(?!\$)', _inline, text)
    return text


def _md_to_html(text: str) -> str:
    """Convert markdown to Qt-compatible HTML with inline styles."""
    cc = C["code_bg"]; cb_c = C["code_bd"]
    ilc_bg = C["inline_code_bg"]; ilc_bd = C["inline_code_bd"]; ilc_t = C["inline_code_txt"]
    code_lang_bg = C["code_lang_bg"]; code_lang_t = C["code_lang_txt"]

    def _fence(m):
        lang = html.escape(m.group(1).strip())
        code = html.escape(m.group(2))
        lang_label = (
            f'<div style="background:{code_lang_bg};color:{code_lang_t};'
            f'font-size:9.5px;padding:4px 12px;letter-spacing:0.8px;'
            f'font-family:{MONO};text-transform:uppercase;'
            f'border-bottom:1px solid #121212;">{lang}</div>'
        ) if lang else ""
        return (
            f'<div style="margin:10px 0;border-radius:7px;overflow:hidden;'
            f'border:1px solid {cb_c};background:{cc};">'
            f'{lang_label}'
            f'<pre style="background:{cc};padding:12px 14px;margin:0;'
            f'font-family:{MONO};font-size:12.5px;color:{C["code_txt"]};'
            f'white-space:pre-wrap;word-wrap:break-word;">{code}</pre>'
            f'</div>'
        )

    text = _render_latex(text)

    # Extract code blocks BEFORE any html.escape, replace with unique placeholders.
    # This avoids the broken nested-div regex split (the old split stopped at the
    # first </div> inside the lang-label, leaving <pre>…</pre> exposed to escape).
    _PLACEHOLDER = "\x00CODE{}\x00"
    code_blocks: list[str] = []

    def _fence_and_stash(m):
        html_block = _fence(m)
        idx = len(code_blocks)
        code_blocks.append(html_block)
        return _PLACEHOLDER.format(idx)

    text = re.sub(r"```(\w*)\n(.*?)```", _fence_and_stash, text, flags=re.DOTALL)

    # Now split on placeholders — safe because they contain no HTML
    parts = re.split(r'(\x00CODE\d+\x00)', text)
    result = []
    for part in parts:
        if part.startswith("\x00CODE") and part.endswith("\x00"):
            # Restore the pre-rendered code block as-is
            try:
                idx = int(part[5:-1])
                result.append(code_blocks[idx])
            except (ValueError, IndexError):
                result.append(part)
            continue
        # If the part already contains HTML tags (model output), pass through
        _HTML_DETECT = re.compile(
            r'<\s*/?\s*(?:code|div|span|pre|a\b|strong|em|ul|ol|li|p\b|br\b|h[1-6]\b|table|tr|td|th)',
            re.IGNORECASE
        )
        if _HTML_DETECT.search(part):
            result.append(part)
            continue
        p = html.escape(part)
        # Inline code
        p = re.sub(
            r"`([^`\n]+)`",
            f'<code style="background:{ilc_bg};border:1px solid {ilc_bd};'
            f'color:{ilc_t};font-family:{MONO};font-size:12.5px;'
            f'padding:2px 5px;border-radius:4px;">\\1</code>',
            p
        )
        p = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#ebebeb;font-weight:600;">\1</strong>', p)
        p = re.sub(r"__(.+?)__",     r'<strong style="color:#ebebeb;font-weight:600;">\1</strong>', p)
        p = re.sub(r"\*([^*\n]+)\*", r'<em style="color:#9a9a9a;font-style:italic;">\1</em>', p)
        p = re.sub(r"_([^_\n]+)_",   r'<em style="color:#9a9a9a;font-style:italic;">\1</em>', p)
        p = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:#6a9fd8;">\1</a>', p)
        p = re.sub(r"(?m)^-{3,}\s*$", '<hr style="border:none;border-top:1px solid #1c1c1c;margin:10px 0;">', p)
        p = re.sub(r"(?m)^#{6}\s+(.+)$", r'<h6 style="color:#e6e6e6;font-size:13px;font-weight:600;margin:12px 0 4px 0;">\1</h6>', p)
        p = re.sub(r"(?m)^#{5}\s+(.+)$", r'<h5 style="color:#e6e6e6;font-size:13px;font-weight:600;margin:12px 0 4px 0;">\1</h5>', p)
        p = re.sub(r"(?m)^#{4}\s+(.+)$", r'<h4 style="color:#e6e6e6;font-size:13px;font-weight:600;margin:12px 0 4px 0;">\1</h4>', p)
        p = re.sub(r"(?m)^#{3}\s+(.+)$", r'<h3 style="color:#e6e6e6;font-size:14px;font-weight:600;margin:14px 0 5px 0;">\1</h3>', p)
        p = re.sub(r"(?m)^#{2}\s+(.+)$", r'<h2 style="color:#e6e6e6;font-size:16px;font-weight:600;margin:14px 0 5px 0;">\1</h2>', p)
        p = re.sub(r"(?m)^#\s+(.+)$",    r'<h1 style="color:#e6e6e6;font-size:18px;font-weight:700;margin:16px 0 6px 0;">\1</h1>', p)
        p = re.sub(r"(?m)^&gt;\s*(.+)$",
            f'<div style="border-left:2px solid #242424;padding:4px 12px;'
            f'color:#606060;margin:8px 0;font-style:italic;">\\1</div>', p)
        p = re.sub(r"(?m)^[\*\-]\s+(.+)$", r"<li>\1</li>", p)
        p = re.sub(r"(?m)^\d+\.\s+(.+)$",  r"<li>\1</li>", p)
        p = re.sub(
            r"(<li>.*?</li>(\n|$))+",
            lambda m: f'<ul style="padding-left:20px;margin:5px 0;">' + m.group(0) + "</ul>",
            p, flags=re.DOTALL,
        )
        p = p.replace("\n", "<br>")
        result.append(p)
    return "".join(result)


# ─────────────────────────────────────────────────────────────────────────────
#  File helpers
# ─────────────────────────────────────────────────────────────────────────────

# Maps extension to heroicon name
_EXT_ICON_MAP = {
    "py": "command-line", "js": "command-line", "ts": "command-line",
    "sh": "command-line", "bat": "command-line",
    "html": "globe-alt", "css": "paint-brush",
    "json": "document-text", "xml": "document-text",
    "yaml": "document-text", "yml": "document-text",
    "pdf": "document", "doc": "document", "docx": "document",
    "xls": "table-cells", "xlsx": "table-cells", "csv": "table-cells",
    "txt": "document-text", "md": "document-text",
    "png": "photo", "jpg": "photo", "jpeg": "photo",
    "gif": "photo", "svg": "photo", "webp": "photo",
    "zip": "archive-box", "tar": "archive-box", "gz": "archive-box",
    "mp3": "musical-note", "wav": "musical-note",
    "mp4": "film", "mov": "film",
    "exe": "cpu-chip",
}


def _file_icon_svg(icon_name: str, color: str = "#666666", size: int = 20) -> str:
    """Return an inline SVG <img> tag for use in Qt HTML."""
    try:
        from src.utils.static_paths import icon as _icon_path
        import base64, os
        path = _icon_path(icon_name)
        if not os.path.exists(path):
            path = _icon_path("document")
        svg = open(path).read().replace("currentColor", color)
        b64 = base64.b64encode(svg.encode()).decode()
        return f'<img src="data:image/svg+xml;base64,{b64}" width="{size}" height="{size}"/>'
    except Exception:
        return "&#128196;"  # fallback: document char


def _file_icon(fn: str) -> str:
    ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
    icon_name = _EXT_ICON_MAP.get(ext, "document")
    return _file_icon_svg(icon_name, "#666666", 20)
def _file_size_str(path):
    try:
        s = os.path.getsize(path)
        if s < 1024: return f"{s} B"
        if s < 1_048_576: return f"{s // 1024} KB"
        return f"{s // 1_048_576} MB"
    except OSError: return ""


# ─────────────────────────────────────────────────────────────────────────────
#  Widgets
# ─────────────────────────────────────────────────────────────────────────────

class MessageInput(QTextEdit):
    submitted   = pyqtSignal()
    file_pasted = pyqtSignal(str)   # path of pasted file

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(False)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
        elif event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime.hasUrls():
                local = [u.toLocalFile() for u in mime.urls()
                         if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
                if local:
                    self.file_pasted.emit(local[0])
                    return
            # Fall through to normal paste
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


class FileChip(QWidget):
    removed = pyqtSignal()
    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 4, 7, 4)
        layout.setSpacing(7)
        icon = QLabel(_file_icon(filename))
        icon.setStyleSheet("background:transparent;font-size:14px;")
        layout.addWidget(icon)
        name = QLabel(filename)
        name.setStyleSheet("background:transparent;color:#b0b0b0;font-size:12px;")
        name.setMaximumWidth(260)
        layout.addWidget(name, 1)
        rm = QPushButton("✕")
        rm.setFixedSize(18, 18)
        rm.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#484848;font-size:11px;}"
            "QPushButton:hover{color:#999999;}"
        )
        rm.clicked.connect(self.removed.emit)
        layout.addWidget(rm)
        self.setStyleSheet(
            "FileChip{background:#111111;border:1px solid #222222;border-radius:7px;}"
        )
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class ModelPickerDialog(QDialog):
    """Modal model picker with live search."""
    model_selected = pyqtSignal(str)

    def __init__(self, models: list, current: str, parent=None, vision_ids: set | None = None):
        super().__init__(parent)
        self._vision_ids = vision_ids or set()
        self.setWindowTitle("Выбор модели")
        self.setMinimumSize(500, 400)
        # No hardcoded stylesheet - inherit from QApplication theme
        pass
        self._all = models
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        hdr = QLabel("Выберите модель:")
        layout.addWidget(hdr)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск…")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)
        self._list = QListWidget()
        self._fill(models, current)
        self._list.itemDoubleClicked.connect(self._pick)
        layout.addWidget(self._list, 1)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Выбрать")
        ok.setDefault(True)
        ok.clicked.connect(self._pick)
        row.addWidget(cancel)
        row.addWidget(ok)
        layout.addLayout(row)

    def _fill(self, models, current=""):
        self._list.clear()
        for m in models:
            from PyQt5.QtWidgets import QListWidgetItem
            vision_ids = getattr(self, "_vision_ids", set())
            label = ("👁 " if m in vision_ids else "   ") + m
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, m)  # store actual model id
            self._list.addItem(item)
            if m == current:
                self._list.setCurrentItem(item)

    def _filter(self, text):
        cur = self._list.currentItem()
        self._fill([m for m in self._all if text.lower() in m.lower()],
                   cur.text() if cur else "")

    def _pick(self):
        item = self._list.currentItem()
        if item:
            # UserRole has clean id; fall back to stripping prefix from text
            mid = item.data(Qt.UserRole) or item.text().lstrip("👁 ").strip()
            self.model_selected.emit(mid)
            self.accept()


class ModelSelector(QWidget):
    model_changed   = pyqtSignal(str)
    refresh_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded: list[str] = []
        self._seen:   list[str] = []
        self._current: str = ""
        self._updating = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        lbl = QLabel("Модель:")
        lbl.setObjectName("modelLabel")
        layout.addWidget(lbl)
        self._btn = QPushButton("—")
        self._btn.setObjectName("modelCombo")
        self._btn.setFixedHeight(28)
        self._btn.setMinimumWidth(200)
        self._btn.setStyleSheet(
            "QPushButton{background:transparent;border:1px solid #1c1c1c;"
            "border-radius:5px;padding:3px 8px;color:#c0c0c0;font-size:11px;"
            "text-align:left;}"
            "QPushButton:hover{border-color:#2c2c2c;color:#ffffff;}"
        )
        self._btn.clicked.connect(self._open_picker)
        layout.addWidget(self._btn)
        # Hidden compatibility widgets
        self.combo = QComboBox()
        self.combo.hide()
        self.refresh_btn = QPushButton()
        self.refresh_btn.hide()
        self.refresh_btn.clicked.connect(self.refresh_clicked.emit)

    def _open_picker(self):
        all_m = self._seen if self._seen else self._loaded
        vision_ids = getattr(self, "_vision_ids", set())
        dlg = ModelPickerDialog(all_m, self._current, self, vision_ids=vision_ids)
        dlg.model_selected.connect(self._select)
        dlg.exec_()

    def _select(self, model_id: str):
        if model_id != self._current:
            self._current = model_id
            self._update_btn_label()
            self.model_changed.emit(model_id)

    def set_models(self, loaded: list, seen: list, vision_ids: set | None = None):
        self._loaded = loaded
        self._seen = seen
        self._vision_ids = vision_ids or set()
        # Refresh label if current model vision status changed
        self._update_btn_label()

    def _update_btn_label(self):
        mid = self._current
        if not mid:
            self._btn.setText("—")
            return
        is_vision = mid in getattr(self, "_vision_ids", set())
        icon_str = " 👁" if is_vision else ""
        self._btn.setText(mid + icon_str)
        self._btn.setToolTip(
            f"Модель: {mid}\n{'✓ Поддерживает изображения' if is_vision else '✗ Изображения не поддерживаются'}"
        )

    def current_model(self):
        return self._current

    def set_current_model(self, model_id: str):
        self._current = model_id
        self._btn.setText(model_id if model_id else "—")

    def _on_changed(self, idx):
        pass  # handled by _select




# ─────────────────────────────────────────────────────────────────────────────
#  QuickSettingsPanel — slides up from the input area
# ─────────────────────────────────────────────────────────────────────────────

class QuickSettingsPanel(QWidget):
    """Slide-up panel for per-chat settings."""
    persistent_toggled = pyqtSignal(bool)
    web_search_toggled = pyqtSignal(bool)
    think_mode_toggled = pyqtSignal(bool)
    mode_changed       = pyqtSignal(str)
    attach_requested   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("quickPanel")
        self.setMaximumHeight(0)  # hidden by default
        self._is_open = False
        self._anim = None

        self.setStyleSheet(
            "#quickPanel{"
            "background:#080808;border-top:1px solid #181818;"
            "}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(10)

        # Row 1: Mode buttons
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        lbl1 = QLabel("Режим:")
        lbl1.setStyleSheet("color:#404040;font-size:11px;min-width:52px;")
        row1.addWidget(lbl1)
        self._mode_btns = {}
        for mode, label in (("auto", "Auto"), ("work", "Work"), ("talk", "Talk"), ("calc", "Calc")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                "QPushButton{background:#0d0d0d;border:1px solid #1e1e1e;"
                "border-radius:5px;color:#404040;font-size:11px;padding:0 10px;}"
                "QPushButton:checked{background:#181818;border-color:#333;color:#c8c8c8;}"
                "QPushButton:hover{background:#111;color:#777;}"
            )
            btn.clicked.connect(lambda checked, m=mode: self._on_mode(m))
            row1.addWidget(btn)
            self._mode_btns[mode] = btn
        row1.addStretch()

        # Row 2: Toggles
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        self._persistent_btn = self._make_toggle("Постоянный", "bookmark", False)
        self._persistent_btn.clicked.connect(lambda c: self.persistent_toggled.emit(c))
        row2.addWidget(self._persistent_btn)

        self._web_btn = self._make_toggle("Веб-поиск", "magnifying-glass", True)
        self._web_btn.clicked.connect(lambda c: self.web_search_toggled.emit(c))
        row2.addWidget(self._web_btn)

        self._think_btn = self._make_toggle("Think mode", "cpu-chip", True)
        self._think_btn.clicked.connect(lambda c: self.think_mode_toggled.emit(c))
        row2.addWidget(self._think_btn)

        row2.addStretch()

        # Attach file button in panel
        attach_btn = QPushButton(" Прикрепить файл")
        attach_btn.setStyleSheet(
            "QPushButton{background:#0d0d0d;border:1px solid #1e1e1e;"
            "border-radius:5px;color:#404040;font-size:11px;padding:3px 10px;}"
            "QPushButton:hover{background:#111;border-color:#2a2a2a;color:#777;}"
        )
        attach_btn.setFixedHeight(26)
        apply_icon(attach_btn, "paper-clip", "#404040", 12)
        attach_btn.clicked.connect(self.attach_requested.emit)
        row2.addWidget(attach_btn)

        outer.addLayout(row1)
        outer.addLayout(row2)

    def _make_toggle(self, label: str, icon_name: str, default: bool) -> QPushButton:
        btn = QPushButton(f" {label}")
        btn.setCheckable(True)
        btn.setChecked(default)
        btn.setFixedHeight(26)
        apply_icon(btn, icon_name, "#404040", 12)
        btn.setStyleSheet(
            "QPushButton{background:#0d0d0d;border:1px solid #1e1e1e;"
            "border-radius:5px;color:#404040;font-size:11px;padding:0 10px;}"
            "QPushButton:checked{background:#111818;border-color:#1e3020;color:#5a9a6a;}"
            "QPushButton:checked:hover{background:#121a14;}"
            "QPushButton:hover{background:#111;color:#777;}"
        )
        return btn

    def _on_mode(self, mode: str):
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)
        self.mode_changed.emit(mode)

    def set_state(self, mode: str, persistent: bool, web_search: bool, think_mode: bool):
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)
        self._persistent_btn.setChecked(persistent)
        self._web_btn.setChecked(web_search)
        self._think_btn.setChecked(think_mode)

    def toggle(self):
        if self._is_open:
            self.slide_out()
        else:
            self.slide_in()

    def slide_in(self):
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        self._is_open = True
        self.setMaximumHeight(0)
        self.show()
        anim = QPropertyAnimation(self, b"maximumHeight")
        anim.setDuration(180)
        anim.setStartValue(0)
        anim.setEndValue(100)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim  # keep reference

    def slide_out(self):
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        self._is_open = False
        anim = QPropertyAnimation(self, b"maximumHeight")
        anim.setDuration(150)
        anim.setStartValue(self.height())
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(lambda: self.hide() if not self._is_open else None)
        anim.start()
        self._anim = anim


# ─────────────────────────────────────────────────────────────────────────────
#  ChatWidget
# ─────────────────────────────────────────────────────────────────────────────

class ChatWidget(QWidget):
    send_message         = pyqtSignal(str)
    attach_file          = pyqtSignal(str)
    stop_requested       = pyqtSignal()
    export_chat          = pyqtSignal(str)
    model_changed        = pyqtSignal(str)
    model_refresh        = pyqtSignal()
    persistent_toggled   = pyqtSignal(bool)
    web_search_toggled   = pyqtSignal(bool)
    think_mode_toggled   = pyqtSignal(bool)
    mode_changed         = pyqtSignal(str)
    log_toggle_requested     = pyqtSignal()
    sidebar_toggle_requested = pyqtSignal()

    _STREAM_INTERVAL_MS = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatArea")
        self._is_busy        = False
        self._messages_html  = ""
        self._streaming_text = ""
        self._streaming_base = ""
        self._stream_buffer  = ""
        self._pending_file: tuple[str, str] | None = None
        self._file_chip: FileChip | None = None
        self._raw_messages: list[dict] = []
        self._chat_title: str = "Чат"
        self._is_persistent: bool = False
        self._is_thinking: bool = False
        self._fade_next: bool = False  # fade in on next full render (chat switch)

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(self._STREAM_INTERVAL_MS)
        self._stream_timer.timeout.connect(self._flush_stream)

        self._think_frame = 0
        self._think_timer = QTimer(self)
        self._think_timer.setInterval(350)
        self._think_timer.timeout.connect(self._tick_think)
        self._panel: "QuickSettingsPanel | None" = None  # created in _build

        self.setAcceptDrops(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ───────────────────────────────────────
        top_bar = QWidget()
        top_bar.setObjectName("chatTopBar")
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(8, 0, 12, 0)
        tl.setSpacing(8)

        self._sidebar_btn = QPushButton()
        self._sidebar_btn.setObjectName("logToggleTopBtn")
        self._sidebar_btn.setFixedSize(28, 28)
        self._sidebar_btn.setToolTip("Скрыть/показать список чатов")
        apply_icon(self._sidebar_btn, "bars-3", "#2a2a2a", 13)
        self._sidebar_btn.clicked.connect(self.sidebar_toggle_requested.emit)
        tl.addWidget(self._sidebar_btn)
        tl.addSpacing(4)

        self.model_selector = ModelSelector()
        self.model_selector.model_changed.connect(self.model_changed.emit)
        self.model_selector.refresh_clicked.connect(self.model_refresh.emit)
        tl.addWidget(self.model_selector)

        sep = QLabel("·")
        sep.setStyleSheet("color:#1e1e1e;background:transparent;font-size:14px;")
        tl.addWidget(sep)

        chat_lbl = QLabel("Чат:")
        chat_lbl.setStyleSheet("color:#2e2e2e;font-size:11px;background:transparent;")
        tl.addWidget(chat_lbl)

        self._btn_persistent = QPushButton(" Постоянный")
        self._btn_persistent.setObjectName("chatModePersistent")
        apply_icon(self._btn_persistent, "bookmark", "#353535", 12)
        self._btn_persistent.setFixedHeight(26)
        self._btn_persistent.clicked.connect(lambda: self._set_persistent_ui(True))
        tl.addWidget(self._btn_persistent)

        self._btn_temp = QPushButton(" Временный")
        self._btn_temp.setObjectName("chatModeTemp")
        apply_icon(self._btn_temp, "clock", "#353535", 12)
        self._btn_temp.setFixedHeight(26)
        self._btn_temp.clicked.connect(lambda: self._set_persistent_ui(False))
        tl.addWidget(self._btn_temp)

        tl.addStretch()

        self._export_btn = QPushButton("↑ Экспорт")
        self._export_btn.setObjectName("exportBtn")
        self._export_btn.setFixedHeight(26)
        self._export_btn.clicked.connect(self._show_export_menu)
        tl.addWidget(self._export_btn)

        self._log_btn = QPushButton("Логи")
        self._log_btn.setObjectName("logToggleTopBtn")
        apply_icon(self._log_btn, "bars-3", "#2a2a2a", 13)
        self._log_btn.setFixedHeight(26)
        self._log_btn.setToolTip("Показать/скрыть панель логов")
        self._log_btn.clicked.connect(self.log_toggle_requested.emit)
        tl.addWidget(self._log_btn)

        layout.addWidget(top_bar)

        # ── Chat browser ──────────────────────────────────
        self.browser = QTextBrowser()
        self.browser.setObjectName("chatBrowser")
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_link_clicked)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setHtml(_message_css() + "<body></body>")
        layout.addWidget(self.browser, 1)

        # ── Agent status bar ──────────────────────────────
        self._agent_bar = QWidget()
        self._agent_bar.setObjectName("agentStatusBar")
        self._agent_bar.setVisible(False)
        abl = QHBoxLayout(self._agent_bar)
        abl.setContentsMargins(16, 0, 12, 0)
        abl.setSpacing(10)

        self._agent_dot = QLabel("●")
        self._agent_dot.setStyleSheet(
            "color:#3a6a4a;font-size:8px;background:transparent;"
        )
        abl.addWidget(self._agent_dot)

        self._agent_status_lbl = QLabel("агент работает…")
        self._agent_status_lbl.setObjectName("agentStatusLabel")
        abl.addWidget(self._agent_status_lbl, 1)

        self._stop_inline_btn = QPushButton("■ стоп")
        self._stop_inline_btn.setFixedHeight(20)
        self._stop_inline_btn.setStyleSheet(
            "QPushButton{background:transparent;border:1px solid #1c1c1c;"
            "border-radius:4px;color:#5a2020;font-size:10px;padding:0 8px;"
            "font-family:'JetBrains Mono',monospace;letter-spacing:0.3px;}"
            "QPushButton:hover{color:#cc3333;border-color:#3a1010;}"
        )
        self._stop_inline_btn.clicked.connect(self.stop_requested.emit)
        abl.addWidget(self._stop_inline_btn)
        layout.addWidget(self._agent_bar)

        # ── Input area ────────────────────────────────────
        # CRITICAL FIX: use fixed minimum height and proper layout
        self._input_container = QWidget()
        self._input_container.setObjectName("inputArea")
        il = QVBoxLayout(self._input_container)
        il.setContentsMargins(14, 8, 14, 14)  # bottom padding = 14 so nothing clips
        il.setSpacing(6)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFixedHeight(14)
        il.addWidget(self.status_label)

        self._chip_row = QHBoxLayout()
        self._chip_row.setContentsMargins(0, 0, 0, 0)
        il.addLayout(self._chip_row)

        # Quick settings panel (slides up from input area)
        self._panel = QuickSettingsPanel()
        self._panel.persistent_toggled.connect(self.persistent_toggled.emit)
        self._panel.web_search_toggled.connect(self.web_search_toggled.emit)
        self._panel.think_mode_toggled.connect(self.think_mode_toggled.emit)
        self._panel.mode_changed.connect(self.mode_changed.emit)
        self._panel.attach_requested.connect(self._on_attach)
        il.addWidget(self._panel)

        # Input row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.attach_btn = QPushButton()
        self.attach_btn.setObjectName("attachBtn")
        self.attach_btn.setFixedSize(44, 44)
        self.attach_btn.setToolTip("Настройки чата")
        self.attach_btn.clicked.connect(self._toggle_panel)
        apply_icon(self.attach_btn, "plus", "#323232", 17)
        row.addWidget(self.attach_btn)

        self.input = MessageInput()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("Введите сообщение или перетащите файл…")
        self.input.setMinimumHeight(44)
        self.input.setMaximumHeight(44)
        self.input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.input.submitted.connect(self._on_send)
        self.input.textChanged.connect(self._adjust_height)
        self.input.file_pasted.connect(self.attach_file.emit)
        row.addWidget(self.input, 1)

        self.send_btn = QPushButton()
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setFixedSize(44, 44)
        self.send_btn.setToolTip("Отправить (Enter)")
        self.send_btn.clicked.connect(self._on_send)
        apply_icon(self.send_btn, "paper-airplane", "#060606", 18)
        row.addWidget(self.send_btn)

        il.addLayout(row)



        layout.addWidget(self._input_container)

        self._update_mode_buttons(False)

    # ── Persistent toggle ─────────────────────────────────

    def _set_persistent_ui(self, is_persistent: bool):
        self._is_persistent = is_persistent
        self._update_mode_buttons(is_persistent)
        self.persistent_toggled.emit(is_persistent)

    def _update_mode_buttons(self, is_persistent: bool):
        self._btn_persistent.setProperty("active", "true" if is_persistent else "false")
        self._btn_temp.setProperty("active", "false" if is_persistent else "true")
        for btn in (self._btn_persistent, self._btn_temp):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_log_btn_active(self, active: bool):
        self._log_btn.setProperty("active", "true" if active else "false")
        self._log_btn.style().unpolish(self._log_btn)
        self._log_btn.style().polish(self._log_btn)

    # ── Panel ────────────────────────────────────────────

    def _toggle_panel(self):
        if self._panel is not None:
            self._panel.toggle()

    def set_chat_state(self, mode: str, persistent: bool, web_search: bool, think_mode: bool):
        """Called when switching chats — syncs the panel state."""
        if self._panel is not None:
            self._panel.set_state(mode, persistent, web_search, think_mode)

    # ── Drag & Drop ───────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile() and os.path.isfile(urls[0].toLocalFile()):
                event.acceptProposedAction()
                self._set_drag_hint(True)
                return
        event.ignore()

    def dragLeaveEvent(self, event): self._set_drag_hint(False)

    def dropEvent(self, event):
        self._set_drag_hint(False)
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if os.path.isfile(path):
                    event.acceptProposedAction()
                    self.attach_file.emit(path)
                    return
        event.ignore()

    def _set_drag_hint(self, active: bool):
        if active:
            self.status_label.setText("📎 Отпустите файл")
            self.status_label.setStyleSheet("color:#5599dd;font-size:11px;")
            self._input_container.setStyleSheet(
                "#inputArea{border-top:1px solid #2a4a7a;background:#0a0f18;}"
            )
        else:
            self.status_label.setText("")
            self.status_label.setStyleSheet("")
            self._input_container.setStyleSheet("")

    # ── Export ────────────────────────────────────────────

    def _show_export_menu(self):
        menu = QMenu(self)
        menu.addAction("🌐  HTML",       lambda: self.export_chat.emit("html"))
        menu.addAction("📄  TXT",        lambda: self.export_chat.emit("txt"))
        menu.addAction("📋  JSON",       lambda: self.export_chat.emit("json"))
        menu.addSeparator()
        menu.addAction("🔧  Dev Logs",   lambda: self.export_chat.emit("devlogs"))
        menu.exec_(self._export_btn.mapToGlobal(self._export_btn.rect().bottomLeft()))

    def set_chat_title(self, title: str):
        self._chat_title = title
        if hasattr(self, "_title_lbl"):
            self._title_lbl.setText(title)
    def get_export_data(self) -> dict:
        return {"title": self._chat_title, "messages": list(self._raw_messages),
                "exported_at": datetime.now().isoformat()}

    # ── Link handler ──────────────────────────────────────

    def _on_link_clicked(self, url: QUrl):
        if url.scheme() == "file":
            abs_path = url.toLocalFile()
            if not os.path.exists(abs_path):
                self.status_label.setText(f"Файл не найден: {os.path.basename(abs_path)}")
                return
            dest, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", os.path.basename(abs_path))
            if dest:
                try:
                    shutil.copy2(abs_path, dest)
                    self.status_label.setText(f"Сохранено: {dest}")
                except Exception as e:
                    self.status_label.setText(f"Ошибка: {e}")
        else:
            QDesktopServices.openUrl(url)

    # ── File chip ─────────────────────────────────────────

    def set_pending_file(self, filename: str, abs_path: str):
        self._clear_chip()
        self._pending_file = (filename, abs_path)
        chip = FileChip(filename)
        chip.removed.connect(self._clear_chip)
        self._chip_row.addWidget(chip)
        self._chip_row.addStretch(1)
        self._file_chip = chip
        self.input.setFocus()

    def _clear_chip(self):
        if self._file_chip:
            self._file_chip.setParent(None)
            self._file_chip = None
        while self._chip_row.count():
            item = self._chip_row.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._pending_file = None

    # ── Input helpers ─────────────────────────────────────

    def _adjust_height(self):
        doc_h = self.input.document().size().height()
        new_h = max(44, min(160, int(doc_h) + 16))
        self.input.setMinimumHeight(new_h)
        self.input.setMaximumHeight(new_h)

    def _on_send(self):
        if self._is_busy:
            self.stop_requested.emit()
            return
        text    = self.input.toPlainText().strip()
        pending = self._pending_file
        if not text and not pending:
            return
        self.input.clear()
        if pending:
            filename, abs_path = pending
            llm_text = f"[Файл: {filename}]\n{text}" if text else f"[Файл: {filename}]"
            self._clear_chip()
            self._add_user_message_with_file(filename, text)
        else:
            llm_text = text
            self._append_message("user", text)
        
        # Принудительная прокрутка после добавления сообщения пользователя
        QTimer.singleShot(0, self._scroll_bottom)
        
        # Небольшая задержка перед отправкой, чтобы сообщение успело отрендериться
        QTimer.singleShot(50, lambda: self.send_message.emit(llm_text))

    def _on_attach(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if path:
            self.attach_file.emit(path)

    # ── State ─────────────────────────────────────────────

    def set_busy(self, busy: bool):
        self._is_busy = busy
        if busy:
            self.send_btn.setText("■")
            self.send_btn.setToolTip("Остановить")
            self.send_btn.setStyleSheet(
                "background:#111111;color:#aa3333;border:1px solid #2a2a2a;"
                "border-radius:10px;font-size:13px;"
            )
            self._agent_bar.setVisible(True)
            self._show_thinking()
        else:
            self.send_btn.setText("↑")
            self.send_btn.setToolTip("Отправить (Enter)")
            self.send_btn.setStyleSheet("")
            self._agent_bar.setVisible(False)
            self._hide_thinking()
        self.input.setReadOnly(busy)

    def _show_thinking(self):
        self._is_thinking = True
        self._think_frame = 0
        self._think_timer.start()
        self._render_with_thinking()

    def _hide_thinking(self):
        self._is_thinking = False
        self._think_timer.stop()

    def _tick_think(self):
        if self._is_thinking:
            self._think_frame += 1
            self._render_with_thinking()

    def set_persistent(self, is_persistent: bool):
        self._is_persistent = is_persistent
        self._update_mode_buttons(is_persistent)

    # ── Message display ───────────────────────────────────

    def clear_messages(self):
        self._messages_html = ""
        self._raw_messages = []
        self._fade_next = True  # animate next render
        self._render(no_scroll=True)

    def load_messages(self, messages: list[dict]):
        self.clear_messages()
        for m in messages:
            role, content, ts = m["role"], m["content"], m.get("ts", "")
            if role == "user":
                if content.startswith("[Файл: ") and "]\n" in content:
                    fname_end = content.index("]")
                    self._add_user_message_with_file(content[7:fname_end], content[fname_end+2:], ts=ts, _record=False)
                    self._raw_messages.append({"role": "user", "content": content, "ts": ts})
                elif content.startswith("[Файл: ") and content.endswith("]"):
                    self._add_user_message_with_file(content[7:-1], "", ts=ts, _record=False)
                    self._raw_messages.append({"role": "user", "content": content, "ts": ts})
                else:
                    self._append_message("user", content, ts=ts, _record=False)
                    self._raw_messages.append({"role": "user", "content": content, "ts": ts})
            elif role == "assistant":
                self._append_message("assistant", content, ts=ts, _record=False)
                self._raw_messages.append({"role": "assistant", "content": content, "ts": ts})
            elif role == "tool":
                self._append_tool(m.get("tool", "tool"), content, ts=ts, _record=False)
                self._raw_messages.append({
                    "role": "tool",
                    "tool": m.get("tool", "tool"),
                    "content": content,
                    "ts": ts,
                })
            elif role == "file_card":
                try:
                    data = json.loads(content)
                    self.add_file_card(data["filename"], data["abs_path"])
                except Exception:
                    pass
        QTimer.singleShot(60, self._scroll_bottom)

    def add_user_message(self, text: str): self._append_message("user", text)
    def add_assistant_message(self, text: str): self._append_message("assistant", text)
    def add_tool_message(self, tool_name: str, args: str, result: str):
        self._append_tool(tool_name, f"{args}\n{result}")
    def add_error_message(self, text: str): self._append_message("error", text)

    def add_file_card(self, filename: str, abs_path: str):
        icon = _file_icon(filename)
        ext  = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
        size = _file_size_str(abs_path)
        meta = f"{ext}  {size}".strip()
        file_url = QUrl.fromLocalFile(abs_path).toString()
        self._messages_html += _file_card_row(
            icon, html.escape(filename), html.escape(meta), file_url
        )
        self._render()

    # ── Streaming ─────────────────────────────────────────

    def begin_stream(self):
        self._hide_thinking()
        self._streaming_text = ""
        self._streaming_base = self._messages_html
        self._stream_buffer  = ""
        self._stream_timer.start()

    def append_stream(self, chunk: str):
        self._stream_buffer += chunk

    @staticmethod
    def _split_think(text: str):
        """Return (think_content, visible_content) from raw streaming text."""
        import re as _re
        think_parts = _re.findall(r'<think>(.*?)</think>', text, _re.DOTALL)
        visible = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL)
        # If think block is not yet closed, strip the open tag and everything after
        if '<think>' in visible:
            visible = visible[:visible.index('<think>')]
        return "\n".join(think_parts), visible.strip()

    def _flush_stream(self):
        if not self._stream_buffer:
            return
        self._streaming_text += self._stream_buffer
        self._stream_buffer   = ""
        think_content, visible = self._split_think(self._streaming_text)
        # Build display HTML
        if visible:
            escaped = html.escape(visible).replace("\n", "<br>")
        else:
            escaped = ""
        cursor_span = (
            f'<span style="display:inline-block;width:2px;height:14px;'
            f'background:{C["cursor"]};margin-left:2px;vertical-align:text-bottom;">|</span>'
        )
        think_html = ""
        if think_content:
            tc_esc = html.escape(think_content[:800]).replace("\n", "<br>")
            think_html = (
                f'<div style="border-left:2px solid #1a1a1a;padding:4px 10px;'
                f'color:#333;font-size:11px;font-family:{MONO};'
                f'background:#080808;margin-bottom:6px;'
                f'border-radius:0 4px 4px 0;max-height:120px;overflow:hidden;">'
                f'<span style="color:#252525;font-size:9.5px;letter-spacing:0.8px;'
                f'text-transform:uppercase;display:block;margin-bottom:3px;">думает&#x2026;</span>'
                f'{tc_esc}</div>'
            )
        block = _asst_bubble(think_html + escaped + cursor_span)
        self.browser.setHtml(_message_css() + f"<body>{self._streaming_base}{block}</body>")
        self._scroll_bottom()

    def end_stream(self):
        self._stream_timer.stop()
        if self._stream_buffer:
            self._streaming_text += self._stream_buffer
            self._stream_buffer   = ""
        if self._streaming_text:
            import re as _re
            think_parts = _re.findall(r'<think>(.*?)</think>', self._streaming_text, _re.DOTALL)
            visible = _re.sub(r'<think>.*?</think>', '', self._streaming_text, flags=_re.DOTALL).strip()
            if '<think>' in visible:
                visible = visible[:visible.index('<think>')].strip()
            # Build collapsible think block
            think_html = ""
            if think_parts:
                tc = "\n---\n".join(think_parts)
                tc_esc = html.escape(tc).replace("\n", "<br>")
                n = len(self._raw_messages)
                think_html = (
                    f'<div style="border-left:2px solid #161616;margin-bottom:8px;'
                    f'padding:4px 10px;border-radius:0 4px 4px 0;background:#070707;">'
                    f'<a href="think://{n}" style="color:#2a2a2a;font-size:9.5px;'
                    f'font-family:{MONO};text-transform:uppercase;letter-spacing:0.8px;'
                    f'text-decoration:none;">&#129504; думал — нажми чтобы развернуть</a>'
                    f'<div id="think-{n}" style="display:none;color:#333;font-size:11px;'
                    f'font-family:{MONO};margin-top:4px;">{tc_esc}</div>'
                    f'</div>'
                )
            rendered = _md_to_html(visible) if visible else ""
            self._messages_html = self._streaming_base + _asst_bubble(think_html + rendered)
            self._raw_messages.append({
                "role": "assistant", "content": visible,
                "ts": datetime.now().isoformat(),
            })
            self._render()
        self._streaming_text = ""
        self._streaming_base = ""

    # ── Private render ────────────────────────────────────

    def _add_user_message_with_file(self, filename: str, text: str, ts: str = "", _record: bool = True):
        icon = _file_icon(filename)
        ext  = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
        chip_html = (
            f'<table cellpadding="0" cellspacing="0" style="background:{C["chip_bg"]};'
            f'border:1px solid {C["chip_bd"]};border-radius:7px;margin-bottom:6px;">'
            f'<tr>'
            f'<td style="padding:7px 7px 7px 9px;font-size:14px;">{icon}</td>'
            f'<td style="padding:7px 5px;color:{C["chip_name"]};font-size:12.5px;font-weight:500;">'
            f'{html.escape(filename)}</td>'
            f'<td style="padding:7px 9px 7px 3px;color:{C["chip_ext"]};font-size:10.5px;'
            f'text-transform:uppercase;letter-spacing:0.4px;font-family:{MONO};">{ext}</td>'
            f'</tr></table>'
        )
        text_html = (
            f'<div style="color:{C["user_text"]};font-size:14px;padding-top:7px;">'
            f'{html.escape(text).replace(chr(10), "<br>")}</div>'
        ) if text else ""
        self._messages_html += _user_bubble(chip_html + text_html)
        if _record:
            raw = f"[Файл: {filename}]\n{text}" if text else f"[Файл: {filename}]"
            self._raw_messages.append({"role": "user", "content": raw, "ts": ts or datetime.now().isoformat()})
        self._render()

    def _append_message(self, css_class: str, content: str, ts: str = "", _record: bool = True):
        if css_class == "user":
            escaped = html.escape(content).replace("\n", "<br>")
            self._messages_html += _user_bubble(escaped)
            if _record:
                self._raw_messages.append({"role": "user", "content": content, "ts": ts or datetime.now().isoformat()})
        elif css_class == "error":
            escaped = html.escape(content).replace("\n", "<br>")
            self._messages_html += _error_row(escaped)
        else:
            rendered = _md_to_html(content)
            self._messages_html += _asst_bubble(rendered)
            if _record:
                self._raw_messages.append({"role": "assistant", "content": content, "ts": ts or datetime.now().isoformat()})
        self._render()

    def _append_tool(self, tool_name: str, content: str, ts: str = "", _record: bool = True):
        tool_name = str(tool_name or "tool")
        content = str(content or "")
        ec_match = re.search(r'\[exit code:\s*(-?\d+)\]', content)
        exit_code = int(ec_match.group(1)) if ec_match else None
        body = re.sub(r'^\[exit code:\s*-?\d+\]\n?', '', content).strip()
        self._messages_html += _tool_row(tool_name, exit_code, body)
        if _record:
            self._raw_messages.append({
                "role": "tool",
                "tool": tool_name,
                "content": content,
                "ts": ts or datetime.now().isoformat(),
            })
        self._render()

    def _render(self, no_scroll: bool = False):
        extra = _thinking_row(self._think_frame) if self._is_thinking else ""
        html = _message_css() + f"<body>{self._messages_html}{extra}</body>"
        anims_on = getattr(__import__("builtins"), "_quadrogent_animations", True)
        if self._fade_next and anims_on:
            self._fade_next = False
            # Fade in: start transparent, animate to full opacity
            effect = QGraphicsOpacityEffect(self.browser)
            self.browser.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(220)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda: self.browser.setGraphicsEffect(None))
            self.browser.setHtml(html)
            anim.start()
            self._fade_anim = anim  # keep reference
        else:
            self.browser.setHtml(html)
        if not no_scroll:
            self._scroll_bottom()

    def _render_with_thinking(self):
        self.browser.setHtml(_message_css() + f"<body>{self._messages_html}{_thinking_row(self._think_frame)}</body>")
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.browser.verticalScrollBar()
        sb.setValue(sb.maximum())
