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
    QSizePolicy, QMenu, QComboBox,
)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QKeyEvent

from src.ui.styles import MESSAGE_CSS


# ─────────────────────────────────────────────────────────────────────────────
#  HTML message builders — all inline styles, table-based layout
# ─────────────────────────────────────────────────────────────────────────────

# Palette constants
C = {
    "user_bg":       "#181818",
    "user_border":   "#2a2a2a",
    "user_text":     "#ededed",
    "asst_text":     "#c4c4c4",
    "avatar_bg":     "#0e0e0e",
    "avatar_border": "#1e1e1e",
    "avatar_text":   "#303030",
    "tool_name":     "#282828",
    "tool_ok":       "#2a5530",
    "tool_err":      "#632020",
    "tool_body_bg":  "#080808",
    "tool_body_bd":  "#131313",
    "tool_body_txt": "#363636",
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
    "code_lang_txt": "#2e2e2e",
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
    "dot1":          "#222222",
    "dot_active":    "#999999",
}

FONT = '"Inter","Segoe UI",system-ui,sans-serif'
MONO = '"JetBrains Mono","Consolas",monospace'


def _avatar():
    return (
        f'<div style="width:26px;height:26px;min-width:26px;'
        f'background:{C["avatar_bg"]};border:1px solid {C["avatar_border"]};'
        f'border-radius:6px;text-align:center;font-family:{MONO};'
        f'font-size:11px;color:{C["avatar_text"]};line-height:26px;'
        f'margin-top:2px;">◈</div>'
    )


def _user_bubble(content_html: str) -> str:
    """Right-aligned user bubble via table."""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:3px 0;">'
        f'<tr>'
        f'<td width="25%"></td>'
        f'<td align="right" valign="top">'
        f'<div style="display:inline-block;background:{C["user_bg"]};'
        f'border:1px solid {C["user_border"]};'
        f'border-radius:16px 16px 3px 16px;'
        f'padding:10px 14px;color:{C["user_text"]};'
        f'font-family:{FONT};font-size:14px;line-height:1.62;'
        f'word-wrap:break-word;max-width:100%;">'
        f'{content_html}</div>'
        f'</td>'
        f'<td width="18"></td>'
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
        f'{html.escape(tool_name)}{badge}</div>'
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


def _thinking_row() -> str:
    """Animated thinking dots (Qt CSS animations won't work, use static dots)."""
    dot_s = (
        f'<span style="display:inline-block;width:6px;height:6px;'
        f'border-radius:50%;background:{C["dot1"]};margin:0 2px;">'
        f'·</span>'
    )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:6px 0;">'
        f'<tr>'
        f'<td width="18"></td>'
        f'<td width="36" valign="middle">{_avatar()}</td>'
        f'<td valign="middle" style="padding-top:2px;">'
        f'<span style="color:{C["dot1"]};font-size:22px;letter-spacing:2px;'
        f'font-family:{MONO};">···</span>'
        f'</td>'
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
    text = re.sub(r"```(\w*)\n(.*?)```", _fence, text, flags=re.DOTALL)

    # Split out already-rendered code blocks
    parts = re.split(r'(<div style="margin:10px.*?</div>)', text, flags=re.DOTALL)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
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

_EXT_ICONS = {
    "py": "🐍", "js": "🟨", "ts": "🔷", "html": "🌐", "css": "🎨",
    "json": "📋", "xml": "📋", "yaml": "📋", "yml": "📋",
    "pdf": "📕", "doc": "📝", "docx": "📝", "xls": "📊", "xlsx": "📊",
    "txt": "📄", "md": "📄", "csv": "📊",
    "png": "🖼", "jpg": "🖼", "jpeg": "🖼", "gif": "🖼", "svg": "🖼",
    "zip": "📦", "tar": "📦", "gz": "📦",
    "mp3": "🎵", "wav": "🎵", "mp4": "🎬",
    "sh": "⚙", "bat": "⚙", "exe": "⚙",
}
def _file_icon(fn): return _EXT_ICONS.get(fn.rsplit(".", 1)[-1].lower() if "." in fn else "", "📄")
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
    submitted = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(False)
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
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


