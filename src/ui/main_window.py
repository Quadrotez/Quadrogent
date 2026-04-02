import json
import os
import shutil
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QSplitter,
    QLabel, QMessageBox, QMenu, QFileDialog,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtCore import QUrl

from src.db.database import Database
from src.core.agent import Agent
from src.ui.chat_widget import ChatWidget
from src.ui.settings_dialog import ChatSettingsDialog, AppSettingsDialog
from src.ui.styles import DARK_THEME
from src.ui.right_log_panel import RightLogPanel


class AgentWorker(QThread):
    message_signal      = pyqtSignal(str, str)
    tool_signal         = pyqtSignal(str, str, str)
    stream_start_signal = pyqtSignal()
    stream_delta_signal = pyqtSignal(str)
    stream_end_signal   = pyqtSignal()
    file_ready_signal   = pyqtSignal(str, str)
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
        self.setMinimumSize(960, 640)
        self.resize(1340, 800)
        self.setStyleSheet(DARK_THEME)

        self._build()
        self._load_chats()
        self._refresh_models()

        if not self.agent.llm.check_connection():
            self.chat.status_label.setText("⚠ LM Studio не найден (localhost:1234)")

        self._init_docker_async()

    # ── Layout ──────────────────────────────────────────────

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QHBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # Main 3-pane splitter: sidebar | chat | logs
        self._main_splitter = QSplitter(Qt.Horizontal)

        # ── Sidebar ──────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        # Logo row
        logo_widget = QWidget()
        logo_widget.setObjectName("sidebarLogo")
        logo_widget.setFixedHeight(52)
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setContentsMargins(14, 0, 14, 0)
        logo_layout.setSpacing(8)

        # Try to load logo image
        logo_img_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "images", "logo.png"
        )
        if os.path.exists(logo_img_path):
            logo_img = QLabel()
            pix = QPixmap(logo_img_path).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_img.setPixmap(pix)
            logo_img.setStyleSheet("background: transparent;")
            logo_layout.addWidget(logo_img)

        logo_lbl = QLabel("Quadrogent")
        logo_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: #c8c8c8; "
            "letter-spacing: 0.3px; background: transparent;"
        )
        logo_layout.addWidget(logo_lbl)
        logo_layout.addStretch()
        sb.addWidget(logo_widget)

        new_btn = QPushButton("＋  Новый чат")
        new_btn.setObjectName("newChatBtn")
        new_btn.clicked.connect(self._new_chat)
        sb.addWidget(new_btn)

        self.chat_list = QListWidget()
        self.chat_list.setObjectName("chatList")
        self.chat_list.currentRowChanged.connect(self._on_chat_selected)
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._chat_context_menu)
        sb.addWidget(self.chat_list, 1)

        settings_btn = QPushButton("⚙  Настройки")
        settings_btn.setObjectName("settingsBtn")
        settings_btn.clicked.connect(self._open_settings)
        sb.addWidget(settings_btn)

        self._main_splitter.addWidget(sidebar)

        # ── Chat + status ─────────────────────────────────
        self.chat = ChatWidget()
        self.chat.send_message.connect(self._on_send)
        self.chat.attach_file.connect(self._on_attach)
        self.chat.save_memory.connect(self._on_save_memory)
        self.chat.stop_requested.connect(self._on_stop)
        self.chat.export_chat.connect(self._on_export_chat)
        self.chat.model_changed.connect(self._on_model_changed)
        self.chat.model_refresh.connect(self._refresh_models)
        self.chat.persistent_toggled.connect(self._on_persistent_toggled)
        self.chat.log_toggle_requested.connect(self._toggle_log_panel)

        self._main_splitter.addWidget(self.chat)

        # ── Right log panel ───────────────────────────────
        self.log_panel = RightLogPanel()
        self.log_panel.setFixedWidth(320)
        self.log_panel.close_requested.connect(self._hide_log_panel)
        self._main_splitter.addWidget(self.log_panel)
        self.log_panel.hide()

        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setStretchFactor(2, 0)
        ml.addWidget(self._main_splitter)

    # ── Log panel toggle ───────────────────────────────────

    def _toggle_log_panel(self):
        if self.log_panel.isVisible():
            self._hide_log_panel()
        else:
            self._show_log_panel()

    def _show_log_panel(self):
        self.log_panel.show()
        self.chat.set_log_btn_active(True)

    def _hide_log_panel(self):
        self.log_panel.hide()
        self.chat.set_log_btn_active(False)

    # ── Docker init ────────────────────────────────────────

    def _init_docker_async(self):
        import threading
        from PyQt5.QtCore import QMetaObject, Q_ARG, Qt as _Qt

        self.chat.send_btn.setEnabled(False)
        self._show_log_panel()

        # Wire docker log → right panel
        self.agent.docker.on_log = self.log_panel.append_docker_log

        def _set_send_enabled(val: bool):
            QMetaObject.invokeMethod(
                self.chat.send_btn, "setEnabled",
                _Qt.QueuedConnection, Q_ARG(bool, val),
            )

        def _run():
            ok = self.agent.docker.ensure_container()
            self.log_panel.set_docker_done(ok)
            _set_send_enabled(True)

        threading.Thread(target=_run, daemon=True).start()

    # ── Chat list ──────────────────────────────────────────

    def _load_chats(self):
        self.chat_list.clear()
        for c in self.db.get_chats():
            prefix = "◉ " if c["persistent"] else ""
            mi = {"work": "[W]", "talk": "[T]", "auto": ""}.get(c["mode"], "")
            label = f"{prefix}{mi} {c['title']}".strip()
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, c["id"])
            self.chat_list.addItem(item)

    def _new_chat(self):
        default_persistent = self.db.get_setting("default_persistent", "0") == "1"
        self.db.create_chat(persistent=1 if default_persistent else 0)
        self._load_chats()
        self.chat_list.setCurrentRow(0)

    def _on_chat_selected(self, row: int):
        if row < 0:
            return
        item = self.chat_list.item(row)
        chat_id = item.data(Qt.UserRole)
        self.current_chat_id = chat_id
        chat_data = self.db.get_chat(chat_id)
        title = chat_data.get("title", "Чат") if chat_data else "Чат"
        self.chat.set_chat_title(title)
        self.chat.load_messages(self.db.get_messages(chat_id))
        is_p = bool(chat_data.get("persistent", 0)) if chat_data else False
        self.chat.set_persistent(is_p)

    def _chat_context_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if not item:
            return
        chat_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        s_act   = menu.addAction("Настройки чата")
        exp_act = menu.addAction("Экспортировать…")
        menu.addSeparator()
        d_act   = menu.addAction("Удалить чат")
        action = menu.exec_(self.chat_list.mapToGlobal(pos))
        if action == s_act:
            self._open_chat_settings(chat_id)
        elif action == exp_act:
            self._export_chat_by_id(chat_id)
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
            "Удалить этот чат?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_chat(chat_id)
            if chat_id == self.current_chat_id:
                self.current_chat_id = None
                self.chat.clear_messages()
            self._load_chats()

    def _on_persistent_toggled(self, is_persistent: bool):
        if self.current_chat_id:
            self.db.update_chat(self.current_chat_id, persistent=1 if is_persistent else 0)
            self._load_chats()

    # ── Model ──────────────────────────────────────────────

    def _refresh_models(self):
        loaded = self.agent.llm.get_models()
        seen_raw = self.db.get_setting("seen_models", "")
        seen: list[str] = json.loads(seen_raw) if seen_raw else []
        for m in loaded:
            if m not in seen:
                seen.append(m)
        self.db.set_setting("seen_models", json.dumps(seen))
        self.chat.model_selector.set_models(loaded, seen)
        saved_model = self.db.get_setting("current_model", "")
        if saved_model:
            self.chat.model_selector.set_current_model(saved_model)
            self.agent.llm.model = saved_model
        elif loaded:
            self.agent.llm.model = loaded[0]

    def _on_model_changed(self, model_id: str):
        self.agent.llm.model = model_id
        self.db.set_setting("current_model", model_id)

    # ── Messages ───────────────────────────────────────────

    def _on_send(self, llm_text: str):
        if not self.current_chat_id:
            self._new_chat()

        chat_data = self.db.get_chat(self.current_chat_id)
        mode = chat_data.get("mode", "auto") if chat_data else "auto"

        if not self.db.get_messages(self.current_chat_id):
            title = llm_text[:50] + ("…" if len(llm_text) > 50 else "")
            self.db.update_chat(self.current_chat_id, title=title)
            self.chat.set_chat_title(title)
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
        self.chat.add_file_card(filename, abs_path)
        chat_id = self.current_chat_id
        if chat_id is not None:
            try:
                self.db.add_message(
                    chat_id, "file_card",
                    json.dumps({"filename": filename, "abs_path": abs_path}),
                )
            except Exception:
                import traceback
                traceback.print_exc()

    def _on_attach(self, filepath: str):
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

    # ── Export ─────────────────────────────────────────────

    def _on_export_chat(self, fmt: str):
        data = self.chat.get_export_data()
        self._do_export(data, fmt)

    def _export_chat_by_id(self, chat_id: int):
        chat_data = self.db.get_chat(chat_id)
        messages  = self.db.get_messages(chat_id)
        raw = [
            {"role": m["role"], "content": m["content"], "ts": m.get("ts", "")}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
        data = {
            "title": chat_data.get("title", "Чат") if chat_data else "Чат",
            "messages": raw,
            "exported_at": datetime.now().isoformat(),
        }
        menu = QMenu(self)
        menu.addAction("🌐  HTML", lambda: self._do_export(data, "html"))
        menu.addAction("📄  TXT",  lambda: self._do_export(data, "txt"))
        menu.addAction("📋  JSON", lambda: self._do_export(data, "json"))
        cursor = self.chat_list.mapToGlobal(self.chat_list.rect().center())
        menu.exec_(cursor)

    def _do_export(self, data: dict, fmt: str):
        title    = data["title"]
        messages = data["messages"]
        exported = data.get("exported_at", "")
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:40].strip() or "chat"
        ext_map = {"html": ".html", "txt": ".txt", "json": ".json"}
        ext = ext_map.get(fmt, ".txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт чата", f"{safe_title}{ext}",
            {"html": "HTML (*.html)", "txt": "Текст (*.txt)", "json": "JSON (*.json)"}.get(fmt, "Все файлы (*)")
        )
        if not path:
            return
        try:
            if fmt == "json":
                content = json.dumps(data, ensure_ascii=False, indent=2)
            elif fmt == "txt":
                content = self._export_txt(title, messages, exported)
            else:
                content = self._export_html(title, messages, exported)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.chat.status_label.setText(f"Экспортировано: {os.path.basename(path)}")
            QTimer.singleShot(4000, lambda: self.chat.status_label.setText(""))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", str(e))

    def _export_txt(self, title, messages, exported):
        lines = [f"=== {title} ===", f"Экспортировано: {exported}", ""]
        for m in messages:
            role = "Вы" if m["role"] == "user" else "Агент"
            ts   = m.get("ts", "")[:19].replace("T", " ") if m.get("ts") else ""
            lines.append(f"[{role}]" + (f"  {ts}" if ts else ""))
            lines.append(m["content"])
            lines.append("")
        return "\n".join(lines)

    def _export_html(self, title, messages, exported):
        from src.ui.chat_widget import _md_to_html
        import html as htmllib
        msg_html = ""
        for m in messages:
            role = m["role"]
            content = m["content"]
            ts = m.get("ts", "")[:19].replace("T", " ") if m.get("ts") else ""
            ts_span = f'<span class="ts">{htmllib.escape(ts)}</span>' if ts else ""
            if role == "user":
                escaped = htmllib.escape(content).replace("\n", "<br>")
                msg_html += (
                    f'<div class="msg user"><div class="bubble user-bubble">{escaped}</div>{ts_span}</div>\n'
                )
            else:
                rendered = _md_to_html(content)
                msg_html += (
                    f'<div class="msg assistant"><div class="label">◈ Агент</div>'
                    f'<div class="bubble asst-bubble">{rendered}</div>{ts_span}</div>\n'
                )
        safe_title = htmllib.escape(title)
        safe_exported = htmllib.escape(exported[:19].replace("T", " "))
        return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>{safe_title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0a0a;color:#c4c4c4;font-family:"Inter",system-ui,sans-serif;
font-size:15px;line-height:1.7;max-width:820px;margin:0 auto;padding:40px 24px 80px}}
header{{border-bottom:1px solid #1a1a1a;padding-bottom:20px;margin-bottom:32px}}
header h1{{font-size:22px;font-weight:700;color:#e0e0e0}}
header .meta{{color:#333;font-size:12px;margin-top:6px}}
.msg{{margin:18px 0}}
.msg.user{{display:flex;flex-direction:column;align-items:flex-end}}
.msg.assistant{{display:flex;flex-direction:column;align-items:flex-start}}
.bubble{{border-radius:14px;padding:11px 16px;max-width:78%;word-wrap:break-word}}
.user-bubble{{background:#161616;border:1px solid #242424;border-radius:14px 14px 3px 14px;color:#eeeeee}}
.asst-bubble{{background:transparent;color:#bdbdbd;padding:0;max-width:92%}}
.label{{font-size:11px;color:#303030;margin-bottom:6px;letter-spacing:0.5px;text-transform:uppercase}}
.ts{{font-size:10px;color:#262626;margin-top:5px}}
</style></head><body>
<header><h1>{safe_title}</h1><div class="meta">Quadrogent · {safe_exported}</div></header>
{msg_html}</body></html>"""

    # ── Settings ───────────────────────────────────────────

    def _open_settings(self):
        dlg = AppSettingsDialog(self.db, self)
        if dlg.exec_():
            url = self.db.get_setting("lm_studio_url", "http://localhost:1234/v1")
            self.agent.llm.base_url = url
            QTimer.singleShot(200, self._refresh_models)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.agent.stop()
            if not self.worker.wait(2000):
                self.worker.terminate()
                self.worker.wait(1000)
        import threading
        threading.Thread(target=self.agent.docker.stop, daemon=True).start()
        self.db.close()
        event.accept()
