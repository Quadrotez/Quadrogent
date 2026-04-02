"""
DockerLogPanel — beautiful bootstrap log panel shown during container setup.
Appears as an overlay inside the chat area.
"""
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QSizePolicy, QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSignal, QMetaObject, Q_ARG
from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat, QFont


LEVEL_CFG = {
    #  level      color       prefix
    "info":  ("#606060", "  "),
    "ok":    ("#4a9a5a", "✓ "),
    "warn":  ("#a07a30", "⚠ "),
    "error": ("#b04040", "✗ "),
    "cmd":   ("#5080b0", "$ "),
    "out":   ("#484848", "  "),
}


class DockerLogPanel(QWidget):
    """
    Semi-transparent panel shown inside the chat area during Docker bootstrap.
    Hidden automatically when bootstrap finishes.
    """

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dockerLogPanel")
        self._build()
        self.hide()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header bar ────────────────────────────────────
        header = QWidget()
        header.setObjectName("dlpHeader")
        header.setFixedHeight(40)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 12, 0)
        hl.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet("color: #3a6a4a; font-size: 10px; background: transparent;")
        hl.addWidget(dot)

        title = QLabel("Docker — инициализация контейнера")
        title.setStyleSheet(
            "color: #707070; font-size: 12px; font-weight: 600; "
            "letter-spacing: 0.3px; background: transparent;"
        )
        hl.addWidget(title, 1)

        self._status_lbl = QLabel("подготовка…")
        self._status_lbl.setStyleSheet(
            "color: #404040; font-size: 11px; background: transparent;"
        )
        hl.addWidget(self._status_lbl)

        layout.addWidget(header)

        # ── Log body ──────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setObjectName("dlpLog")
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self._log, 1)

        self.setStyleSheet("""
            #dockerLogPanel {
                background: #080808;
                border-top: 1px solid #141414;
            }
            #dlpHeader {
                background: #0a0a0a;
                border-bottom: 1px solid #141414;
            }
            #dlpLog {
                background: #070707;
                border: none;
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 12px;
                color: #505050;
                padding: 10px 16px;
            }
            QScrollBar:vertical {
                background: transparent; width: 4px;
            }
            QScrollBar::handle:vertical {
                background: #1e1e1e; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    # ── Public API ────────────────────────────────────────

    def show_panel(self):
        self._log.clear()
        self._set_status("подготовка…", "#404040")
        self.show()

    def append_log(self, level: str, message: str):
        """Thread-safe log append — can be called from any thread."""
        QMetaObject.invokeMethod(
            self, "_append_log_main",
            Qt.QueuedConnection,
            Q_ARG(str, level),
            Q_ARG(str, message),
        )

    def set_done(self, success: bool):
        """Call when bootstrap completes."""
        if success:
            self.append_log("ok", "")
            QMetaObject.invokeMethod(
                self, "_mark_done",
                Qt.QueuedConnection,
                Q_ARG(bool, True),
            )
        else:
            QMetaObject.invokeMethod(
                self, "_mark_done",
                Qt.QueuedConnection,
                Q_ARG(bool, False),
            )

    # ── Slots (main thread) ───────────────────────────────

    def _append_log_main(self, level: str, message: str):
        color_hex, prefix = LEVEL_CFG.get(level, ("#505050", "  "))

        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Timestamp (very dim)
        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor("#252525"))
        ts_fmt.setFont(QFont("JetBrains Mono, Consolas", 10))
        now = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"{now}  ", ts_fmt)

        # Message
        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor(color_hex))

        # "out" level lines are indented and slightly dimmer
        if level == "out":
            for line in message.splitlines():
                cursor.insertText("           " + line + "\n", msg_fmt)
        else:
            cursor.insertText(prefix + message + "\n", msg_fmt)

        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

        # Keep status label updated with last non-out line
        if level not in ("out",) and message.strip():
            short = message[:60] + ("…" if len(message) > 60 else "")
            color_map = {"ok": "#4a9a5a", "error": "#b04040", "warn": "#a07a30"}
            self._set_status(short, color_map.get(level, "#404040"))

    def _mark_done(self, success: bool):
        if success:
            self._set_status("готов  ✓", "#4a9a5a")
            # Collapse panel after 4 seconds
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(4000, self._collapse)
        else:
            self._set_status("ошибка — см. лог", "#b04040")

    def _collapse(self):
        # Shrink to just the header bar
        self.setMaximumHeight(40)
        self.closed.emit()

    def expand(self):
        self.setMaximumHeight(16777215)
        self.show()

    def _set_status(self, text: str, color: str):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: 11px; background: transparent;"
        )

    # Make append_log / _mark_done callable via invokeMethod
    from PyQt5.QtCore import pyqtSlot

    @pyqtSlot(str, str)
    def _append_log_main(self, level: str, message: str):  # noqa: F811
        color_hex, prefix = LEVEL_CFG.get(level, ("#505050", "  "))
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)

        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor("#252525"))
        now = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"{now}  ", ts_fmt)

        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor(color_hex))
        if level == "out":
            for line in message.splitlines():
                if line.strip():
                    cursor.insertText("           " + line + "\n", msg_fmt)
        else:
            cursor.insertText(prefix + message + "\n", msg_fmt)

        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()

        if level not in ("out",) and message.strip():
            short = message[:60] + ("…" if len(message) > 60 else "")
            color_map = {"ok": "#4a9a5a", "error": "#b04040", "warn": "#a07a30"}
            self._set_status(short, color_map.get(level, "#404040"))

    @pyqtSlot(bool)
    def _mark_done(self, success: bool):  # noqa: F811
        if success:
            self._set_status("готов  ✓", "#4a9a5a")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(4000, self._collapse)
        else:
            self._set_status("ошибка — см. лог", "#b04040")
