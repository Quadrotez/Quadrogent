import html
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QLabel, QFileDialog, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QKeyEvent

from src.ui.styles import MESSAGE_CSS


class MessageInput(QTextEdit):
    """Custom text input that sends on Enter (Shift+Enter for newline)."""
    submitted = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
        else:
            super().keyPressEvent(event)


class ChatWidget(QWidget):
    """Chat display and input area."""

    send_message = pyqtSignal(str)          # user text
    attach_file = pyqtSignal(str)           # file path
    save_memory = pyqtSignal()              # save memory button
    stop_requested = pyqtSignal()           # stop agent

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatArea")
        self._build()
        self._is_busy = False

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Messages display
        self.browser = QTextBrowser()
        self.browser.setObjectName("chatBrowser")
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(MESSAGE_CSS + "<body></body>")
        layout.addWidget(self.browser, 1)

        # Input area
        input_container = QWidget()
        input_container.setObjectName("inputArea")
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(8)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        input_layout.addWidget(self.status_label)

        # Input row
        row = QHBoxLayout()
        row.setSpacing(8)

        # Attach button
        attach_btn = QPushButton("+")
        attach_btn.setFixedSize(36, 36)
        attach_btn.setToolTip("Прикрепить файл")
        attach_btn.clicked.connect(self._on_attach)
        row.addWidget(attach_btn)

        # Text input
        self.input = MessageInput()
        self.input.setObjectName("messageInput")
        self.input.setPlaceholderText("Введите сообщение...")
        self.input.setFixedHeight(44)
        self.input.submitted.connect(self._on_send)
        self.input.textChanged.connect(self._adjust_height)
        row.addWidget(self.input, 1)

        # Send / Stop button
        self.send_btn = QPushButton("→")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setFixedSize(44, 36)
        self.send_btn.clicked.connect(self._on_send)
        row.addWidget(self.send_btn)

        input_layout.addLayout(row)

        # Memory button (hidden by default)
        self.memory_btn = QPushButton("Сохранить в память")
        self.memory_btn.setVisible(False)
        self.memory_btn.clicked.connect(self.save_memory.emit)
        input_layout.addWidget(self.memory_btn)

        layout.addWidget(input_container)

        self._messages_html = ""
        self._streaming_text = ""
        self._streaming_base = ""

    def _adjust_height(self):
        doc_height = self.input.document().size().height()
        new_h = max(44, min(150, int(doc_height) + 24))
        self.input.setFixedHeight(new_h)

    def _on_send(self):
        if self._is_busy:
            self.stop_requested.emit()
            return
        text = self.input.toPlainText().strip()
        if text:
            self.input.clear()
            self.send_message.emit(text)

    def _on_attach(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if path:
            self.attach_file.emit(path)

    def set_busy(self, busy: bool):
        self._is_busy = busy
        self.send_btn.setText("■" if busy else "→")
        self.input.setReadOnly(busy)
        self.status_label.setText("Агент работает..." if busy else "")

    def set_persistent(self, is_persistent: bool):
        self.memory_btn.setVisible(is_persistent)

    def clear_messages(self):
        self._messages_html = ""
        self.browser.setHtml(MESSAGE_CSS + "<body></body>")

    def load_messages(self, messages: list[dict]):
        self.clear_messages()
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "user":
                self._append_message("user", content)
            elif role == "assistant":
                self._append_message("assistant", content)
            elif role == "tool":
                self._append_tool(m.get("tool", "tool"), content)

    def add_user_message(self, text: str):
        self._append_message("user", text)

    def add_assistant_message(self, text: str):
        self._append_message("assistant", text)

    def add_tool_message(self, tool_name: str, args: str, result: str):
        display = f"[{tool_name}]: {args}\n{result}"
        self._append_tool(tool_name, display)

    def add_error_message(self, text: str):
        self._append_message("error", text)

    # ── Streaming ─────────────────────────────────────────

    def begin_stream(self):
        """Start a new streaming assistant message."""
        self._streaming_text = ""
        self._streaming_base = self._messages_html

    def append_stream(self, chunk: str):
        """Append a text chunk to the current streaming message."""
        self._streaming_text += chunk
        escaped = html.escape(self._streaming_text).replace("\n", "<br>")
        streaming_block = f'<div class="message assistant">{escaped}<span class="cursor">|</span></div>'
        combined = self._streaming_base + streaming_block
        self.browser.setHtml(MESSAGE_CSS + f"<body>{combined}</body>")
        self._scroll_bottom()

    def end_stream(self):
        """Finalize the streaming message."""
        if hasattr(self, "_streaming_text") and self._streaming_text:
            escaped = html.escape(self._streaming_text).replace("\n", "<br>")
            block = f'<div class="message assistant">{escaped}</div>'
            self._messages_html = self._streaming_base + block
            self.browser.setHtml(MESSAGE_CSS + f"<body>{self._messages_html}</body>")
            self._scroll_bottom()
        self._streaming_text = ""
        self._streaming_base = ""

    def _append_message(self, css_class: str, content: str):
        escaped = html.escape(content).replace("\n", "<br>")
        block = f'<div class="message {css_class}">{escaped}</div>'
        self._messages_html += block
        self.browser.setHtml(MESSAGE_CSS + f"<body>{self._messages_html}</body>")
        self._scroll_bottom()

    def _append_tool(self, tool_name: str, content: str):
        escaped = html.escape(content)
        block = (
            f'<div class="tool-label">&gt; {html.escape(tool_name)}</div>'
            f'<div class="tool">{escaped}</div>'
        )
        self._messages_html += block
        self.browser.setHtml(MESSAGE_CSS + f"<body>{self._messages_html}</body>")
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.browser.verticalScrollBar()
        sb.setValue(sb.maximum())
