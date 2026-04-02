import json
import os
from typing import Callable

from src.core.llm_client import LLMClient
from src.core.docker_manager import DockerManager
from src.core.web_search import WebSearch
from src.utils.file_manager import FileManager
from src.db.database import Database


SYSTEM_WORK = """Ты — Quadrogent, ИИ-агент с открытым исходным кодом.
Режим: Work. Ты выполняешь задачи автономно.

Правила:
1. Составь чёткий план действий и сообщи его пользователю.
2. Выполняй план шаг за шагом, используя доступные инструменты.
3. Не останавливайся, пока задача не будет выполнена.
4. Никогда не говори "я не могу" — всегда используй инструменты.
5. Если команда завершилась с ошибкой — ОБЯЗАТЕЛЬНО прочитай вывод, найди причину и исправь её.
   - Если утилита не найдена — установи её через apt-get или используй альтернативу (python, tar, etc.).
   - Если exit code != 0 — проанализируй stderr и попробуй снова или другим способом.
   - НИКОГДА не сдавайся из-за одной неудачной команды. Всегда показывай полный вывод пользователю.
6. Когда задача полностью выполнена, напиши "ready" на отдельной строке.

Обработка ошибок команд:
- apt-get недоступен? → используй pip, conda, или Python-альтернативы.
- zip не найден? → используй "python3 -c 'import zipfile; ...'" или "tar -czf".
- Команда висит? → добавь timeout или флаг -y.
- Всегда показывай пользователю что именно пошло не так и что ты делаешь дальше.

Доступные инструменты:
- execute_command: выполнить команду Linux в Docker (root, интернет есть).
  Рабочая директория /workspace, папка uploads доступна как /workspace/uploads.
- install_packages: установить пакет(ы) через apt или pip. Используй ВМЕСТО ручного apt-get/pip.
  Примеры: install_packages("ffmpeg imagemagick", "apt"), install_packages("pandas numpy", "pip")
- web_search: поиск в интернете
- read_file: прочитать текстовый файл из uploads/ по имени (например "report.pdf")
- write_file: записать ТЕКСТОВЫЙ файл в uploads/ — пользователь получит кнопку скачать.
  НЕ ИСПОЛЬЗОВАТЬ для бинарных файлов (zip, png, exe и т.д.)!
- deliver_file: показать пользователю файл, уже созданный в /workspace/uploads/.
  Используй вместо write_file для бинарных файлов.
  Workflow для zip/image/binary: execute_command создаёт файл в /workspace/uploads/, затем deliver_file(имя_файла).
- delete_file: удалить файл или папку из uploads/ (путь "." очищает всё)
- list_files: список файлов в uploads/
"""

SYSTEM_TALK = """Ты — Quadrogent, ИИ-агент с открытым исходным кодом.
Режим: Talk. Ты ведёшь обычный диалог с пользователем.
Отвечай по существу, кратко и понятно. Используй markdown для форматирования.
"""

SYSTEM_AUTO = """Ты — Quadrogent, ИИ-агент с открытым исходным кодом.
Режим: Auto. Определи сам, нужно ли использовать инструменты для этого запроса.

Если задача требует действий (код, файлы, поиск, команды) — работай автономно:
1. Составь план, сообщи пользователю.
2. Выполняй, используя инструменты.
3. Если команда завершилась с ошибкой — прочитай вывод, найди причину и исправь.
   Никогда не сдавайся из-за одной неудачной команды. Покажи вывод и действуй дальше.
4. Когда готово — напиши "ready".

Если это обычный вопрос — просто ответь. Используй markdown для форматирования.

Доступные инструменты:
- execute_command: команда Linux в Docker (root, интернет).
  Рабочая директория /workspace, uploads → /workspace/uploads.
- install_packages: установить пакет(ы) через apt или pip. Используй ВМЕСТО ручного apt-get/pip.
  Примеры: install_packages("zip curl", "apt"), install_packages("requests", "pip")
- web_search: поиск в интернете
- read_file: прочитать текстовый файл из uploads/ по имени
- write_file: записать ТЕКСТОВЫЙ файл в uploads/ — пользователь получит кнопку скачать.
  НЕ ИСПОЛЬЗОВАТЬ для бинарных файлов (zip, png, exe и т.д.)!
- deliver_file: показать пользователю файл, уже созданный в /workspace/uploads/.
  Используй вместо write_file для бинарных файлов.
  Workflow для zip/image/binary: execute_command создаёт файл в /workspace/uploads/, затем deliver_file(имя_файла).
- delete_file: удалить файл или папку из uploads/ (путь "." очищает всё)
- list_files: список файлов в uploads/
"""

