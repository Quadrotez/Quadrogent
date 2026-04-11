"""
RightLogPanel — collapsible right-side panel with Docker and LM Studio logs.
"""
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QTabWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat, QFont


DOCKER_LEVEL_CFG = {
    "info":  ("#6a6a6a", "  "),
    "ok":    ("#4a9a5a", "OK "),
    "warn":  ("#ca9a38", "!! "),
    "error": ("#da4848", "EE "),
    "cmd":   ("#5a8ab0", ">> "),
    "out":   ("#5a5a5a", "   "),
}


class RightLogPanel(QWidget):
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPanel")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ───────────────────────────────────────
        header = QWidget()
        header.setObjectName("logPanelHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        title = QLabel("ЛОГИ")
        title.setObjectName("logPanelTitle")
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton("x")
        close_btn.setObjectName("logCloseBtn")
        close_btn.setFixedSize(22, 22)
        close_btn.clicked.connect(self.close_requested.emit)
        hl.addWidget(close_btn)

        layout.addWidget(header)

        # ── Tabs ─────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #050505;
            }
            QTabBar {
                background: #070707;
            }
            QTabBar::tab {
                background: transparent;
                color: #2a2a2a;
                padding: 6px 14px;
                border: none;
                border-bottom: 1px solid transparent;
                font-size: 10px;
                letter-spacing: 0.8px;
                font-family: "JetBrains Mono", "Consolas", monospace;
                text-transform: uppercase;
            }
            QTabBar::tab:selected {
                color: #888888;
                border-bottom: 1px solid #555555;
            }
            QTabBar::tab:hover:!selected { color: #505050; }
            QTabBar::tab:first { margin-left: 4px; }
        """)

        # Docker log tab
        self._docker_log = QTextEdit()
        self._docker_log.setObjectName("dockerLog")
        self._docker_log.setReadOnly(True)
        self._docker_log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._docker_log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._docker_log.setStyleSheet("""
            QTextEdit {
                background: #050505;
                border: none;
                font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
                font-size: 11px;
                color: #6a6a6a;
                padding: 8px 12px;
            }
            QScrollBar:vertical { background: transparent; width: 3px; }
            QScrollBar::handle:vertical { background: #1a1a1a; border-radius: 1px; min-height: 16px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._tabs.addTab(self._docker_log, "Docker")

        # LM Studio log tab
        self._lm_log = QTextEdit()
        self._lm_log.setObjectName("lmLog")
        self._lm_log.setReadOnly(True)
        self._lm_log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._lm_log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._lm_log.setStyleSheet("""
            QTextEdit {
                background: #050505;
                border: none;
                font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
                font-size: 11px;
                color: #6a6a6a;
                padding: 8px 12px;
            }
            QScrollBar:vertical { background: transparent; width: 3px; }
            QScrollBar::handle:vertical { background: #1a1a1a; border-radius: 1px; min-height: 16px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._tabs.addTab(self._lm_log, "LM Studio")
        layout.addWidget(self._tabs, 1)

        # ── Docker status bar ─────────────────────────────
        self._docker_status = QLabel("  инициализация…")
        self._docker_status.setStyleSheet(
            "color: #303030; font-size: 10px; padding: 5px 14px; "
            "background: #070707; border-top: 1px solid #0f0f0f; "
            "font-family: 'JetBrains Mono', monospace; letter-spacing: 0.3px;"
        )
        layout.addWidget(self._docker_status)

    # ── Public API ─────────────────────────────────────────

    def append_docker_log(self, level: str, message: str):
        """Thread-safe Docker log append."""
        QMetaObject.invokeMethod(
            self, "_docker_log_main",
            Qt.QueuedConnection,
            Q_ARG(str, level),
            Q_ARG(str, message),
        )

    def append_lm_log(self, message: str):
        """Append a line to the LM Studio log."""
        QMetaObject.invokeMethod(
            self, "_lm_log_main",
            Qt.QueuedConnection,
            Q_ARG(str, message),
        )

    def set_docker_done(self, success: bool):
        QMetaObject.invokeMethod(
            self, "_docker_done",
            Qt.QueuedConnection,
            Q_ARG(bool, success),
        )

    # ── Slots ──────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _docker_log_main(self, level: str, message: str):
        color_hex, prefix = DOCKER_LEVEL_CFG.get(level, ("#383838", "  "))
        cursor = self._docker_log.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Timestamp
        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor("#6a6a6a"))  # СВЕТЛО-СЕРЫЙ, не #2e2e2e!
        ts_fmt.setFont(QFont("JetBrains Mono, Consolas", 10))
        now = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"{now}  ", ts_fmt)

        # Message
        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor(color_hex))
        if level == "out":
            for line in message.splitlines():
                if line.strip():
                    cursor.insertText("           " + line + "\n", msg_fmt)
        else:
            cursor.insertText(prefix + message + "\n", msg_fmt)

        self._docker_log.setTextCursor(cursor)
        self._docker_log.ensureCursorVisible()

        if level not in ("out",) and message.strip():
            short = message[:55] + ("…" if len(message) > 55 else "")
            colors = {"ok": "#2e6036", "error": "#8a2e2e", "warn": "#7a5820"}
            c = colors.get(level, "#303030")
            self._docker_status.setText(f"  {short}")
            self._docker_status.setStyleSheet(
                f"color: {c}; font-size: 10px; padding: 5px 14px; "
                "background: #070707; border-top: 1px solid #0f0f0f; "
                "font-family: 'JetBrains Mono', monospace;"
            )

    @pyqtSlot(str)
    def _lm_log_main(self, message: str):
        cursor = self._lm_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor("#6a6a6a"))  # СВЕТЛО-СЕРЫЙ!
        now = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"{now}  ", ts_fmt)
        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor("#9a9a9a"))  # ЕЩЁ СВЕТЛЕЕ для сообщений!
        cursor.insertText(message + "\n", msg_fmt)
        self._lm_log.setTextCursor(cursor)
        self._lm_log.ensureCursorVisible()

    @pyqtSlot(bool)
    def _docker_done(self, success: bool):
        if success:
            self._docker_status.setText("  готов  ✓")
            self._docker_status.setStyleSheet(
                "color: #2e6036; font-size: 10px; padding: 5px 14px; "
                "background: #070707; border-top: 1px solid #0f0f0f; "
                "font-family: 'JetBrains Mono', monospace;"
            )
        else:
            self._docker_status.setText("  ошибка — проверьте лог")
            self._docker_status.setStyleSheet(
                "color: #8a2e2e; font-size: 10px; padding: 5px 14px; "
                "background: #070707; border-top: 1px solid #0f0f0f; "
                "font-family: 'JetBrains Mono', monospace;"
            )

    # ── Export logs ────────────────────────────────────────────

    def get_docker_logs(self) -> str:
        """Get all Docker logs as plain text."""
        return self._docker_log.toPlainText()

    def get_lm_logs(self) -> str:
        """Get all LM Studio logs as plain text."""
        return self._lm_log.toPlainText()
