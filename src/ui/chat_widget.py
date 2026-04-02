import html
import json
import os
import re
import shutil

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QLabel, QFileDialog,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QKeyEvent

from src.ui.styles import MESSAGE_CSS


# ── Markdown → HTML (lightweight, QTextBrowser-safe) ─────────────────────────

def _md_to_html(text: str) -> str:
    def _fence(m):
        lang = html.escape(m.group(1).strip())
        code = html.escape(m.group(2))
        label = f'<span class="code-lang">{lang}</span>' if lang else ""
        return f'<div class="code-block">{label}<pre><code>{code}</code></pre></div>'

    text = re.sub(r"```(\w*)\n(.*?)```", _fence, text, flags=re.DOTALL)

    parts = re.split(r'(<div class="code-block">.*?</div>)', text, flags=re.DOTALL)
    result_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            result_parts.append(part)
            continue
        p = html.escape(part)
        p = re.sub(r"`([^`\n]+)`", r'<code>\1</code>', p)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"__(.+?)__",     r"<strong>\1</strong>", p)
        p = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", p)
        p = re.sub(r"_([^_\n]+)_",   r"<em>\1</em>", p)
        p = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', p)
        p = re.sub(r"(?m)^-{3,}\s*$", "<hr>", p)
        p = re.sub(r"(?m)^#{6}\s+(.+)$", r"<h6>\1</h6>", p)
        p = re.sub(r"(?m)^#{5}\s+(.+)$", r"<h5>\1</h5>", p)
        p = re.sub(r"(?m)^#{4}\s+(.+)$", r"<h4>\1</h4>", p)
        p = re.sub(r"(?m)^#{3}\s+(.+)$", r"<h3>\1</h3>", p)
        p = re.sub(r"(?m)^#{2}\s+(.+)$", r"<h2>\1</h2>", p)
        p = re.sub(r"(?m)^#\s+(.+)$",    r"<h1>\1</h1>", p)
        p = re.sub(r"(?m)^&gt;\s*(.+)$", r'<div class="blockquote">\1</div>', p)
        p = re.sub(r"(?m)^[\*\-]\s+(.+)$", r"<li>\1</li>", p)
        p = re.sub(r"(?m)^\d+\.\s+(.+)$",  r"<li>\1</li>", p)
        p = re.sub(
            r"(<li>.*?</li>(\n|$))+",
            lambda m: "<ul>" + m.group(0) + "</ul>",
            p, flags=re.DOTALL,
        )
        p = p.replace("\n", "<br>")
        result_parts.append(p)
    return "".join(result_parts)


# ── File icon / size helpers ──────────────────────────────────────────────────

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

def _file_icon(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXT_ICONS.get(ext, "📄")

def _file_size_str(path: str) -> str:
    try:
        s = os.path.getsize(path)
        if s < 1024:        return f"{s} B"
        if s < 1_048_576:   return f"{s // 1024} KB"
        return f"{s // 1_048_576} MB"
    except OSError:
        return ""


# ── MessageInput ──────────────────────────────────────────────────────────────

class MessageInput(QTextEdit):
    submitted = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
        else:
            super().keyPressEvent(event)


# ── FileChip ──────────────────────────────────────────────────────────────────

class FileChip(QWidget):
    removed = pyqtSignal()

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.filename = filename
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(7)

        icon = QLabel(_file_icon(filename))
        icon.setStyleSheet("background: transparent; font-size: 15px;")
        layout.addWidget(icon)

        name = QLabel(filename)
        name.setStyleSheet("background: transparent; color: #c0c0c0; font-size: 12px;")
        name.setMaximumWidth(260)
        layout.addWidget(name, 1)

        rm = QPushButton("✕")
        rm.setFixedSize(18, 18)
        rm.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #555; "
            "font-size: 11px; } QPushButton:hover { color: #aaa; }"
        )
        rm.clicked.connect(self.removed.emit)
        layout.addWidget(rm)

        self.setStyleSheet(
            "FileChip { background: #181818; border: 1px solid #2a2a2a; border-radius: 8px; }"
        )
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


# ── ChatWidget ────────────────────────────────────────────────────────────────

