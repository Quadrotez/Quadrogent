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
        self.setMinimumSize(900, 600)
        self.resize(1200, 750)
        self.setStyleSheet(DARK_THEME)

        self._build()
        self._load_chats()
        self._refresh_models()

        if not self.agent.llm.check_connection():
            self.chat.status_label.setText("⚠ LM Studio не найден (localhost:1234)")

        # Bootstrap Docker container in background so UI stays responsive
        self._init_docker_async()

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

        logo = QLabel("  Quadrogent")
        logo.setObjectName("logoLabel")
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
        self.chat.export_chat.connect(self._on_export_chat)
        self.chat.model_changed.connect(self._on_model_changed)
        self.chat.model_refresh.connect(self._refresh_models)
        splitter.addWidget(self.chat)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        ml.addWidget(splitter)

    # ── Docker init ───────────────────────────────────────

    def _init_docker_async(self):
        """Bootstrap Docker container in background; show log panel; block send until ready."""
        import threading
        from PyQt5.QtCore import QMetaObject, Q_ARG, Qt as _Qt

        self.chat.send_btn.setEnabled(False)
        self.chat.show_docker_log()

        # Wire docker log callback → chat widget's docker panel
        self.agent.docker.on_log = self.chat.append_docker_log

        def _set_send_enabled(val: bool):
            QMetaObject.invokeMethod(
                self.chat.send_btn, "setEnabled",
                _Qt.QueuedConnection, Q_ARG(bool, val),
            )

        def _run():
            ok = self.agent.docker.ensure_container()
            self.chat.set_docker_log_done(ok)
            _set_send_enabled(True)

        threading.Thread(target=_run, daemon=True).start()

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
        title = chat_data.get("title", "Чат") if chat_data else "Чат"
        self.chat.set_chat_title(title)
        self.chat.load_messages(self.db.get_messages(chat_id))
        self.chat.set_persistent(bool(chat_data.get("persistent", 0)))

    def _chat_context_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if not item:
            return
        chat_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        s_act   = menu.addAction("Настройки чата")
        exp_act = menu.addAction("Экспортировать чат…")
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
            "Вы уверены, что хотите удалить этот чат?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_chat(chat_id)
            if chat_id == self.current_chat_id:
                self.current_chat_id = None
                self.chat.clear_messages()
            self._load_chats()

    # ── Model switcher ────────────────────────────────────

    def _refresh_models(self):
        """Ask LM Studio for loaded models and update the selector."""
        loaded = self.agent.llm.get_models()        # currently loaded/running
        # LM Studio /v1/models returns only currently-loaded models.
        # We store previously-seen model IDs in settings so the list grows.
        seen_raw = self.db.get_setting("seen_models", "")
        seen: list[str] = json.loads(seen_raw) if seen_raw else []
        for m in loaded:
            if m not in seen:
                seen.append(m)
        self.db.set_setting("seen_models", json.dumps(seen))

        self.chat.model_selector.set_models(loaded, seen)

        # Restore saved model choice
        saved_model = self.db.get_setting("current_model", "")
        if saved_model:
            self.chat.model_selector.set_current_model(saved_model)
            self.agent.llm.model = saved_model
        elif loaded:
            self.agent.llm.model = loaded[0]

    def _on_model_changed(self, model_id: str):
        self.agent.llm.model = model_id
        self.db.set_setting("current_model", model_id)

    # ── Messages ──────────────────────────────────────────

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
                    chat_id,
                    "file_card",
                    json.dumps({"filename": filename, "abs_path": abs_path}),
                )
            except Exception as e:
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

    # ── Export ────────────────────────────────────────────

    def _on_export_chat(self, fmt: str):
        """Called from ChatWidget export button."""
        data = self.chat.get_export_data()
        self._do_export(data, fmt)

    def _export_chat_by_id(self, chat_id: int):
        """Called from sidebar context menu."""
        chat_data = self.db.get_chat(chat_id)
        messages  = self.db.get_messages(chat_id)
        # Include ALL message types: user, assistant, AND tool calls
        raw = [
            {"role": m["role"], "content": m["content"], "ts": m.get("ts", ""), "tool": m.get("tool")}
            for m in messages
            if m["role"] in ("user", "assistant", "tool")
        ]
        data = {
            "title": chat_data.get("title", "Чат") if chat_data else "Чат",
            "messages": raw,
            "exported_at": datetime.now().isoformat(),
        }
        # Ask format via small menu
        menu = QMenu(self)
        menu.addAction("🌐  Красивый HTML", lambda: self._do_export(data, "html"))
        menu.addAction("📄  Текст (TXT)",  lambda: self._do_export(data, "txt"))
        menu.addAction("📋  Данные (JSON)", lambda: self._do_export(data, "json"))
        cursor = self.chat_list.mapToGlobal(self.chat_list.rect().center())
        menu.exec_(cursor)

    def _do_export(self, data: dict, fmt: str):
        title    = data["title"]
        messages = data["messages"]
        exported = data.get("exported_at", "")
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:40].strip() or "chat"

        ext_map = {"html": ".html", "txt": ".txt", "json": ".json"}
        ext = ext_map.get(fmt, ".txt")
        default_name = f"{safe_title}{ext}"

        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт чата", default_name,
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

    def _export_txt(self, title: str, messages: list[dict], exported: str) -> str:
        lines = [f"=== {title} ===", f"Экспортировано: {exported}", ""]
        for m in messages:
            role = m["role"]
            ts   = m.get("ts", "")[:19].replace("T", " ") if m.get("ts") else ""
            
            if role == "user":
                header = "[Вы]" + (f"  {ts}" if ts else "")
                lines.append(header)
                lines.append(m["content"])
            elif role == "assistant":
                header = "[Агент]" + (f"  {ts}" if ts else "")
                lines.append(header)
                lines.append(m["content"])
            elif role == "tool":
                tool_name = m.get("tool", "tool")
                header = f"[Инструмент: {tool_name}]" + (f"  {ts}" if ts else "")
                lines.append(header)
                lines.append(m["content"])
            lines.append("")
        return "\n".join(lines)

    def _export_html(self, title: str, messages: list[dict], exported: str) -> str:
        from src.ui.chat_widget import _md_to_html
        import html as htmllib

        msg_html = ""
        for m in messages:
            role    = m["role"]
            content = m["content"]
            ts      = m.get("ts", "")[:19].replace("T", " ") if m.get("ts") else ""
            tool    = m.get("tool")
            ts_span = f'<span class="ts">{htmllib.escape(ts)}</span>' if ts else ""

            if role == "user":
                escaped = htmllib.escape(content).replace("\n", "<br>")
                msg_html += (
                    f'<div class="msg user">'
                    f'<div class="bubble user-bubble">{escaped}</div>'
                    f'{ts_span}</div>\n'
                )
            elif role == "tool":
                tool_name = tool or "tool"
                # Parse exit code if present
                import re as _re
                ec_match = _re.search(r'\[exit code:\s*(-?\d+)\]', content)
                exit_code = int(ec_match.group(1)) if ec_match else None
                
                # Determine status styling
                if exit_code is not None:
                    status_class = "tool-ok" if exit_code == 0 else "tool-err"
                    status_text = f"exit {exit_code}"
                else:
                    status_class = "tool-info"
                    status_text = "выполнен"
                
                # Strip exit code line from body
                body = _re.sub(r'^\[exit code:\s*-?\d+\]\n?', '', content).strip()
                escaped_body = htmllib.escape(body) if body else "(нет вывода)"
                
                msg_html += (
                    f'<div class="msg tool">'
                    f'<div class="tool-header {status_class}">'
                    f'<span class="tool-name">⚙ {htmllib.escape(tool_name)}</span>'
                    f'<span class="tool-status">{status_text}</span>'
                    f'</div>'
                    f'<div class="tool-body"><pre>{escaped_body}</pre></div>'
                    f'{ts_span}</div>\n'
                )
            else:  # assistant
                rendered = _md_to_html(content)
                msg_html += (
                    f'<div class="msg assistant">'
                    f'<div class="label">◈ Агент</div>'
                    f'<div class="bubble asst-bubble">{rendered}</div>'
                    f'{ts_span}</div>\n'
                )

        safe_title = htmllib.escape(title)
        safe_exported = htmllib.escape(exported[:19].replace("T", " "))

        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f0f0f; color: #c8c8c8;
    font-family: "Inter", "Segoe UI", system-ui, sans-serif;
    font-size: 15px; line-height: 1.7;
    max-width: 820px; margin: 0 auto; padding: 40px 24px 80px;
  }}
  header {{ border-bottom: 1px solid #1e1e1e; padding-bottom: 20px; margin-bottom: 32px; }}
  header h1 {{ font-size: 22px; font-weight: 600; color: #e0e0e0; }}
  header .meta {{ color: #444; font-size: 12px; margin-top: 6px; }}
  .msg {{ margin: 18px 0; }}
  .msg.user {{ display: flex; flex-direction: column; align-items: flex-end; }}
  .msg.assistant {{ display: flex; flex-direction: column; align-items: flex-start; }}
  .bubble {{
    border-radius: 16px; padding: 12px 17px;
    max-width: 78%; word-wrap: break-word;
  }}
  .user-bubble {{
    background: #1c1c1c; border: 1px solid #282828;
    border-radius: 16px 16px 4px 16px; color: #ececec;
  }}
  .asst-bubble {{
    background: transparent; color: #c0c0c0;
    padding: 0; max-width: 90%;
  }}
  .label {{ font-size: 11px; color: #383838; margin-bottom: 6px;
            letter-spacing: 0.5px; text-transform: uppercase; }}
  .ts {{ font-size: 10px; color: #303030; margin-top: 5px; }}
  h1,h2,h3,h4,h5,h6 {{ color: #e0e0e0; font-weight: 600; margin: 14px 0 5px; }}
  h1 {{ font-size: 20px; }} h2 {{ font-size: 17px; }} h3 {{ font-size: 15px; }}
  strong {{ color: #e8e8e8; }}
  em {{ color: #b0b0b0; font-style: italic; }}
  a {{ color: #5599dd; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{
    background: #181818; border: 1px solid #242424;
    padding: 1px 5px; border-radius: 4px;
    font-family: "JetBrains Mono", Consolas, monospace; font-size: 13px; color: #b0b0b0;
  }}
  .code-block {{
    margin: 10px 0; border-radius: 8px;
    overflow: hidden; border: 1px solid #1e1e1e;
  }}
  .code-lang {{
    display: block; background: #0e0e0e; color: #444; font-size: 10px;
    padding: 4px 12px; letter-spacing: 0.5px; font-family: monospace;
    text-transform: uppercase; border-bottom: 1px solid #1a1a1a;
  }}
  .code-block pre {{
    background: #0b0b0b; padding: 12px 14px; margin: 0;
  }}
  .code-block pre code {{
    background: none; border: none; padding: 0; color: #909090;
  }}
  pre {{
    background: #0b0b0b; border: 1px solid #1c1c1c;
    padding: 12px 14px; border-radius: 8px;
    font-family: "JetBrains Mono", Consolas, monospace;
    color: #888; margin: 8px 0; white-space: pre-wrap;
  }}
  ul, ol {{ padding-left: 22px; margin: 6px 0; }}
  li {{ margin: 3px 0; color: #c0c0c0; }}
  hr {{ border: none; border-top: 1px solid #252525; margin: 12px 0; }}
  .blockquote {{
    border-left: 3px solid #333; padding: 4px 12px;
    color: #888; margin: 6px 0; font-style: italic;
  }}
  /* Tool call styling */
  .msg.tool {{ display: flex; flex-direction: column; align-items: flex-start; margin: 14px 0; }}
  .tool-header {{
    display: flex; align-items: center; gap: 10px;
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px;
    font-family: "JetBrains Mono", Consolas, monospace;
    padding: 4px 10px; border-radius: 6px; margin-bottom: 6px;
  }}
  .tool-header .tool-name {{ color: #5a5a5a; }}
  .tool-header .tool-status {{
    padding: 1px 6px; border-radius: 3px; font-size: 9px;
  }}
  .tool-ok {{ background: #0d1a0d; border: 1px solid #1a3a1a; }}
  .tool-ok .tool-status {{ color: #3a6a3a; }}
  .tool-err {{ background: #1a0808; border: 1px solid #3a1010; }}
  .tool-err .tool-status {{ color: #7a3030; }}
  .tool-info {{ background: #101018; border: 1px solid #202030; }}
  .tool-info .tool-status {{ color: #505070; }}
  .tool-body {{
    background: #0b0b0b; border: 1px solid #1c1c1c;
    border-radius: 8px; padding: 10px 14px; max-width: 95%;
  }}
  .tool-body pre {{
    background: transparent; border: none; padding: 0; margin: 0;
    font-family: "JetBrains Mono", Consolas, monospace; font-size: 12px;
    color: #505050; white-space: pre-wrap; word-wrap: break-word;
  }}
</style>
</head>
<body>
<header>
  <h1>◈ {safe_title}</h1>
  <div class="meta">Экспортировано {safe_exported} · Quadrogent</div>
</header>
{msg_html}
</body>
</html>"""

    # ── Settings ──────────────────────────────────────────

    def _open_settings(self):
        dlg = AppSettingsDialog(self.db, self)
        if dlg.exec_():
            url = self.db.get_setting("lm_studio_url", "http://localhost:1234/v1")
            self.agent.llm.base_url = url
            # Refresh models after settings change
            QTimer.singleShot(200, self._refresh_models)

    def closeEvent(self, event):
        # Stop the agent immediately — abort LLM stream so the thread exits fast
        if self.worker and self.worker.isRunning():
            self.agent.stop()
            # Give the worker up to 2 s to finish cleanly; if not, terminate it
            if not self.worker.wait(2000):
                self.worker.terminate()
                self.worker.wait(1000)
        # Stop Docker container in a daemon thread so the window closes instantly
        import threading
        threading.Thread(target=self.agent.docker.stop, daemon=True).start()
        self.db.close()
        event.accept()
