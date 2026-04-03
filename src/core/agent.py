"""
agent.py — Quadrogent core agent.

Root causes fixed in this version:
  1. write_file in work mode causes files to land in uploads/ instead of /workspace/.
     FIXED: write_file removed from WORK_TOOLS. Model must use execute_command+heredoc.

  2. Silent "stop" — model finishes streaming with no text and no tool_calls.
     LM Studio considers it done; agent loop exited. Task incomplete.
     FIXED: stream now yields {"type":"finish","reason":...}. Agent detects
     finish_reason="stop" + no tools + work mode → injects re-prompt and continues.

  3. Error context: model repeats failing commands without fixing them.
     FIXED: _make_next_step() injects exit code + stderr snippet after every tool call.

  4. Context explosion from write_file content: large file contents bloat context,
     confuse the model about what state the workspace is in.
     FIXED: write_file excluded from work mode entirely.

  5. Model loses track of workspace state mid-task.
     FIXED: Periodic workspace snapshot injected every 8 tool calls.
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
#  System prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_WORK = """\
You are Quadrogent — an autonomous execution agent. Respond in the user's language.

ENVIRONMENT: Docker Ubuntu 22.04. Root access, internet available.
Pre-installed: python3, pip3, python3-venv, zip, unzip, curl, wget, git, jq.
Project workspace: /workspace/
Deliver results here: /workspace/uploads/

━━━ MANDATORY RULES ━━━
1. ALWAYS call a tool every turn. NEVER output text without a tool call.
2. ALL project files go in /workspace/ — create them with execute_command + heredoc.
3. The uploads/ dir is ONLY for final deliverables (zip files, etc).
4. Do NOT use write_file — it does not exist in this mode. Use execute_command.
5. After each tool result: read the output, then call the next tool immediately.
6. If exit code != 0: fix the exact error shown in stderr and retry.
7. Never repeat a failing command unchanged. Always fix it first.
8. install_packages is the ONLY way to install packages — never apt-get/pip in execute_command.
9. FINISH by zipping the project, copying to uploads/, then calling deliver_file.

━━━ HOW TO CREATE FILES (heredoc) ━━━
execute_command:
  mkdir -p /workspace/myproject/app && cat > /workspace/myproject/app/views.py << 'EOF'
  from django.shortcuts import render

  def home(request):
      return render(request, 'home.html', {})
  EOF

━━━ WRONG (DO NOT DO THIS) ━━━
  ✗ write_file("portfolio/views.py", "...") — write_file does not exist here
  ✗ execute_command("pip install django") — use install_packages instead
  ✗ Creating files in /workspace/uploads/ — that's only for the final zip

━━━ COMPLETION SEQUENCE ━━━
  execute_command: cd /workspace && zip -r uploads/portfolio.zip portfolio/
  deliver_file: portfolio.zip
"""

SYSTEM_TALK = """\
You are Quadrogent, an open-source AI agent. Respond in the user's language.
Mode: Talk — have a normal conversation. Use markdown formatting.
"""

SYSTEM_AUTO = """\
You are Quadrogent — autonomous AI agent. Respond in the user's language.
Workspace: /workspace/ | Deliver files via: /workspace/uploads/
Pre-installed: python3, pip3, zip, unzip, curl, wget, git, python3-venv.

For action tasks:
  - Call tools immediately. Do NOT just describe steps.
  - Create project files in /workspace/ using execute_command with heredoc.
  - install_packages for installing packages (never apt-get/pip in execute_command).
  - Finish with: zip → uploads/ → deliver_file.

