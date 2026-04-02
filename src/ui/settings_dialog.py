from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QPushButton, QTabWidget,
    QWidget, QLineEdit, QFormLayout, QTextEdit,
)
from PyQt5.QtCore import Qt


class ChatSettingsDialog(QDialog):
    """Settings dialog for current chat."""

    def __init__(self, chat_data: dict, parent=None):
        super().__init__(parent)
        self.chat_data = chat_data
        self.result_data = {}
        self.setWindowTitle("Настройки чата")
        self.setMinimumWidth(400)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title_label = QLabel("Название чата")
        self.title_edit = QLineEdit(self.chat_data.get("title", ""))
        layout.addWidget(title_label)
        layout.addWidget(self.title_edit)

        mode_label = QLabel("Режим")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "work", "talk"])
        current = self.chat_data.get("mode", "auto")
        self.mode_combo.setCurrentText(current)
        layout.addWidget(mode_label)
        layout.addWidget(self.mode_combo)

        self.persistent_check = QCheckBox("Постоянный чат (сохранять в память)")
        self.persistent_check.setChecked(bool(self.chat_data.get("persistent", 0)))
        layout.addWidget(self.persistent_check)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("sendBtn")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _save(self):
        self.result_data = {
            "title": self.title_edit.text().strip() or "Новый чат",
            "mode": self.mode_combo.currentText(),
            "persistent": 1 if self.persistent_check.isChecked() else 0,
        }
        self.accept()


class AppSettingsDialog(QDialog):
    """Global application settings."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Настройки")
        self.setMinimumSize(500, 400)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        conn_widget = QWidget()
        conn_layout = QFormLayout(conn_widget)
        self.url_edit = QLineEdit(
            self.db.get_setting("lm_studio_url", "http://localhost:1234/v1")
        )
        conn_layout.addRow("LM Studio URL:", self.url_edit)
        self.temp_edit = QLineEdit(self.db.get_setting("temperature", "0.7"))
        conn_layout.addRow("Temperature:", self.temp_edit)
        tabs.addTab(conn_widget, "Подключение")

        mem_widget = QWidget()
        mem_layout = QVBoxLayout(mem_widget)
        mem_layout.addWidget(QLabel("Сохранённые воспоминания:"))
        self.mem_text = QTextEdit()
        self.mem_text.setReadOnly(True)
        memories = self.db.get_all_memories()
        text = "\n\n".join(
            f"[{m['created_at'][:10]}] {m['summary']}" for m in memories
        ) or "Пока нет воспоминаний."
        self.mem_text.setPlainText(text)
        mem_layout.addWidget(self.mem_text)
        clear_mem_btn = QPushButton("Очистить все воспоминания")
        clear_mem_btn.clicked.connect(self._clear_memories)
        mem_layout.addWidget(clear_mem_btn)
        tabs.addTab(mem_widget, "Память")

        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("sendBtn")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _save(self):
        self.db.set_setting("lm_studio_url", self.url_edit.text().strip())
        self.db.set_setting("temperature", self.temp_edit.text().strip())
        self.accept()

    def _clear_memories(self):
        self.db.conn.execute("DELETE FROM memories")
        self.db.conn.commit()
        self.mem_text.setPlainText("Воспоминания очищены.")
