"""
DockerLogPanel — bootstrap log panel, collapses to a tiny status pill after done.
"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG, QTimer
from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat


LEVEL_CFG = {
    "info":  ("#555555", "  "),
    "ok":    ("#4a9a5a", "✓ "),
    "warn":  ("#a07a30", "⚠ "),
    "error": ("#b04040", "✗ "),
    "cmd":   ("#5080b0", "$ "),
    "out":   ("#383838", "  "),
}


class DockerLogPanel(QWidget):
    """
    Full log panel during bootstrap.
    After bootstrap: collapses to a small pill button at the bottom.
    Clicking the pill re-expands the log.
    """
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dockerLogPanel")
        self._expanded = True
        self._build()
        self.hide()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Full panel (shown during bootstrap) ───────────
        self._full = QWidget()
        self._full.setObjectName("dlpFull")
        fl = QVBoxLayout(self._full)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("dlpHeader")
        header.setFixedHeight(36)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet("color: #3a5a3a; font-size: 9px; background: transparent;")
        hl.addWidget(dot)

        title = QLabel("Docker — инициализация контейнера")
        title.setStyleSheet(
            "color: #606060; font-size: 11px; font-weight: 600; "
            "letter-spacing: 0.3px; background: transparent;"
        )
        hl.addWidget(title, 1)

        self._status_lbl = QLabel("подготовка…")
        self._status_lbl.setStyleSheet("color: #404040; font-size: 11px; background: transparent;")
        hl.addWidget(self._status_lbl)

        fl.addWidget(header)

        # Log body
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setObjectName("dlpLog")
        self._log.setFixedHeight(180)
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        fl.addWidget(self._log)

        layout.addWidget(self._full)

        # ── Collapsed pill (shown after bootstrap) ────────
        self._pill = QWidget()
        self._pill.setObjectName("dlpPill")
        self._pill.setFixedHeight(26)
        self._pill.hide()
        pl = QHBoxLayout(self._pill)
        pl.setContentsMargins(10, 0, 10, 0)
        pl.setSpacing(6)
        pl.addStretch()

        self._pill_btn = QPushButton("🐳 Docker лог")
        self._pill_btn.setObjectName("dlpPillBtn")
        self._pill_btn.setFixedHeight(20)
        self._pill_btn.clicked.connect(self._toggle_expand)
        pl.addWidget(self._pill_btn)

        layout.addWidget(self._pill)

        self.setStyleSheet("""
            #dockerLogPanel { background: transparent; }
            #dlpFull { background: #080808; border-top: 1px solid #141414; }
            #dlpHeader { background: #0a0a0a; border-bottom: 1px solid #131313; }
            #dlpLog {
                background: #060606; border: none;
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 11.5px; color: #484848; padding: 8px 14px;
            }
            QScrollBar:vertical { background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: #1a1a1a; border-radius: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            #dlpPill { background: transparent; }
            #dlpPillBtn {
                background: transparent; border: 1px solid #1c1c1c;
                border-radius: 10px; color: #333333; font-size: 10px; padding: 0 10px;
            }
            #dlpPillBtn:hover { background: #0f0f0f; color: #555555; border-color: #252525; }
        """)

    # ── Public API ────────────────────────────────────────

    def show_panel(self):
        self._log.clear()
        self._full.show()
        self._pill.hide()
        self._expanded = True
        self._set_status("подготовка…", "#404040")
        self.show()

    def append_log(self, level: str, message: str):
        QMetaObject.invokeMethod(self, "_append_main",
            Qt.QueuedConnection, Q_ARG(str, level), Q_ARG(str, message))

    def set_done(self, success: bool):
        QMetaObject.invokeMethod(self, "_mark_done",
            Qt.QueuedConnection, Q_ARG(bool, success))

    # ── Slots ─────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _append_main(self, level: str, message: str):
        color_hex, prefix = LEVEL_CFG.get(level, ("#484848", "  "))
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)

        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor("#222222"))
        cursor.insertText(datetime.now().strftime("%H:%M:%S") + "  ", ts_fmt)

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
            short = message[:55] + ("…" if len(message) > 55 else "")
            clr = {"ok": "#4a9a5a", "error": "#b04040", "warn": "#a07a30"}.get(level, "#404040")
            self._set_status(short, clr)

    @pyqtSlot(bool)
    def _mark_done(self, success: bool):
        if success:
            self._set_status("готов ✓", "#4a9a5a")
            self._pill_btn.setText("🐳 Docker ✓")
            self._pill_btn.setStyleSheet(
                "#dlpPillBtn { background: transparent; border: 1px solid #1a2a1a; "
                "border-radius: 10px; color: #2a5a2a; font-size: 10px; padding: 0 10px; }"
                "#dlpPillBtn:hover { background: #0a0f0a; color: #4a8a4a; }"
            )
        else:
            self._set_status("ошибка", "#b04040")
            self._pill_btn.setText("🐳 Docker ✗")
            self._pill_btn.setStyleSheet(
                "#dlpPillBtn { background: transparent; border: 1px solid #2a1a1a; "
                "border-radius: 10px; color: #5a2a2a; font-size: 10px; padding: 0 10px; }"
                "#dlpPillBtn:hover { background: #0f0a0a; color: #8a4a4a; }"
            )
        # Collapse to pill after 3 seconds
        QTimer.singleShot(3000, self._collapse)

    def _collapse(self):
        self._full.hide()
        self._pill.show()
        self._expanded = False

    def _toggle_expand(self):
        if self._expanded:
            self._collapse()
        else:
            self._full.show()
            self._pill.hide()
            self._expanded = True

    def _set_status(self, text: str, color: str):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: 11px; background: transparent;")