class ModelSelector(QWidget):
    model_changed   = pyqtSignal(str)
    refresh_clicked = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        lbl = QLabel("Модель:")
        lbl.setObjectName("modelLabel")
        layout.addWidget(lbl)
        self.combo = QComboBox()
        self.combo.setObjectName("modelCombo")
        self.combo.setFixedHeight(26)
        self.combo.setMinimumWidth(200)
        self.combo.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self.combo)
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setObjectName("modelRefreshBtn")
        self.refresh_btn.setFixedSize(26, 26)
        self.refresh_btn.setToolTip("Обновить модели")
        self.refresh_btn.clicked.connect(self.refresh_clicked.emit)
        layout.addWidget(self.refresh_btn)
        self._loaded: list[str] = []
        self._current: str = ""
        self._updating = False

    def set_models(self, loaded, available):
        self._loaded = loaded
        self._updating = True
        prev = self._current
        self.combo.clear()
        sections = [(m, True) for m in loaded] + [(m, False) for m in available if m not in loaded]
        if not sections:
            self.combo.addItem("(нет моделей)")
            self._updating = False
            return
        target_idx = 0
        from PyQt5.QtGui import QColor
        for i, (model_id, is_loaded) in enumerate(sections):
            self.combo.addItem(("● " if is_loaded else "○ ") + model_id, userData=model_id)
            item = self.combo.model().item(i)
            if item:
                item.setForeground(QColor("#bbbbbb" if is_loaded else "#404040"))
            if model_id == prev:
                target_idx = i
            elif is_loaded and not prev:
                target_idx = i
        self.combo.setCurrentIndex(target_idx)
        if self.combo.count() > 0:
            self._current = self.combo.itemData(target_idx) or ""
        self._updating = False

    def current_model(self): return self._current
    def set_current_model(self, model_id):
        self._current = model_id
        self._updating = True
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == model_id:
                self.combo.setCurrentIndex(i)
                break
        self._updating = False

    def _on_changed(self, idx):
        if self._updating: return
        model_id = self.combo.itemData(idx)
        if model_id and model_id != self._current:
            self._current = model_id
            self.model_changed.emit(model_id)


# ─────────────────────────────────────────────────────────────────────────────
#  ChatWidget
# ─────────────────────────────────────────────────────────────────────────────