For questions: just answer with markdown.
"""

MEMORY_SUMMARIZE_PROMPT = (
    "Summarize this conversation in 1-3 sentences. What was discussed? Be brief."
)

_HARD_REFORCE = (
    "STOP. You output text without calling a tool. In work mode you MUST call a tool every turn.\n"
    "Call execute_command or install_packages RIGHT NOW. Do not write any text."
)

# Injected when model does a silent stop (finish_reason=stop, no content, no tools)
_SILENT_STOP_REFORCE = (
    "The task is NOT complete. You stopped without calling a tool or writing anything.\n"
    "You MUST call a tool RIGHT NOW to continue the task.\n"
    "What is the next step? Execute it immediately with execute_command."
)


def _make_next_step(tool_name: str, exit_code, output_snippet: str) -> str:
    """Context-aware continue prompt injected after each tool result."""
    if exit_code is not None and exit_code != 0:
        return (
            f"[Tool '{tool_name}' FAILED — exit code {exit_code}]\n"
            f"Error: {output_snippet[:500]}\n"
            "You MUST fix this error. Read the error carefully, then call execute_command "
            "with the corrected command. Do NOT move to the next step until this is fixed."
        )
    return (
        f"[Tool '{tool_name}' succeeded]\n"
        "Call the NEXT tool immediately. Keep working. "
        "Do NOT stop until deliver_file has been called."
    )


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks — don't store internal reasoning."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_exit_code(result: str):
    m = re.search(r"\[exit code:\s*(-?\d+)\]", result)
    return int(m.group(1)) if m else None


def _short_output(result: str, maxlen: int = 800) -> str:
    """Trim tool output — keep the tail (errors are at the end)."""
    clean = re.sub(r"^\[.*?\]\n?", "", result).strip()
    return ("..." + clean[-maxlen:]) if len(clean) > maxlen else clean


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
            # Guard: PyQt signal expects str; non-string args/result cause
            # "'int' object has no attribute 'strip'" downstream.
            self.on_tool_call(str(name), str(args), str(result))

    def _get_system_prompt(self, mode: str) -> str:
        memories = self.db.get_memories_text()
        base = {"work": SYSTEM_WORK, "talk": SYSTEM_TALK, "auto": SYSTEM_AUTO}.get(
            mode, SYSTEM_AUTO
        )
        if memories:
            base += f"\n\nLong-term memory:\n{memories}"
        return base

    def _workspace_snapshot(self) -> str:
        """Get current state of /workspace for context injection."""
        exit_code, output = self.docker.execute(
            "find /workspace -not -path '*/\\.*' -not -path '*/uploads/*' "
            "| head -60 | sort 2>/dev/null || echo '(empty)'"
        )
        _, files_in_uploads = self.docker.execute(
            "ls /workspace/uploads/ 2>/dev/null || echo '(empty)'"
        )
        return (
            f"[WORKSPACE STATE]\n"
            f"/workspace files:\n{output.strip()}\n\n"
            f"/workspace/uploads/ contents: {files_in_uploads.strip()}\n"
            "Continue the task based on what is already created above."
        )

    # ── Tool execution ────────────────────────────────────────────────────────

    def _execute_tool(self, name: str, arguments: dict) -> str:

        if name == "execute_command":
            cmd = arguments.get("command", "")
            # Intercept raw apt-get → safe handler
            if re.search(r"(?:^|&&|\|)\s*apt(?:-get)?\s+install\b", cmd, re.MULTILINE):
                m = re.search(
                    r"apt(?:-get)?\s+install\s+(?:-[^\s]+\s+)*(.+?)(?:\s*&&|\s*\||\s*2>&1|$)",
                    cmd, re.DOTALL,
                )
                if m:
                    pkgs = [p for p in m.group(1).strip().split()
                            if not p.startswith("-") and p != "2>&1"]
                    if pkgs:
                        ec, out = self.docker.execute_apt(" ".join(pkgs))
                        result = f"[intercepted apt | exit code: {ec}]\n{out}"
                        self._emit_tool(name, cmd, result)
                        return result
            ec, out = self.docker.execute(cmd)
            result = f"[exit code: {ec}]\n{out}"
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
            # In work mode this tool is not in the tool list, but model might
            # hallucinate it. Intercept gracefully.
            path = arguments.get("path", "").strip()
            content = arguments.get("content", "")
            if not path:
                result = (
                    "Error: write_file is not available in work mode. "
                    "Use execute_command with heredoc to create files in /workspace/."
                )
                self._emit_tool(name, path, result)
                return result
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
            except Exception:
                return "uploads/ is empty"

        elif name == "install_packages":
            packages = arguments.get("packages", "").strip()
            manager  = arguments.get("manager", "apt").lower()
            if not packages:
                return "Error: no packages specified"
            if manager == "pip":
                ec, out = self.docker.execute(f"pip3 install --quiet {packages} 2>&1")
            else:
                ec, out = self.docker.execute_apt(packages)
            status = "OK" if ec == 0 else f"exit code {ec}"
            result = f"[{status}]\n{out}" if out else f"[{status}]"
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

    # ── Main agent loop ───────────────────────────────────────────────────────

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

        use_tools  = mode in ("work", "auto")
        work_mode  = mode == "work"
        # "required" in work mode: model MUST call a tool every turn
        tool_choice = "required" if work_mode else "auto"
        delivered   = False
        tool_call_count = 0
        max_iterations  = 60
        silent_stops    = 0  # consecutive turns with no content and no tools

        # Inject initial workspace snapshot so model knows what already exists.
        # Prevents repeated "startproject" / "mkdir" when workspace is not empty.
        if work_mode:
            try:
                snapshot = self._workspace_snapshot()
                messages.append({"role": "user", "content": snapshot})
            except Exception:
                pass

        for iteration in range(max_iterations):
            if self._stop:
                break

            try:
                if self.on_stream_start:
                    self.on_stream_start()

                raw_content  = ""
                tool_calls   = None
                finish_reason = "stop"

                for item in self.llm.chat(
                    messages,
                    use_tools=use_tools,
                    stream=True,
                    tool_choice=tool_choice,
                    work_mode=work_mode,
                ):
                    if self._stop:
                        break
                    t = item.get("type")
                    if t == "delta":
                        text = item.get("content", "")
                        if text:
                            raw_content += text
                            if self.on_stream_delta:
                                self.on_stream_delta(text)
                    elif t == "tool_calls":
                        tool_calls = item["tool_calls"]
                    elif t == "finish":
                        finish_reason = item.get("reason", "stop")

                if self.on_stream_end:
                    self.on_stream_end()

                display_content = _strip_think(raw_content)

                # ── Post-delivery wrap-up ─────────────────────────────────────
                if delivered:
                    if display_content.strip():
                        self.db.add_message(chat_id, "assistant", display_content)
                    break

                # ── Silent stop detection ─────────────────────────────────────
                # Model emitted nothing and no tool calls. This happens when
                # LM Studio considers the generation "complete" spuriously.
                if not display_content.strip() and not tool_calls:
                    silent_stops += 1
                    if silent_stops >= 3:
                        break  # genuinely stuck, give up
                    msg = {"role": "user", "content": _SILENT_STOP_REFORCE}
                    messages.append(msg)
                    self.db.add_message(chat_id, "tool", _SILENT_STOP_REFORCE)
                    continue
                silent_stops = 0

                # ── Text-only response in work mode ───────────────────────────
                if use_tools and not tool_calls:
                    if display_content.strip():
                        self.db.add_message(chat_id, "assistant", display_content)
                        messages.append({"role": "assistant", "content": display_content})
                    if work_mode:
                        messages.append({"role": "user", "content": _HARD_REFORCE})
                        self.db.add_message(chat_id, "tool", _HARD_REFORCE)
                        continue
                    else:
                        break

                # Save reasoning text
                if display_content.strip():
                    self.db.add_message(chat_id, "assistant", display_content)
                    messages.append({"role": "assistant", "content": display_content})

                # ── Execute tool calls ────────────────────────────────────────
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
                    tool_call_count += 1

                    if name == "deliver_file" and result.startswith("DELIVERED:"):
                        delivered = True
                        tool_choice = "auto"  # allow text-only wrap-up after delivery

                    tool_msg = f"[Tool: {name}]\n{result}"
                    messages.append({"role": "user", "content": tool_msg})
                    self.db.add_message(chat_id, "tool", tool_msg, tool=name)

                    if not delivered:
                        # Inject context-aware next-step prompt after EVERY tool
                        ec = _extract_exit_code(result)
                        snippet = _short_output(result)
                        next_msg = _make_next_step(name, ec, snippet)
                        messages.append({"role": "user", "content": next_msg})

                        # Periodic workspace snapshot to keep model oriented
                        if tool_call_count % 4 == 0:
                            snapshot = self._workspace_snapshot()
                            messages.append({"role": "user", "content": snapshot})

                if delivered:
                    continue  # one more turn for wrap-up

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
            {"role": "system",  "content": MEMORY_SUMMARIZE_PROMPT},
            {"role": "user",    "content": conversation},
        ]
        try:
            response = self.llm.chat(messages, use_tools=False, stream=False)
            summary = response.get("content", "").strip()
            if summary:
                self.db.save_memory(chat_id, summary)
            return summary
        except Exception:
            return ""
