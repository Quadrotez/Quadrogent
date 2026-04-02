"""
agent.py — Quadrogent core agent.

Key fixes for weak local models (7B):
 1. SYSTEM PROMPTS: Short, imperative, with explicit tool-call examples.
    Weak models get confused by long instructions — they start narrating instead of acting.

 2. tool_choice "required" in work mode: forces the model to ALWAYS call a tool.
    With "auto", weak models often choose to write text instead of calling tools.

 3. Anti-narration detection: if the model responds with a plan/text and NO tool calls
    in work mode, we inject a hard re-prompt: "DO NOT WRITE TEXT. CALL A TOOL NOW."

 4. Step-by-step forcing: after each tool result, the next turn reminds the model
    to continue executing (not summarize).

 5. "ready" detection at tool-call level: model calls deliver_file or a sentinel
    instead of writing "ready" in text (which gets ignored by some models).
"""
import json
import os
import re
import shutil
from typing import Callable

from src.core.llm_client import LLMClient
from src.core.docker_manager import DockerManager
from src.core.web_search import WebSearch
from src.utils.file_manager import FileManager
from src.db.database import Database


# ─────────────────────────────────────────────────────────────────────────────
#  System prompts — SHORT and IMPERATIVE for weak models
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_WORK = """\
You are Quadrogent, an autonomous AI agent. Respond in the same language as the user.

ENVIRONMENT: Docker Ubuntu 22.04. Pre-installed: python3, pip3, zip, unzip, curl, git.
Working dir: /workspace. User files: /workspace/uploads/.

RULES — READ CAREFULLY:
- NEVER write a plan and stop. ALWAYS immediately call a tool after any explanation.
- NEVER say "you can run..." or "next step is..." — DO IT YOURSELF with a tool.
- After EVERY tool result, call the NEXT tool. Keep going until task is done.
- When fully done: call deliver_file (if there's a file) then write "TASK_COMPLETE".
- If a command fails: read the error, fix it, retry. Never give up.
- Packages: use install_packages tool only. Never run apt-get/pip via execute_command.

TOOL CALL EXAMPLES:
  execute_command({"command": "mkdir -p /workspace/myapp && cd /workspace/myapp && django-admin startproject portfolio ."})
  install_packages({"packages": "django pillow", "manager": "pip"})
  execute_command({"command": "cat > /workspace/myapp/main/views.py << 'EOF'\\nfrom django.shortcuts import render\\nEOF"})
  deliver_file({"path": "portfolio.zip"})

START: Call a tool immediately. Do not write only text.
"""

SYSTEM_TALK = """\
You are Quadrogent, an open-source AI agent. Respond in the same language as the user.
Mode: Talk. Have a normal conversation. Use markdown for formatting.
"""

SYSTEM_AUTO = """\
You are Quadrogent, an autonomous AI agent. Respond in the same language as the user.

ENVIRONMENT: Docker Ubuntu 22.04. Pre-installed: python3, pip3, zip, unzip, curl, git.
Working dir: /workspace. User files: /workspace/uploads/.

If the task requires actions (code, files, commands): work autonomously.
- Call tools immediately. Do not just describe steps — execute them.
- After each tool result, call the next tool. Keep going until done.
- When done: call deliver_file if there's a file, then write "TASK_COMPLETE".
- If error: read output, fix, retry.
- Packages: install_packages tool only.

If it's a simple question: just answer. Use markdown.
"""

MEMORY_SUMMARIZE_PROMPT = (
    "Summarize this conversation in 1-3 sentences. "
    "What was discussed and what conclusions were reached? Be brief."
)

# Patterns that indicate the model is narrating instead of acting
_NARRATION_PATTERNS = [
    r"шаг\s*\d+",          # "Шаг 1:", "Шаг 2:"
    r"step\s*\d+",          # "Step 1:"
    r"сначала\s+(нужно|надо|установим|создадим)",
    r"для начала",
    r"план\s*:",
    r"давайте\s+(начнём|создадим|установим|сделаем)",
    r"теперь\s+(нужно|надо|создадим|запустим)",
    r"следующий шаг",
    r"next step",
    r"выполним следующие шаги",
    r"разделим на",
    r"вот\s+что\s+(нужно|надо|мы)",
    r"можно\s+(запустить|выполнить|сделать)",
    r"you can run",
    r"you should run",
    r"run the following",
]
_NARRATION_RE = re.compile("|".join(_NARRATION_PATTERNS), re.IGNORECASE)

# Injected message when model narrates without acting
_FORCE_ACTION_MSG = (
    "[SYSTEM: You wrote text but called NO tools. "
    "This is WRONG. You MUST call a tool RIGHT NOW. "
    "Do not write any more text — call execute_command or install_packages immediately. "
    "Start executing, not explaining.]"
)

# After a tool result, remind the model to continue
_CONTINUE_MSG = (
    "[SYSTEM: Tool executed. Now call the NEXT tool to continue the task. "
    "Keep working until the task is fully complete. Do NOT stop or summarize yet.]"
)