class ChatWidget(QWidget):
    send_message         = pyqtSignal(str)
    attach_file          = pyqtSignal(str)
    save_memory          = pyqtSignal()
    stop_requested       = pyqtSignal()
    export_chat          = pyqtSignal(str)
    model_changed        = pyqtSignal(str)
    model_refresh        = pyqtSignal()
    persistent_toggled   = pyqtSignal(bool)
    log_toggle_requested = pyqtSignal()

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

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(self._STREAM_INTERVAL_MS)
        self._stream_timer.timeout.connect(self._flush_stream)

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
        tl.setContentsMargins(14, 0, 12, 0)
        tl.setSpacing(8)

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

        self._btn_persistent = QPushButton("◉ Постоянный")
        self._btn_persistent.setObjectName("chatModePersistent")
        self._btn_persistent.setFixedHeight(26)
        self._btn_persistent.clicked.connect(lambda: self._set_persistent_ui(True))
        tl.addWidget(self._btn_persistent)

        self._btn_temp = QPushButton("○ Временный")
        self._btn_temp.setObjectName("chatModeTemp")
        self._btn_temp.setFixedHeight(26)
        self._btn_temp.clicked.connect(lambda: self._set_persistent_ui(False))
        tl.addWidget(self._btn_temp)

        tl.addStretch()

        self._export_btn = QPushButton("↑ Экспорт")
        self._export_btn.setObjectName("exportBtn")
        self._export_btn.setFixedHeight(26)
        self._export_btn.clicked.connect(self._show_export_menu)
        tl.addWidget(self._export_btn)

        self._log_btn = QPushButton("◫ Логи")
        self._log_btn.setObjectName("logToggleTopBtn")
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
        self.browser.setHtml(MESSAGE_CSS + "<body></body>")
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

        # Input row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.attach_btn = QPushButton("+")
        self.attach_btn.setObjectName("attachBtn")
        self.attach_btn.setFixedSize(44, 44)
        self.attach_btn.setToolTip("Прикрепить файл")
        self.attach_btn.clicked.connect(self._on_attach)
        row.addWidget(self.attach_btn)

        self.input = MessageInput()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("Введите сообщение или перетащите файл…")
        self.input.setMinimumHeight(44)
        self.input.setMaximumHeight(44)
        self.input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.input.submitted.connect(self._on_send)
        self.input.textChanged.connect(self._adjust_height)
        row.addWidget(self.input, 1)

        self.send_btn = QPushButton("↑")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setFixedSize(44, 44)
        self.send_btn.setToolTip("Отправить (Enter)")
        self.send_btn.clicked.connect(self._on_send)
        row.addWidget(self.send_btn)

        il.addLayout(row)

        self.memory_btn = QPushButton("Сохранить в память")
        self.memory_btn.setVisible(False)
        self.memory_btn.clicked.connect(self.save_memory.emit)
        il.addWidget(self.memory_btn)

        layout.addWidget(self._input_container)

        self._update_mode_buttons(False)

    # ── Persistent toggle ─────────────────────────────────

    def _set_persistent_ui(self, is_persistent: bool):
        self._is_persistent = is_persistent
        self._update_mode_buttons(is_persistent)
        self.memory_btn.setVisible(is_persistent)
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
        menu.addAction("🌐  HTML",   lambda: self.export_chat.emit("html"))
        menu.addAction("📄  TXT",    lambda: self.export_chat.emit("txt"))
        menu.addAction("📋  JSON",   lambda: self.export_chat.emit("json"))
        menu.exec_(self._export_btn.mapToGlobal(self._export_btn.rect().bottomLeft()))

    def set_chat_title(self, title: str): self._chat_title = title
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
        self.send_message.emit(llm_text)

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
        self._render_with_thinking()

    def _hide_thinking(self):
        self._is_thinking = False

    def set_persistent(self, is_persistent: bool):
        self._is_persistent = is_persistent
        self._update_mode_buttons(is_persistent)
        self.memory_btn.setVisible(is_persistent)

    # ── Message display ───────────────────────────────────

    def clear_messages(self):
        self._messages_html = ""
        self._raw_messages = []
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
                self._append_tool(m.get("tool", "tool"), content)
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

    def _flush_stream(self):
        if not self._stream_buffer:
            return
        self._streaming_text += self._stream_buffer
        self._stream_buffer   = ""
        escaped = html.escape(self._streaming_text).replace("\n", "<br>")
        cursor_span = (
            f'<span style="display:inline-block;width:2px;height:14px;'
            f'background:{C["cursor"]};margin-left:2px;vertical-align:text-bottom;">|</span>'
        )
        block = _asst_bubble(escaped + cursor_span)
        self.browser.setHtml(MESSAGE_CSS + f"<body>{self._streaming_base}{block}</body>")
        self._scroll_bottom()

    def end_stream(self):
        self._stream_timer.stop()
        if self._stream_buffer:
            self._streaming_text += self._stream_buffer
            self._stream_buffer   = ""
        if self._streaming_text:
            rendered = _md_to_html(self._streaming_text)
            self._messages_html = self._streaming_base + _asst_bubble(rendered)
            self._raw_messages.append({
                "role": "assistant", "content": self._streaming_text,
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

    def _append_tool(self, tool_name: str, content: str):
        ec_match = re.search(r'\[exit code:\s*(-?\d+)\]', content)
        exit_code = int(ec_match.group(1)) if ec_match else None
        body = re.sub(r'^\[exit code:\s*-?\d+\]\n?', '', content).strip()
        self._messages_html += _tool_row(tool_name, exit_code, body)
        self._render()

    def _render(self, no_scroll: bool = False):
        extra = _thinking_row() if self._is_thinking else ""
        self.browser.setHtml(MESSAGE_CSS + f"<body>{self._messages_html}{extra}</body>")
        if not no_scroll:
            self._scroll_bottom()

    def _render_with_thinking(self):
        self.browser.setHtml(MESSAGE_CSS + f"<body>{self._messages_html}{_thinking_row()}</body>")
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.browser.verticalScrollBar()
        sb.setValue(sb.maximum())