MEMORY_SUMMARIZE_PROMPT = """Проанализируй этот диалог и напиши краткое резюме (1-3 предложения) — что было обсуждено и к каким выводам пришли. Только суть, без лишних слов."""


class Agent:
    """Core agent that orchestrates LLM, tools, and modes."""

    def __init__(self, db: Database):
        self.db = db
        self.llm = LLMClient()
        self.docker = DockerManager()
        self.search = WebSearch()
        self.files = FileManager()
        self.on_message:      Callable[[str, str], None]       | None = None
        self.on_tool_call:    Callable[[str, str, str], None]  | None = None
        self.on_stream_start: Callable[[], None]               | None = None
        self.on_stream_delta: Callable[[str], None]            | None = None
        self.on_stream_end:   Callable[[], None]               | None = None
        # (filename, abs_path) — emitted when write_file succeeds
        self.on_file_ready:   Callable[[str, str], None]       | None = None
        self._stop = False

    def stop(self):
        self._stop = True

    # ── Callbacks ─────────────────────────────────────────

    def _emit(self, role: str, content: str):
        if self.on_message:
            self.on_message(role, content)

    def _emit_tool(self, name: str, args: str, result: str):
        if self.on_tool_call:
            self.on_tool_call(name, args, result)

    # ── System prompt ─────────────────────────────────────

    def _get_system_prompt(self, mode: str) -> str:
        memories = self.db.get_memories_text()
        base = {"work": SYSTEM_WORK, "talk": SYSTEM_TALK, "auto": SYSTEM_AUTO}.get(
            mode, SYSTEM_AUTO
        )
        if memories:
            base += f"\n\n{memories}"
        return base

    # ── Tool execution ────────────────────────────────────

    def _execute_tool(self, name: str, arguments: dict) -> str:
        if name == "execute_command":
            cmd = arguments.get("command", "")
            # Intercept raw apt-get calls — route them through the safe apt handler
            # so lock conflicts and retries are handled properly
            import re as _re
            _apt_pat = _re.compile(
                r"(?:^|&&|\|)\s*apt(?:-get)?\s+install\b", _re.MULTILINE
            )
            if _apt_pat.search(cmd):
                # Extract package names from simple "apt-get install [-flags] pkg1 pkg2" patterns
                pkg_match = _re.search(
                    r"apt(?:-get)?\s+install\s+(?:-[^\s]+\s+)*(.+?)(?:\s*&&|\s*\||\s*2>&1|$)",
                    cmd, _re.DOTALL,
                )
                if pkg_match:
                    pkgs = pkg_match.group(1).strip().split()
                    # Filter out flags (start with -)
                    pkgs = [p for p in pkgs if not p.startswith("-") and p != "2>&1"]
                    if pkgs:
                        exit_code, output = self.docker.execute_apt(" ".join(pkgs))
                        result = f"[install_packages intercepted apt-get | exit code: {exit_code}]\n{output}"
                        self._emit_tool(name, cmd, result)
                        return result
            exit_code, output = self.docker.execute(cmd)
            result = f"[exit code: {exit_code}]\n{output}"
            self._emit_tool(name, cmd, result)
            return result

        elif name == "web_search":
            query = arguments.get("query", "")
            results = self.search.search(query)
            formatted = self.search.format_results(results)
            self._emit_tool(name, query, formatted)
            return formatted

        elif name == "read_file":
            path = arguments.get("path", "")
            try:
                content = self.files.read(path)
                self._emit_tool(name, path, f"[{len(content)} chars read]")
                return content
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error reading file: {e}"

        elif name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            try:
                abs_path = self.files.write(path, content)
                self._emit_tool(name, path, f"Written → {abs_path}")
                if self.on_file_ready:
                    self.on_file_ready(path, abs_path)
                return f"File written: {abs_path}"
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error writing file: {e}"

        elif name == "delete_file":
            path = arguments.get("path", "").strip()
            try:
                if path in (".", "", "/"):
                    # Clear all contents of uploads dir
                    import os, shutil
                    base = os.path.abspath(self.files.base_dir)
                    deleted = []
                    for entry in os.listdir(base):
                        entry_path = os.path.join(base, entry)
                        if os.path.isdir(entry_path):
                            shutil.rmtree(entry_path)
                        else:
                            os.remove(entry_path)
                        deleted.append(entry)
                    result = f"Cleared uploads/: deleted {len(deleted)} item(s): {', '.join(deleted)}" if deleted else "uploads/ was already empty"
                else:
                    self.files.delete(path)
                    result = f"Deleted: {path}"
                self._emit_tool(name, path, result)
                return result
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error deleting file: {e}"

        elif name == "list_files":
            try:
                files = self.files.list_files()
                if files:
                    result = "Files in uploads/:\n" + "\n".join(f"  {f}" for f in files)
                else:
                    result = "uploads/ is empty"
                self._emit_tool(name, "", result)
                return result
            except Exception as e:
                self._emit_tool(name, "", f"Error: {e}")
                return f"Error listing files: {e}"

        elif name == "install_packages":
            packages = arguments.get("packages", "").strip()
            manager  = arguments.get("manager", "apt").lower()
            if not packages:
                return "Error: no packages specified"
            if manager == "pip":
                cmd = f"pip3 install --quiet {packages} 2>&1"
                exit_code, output = self.docker.execute(cmd)
            else:
                # Use the safe apt handler: handles lock wait, update, retry
                exit_code, output = self.docker.execute_apt(packages)
            status = "OK" if exit_code == 0 else f"exit code {exit_code}"
            result = f"[{status}]\n{output}" if output else f"[{status}]"
            self._emit_tool(name, f"{manager}: {packages}", result)
            return result

        elif name == "deliver_file":
            path = arguments.get("path", "").strip()
            try:
                abs_path = self.files._safe_path(path)
                if not os.path.exists(abs_path):
                    result = f"Error: file '{path}' not found in uploads/"
                    self._emit_tool(name, path, result)
                    return result
                self._emit_tool(name, path, f"Delivered to user: {abs_path}")
                if self.on_file_ready:
                    self.on_file_ready(path, abs_path)
                return f"File delivered: {abs_path}"
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error: {e}"

        return f"Unknown tool: {name}"

    # ── Main agent loop ───────────────────────────────────

    def run(self, chat_id: int, user_message: str, mode: str = "auto"):
        """Run the agent loop for a user message."""
        self._stop = False

        self.db.add_message(chat_id, "user", user_message)

        system = self._get_system_prompt(mode)
        db_messages = self.db.get_messages(chat_id)
        messages = [{"role": "system", "content": system}]
        for m in db_messages:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
            elif m["role"] == "tool":
                messages.append({"role": "user", "content": m["content"]})

        use_tools = mode in ("work", "auto")
        max_iterations = 25

        for _ in range(max_iterations):
            if self._stop:
                break

            try:
                if self.on_stream_start:
                    self.on_stream_start()

                full_content = ""
                tool_calls = None

                for item in self.llm.chat(messages, use_tools=use_tools, stream=True):
                    if self._stop:
                        break
                    if item.get("type") == "delta":
                        text = item.get("content", "")
                        if text:
                            full_content += text
                            if self.on_stream_delta:
                                self.on_stream_delta(text)
                    elif item.get("type") == "tool_calls":
                        tool_calls = item["tool_calls"]

                if self.on_stream_end:
                    self.on_stream_end()

                if full_content.strip():
                    self.db.add_message(chat_id, "assistant", full_content)
                    messages.append({"role": "assistant", "content": full_content})

                # No tools or talk mode → done
                if not use_tools or not tool_calls:
                    break
                if "ready" in full_content.lower().split():
                    break

                # Process tool calls
                for tc in tool_calls:
                    if self._stop:
                        break
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    result = self._execute_tool(name, args)
                    tool_msg = f"[Tool: {name}]\n{result}"
                    messages.append({"role": "user", "content": tool_msg})
                    self.db.add_message(chat_id, "tool", tool_msg, tool=name)

            except Exception as e:
                if self.on_stream_end:
                    self.on_stream_end()
                error_msg = f"Ошибка подключения к LLM: {e}"
                self._emit("error", error_msg)
                self.db.add_message(chat_id, "assistant", error_msg)
                return

    def summarize_chat(self, chat_id: int) -> str:
        db_messages = self.db.get_messages(chat_id)
        if not db_messages:
            return ""

        conversation = "\n".join(
            f"{m['role']}: {m['content'][:500]}" for m in db_messages[:30]
        )

        messages = [
            {"role": "system", "content": MEMORY_SUMMARIZE_PROMPT},
            {"role": "user", "content": conversation},
        ]

        try:
            response = self.llm.chat(messages, use_tools=False, stream=False)
            summary = response.get("content", "").strip()
            if summary:
                self.db.save_memory(chat_id, summary)
            return summary
        except Exception:
            return ""
