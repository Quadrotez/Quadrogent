import os
import shutil
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QSplitter,
    QLabel, QMessageBox, QMenu,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl

from src.db.database import Database
from src.core.agent import Agent
from src.ui.chat_widget import ChatWidget
from src.ui.settings_dialog import ChatSettingsDialog, AppSettingsDialog
from src.ui.styles import DARK_THEME


class AgentWorker(QThread):
    message_signal      = pyqtSignal(str, str)
    tool_signal         = pyqtSignal(str, str, str)
    stream_start_signal = pyqtSignal()
    stream_delta_signal = pyqtSignal(str)
    stream_end_signal   = pyqtSignal()
    file_ready_signal   = pyqtSignal(str, str)   # filename, abs_path
    finished_signal     = pyqtSignal()

    def __init__(self, agent: Agent, chat_id: int, text: str, mode: str):
        super().__init__()
        self.agent = agent
        self.chat_id = chat_id
        self.text = text
        self.mode = mode

    def run(self):
        self.agent.on_message      = lambda r, c: self.message_signal.emit(r, c)
        self.agent.on_tool_call    = lambda n, a, r: self.tool_signal.emit(n, a, r)
        self.agent.on_stream_start = lambda: self.stream_start_signal.emit()
        self.agent.on_stream_delta = lambda t: self.stream_delta_signal.emit(t)
        self.agent.on_stream_end   = lambda: self.stream_end_signal.emit()
        self.agent.on_file_ready   = lambda n, p: self.file_ready_signal.emit(n, p)
        self.agent.run(self.chat_id, self.text, self.mode)
        self.finished_signal.emit()


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.agent = Agent(db)
        self.current_chat_id: int | None = None
        self.worker: AgentWorker | None = None

        self.setWindowTitle("Quadrogent")
        self.setMinimumSize(900, 600)
        self.resize(1200, 750)
        self.setStyleSheet(DARK_THEME)

        self._build()
        self._load_chats()

        if not self.agent.llm.check_connection():
            self.chat.status_label.setText("⚠ LM Studio не найден (localhost:1234)")

    # ── Layout ────────────────────────────────────────────

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QHBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 8, 0, 8)
        sb.setSpacing(4)

        logo = QLabel("  ◈ Quadrogent")
        logo.setStyleSheet(
            "font-size: 17px; font-weight: 600; color: #e0e0e0; "
            "padding: 10px 16px 14px 16px;"
        )
        sb.addWidget(logo)

        new_btn = QPushButton("+ Новый чат")
        new_btn.setObjectName("newChatBtn")
        new_btn.clicked.connect(self._new_chat)
        sb.addWidget(new_btn)

        self.chat_list = QListWidget()
        self.chat_list.setObjectName("chatList")
        self.chat_list.currentRowChanged.connect(self._on_chat_selected)
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._chat_context_menu)
        sb.addWidget(self.chat_list, 1)

        settings_btn = QPushButton("Настройки")
        settings_btn.clicked.connect(self._open_settings)
        sb.addWidget(settings_btn)

        splitter.addWidget(sidebar)

        self.chat = ChatWidget()
        self.chat.send_message.connect(self._on_send)
        self.chat.attach_file.connect(self._on_attach)
        self.chat.save_memory.connect(self._on_save_memory)
        self.chat.stop_requested.connect(self._on_stop)
        splitter.addWidget(self.chat)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        ml.addWidget(splitter)

    # ── Chat list ─────────────────────────────────────────

    def _load_chats(self):
        self.chat_list.clear()
        for c in self.db.get_chats():
            prefix = "[P] " if c["persistent"] else ""
            mi = {"work": "[W]", "talk": "[T]", "auto": "[A]"}.get(c["mode"], "")
            item = QListWidgetItem(f"{prefix}{mi} {c['title']}")
            item.setData(Qt.UserRole, c["id"])
            self.chat_list.addItem(item)

    def _new_chat(self):
        self.db.create_chat()
        self._load_chats()
        self.chat_list.setCurrentRow(0)

    def _on_chat_selected(self, row: int):
        if row < 0:
            return
        item = self.chat_list.item(row)
        chat_id = item.data(Qt.UserRole)
        self.current_chat_id = chat_id
        chat_data = self.db.get_chat(chat_id)
        self.chat.load_messages(self.db.get_messages(chat_id))
        self.chat.set_persistent(bool(chat_data.get("persistent", 0)))

    def _chat_context_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if not item:
            return
        chat_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        s_act = menu.addAction("Настройки чата")
        d_act = menu.addAction("Удалить чат")
        action = menu.exec_(self.chat_list.mapToGlobal(pos))
        if action == s_act:
            self._open_chat_settings(chat_id)
        elif action == d_act:
            self._delete_chat(chat_id)

    def _open_chat_settings(self, chat_id: int):
        chat_data = self.db.get_chat(chat_id)
        if not chat_data:
            return
        dlg = ChatSettingsDialog(chat_data, self)
        if dlg.exec_():
            self.db.update_chat(chat_id, **dlg.result_data)
            self._load_chats()
            if chat_id == self.current_chat_id:
                self.chat.set_persistent(bool(dlg.result_data.get("persistent", 0)))

    def _delete_chat(self, chat_id: int):
        reply = QMessageBox.question(
            self, "Удалить чат",
            "Вы уверены, что хотите удалить этот чат?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_chat(chat_id)
            if chat_id == self.current_chat_id:
                self.current_chat_id = None
                self.chat.clear_messages()
            self._load_chats()

    # ── Messages ──────────────────────────────────────────

    def _on_send(self, llm_text: str):
        """Called after ChatWidget has already added the user bubble to display."""
        if not self.current_chat_id:
            self._new_chat()

        chat_data = self.db.get_chat(self.current_chat_id)
        mode = chat_data.get("mode", "auto") if chat_data else "auto"

        # Update title from first message
        if not self.db.get_messages(self.current_chat_id):
            title = llm_text[:50] + ("…" if len(llm_text) > 50 else "")
            self.db.update_chat(self.current_chat_id, title=title)
            self._load_chats()

        self.chat.set_busy(True)

        self.worker = AgentWorker(self.agent, self.current_chat_id, llm_text, mode)
        self.worker.message_signal.connect(self._on_agent_message)
        self.worker.tool_signal.connect(self._on_agent_tool)
        self.worker.stream_start_signal.connect(self._on_stream_start)
        self.worker.stream_delta_signal.connect(self._on_stream_delta)
        self.worker.stream_end_signal.connect(self._on_stream_end)
        self.worker.file_ready_signal.connect(self._on_file_ready)
        self.worker.finished_signal.connect(self._on_agent_done)
        self.worker.start()

    def _on_agent_message(self, role: str, content: str):
        if role == "assistant":
            self.chat.add_assistant_message(content)
        elif role == "error":
            self.chat.add_error_message(content)

    def _on_agent_tool(self, name: str, args: str, result: str):
        self.chat.add_tool_message(name, args, result)

    def _on_stream_start(self):  self.chat.begin_stream()
    def _on_stream_delta(self, c): self.chat.append_stream(c)
    def _on_stream_end(self):    self.chat.end_stream()

    def _on_agent_done(self):
        self.chat.set_busy(False)
        self.worker = None

    def _on_stop(self):
        if self.worker:
            self.agent.stop()

    def _on_file_ready(self, filename: str, abs_path: str):
        """Show a file card in chat and save it to DB so it survives reload."""
        self.chat.add_file_card(filename, abs_path)
        if self.current_chat_id:
            import json
            self.db.add_message(
                self.current_chat_id,
                "file_card",
                json.dumps({"filename": filename, "abs_path": abs_path}),
            )

    def _on_attach(self, filepath: str):
        """Copy file to uploads, show chip in input area."""
        if not self.current_chat_id:
            self._new_chat()

        filename = os.path.basename(filepath)
        uploads_dir = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "uploads")
        )
        os.makedirs(uploads_dir, exist_ok=True)
        dest = os.path.join(uploads_dir, filename)
        try:
            shutil.copy2(filepath, dest)
        except shutil.SameFileError:
            pass

        self.chat.set_pending_file(filename, dest)

    def _on_save_memory(self):
        if not self.current_chat_id:
            return
        self.chat.status_label.setText("Сохранение в память…")
        summary = self.agent.summarize_chat(self.current_chat_id)
        self.chat.status_label.setText(
            f"Сохранено: {summary[:60]}…" if summary else "Не удалось сохранить"
        )

    # ── Settings ──────────────────────────────────────────

    def _open_settings(self):
        dlg = AppSettingsDialog(self.db, self)
        if dlg.exec_():
            url = self.db.get_setting("lm_studio_url", "http://localhost:1234/v1")
            self.agent.llm.base_url = url

    def closeEvent(self, event):
        if self.worker:
            self.agent.stop()
            self.worker.wait(3000)
        self.agent.docker.stop()
        self.db.close()
        event.accept()
