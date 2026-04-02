import html
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QLabel, QFileDialog,
    QApplication, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QKeyEvent

from src.ui.styles import MESSAGE_CSS


# ── File icon helper ──────────────────────────────────────────────────────────

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
        if s < 1024:      return f"{s} B"
        if s < 1048576:   return f"{s // 1024} KB"
        return f"{s // 1048576} MB"
    except OSError:
        return ""


# ── MessageInput ──────────────────────────────────────────────────────────────

class MessageInput(QTextEdit):
    """Enter sends; Shift+Enter inserts newline."""
    submitted = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
        else:
            super().keyPressEvent(event)


# ── FileChip (input-area badge) ───────────────────────────────────────────────

class FileChip(QWidget):
    """Small file badge shown above the input field."""
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
        name.setStyleSheet(
            "background: transparent; color: #c0c0c0; font-size: 12px;"
        )
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
            "FileChip { background: #181818; border: 1px solid #2a2a2a; "
            "border-radius: 8px; }"
        )
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


# ── ChatWidget ────────────────────────────────────────────────────────────────

class ChatWidget(QWidget):
    send_message   = pyqtSignal(str)   # LLM text (may include [Файл:] prefix)
    attach_file    = pyqtSignal(str)   # file path chosen in dialog
    save_memory    = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatArea")
        self._is_busy = False
        self._messages_html = ""
        self._streaming_text = ""
        self._streaming_base = ""
        self._pending_file: tuple[str, str] | None = None   # (filename, abs_path)
        self._file_chip: FileChip | None = None
        self._build()

    # ── Build ─────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Messages area
        self.browser = QTextBrowser()
        self.browser.setObjectName("chatBrowser")
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(MESSAGE_CSS + "<body></body>")
        layout.addWidget(self.browser, 1)

        # Input container
        self._input_container = QWidget()
        self._input_container.setObjectName("inputArea")
        self._input_layout = QVBoxLayout(self._input_container)
        self._input_layout.setContentsMargins(16, 10, 16, 14)
        self._input_layout.setSpacing(6)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self._input_layout.addWidget(self.status_label)

        # File chip slot (hidden until a file is attached)
        self._chip_row = QHBoxLayout()
        self._chip_row.setContentsMargins(0, 0, 0, 0)
        self._input_layout.addLayout(self._chip_row)

        # Input row
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
        self.input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # fix phantom scrollbar
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

    # ── File chip (input area) ────────────────────────────

    def set_pending_file(self, filename: str, abs_path: str):
        """Show a file chip above the input field."""
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
        # clear stretch
        while self._chip_row.count():
            item = self._chip_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pending_file = None

    # ── Input helpers ─────────────────────────────────────

    def _adjust_height(self):
        doc_h = self.input.document().size().height()
        new_h = max(44, min(160, int(doc_h) + 20))
        self.input.setFixedHeight(new_h)

    def _on_send(self):
        if self._is_busy:
            self.stop_requested.emit()
            return
        text = self.input.toPlainText().strip()
        pending = self._pending_file

        if not text and not pending:
            return

        self.input.clear()

        # Compose display + LLM text
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

    # ── Message display (public API) ──────────────────────

    def clear_messages(self):
        self._messages_html = ""
        self._render()

    def load_messages(self, messages: list[dict]):
        self.clear_messages()
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "user":
                # Detect [Файл: name] prefix in historical messages
                if content.startswith("[Файл: ") and "]\n" in content:
                    fname_end = content.index("]")
                    fname = content[7:fname_end]
                    rest = content[fname_end + 2:]
                    self._add_user_message_with_file(fname, rest)
                elif content.startswith("[Файл: ") and content.endswith("]"):
                    fname = content[7:-1]
                    self._add_user_message_with_file(fname, "")
                else:
                    self._append_message("user", content)
            elif role == "assistant":
                self._append_message("assistant", content)
            elif role == "tool":
                self._append_tool(m.get("tool", "tool"), content)

    def add_user_message(self, text: str):
        """Used when loading history or in edge cases without file."""
        self._append_message("user", text)

    def add_assistant_message(self, text: str):
        self._append_message("assistant", text)

    def add_tool_message(self, tool_name: str, args: str, result: str):
        display = f"{args}\n{result}"
        self._append_tool(tool_name, display)

    def add_error_message(self, text: str):
        self._append_message("error", text)

    def add_file_card(self, filename: str, abs_path: str):
        """Show a downloadable file card in the chat (after write_file)."""
        icon = _file_icon(filename)
        ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
        size_str = _file_size_str(abs_path)
        meta = f"{ext}  {size_str}".strip()
        safe_name = html.escape(filename)
        safe_meta = html.escape(meta)
        # Use file:// URL for QTextBrowser to open
        file_url = "file:///" + abs_path.replace("\\", "/").lstrip("/")

        block = (
            f'<div class="fc-wrap">'
            f'<table class="file-card" cellpadding="0" cellspacing="0" border="0" width="100%">'
            f'<tr>'
            f'<td class="fc-icon-cell" width="36">{icon}</td>'
            f'<td class="fc-info-cell">'
            f'<div class="fc-name">{safe_name}</div>'
            f'<div class="fc-meta">{safe_meta}</div>'
            f'</td>'
            f'<td class="fc-action-cell" width="80" align="right">'
            f'<a href="{file_url}" class="fc-link">Открыть →</a>'
            f'</td>'
            f'</tr>'
            f'</table>'
            f'</div>'
        )
        self._messages_html += block
        self._render()

    # ── Streaming ─────────────────────────────────────────

    def begin_stream(self):
        self._streaming_text = ""
        self._streaming_base = self._messages_html

    def append_stream(self, chunk: str):
        self._streaming_text += chunk
        escaped = html.escape(self._streaming_text).replace("\n", "<br>")
        block = (
            f'<div class="msg-wrap assistant">'
            f'<div class="bubble-assistant">{escaped}'
            f'<span class="cursor"></span></div></div>'
        )
        self.browser.setHtml(MESSAGE_CSS + f"<body>{self._streaming_base}{block}</body>")
        self._scroll_bottom()
        QApplication.processEvents()

    def end_stream(self):
        if self._streaming_text:
            escaped = html.escape(self._streaming_text).replace("\n", "<br>")
            block = (
                f'<div class="msg-wrap assistant">'
                f'<div class="bubble-assistant">{escaped}</div></div>'
            )
            self._messages_html = self._streaming_base + block
            self._render()
        self._streaming_text = ""
        self._streaming_base = ""

    # ── Private render helpers ────────────────────────────

    def _add_user_message_with_file(self, filename: str, text: str):
        """Render a user bubble that includes a file chip + optional text."""
        icon = _file_icon(filename)
        ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
        safe_name = html.escape(filename)
        text_block = (
            f'<div class="bubble-file-text">{html.escape(text).replace(chr(10), "<br>")}</div>'
            if text else ""
        )
        block = (
            f'<div class="msg-wrap user">'
            f'<div class="bubble-user">'
            f'<table class="attach-chip" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>'
            f'<td class="ac-icon">{icon}</td>'
            f'<td class="ac-name">{safe_name}</td>'
            f'<td class="ac-ext">{ext}</td>'
            f'</tr>'
            f'</table>'
            f'{text_block}'
            f'</div></div>'
        )
        self._messages_html += block
        self._render()

    def _append_message(self, css_class: str, content: str):
        escaped = html.escape(content).replace("\n", "<br>")
        if css_class == "user":
            block = (
                f'<div class="msg-wrap user">'
                f'<div class="bubble-user">{escaped}</div></div>'
            )
        elif css_class == "error":
            block = (
                f'<div class="msg-wrap error">'
                f'<div class="bubble-error">{escaped}</div></div>'
            )
        else:
            block = (
                f'<div class="msg-wrap assistant">'
                f'<div class="bubble-assistant">{escaped}</div></div>'
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
