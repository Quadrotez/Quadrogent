import os
import sys

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QPushButton, QTabWidget,
    QWidget, QLineEdit, QFormLayout, QTextEdit,
    QScrollArea, QFrame, QFileDialog, QSizePolicy,
    QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap


class ChatSettingsDialog(QDialog):
    def __init__(self, chat_data: dict, parent=None):
        super().__init__(parent)
        self.chat_data = chat_data
        self.result_data = {}
        self.setWindowTitle("Настройки чата")
        self.setMinimumWidth(400)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        self.title_edit = QLineEdit(self.chat_data.get("title", ""))
        layout.addWidget(QLabel("Название чата"))
        layout.addWidget(self.title_edit)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "work", "talk"])
        self.mode_combo.setCurrentText(self.chat_data.get("mode", "auto"))
        layout.addWidget(QLabel("Режим агента"))
        layout.addWidget(self.mode_combo)

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
        }
        self.db.set_setting("search_engine",   self._search_engine.currentData())
        self.db.set_setting("search_proxy",    self._search_proxy.text().strip())
        self.db.set_setting("search_follow",   "1" if self._search_follow.isChecked() else "0")
        self.db.set_setting("search_download", "1" if self._search_download.isChecked() else "0")
        self.db.set_setting("theme", self._theme_combo.currentData())
        self.db.set_setting("accent", self._accent_combo.currentData())
        self.db.set_setting("animations", "1" if self._animations_check.isChecked() else "0")
        self.accept()


# ── Memory block widget ────────────────────────────────────────────────────────

