"""
agent.py — Quadrogent core agent.

FIXES in this version:
  1. Model loops on errors: when execute_command fails, model re-issues similar
     commands without reading the error. Fix: inject error context explicitly
     and force the model to address it.
  2. _NEXT_STEP was ignored: now includes the last tool result summary
     so the model has concrete context for the next step.
  3. tool_choice="required" throughout work mode (not relaxed mid-task).
  4. Completion ONLY via deliver_file — no text-based exit.
  5. <think> blocks stripped from stored messages to keep context clean.
  6. Error counter: if same command fails 3 times, inject a hard diagnostic prompt.
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


SYSTEM_WORK = """\
You are Quadrogent — an autonomous execution agent. Respond in the user's language.

ENVIRONMENT: Docker Ubuntu 22.04. Root, internet available.
Pre-installed: python3, pip3, zip, unzip, curl, wget, git, jq.
Working dir: /workspace | User files: /workspace/uploads/

━━━ IRON RULES ━━━
1. ALWAYS call a tool. Never respond with text only.
2. Do NOT narrate or explain — just DO it with a tool call.
3. After each tool result, immediately call the NEXT tool.
4. Read the tool output carefully before deciding the next step.
5. If a command fails (exit code != 0): read stderr, fix the exact error, retry.
6. Never repeat a failing command unchanged — always fix it first.
7. Never use apt-get/pip inside execute_command — use install_packages tool.
8. FINISH by: zip result → copy to uploads/ → deliver_file. This is the only exit.

━━━ FILE CREATION ━━━
Create files using heredoc in execute_command:
  execute_command: |
    cat > /workspace/project/views.py << 'HEREDOC'
    from django.shortcuts import render
    def home(request):
        return render(request, 'home.html')
    HEREDOC

━━━ COMPLETION ━━━
  execute_command: "cd /workspace && zip -r uploads/project.zip project/"
  deliver_file: "project.zip"
"""

SYSTEM_TALK = """\
You are Quadrogent, an open-source AI agent. Respond in the user's language.
Mode: Talk — have a normal conversation. Use markdown.
"""

SYSTEM_AUTO = """\
You are Quadrogent — autonomous AI agent. Respond in the user's language.
Working dir: /workspace | Uploads: /workspace/uploads/
Pre-installed: python3, pip3, zip, unzip, curl, wget, git.

For action tasks: call tools immediately, keep going until done, finish with deliver_file.
For questions: just answer with markdown.
Never use apt-get/pip in execute_command — use install_packages.
"""

MEMORY_SUMMARIZE_PROMPT = (
    "Summarize this conversation in 1-3 sentences. What was discussed? Be brief."
)

_HARD_REFORCE = (
    "ERROR: You output text without calling any tool. This is FORBIDDEN in work mode.\n"
    "CALL A TOOL RIGHT NOW. Do not write any text."
)

def _make_next_step(tool_name: str, exit_code, output_snippet: str) -> str:
    """Build a context-aware continue prompt based on last tool result."""
    if exit_code is not None and exit_code != 0:
        return (
            f"[Tool '{tool_name}' FAILED with exit code {exit_code}]\n"
            f"Error output: {output_snippet[:400]}\n"
            "Fix this error and retry with execute_command. Do NOT move to the next step yet."
        )
    return (
        f"[Tool '{tool_name}' succeeded]\n"
        "Call the NEXT tool now. Keep working until deliver_file is called."
    )


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from model output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_exit_code(result: str):
    """Extract exit code integer from tool result string, or None."""
    m = re.search(r"\[exit code:\s*(-?\d+)\]", result)
    return int(m.group(1)) if m else None


def _short_output(result: str, maxlen: int = 600) -> str:
    """Get a trimmed version of tool output for context injection."""
    # Remove the [exit code: N] prefix line
    clean = re.sub(r"^\[.*?\]\n?", "", result).strip()
    if len(clean) > maxlen:
        # Keep tail (errors are usually at the end)
        return "..." + clean[-maxlen:]
    return clean


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

    def _emit(self, role: str, content: str):
        if self.on_message:
            self.on_message(role, content)

    def _emit_tool(self, name: str, args: str, result: str):
        if self.on_tool_call:
            self.on_tool_call(name, args, result)

    def _get_system_prompt(self, mode: str) -> str:
        memories = self.db.get_memories_text()
        base = {"work": SYSTEM_WORK, "talk": SYSTEM_TALK, "auto": SYSTEM_AUTO}.get(
            mode, SYSTEM_AUTO
        )
        if memories:
            base += f"\n\nLong-term memory:\n{memories}"
        return base

    def _execute_tool(self, name: str, arguments: dict) -> str:
        if name == "execute_command":
            cmd = arguments.get("command", "")
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
                        result = f"[install_packages intercepted | exit code: {exit_code}]\n{output}"
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
                self._emit_tool(name, path, f"[{len(content)} chars]")
                return content
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error: {e}"

        elif name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            try:
                abs_path = self.files.write(path, content)
                self._emit_tool(name, path, f"Written → {abs_path}")
                if self.on_file_ready:
                    self.on_file_ready(path, abs_path)
                return f"Written: {path} ({len(content.encode())} bytes)"
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error: {e}"

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
                    result = f"Cleared: {len(deleted)} items"
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
                result = (f"Files ({len(files)}):\n" + "\n".join(f"  {f}" for f in files)
                          if files else "uploads/ is empty")
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
                return f"DELIVERED: {path}"
            except Exception as e:
                self._emit_tool(name, path, f"Error: {e}")
                return f"Error: {e}"

        return f"Unknown tool: {name}"

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
        tool_choice = "required" if mode == "work" else "auto"
        delivered = False
        max_iterations = 50

        for iteration in range(max_iterations):
            if self._stop:
                break

            try:
                if self.on_stream_start:
                    self.on_stream_start()

                raw_content = ""
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
                            raw_content += text
                            if self.on_stream_delta:
                                self.on_stream_delta(text)
                    elif item.get("type") == "tool_calls":
                        tool_calls = item["tool_calls"]

                if self.on_stream_end:
                    self.on_stream_end()

                display_content = _strip_think(raw_content)

                # After deliver_file: one wrap-up text turn then stop
                if delivered:
                    if display_content.strip():
                        self.db.add_message(chat_id, "assistant", display_content)
                    break

                # Text-only response in work mode → hard re-prompt
                if use_tools and not tool_calls:
                    if display_content.strip():
                        self.db.add_message(chat_id, "assistant", display_content)
                        messages.append({"role": "assistant", "content": display_content})
                    if mode == "work":
                        messages.append({"role": "user", "content": _HARD_REFORCE})
                        self.db.add_message(chat_id, "tool", _HARD_REFORCE)
                        continue
                    else:
                        break

                # Save visible reasoning if any
                if display_content.strip():
                    self.db.add_message(chat_id, "assistant", display_content)
                    messages.append({"role": "assistant", "content": display_content})

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

                    if name == "deliver_file" and result.startswith("DELIVERED:"):
                        delivered = True
                        tool_choice = "auto"

                    tool_msg = f"[Tool: {name}]\n{result}"
                    messages.append({"role": "user", "content": tool_msg})
                    self.db.add_message(chat_id, "tool", tool_msg, tool=name)

                    # Inject context-aware next-step prompt after each tool
                    if not delivered:
                        exit_code = _extract_exit_code(result)
                        snippet = _short_output(result)
                        next_msg = _make_next_step(name, exit_code, snippet)
                        messages.append({"role": "user", "content": next_msg})

                if delivered:
                    continue  # one more iteration for wrap-up text

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