class Agent:
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
        self.on_file_ready:   Callable[[str, str], None]       | None = None
        self._stop = False

    def stop(self):
        self._stop = True
        self.llm.abort()

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
            base += f"\n\nLong-term memory:\n{memories}"
        return base

    # ── Tool execution ────────────────────────────────────

    def _execute_tool(self, name: str, arguments: dict) -> str:
        if name == "execute_command":
            cmd = arguments.get("command", "")
            # Intercept raw apt-get — route through safe handler
            _apt_pat = re.compile(r"(?:^|&&|\|)\s*apt(?:-get)?\s+install\b", re.MULTILINE)
            if _apt_pat.search(cmd):
                pkg_match = re.search(
                    r"apt(?:-get)?\s+install\s+(?:-[^\s]+\s+)*(.+?)(?:\s*&&|\s*\||\s*2>&1|$)",
                    cmd, re.DOTALL,
                )
                if pkg_match:
                    pkgs = [p for p in pkg_match.group(1).strip().split()
                            if not p.startswith("-") and p != "2>&1"]
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
                return f"File written: {path} ({len(content.encode())} bytes)"
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error writing file: {e}"

        elif name == "delete_file":
            path = arguments.get("path", "").strip()
            try:
                if path in (".", "", "/"):
                    base = os.path.abspath(self.files.base_dir)
                    deleted = []
                    for entry in os.listdir(base):
                        ep = os.path.join(base, entry)
                        shutil.rmtree(ep) if os.path.isdir(ep) else os.remove(ep)
                        deleted.append(entry)
                    result = f"Cleared {len(deleted)} items" if deleted else "Already empty"
                else:
                    self.files.delete(path)
                    result = f"Deleted: {path}"
                self._emit_tool(name, path, result)
                return result
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error: {e}"

        elif name == "list_files":
            try:
                files = self.files.list_files()
                result = (
                    f"Files ({len(files)}):\n" + "\n".join(f"  {f}" for f in files)
                    if files else "uploads/ is empty"
                )
                self._emit_tool(name, "", result)
                return result
            except Exception as e:
                self._emit_tool(name, "", f"Error: {e}")
                return f"Error: {e}"

        elif name == "install_packages":
            packages = arguments.get("packages", "").strip()
            manager  = arguments.get("manager", "apt").lower()
            if not packages:
                return "Error: no packages specified"
            if manager == "pip":
                exit_code, output = self.docker.execute(
                    f"pip3 install --quiet {packages} 2>&1"
                )
            else:
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
                    result = f"Error: '{path}' not found in uploads/"
                    self._emit_tool(name, path, result)
                    return result
                self._emit_tool(name, path, f"Delivered: {abs_path}")
                if self.on_file_ready:
                    self.on_file_ready(path, abs_path)
                return f"File delivered: {path}"
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error: {e}"

        return f"Unknown tool: {name}"

    # ── Helpers ───────────────────────────────────────────

    def _is_narrating(self, text: str, tool_calls) -> bool:
        """Return True if model wrote a plan/text but called no tools in work mode."""
        if tool_calls:
            return False
        return bool(text.strip()) and bool(_NARRATION_RE.search(text))

    def _is_done(self, text: str, tool_calls) -> bool:
        """Return True if task is complete."""
        if not text:
            return False
        t = text.strip().lower()
        # Must have delivered a file or explicitly signalled done
        return "task_complete" in t or (
            "ready" in t.split() and not tool_calls
        )

    # ── Main agent loop ───────────────────────────────────

    def run(self, chat_id: int, user_message: str, mode: str = "auto"):
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

        # In work mode: force tool calls — don't let model choose to skip
        # "required" forces the model to always call at least one tool per turn.
        # We'll relax this to "auto" once the model signals completion.
        tool_choice = "required" if mode == "work" else "auto"

        max_iterations = 40
        consecutive_narrations = 0
        tools_called_total = 0

        for iteration in range(max_iterations):
            if self._stop:
                break

            try:
                if self.on_stream_start:
                    self.on_stream_start()

                full_content = ""
                tool_calls = None

                for item in self.llm.chat(
                    messages,
                    use_tools=use_tools,
                    stream=True,
                    tool_choice=tool_choice,
                ):
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

                # Save assistant text if any
                if full_content.strip():
                    self.db.add_message(chat_id, "assistant", full_content)
                    messages.append({"role": "assistant", "content": full_content})

                # ── Talk mode / no tools ──────────────────────────
                if not use_tools or not tool_calls:
                    # Check for narration without action in work mode
                    if use_tools and mode == "work" and self._is_narrating(full_content, tool_calls):
                        consecutive_narrations += 1
                        if consecutive_narrations >= 2:
                            # Hard stop — model is stuck narrating
                            break
                        # Inject hard re-prompt
                        messages.append({"role": "user", "content": _FORCE_ACTION_MSG})
                        self.db.add_message(chat_id, "tool", _FORCE_ACTION_MSG)
                        continue
                    break

                consecutive_narrations = 0

                # ── Process tool calls ────────────────────────────
                task_done = False
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
                    tools_called_total += 1

                    # deliver_file signals the end of a file-delivery task
                    if name == "deliver_file" and "Error" not in result:
                        task_done = True

                    tool_msg = f"[Tool: {name}]\n{result}"
                    messages.append({"role": "user", "content": tool_msg})
                    self.db.add_message(chat_id, "tool", tool_msg, tool=name)

                if task_done or self._is_done(full_content, tool_calls):
                    break

                # After tool calls: switch tool_choice back to "auto"
                # so model can choose to write a final message if done
                # But keep "required" until at least some tools have run
                if tools_called_total >= 2:
                    tool_choice = "auto"

                # Inject continue reminder after each tool batch
                # This prevents the model from stopping to summarize mid-task
                if not task_done and tools_called_total < 30:
                    messages.append({"role": "user", "content": _CONTINUE_MSG})

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