class MemoryBlock(QFrame):
    """Single deletable/editable memory entry."""
    deleted = pyqtSignal(int)
    saved   = pyqtSignal(int, str)

    def __init__(self, memory: dict, parent=None):
        super().__init__(parent)
        self.memory_id = memory["id"]
        self.setObjectName("memoryBlock")
        self.setStyleSheet(
            "QFrame#memoryBlock{background:#0d0d0d;border:1px solid #1a1a1a;"
            "border-radius:7px;margin:2px 0;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        hdr = QHBoxLayout()
        date_str = memory.get("created_at", "")[:10]
        date_lbl = QLabel(date_str)
        date_lbl.setStyleSheet("color:#303030;font-size:10px;")
        hdr.addWidget(date_lbl)
        hdr.addStretch()

        self._edit_btn = QPushButton("✎")
        self._edit_btn.setFixedSize(22, 22)
        self._edit_btn.setStyleSheet(
            "QPushButton{background:transparent;border:1px solid #1e1e1e;"
            "border-radius:4px;color:#363636;font-size:11px;padding:0;}"
            "QPushButton:hover{color:#999;border-color:#333;}"
        )
        self._edit_btn.clicked.connect(self._toggle_edit)
        hdr.addWidget(self._edit_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;border:1px solid #1e1e1e;"
            "border-radius:4px;color:#363636;font-size:11px;padding:0;}"
            "QPushButton:hover{color:#cc4444;border-color:#333;}"
        )
        del_btn.clicked.connect(lambda: self.deleted.emit(self.memory_id))
        hdr.addWidget(del_btn)
        layout.addLayout(hdr)

        self._text = memory.get("summary", "")
        self._label = QLabel(self._text)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color:#888;font-size:12px;")
        layout.addWidget(self._label)

        self._editor = QTextEdit()
        self._editor.setPlainText(self._text)
        self._editor.setFixedHeight(60)
        self._editor.setVisible(False)
        layout.addWidget(self._editor)

        self._save_btn = QPushButton("Сохранить изменения")
        self._save_btn.setObjectName("sendBtn")
        self._save_btn.setVisible(False)
        self._save_btn.clicked.connect(self._save_edit)
        layout.addWidget(self._save_btn)

    def _toggle_edit(self):
        editing = not self._editor.isVisible()
        self._label.setVisible(not editing)
        self._editor.setVisible(editing)
        self._save_btn.setVisible(editing)
        self._edit_btn.setText("✕" if editing else "✎")

    def _save_edit(self):
        new_text = self._editor.toPlainText().strip()
        if new_text:
            self._text = new_text
            self._label.setText(new_text)
            self.saved.emit(self.memory_id, new_text)
        self._toggle_edit()


# ── AppSettingsDialog ──────────────────────────────────────────────────────────

class AppSettingsDialog(QDialog):
    avatar_changed = pyqtSignal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Настройки приложения")
        self.setMinimumSize(560, 560)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # ── Подключение ───────────────────────────────────
        conn_widget = QWidget()
        conn_layout = QFormLayout(conn_widget)
        conn_layout.setSpacing(12)
        conn_layout.setContentsMargins(16, 16, 16, 16)
        self.url_edit = QLineEdit(
            self.db.get_setting("lm_studio_url", "http://localhost:1234/v1")
        )
        conn_layout.addRow("LM Studio URL:", self.url_edit)
        self.temp_edit = QLineEdit(self.db.get_setting("temperature", "0.7"))
        conn_layout.addRow("Temperature:", self.temp_edit)

        self.title_combo = QComboBox()
        self.title_combo.addItem("Первые 4 слова (быстро)", "words")
        self.title_combo.addItem("Генерация через AI", "ai")
        saved_mode = self.db.get_setting("title_mode", "words")
        self.title_combo.setCurrentIndex(0 if saved_mode == "words" else 1)
        conn_layout.addRow("Название чата:", self.title_combo)

        self.lang_combo = QComboBox()
        langs = [
            ("Авто (язык пользователя)", "auto"),
            ("Русский", "ru"),
            ("English", "en"),
            ("Deutsch", "de"),
            ("Français", "fr"),
            ("Español", "es"),
            ("中文", "zh"),
            ("日本語", "ja"),
        ]
        for label, code in langs:
            self.lang_combo.addItem(label, code)
        saved_lang = self.db.get_setting("language", "auto")
        idx = next((i for i, (_, c) in enumerate(langs) if c == saved_lang), 0)
        self.lang_combo.setCurrentIndex(idx)
        conn_layout.addRow("Язык ответов:", self.lang_combo)
        tabs.addTab(conn_widget, "Подключение")

        # ── Промпты ───────────────────────────────────────
        prompt_widget = QWidget()
        prompt_layout = QVBoxLayout(prompt_widget)
        prompt_layout.setContentsMargins(16, 12, 16, 16)
        prompt_layout.setSpacing(8)
        hint = QLabel("Пустое поле = системный промпт по умолчанию.")
        hint.setStyleSheet("color:#606060;font-size:11px;")
        prompt_layout.addWidget(hint)

        # Title generation prompt
        lbl_title_p = QLabel("Промпт для генерации заголовка чата:")
        lbl_title_p.setStyleSheet("color:#555;font-size:11px;margin-top:8px;")
        prompt_layout.addWidget(lbl_title_p)
        self._title_prompt_ed = QTextEdit()
        try:
            from src.core.agent import TITLE_GEN_PROMPT_DEFAULT
            _def_title = TITLE_GEN_PROMPT_DEFAULT
        except Exception:
            _def_title = ""
        saved_tp = self.db.get_setting("title_gen_prompt", "")
        self._title_prompt_ed.setPlainText(saved_tp if saved_tp.strip() else _def_title)
        self._title_prompt_ed.setFixedHeight(70)
        prompt_layout.addWidget(self._title_prompt_ed)
        hint.setStyleSheet("color:#404040;font-size:11px;")
        prompt_layout.addWidget(hint)
        # Import default prompts lazily to avoid circular import
        try:
            _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _here not in sys.path:
                sys.path.insert(0, _here)
            from src.core.agent import SYSTEM_AUTO, SYSTEM_WORK, SYSTEM_TALK
            _defaults = {"auto": SYSTEM_AUTO, "work": SYSTEM_WORK, "talk": SYSTEM_TALK}
        except Exception:
            _defaults = {"auto": "", "work": "", "talk": ""}

        for mode, label in (("auto", "Auto"), ("work", "Work"), ("talk", "Talk")):
            lbl = QLabel(f"Режим {label}:")
            lbl.setStyleSheet("color:#555;font-size:11px;margin-top:6px;")
            prompt_layout.addWidget(lbl)
            ed = QTextEdit()
            saved = self.db.get_setting(f"system_prompt_{mode}", "")
            # Show saved value, or fall back to the compiled-in default
            ed.setPlainText(saved if saved.strip() else _defaults.get(mode, ""))
            ed.setFixedHeight(88)
            setattr(self, f"_prompt_{mode}", ed)
            prompt_layout.addWidget(ed)
        prompt_layout.addStretch()
        tabs.addTab(prompt_widget, "Промпты")

        # ── Профиль ───────────────────────────────────────
        profile_widget = QWidget()
        profile_layout = QVBoxLayout(profile_widget)
        profile_layout.setContentsMargins(16, 16, 16, 16)
        profile_layout.setSpacing(12)
        profile_layout.addWidget(QLabel("Аватарка пользователя:"))

        avatar_row = QHBoxLayout()
        self._avatar_preview = QLabel()
        self._avatar_preview.setFixedSize(56, 56)
        self._avatar_preview.setStyleSheet(
            "background:#0d0d0d;border:1px solid #1a1a1a;border-radius:8px;"
        )
        self._avatar_preview.setAlignment(Qt.AlignCenter)
        avatar_row.addWidget(self._avatar_preview)

        av_btns = QVBoxLayout()
        choose_btn = QPushButton("Выбрать изображение…")
        choose_btn.clicked.connect(self._choose_avatar)
        av_btns.addWidget(choose_btn)
        reset_btn = QPushButton("Сбросить к user.png")
        reset_btn.clicked.connect(self._reset_avatar)
        av_btns.addWidget(reset_btn)
        av_btns.addStretch()
        avatar_row.addLayout(av_btns)
        avatar_row.addStretch()
        profile_layout.addLayout(avatar_row)
        profile_layout.addStretch()
        tabs.addTab(profile_widget, "Профиль")
        self._load_avatar_preview()

        # ── Память ────────────────────────────────────────
        mem_widget = QWidget()
        mem_layout = QVBoxLayout(mem_widget)
        mem_layout.setContentsMargins(16, 12, 16, 16)
        mem_layout.setSpacing(8)
        mem_layout.addWidget(QLabel("Сохранённые воспоминания:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        self._mem_container = QWidget()
        self._mem_vbox = QVBoxLayout(self._mem_container)
        self._mem_vbox.setContentsMargins(0, 0, 0, 0)
        self._mem_vbox.setSpacing(4)
        self._mem_vbox.addStretch()
        scroll.setWidget(self._mem_container)
        mem_layout.addWidget(scroll, 1)
        self._load_memory_blocks()

        clear_mem_btn = QPushButton("Очистить все воспоминания")
        clear_mem_btn.clicked.connect(self._clear_memories)
        mem_layout.addWidget(clear_mem_btn)

        del_chats_btn = QPushButton("Удалить все диалоги")
        del_chats_btn.setStyleSheet("QPushButton{color:#cc3333;border-color:#3a1010;}"
                                    "QPushButton:hover{background:#130808;color:#ee5555;}")
        del_chats_btn.clicked.connect(self._delete_all_chats)
        mem_layout.addWidget(del_chats_btn)
        tabs.addTab(mem_widget, "Память")

        # ── Поиск ────────────────────────────────────────
        search_widget = QWidget()
        search_layout = QFormLayout(search_widget)
        search_layout.setSpacing(12)
        search_layout.setContentsMargins(16, 16, 16, 16)

        self._search_engine = QComboBox()
        self._search_engine.addItem("DuckDuckGo (по умолчанию)", "duckduckgo")
        self._search_engine.addItem("Google", "google")
        self._search_engine.addItem("Bing", "bing")
        saved_eng = self.db.get_setting("search_engine", "duckduckgo")
        idx_eng = next((i for i in range(self._search_engine.count())
                        if self._search_engine.itemData(i) == saved_eng), 0)
        self._search_engine.setCurrentIndex(idx_eng)
        search_layout.addRow("Поисковик:", self._search_engine)

        self._search_proxy = QLineEdit(self.db.get_setting("search_proxy", ""))
        self._search_proxy.setPlaceholderText("http://user:pass@host:port (необязательно)")
        search_layout.addRow("Прокси:", self._search_proxy)

        self._search_follow = QCheckBox("Переходить по ссылкам и читать страницы")
        self._search_follow.setChecked(self.db.get_setting("search_follow", "0") == "1")
        search_layout.addRow("", self._search_follow)

        self._search_download = QCheckBox("Разрешить скачивать файлы по ссылке")
        self._search_download.setChecked(self.db.get_setting("search_download", "0") == "1")
        search_layout.addRow("", self._search_download)

        max_lbl = QLabel("Больше результатов = медленнее, но точнее.")
        max_lbl.setStyleSheet("color:#555;font-size:10px;")
        search_layout.addRow("", max_lbl)

        tabs.addTab(search_widget, "Поиск")

        # ── Внешний вид ───────────────────────────────────
        appear_widget = QWidget()
        appear_layout = QVBoxLayout(appear_widget)
        appear_layout.setContentsMargins(16, 12, 16, 16)
        appear_layout.setSpacing(12)

        appear_layout.addWidget(QLabel("Тема:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Тёмная", "dark")
        self._theme_combo.addItem("Светлая", "light")
        saved_theme = self.db.get_setting("theme", "dark")
        self._theme_combo.setCurrentIndex(0 if saved_theme == "dark" else 1)
        appear_layout.addWidget(self._theme_combo)

        appear_layout.addWidget(QLabel("Акцентный цвет:"))
        self._accent_combo = QComboBox()
        for label, val in [("Монохромный (по умолчанию)", "mono"), ("Синий", "blue"),
                            ("Зелёный", "green"), ("Оранжевый", "orange"),
                            ("Розовый", "pink"), ("Красный", "red")]:
            self._accent_combo.addItem(label, val)
        saved_acc = self.db.get_setting("accent", "mono")
        idx_acc = next((i for i in range(self._accent_combo.count())
                        if self._accent_combo.itemData(i) == saved_acc), 0)
        self._accent_combo.setCurrentIndex(idx_acc)
        appear_layout.addWidget(self._accent_combo)

        self._animations_check = QCheckBox("Включить анимации")
        self._animations_check.setChecked(self.db.get_setting("animations", "1") == "1")
        appear_layout.addWidget(self._animations_check)

        appear_layout.addStretch()
        tabs.addTab(appear_widget, "Внешний вид")

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

    # ── Avatar ────────────────────────────────────────────

    def _default_avatar_path(self) -> str:
        try:
            from src.utils.static_paths import image as _img
            return _img("user.png")
        except Exception:
            return os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "static", "images", "user.png"
            ))

    def _load_avatar_preview(self):
        path = self.db.get_setting("user_avatar", self._default_avatar_path())
        if os.path.exists(path):
            pix = QPixmap(path).scaled(56, 56, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self._avatar_preview.setPixmap(pix)
        else:
            self._avatar_preview.setText("👤")

    def _choose_avatar(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать аватарку", "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.db.set_setting("user_avatar", path)
            self._load_avatar_preview()
            self.avatar_changed.emit(path)

    def _reset_avatar(self):
        path = self._default_avatar_path()
        self.db.set_setting("user_avatar", path)
        self._load_avatar_preview()
        self.avatar_changed.emit(path)

    # ── Memory ────────────────────────────────────────────

    def _load_memory_blocks(self):
        while self._mem_vbox.count() > 1:
            item = self._mem_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        memories = self.db.get_all_memories()
        if not memories:
            lbl = QLabel("Пока нет воспоминаний.")
            lbl.setStyleSheet("color:#333;font-size:12px;padding:8px;")
            self._mem_vbox.insertWidget(0, lbl)
            return

        for m in memories:
            block = MemoryBlock(m)
            block.deleted.connect(self._delete_memory)
            block.saved.connect(self._update_memory)
            self._mem_vbox.insertWidget(self._mem_vbox.count() - 1, block)

    def _delete_memory(self, memory_id: int):
        self.db.delete_memory(memory_id)
        self._load_memory_blocks()

    def _update_memory(self, memory_id: int, text: str):
        self.db.update_memory(memory_id, text)

    def _clear_memories(self):
        reply = QMessageBox.question(
            self, "Очистить память", "Удалить все воспоминания?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.conn.execute("DELETE FROM memories")
            self.db.conn.commit()
            self._load_memory_blocks()

    def _delete_all_chats(self):
        reply = QMessageBox.question(
            self, "Удалить все диалоги",
            "Удалить ВСЕ диалоги и сообщения? Это действие необратимо.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.conn.execute("DELETE FROM messages")
            self.db.conn.execute("DELETE FROM chats")
            self.db.conn.commit()
            QMessageBox.information(self, "Готово", "Все диалоги удалены.")

    # ── Save ──────────────────────────────────────────────

    def _save(self):
        self.db.set_setting("lm_studio_url", self.url_edit.text().strip())
        self.db.set_setting("temperature", self.temp_edit.text().strip())
        self.db.set_setting("title_mode", self.title_combo.currentData())
        self.db.set_setting("language", self.lang_combo.currentData())
        try:
            from src.core.agent import SYSTEM_AUTO, SYSTEM_WORK, SYSTEM_TALK
            _defaults = {"auto": SYSTEM_AUTO, "work": SYSTEM_WORK, "talk": SYSTEM_TALK}
        except Exception:
            _defaults = {}
        tp = self._title_prompt_ed.toPlainText().strip()
        try:
            from src.core.agent import TITLE_GEN_PROMPT_DEFAULT
            self.db.set_setting("title_gen_prompt", "" if tp == TITLE_GEN_PROMPT_DEFAULT.strip() else tp)
        except Exception:
            self.db.set_setting("title_gen_prompt", tp)
        for mode in ("auto", "work", "talk"):
            text = getattr(self, f"_prompt_{mode}").toPlainText().strip()
            # If user left it as the default, store empty (= use compiled default)
            if text == _defaults.get(mode, "").strip():
                text = ""
            self.db.set_setting(f"system_prompt_{mode}", text)
        self.accept()