class ChatWidget(QWidget):
    send_message   = pyqtSignal(str)
    attach_file    = pyqtSignal(str)
    save_memory    = pyqtSignal()
    stop_requested = pyqtSignal()

    _STREAM_INTERVAL_MS = 40   # ~25 fps streaming updates

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

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(self._STREAM_INTERVAL_MS)
        self._stream_timer.timeout.connect(self._flush_stream)

        self._build()

    # ── Build ─────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.browser = QTextBrowser()
        self.browser.setObjectName("chatBrowser")
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._on_link_clicked)
        self.browser.setHtml(MESSAGE_CSS + "<body></body>")
        layout.addWidget(self.browser, 1)

        self._input_container = QWidget()
        self._input_container.setObjectName("inputArea")
        self._input_layout = QVBoxLayout(self._input_container)
        self._input_layout.setContentsMargins(16, 10, 16, 14)
        self._input_layout.setSpacing(6)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self._input_layout.addWidget(self.status_label)

        self._chip_row = QHBoxLayout()
        self._chip_row.setContentsMargins(0, 0, 0, 0)
        self._input_layout.addLayout(self._chip_row)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.attach_btn = QPushButton("+")
        self.attach_btn.setObjectName("attachBtn")
        self.attach_btn.setFixedSize(44, 44)
        self.attach_btn.setToolTip("Прикрепить файл")
        self.attach_btn.clicked.connect(self._on_attach)
        row.addWidget(self.attach_btn)

        self.input = MessageInput()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("Введите сообщение…")
        self.input.setFixedHeight(44)
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

        self._input_layout.addLayout(row)

        self.memory_btn = QPushButton("Сохранить в память")
        self.memory_btn.setVisible(False)
        self.memory_btn.clicked.connect(self.save_memory.emit)
        self._input_layout.addWidget(self.memory_btn)

        layout.addWidget(self._input_container)

    # ── Link handler ──────────────────────────────────────

    def _on_link_clicked(self, url: QUrl):
        """
        file:// links  → "Save As" dialog
        http(s):// etc → system browser
        """
        if url.scheme() == "file":
            abs_path = url.toLocalFile()
            if not os.path.exists(abs_path):
                self.status_label.setText(f"Файл не найден: {os.path.basename(abs_path)}")
                return
            filename = os.path.basename(abs_path)
            dest, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", filename)
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
            if item.widget():
                item.widget().deleteLater()
        self._pending_file = None

    # ── Input helpers ─────────────────────────────────────

    def _adjust_height(self):
        doc_h = self.input.document().size().height()
        self.input.setFixedHeight(max(44, min(160, int(doc_h) + 20)))

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
                "background:#181818; color:#cc4444; border:1px solid #2e2e2e; "
                "border-radius:10px; font-size:14px;"
            )
        else:
            self.send_btn.setText("↑")
            self.send_btn.setToolTip("Отправить (Enter)")
            self.send_btn.setStyleSheet("")
        self.input.setReadOnly(busy)
        self.status_label.setText("агент работает…" if busy else "")

    def set_persistent(self, is_persistent: bool):
        self.memory_btn.setVisible(is_persistent)

    # ── Message display ───────────────────────────────────

    def clear_messages(self):
        self._messages_html = ""
        self._render()

    def load_messages(self, messages: list[dict]):
        self.clear_messages()
        for m in messages:
            role    = m["role"]
            content = m["content"]
            if role == "user":
                if content.startswith("[Файл: ") and "]\n" in content:
                    fname_end = content.index("]")
                    self._add_user_message_with_file(content[7:fname_end], content[fname_end + 2:])
                elif content.startswith("[Файл: ") and content.endswith("]"):
                    self._add_user_message_with_file(content[7:-1], "")
                else:
                    self._append_message("user", content)
            elif role == "assistant":
                self._append_message("assistant", content)
            elif role == "tool":
                self._append_tool(m.get("tool", "tool"), content)
            elif role == "file_card":
                try:
                    data = json.loads(content)
                    self.add_file_card(data["filename"], data["abs_path"])
                except Exception:
                    pass

    def add_user_message(self, text: str):
        self._append_message("user", text)

    def add_assistant_message(self, text: str):
        self._append_message("assistant", text)

    def add_tool_message(self, tool_name: str, args: str, result: str):
        self._append_tool(tool_name, f"{args}\n{result}")

    def add_error_message(self, text: str):
        self._append_message("error", text)

    def add_file_card(self, filename: str, abs_path: str):
        icon      = _file_icon(filename)
        ext       = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
        size_str  = _file_size_str(abs_path)
        meta      = f"{ext}  {size_str}".strip()
        safe_name = html.escape(filename)
        safe_meta = html.escape(meta)
        file_url  = QUrl.fromLocalFile(abs_path).toString()

        block = (
            f'<div class="fc-wrap">'
            f'<table class="file-card" cellpadding="0" cellspacing="0" border="0" width="100%">'
            f'<tr>'
            f'<td class="fc-icon-cell" width="36">{icon}</td>'
            f'<td class="fc-info-cell">'
            f'<div class="fc-name">{safe_name}</div>'
            f'<div class="fc-meta">{safe_meta}</div>'
            f'</td>'
            f'<td class="fc-action-cell" width="110" align="right">'
            f'<a href="{file_url}" class="fc-link">&#128190; Скачать</a>'
            f'</td>'
            f'</tr>'
            f'</table>'
            f'</div>'
        )
        self._messages_html += block
        self._render()

    # ── Streaming (QTimer-buffered) ───────────────────────

    def begin_stream(self):
        self._streaming_text = ""
        self._streaming_base = self._messages_html
        self._stream_buffer  = ""
        self._stream_timer.start()

    def append_stream(self, chunk: str):
        """Called from main thread via queued signal — only buffers, no UI."""
        self._stream_buffer += chunk

    def _flush_stream(self):
        """QTimer slot: drains buffer → updates browser at ~25 fps."""
        if not self._stream_buffer:
            return
        self._streaming_text += self._stream_buffer
        self._stream_buffer   = ""
        escaped = html.escape(self._streaming_text).replace("\n", "<br>")
        block = (
            f'<div class="msg-wrap assistant">'
            f'<div class="bubble-assistant">{escaped}'
            f'<span class="cursor"></span></div></div>'
        )
        self.browser.setHtml(
            MESSAGE_CSS + f"<body>{self._streaming_base}{block}</body>"
        )
        self._scroll_bottom()

    def end_stream(self):
        self._stream_timer.stop()
        if self._stream_buffer:
            self._streaming_text += self._stream_buffer
            self._stream_buffer   = ""
        if self._streaming_text:
            rendered = _md_to_html(self._streaming_text)
            block = (
                f'<div class="msg-wrap assistant">'
                f'<div class="bubble-assistant">{rendered}</div></div>'
            )
            self._messages_html = self._streaming_base + block
            self._render()
        self._streaming_text = ""
        self._streaming_base = ""

    # ── Private render ────────────────────────────────────

    def _add_user_message_with_file(self, filename: str, text: str):
        icon      = _file_icon(filename)
        ext       = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
        safe_name = html.escape(filename)
        text_block = (
            f'<div class="bubble-file-text">'
            f'{html.escape(text).replace(chr(10), "<br>")}</div>'
            if text else ""
        )
        block = (
            f'<div class="msg-wrap user"><div class="bubble-user">'
            f'<table class="attach-chip" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>'
            f'<td class="ac-icon">{icon}</td>'
            f'<td class="ac-name">{safe_name}</td>'
            f'<td class="ac-ext">{ext}</td>'
            f'</tr></table>'
            f'{text_block}</div></div>'
        )
        self._messages_html += block
        self._render()

    def _append_message(self, css_class: str, content: str):
        if css_class == "user":
            escaped = html.escape(content).replace("\n", "<br>")
            block = (
                f'<div class="msg-wrap user">'
                f'<div class="bubble-user">{escaped}</div></div>'
            )
        elif css_class == "error":
            escaped = html.escape(content).replace("\n", "<br>")
            block = (
                f'<div class="msg-wrap error">'
                f'<div class="bubble-error">{escaped}</div></div>'
            )
        else:
            rendered = _md_to_html(content)
            block = (
                f'<div class="msg-wrap assistant">'
                f'<div class="bubble-assistant">{rendered}</div></div>'
            )
        self._messages_html += block
        self._render()

    def _append_tool(self, tool_name: str, content: str):
        escaped = html.escape(content)
        block = (
            f'<div class="tool-wrap">'
            f'<div class="tool-header">&gt; {html.escape(tool_name)}</div>'
            f'<div class="tool-body">{escaped}</div></div>'
        )
        self._messages_html += block
        self._render()

    def _render(self):
        self.browser.setHtml(MESSAGE_CSS + f"<body>{self._messages_html}</body>")
        self._scroll_bottom()

    def _scroll_bottom(self):
        self.browser.verticalScrollBar().setValue(
            self.browser.verticalScrollBar().maximum()
        )
