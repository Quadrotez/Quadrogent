"""
llm_client.py — LM Studio OpenAI-compatible API client.

Changes:
  - Stream now yields finish_reason so agent can detect silent "stop"
    (model finished without text AND without tool_calls — needs re-prompt)
  - write_file removed from WORK_TOOLS; it stays in TALK_TOOLS only.
    In work mode the model MUST use execute_command+heredoc to create files.
    This prevents the #1 failure mode: model dumps project files into uploads/
    instead of /workspace/, bloats context, gets confused about paths.
  - Lower temperature: 0.3 for work mode (more deterministic tool selection)
"""
import json
import requests
from typing import Generator


LM_STUDIO_URL = "http://localhost:1234/v1"

# Known API providers — all OpenAI-compatible
PROVIDERS = {
    "lmstudio": {
        "name": "LM Studio (локальный)",
        "base_url": "http://localhost:1234/v1",
        "needs_key": False,
        "default_models": [],
        "hint": "Локальный LM Studio — ключ не нужен",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "needs_key": True,
        "default_models": ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-pro"],
        "hint": "API-ключ из Google AI Studio: aistudio.google.com",
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "needs_key": True,
        "default_models": ["llama-3.3-70b-versatile", "llama3-8b-8192", "mixtral-8x7b-32768"],
        "hint": "API-ключ из Groq Console: console.groq.com",
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "needs_key": True,
        "default_models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku", "google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"],
        "hint": "API-ключ из openrouter.ai/keys",
    },
    "mistral": {
        "name": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "needs_key": True,
        "default_models": ["mistral-small-latest", "mistral-large-latest", "codestral-latest"],
        "hint": "API-ключ из console.mistral.ai",
    },
    "gpt4free": {
        "name": "GPT4Free (экспериментально)",
        "base_url": "http://localhost:1337/v1",
        "needs_key": False,
        "default_models": ["gpt-4o", "gpt-4", "claude-3.5-sonnet", "gemini-pro"],
        "hint": "Требует запущенного g4f API: pip install g4f && python -m g4f api",
    },
    "custom": {
        "name": "Свой провайдер",
        "base_url": "",
        "needs_key": False,
        "default_models": [],
        "hint": "Любой OpenAI-совместимый API",
    },
}


# ── Tools available in WORK mode ─────────────────────────────────────────────
# write_file intentionally EXCLUDED — forces model to use execute_command+heredoc
# for all project file creation. write_file is only for delivering single
# text files directly to the user (not useful in agentic work sessions).
WORK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Execute a shell command in Docker (Ubuntu 22.04, root, internet). "
                "Working dir: /workspace. All files must be created in /workspace/. "
                "Use heredoc to create files:\n"
                "  cat > /workspace/project/file.py << 'EOF'\n"
                "  file content here\n"
                "  EOF\n"
                "NEVER use apt-get or pip here — use install_packages tool instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command. Can be multi-line with &&, heredoc, etc."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "install_packages",
            "description": (
                "Install packages in Docker. "
                "manager='pip' for Python packages, manager='apt' for system packages. "
                "ONLY correct way to install — never use apt-get/pip in execute_command."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "packages": {
                        "type": "string",
                        "description": "Space-separated names, e.g. 'django pillow' or 'ffmpeg'"
                    },
                    "manager": {
                        "type": "string",
                        "enum": ["apt", "pip"],
                        "description": "'pip' for Python, 'apt' for system packages"
                    }
                },
                "required": ["packages"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deliver_file",
            "description": (
                "Deliver a file from /workspace/ to the user as a download. "
                "MUST be called as the FINAL step after zipping the result. "
                "Workflow: execute_command('cd /workspace && zip -r result.zip project/') → deliver_file('result.zip')"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename in /workspace/ (e.g. 'portfolio.zip')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a text file. Accepts: (1) a filename relative to /workspace/ "
                "(e.g. 'report.txt'), or (2) an absolute path inside /workspace/ "
                "(e.g. '/workspace/portfolio/models.py')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Relative filename in /workspace/ OR absolute /workspace/... path"
                        )
                    }
                },
                "required": ["path"]
            }
        }
    },
]

# ── Tools available in AUTO/TALK mode ────────────────────────────────────────
# Includes write_file for simple single-file delivery tasks
CALC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Run a Python script or one-liner in Docker for calculations/data processing. "
                "Use ONLY Python: python3 -c '...' or save script + run it. "
                "No other shell commands."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Python execution command."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "install_packages",
            "description": "Install Python packages (pip only).",
            "parameters": {
                "type": "object",
                "properties": {
                    "packages": {"type": "string"},
                    "manager": {"type": "string", "enum": ["pip"], "default": "pip"}
                },
                "required": ["packages"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deliver_file",
            "description": "Deliver result file to user.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
]

FETCH_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": (
            "Fetch the text content of any URL (web page, article, link). "
            "Use this when the user shares a URL and wants you to read it, "
            "or when search results reference a page you need to open. "
            "Returns the page text (up to 4000 chars)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to fetch, e.g. https://example.com/page"
                }
            },
            "required": ["url"]
        }
    }
}

AUTO_TOOLS = WORK_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write a single text file to /workspace/ and deliver it to the user. "
                "Use for simple tasks: 'write me a script', 'create a config file'. "
                "NOT for project scaffolding — use execute_command+heredoc for that."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename only with extension (e.g. 'script.py', 'data.json')"
                    },
                    "content": {
                        "type": "string",
                        "description": "Full text content"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file/folder from /workspace/. Use '.' to clear all.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Filename or '.' to clear all"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in the /workspace/ directory.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


class LLMClient:
    def __init__(self, base_url: str = LM_STUDIO_URL, api_key: str = "",
                 extra_headers: dict | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key  = api_key
        self.model: str | None = None
        self.session = requests.Session()
        self._active_response = None
        self.on_log: callable | None = None
        self._update_session_headers(api_key, extra_headers or {})

    def _update_session_headers(self, api_key: str = "", extra: dict | None = None):
        """Rebuild session headers from current api_key + extras."""
        self.session.headers.clear()
        self.session.headers.update({"Content-Type": "application/json"})
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"
        for k, v in (extra or {}).items():
            self.session.headers[k] = v

    def set_provider(self, provider_id: str, api_key: str = "",
                     base_url_override: str = "", proxy: str = ""):
        """Switch to a different provider. Called from main_window after settings save."""
        info = PROVIDERS.get(provider_id, PROVIDERS["lmstudio"])
        self.base_url = (base_url_override or info["base_url"]).rstrip("/")
        self.api_key  = api_key
        # OpenRouter expects attribution headers
        extra = {}
        if provider_id == "openrouter":
            extra = {"HTTP-Referer": "https://quadrogent.app", "X-Title": "Quadrogent"}
        self._update_session_headers(api_key, extra)
        # Apply proxy to session
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        else:
            self.session.proxies = {}
        self.model = None  # reset model — let caller set a new one

    def abort(self):
        r = self._active_response
        if r is not None:
            try:
                r.close()
            except Exception:
                pass
            self._active_response = None

    def check_connection(self) -> bool:
        try:
            r = self.session.get(f"{self.base_url}/models", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _parse_models_response(self, data) -> list[dict]:
        """Parse /models response in various formats into [{id, vision}]."""
        vision_keywords = ("vl", "vision", "visual", "llava", "minicpm",
                           "qwen2-vl", "qwen2.5-vl", "pixtral", "phi-3-vision",
                           "gemma-vision", "claude-3", "gpt-4-vision",
                           "idefics", "cogvlm", "internvl", "molmo")
        results = []
        # Normalise: list or {"data": [...]} or {"models": [...]} or {"object":"list","data":[...]}
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data") or data.get("models") or []
        for m in items:
            if isinstance(m, str):
                mid = m
            elif isinstance(m, dict):
                mid = m.get("id") or m.get("name") or m.get("model") or ""
            else:
                continue
            if not mid:
                continue
            has_vision = any(kw in mid.lower() for kw in vision_keywords)
            if isinstance(m, dict):
                props = m.get("props", {}) or {}
                if props.get("vision") or props.get("multimodal"):
                    has_vision = True
            results.append({"id": mid, "vision": has_vision})
        return results

    def get_models(self) -> list[str]:
        try:
            r = self.session.get(f"{self.base_url}/models", timeout=8)
            r.raise_for_status()
            return [m["id"] for m in self._parse_models_response(r.json())]
        except Exception:
            return []

    def get_models_with_meta(self) -> list[dict]:
        try:
            r = self.session.get(f"{self.base_url}/models", timeout=8)
            r.raise_for_status()
            return self._parse_models_response(r.json())
        except Exception:
            return []

    def chat(
        self,
        messages: list[dict],
        use_tools: bool = False,
        stream: bool = True,
        temperature: float = 0.3,
        tool_choice: str = "auto",
        work_mode: bool = False,   # selects WORK_TOOLS vs AUTO_TOOLS
        use_web_search: bool = True,
    ) -> dict | Generator:
        payload: dict = {
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if self.model:
            payload["model"] = self.model
        if use_tools:
            if work_mode:
                payload["tools"] = WORK_TOOLS
            elif getattr(self, "_calc_mode", False):
                payload["tools"] = CALC_TOOLS
            else:
                tools = AUTO_TOOLS if use_web_search else [
                    t for t in AUTO_TOOLS
                    if t.get("function", {}).get("name") != "web_search"
                ]
                payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        return self._stream(payload) if stream else self._complete(payload)

    def _complete(self, payload: dict) -> dict:
        if self.on_log:
            self.on_log(f"[REQUEST] {payload.get('model', 'unknown')}")
            self.on_log(f"Messages: {len(payload.get('messages', []))} msg(s)")
            if payload.get('tools'):
                self.on_log(f"Tools: {len(payload['tools'])} tool(s)")
        
        r = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload, timeout=300,
        )
        r.raise_for_status()
        data = r.json()
        
        if self.on_log:
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")
            self.on_log(f"[RESPONSE] finish_reason={choice.get('finish_reason')}")
            if content:
                self.on_log(f"Content: {len(content)} chars")
            if tool_calls:
                self.on_log(f"Tool calls: {len(tool_calls)}")
        
        choice = data["choices"][0]
        msg = choice["message"]
        return {
            "content": msg.get("content", ""),
            "tool_calls": msg.get("tool_calls"),
            "finish_reason": choice.get("finish_reason"),
        }

    def _stream(self, payload: dict) -> Generator:
        """
        Yields:
          {"type": "delta",        "content": str}
          {"type": "tool_calls",   "tool_calls": list}
          {"type": "finish",       "reason": str}   ← NEW: always emitted at end
        """
        if self.on_log:
            self.on_log(f"[STREAM REQUEST] {payload.get('model', 'unknown')}")
            self.on_log(f"Messages: {len(payload.get('messages', []))} msg(s)")
            if payload.get('tools'):
                self.on_log(f"Tools: {len(payload['tools'])} tool(s), choice={payload.get('tool_choice', 'auto')}")
        
        r = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload, stream=True, timeout=300,
        )
        r.raise_for_status()
        r.encoding = "utf-8"
        self._active_response = r

        tc_asm: dict[int, dict] = {}
        finish_reason = "stop"
        total_chars = 0
        stream_error: Exception | None = None

        try:
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choice = chunk["choices"][0]
                    delta = choice.get("delta", {})

                    # Capture finish_reason when it appears
                    fr = choice.get("finish_reason")
                    if fr:
                        finish_reason = fr

                    text = delta.get("content") or ""
                    if text:
                        total_chars += len(text)
                        yield {"type": "delta", "content": text}

                    for tc in delta.get("tool_calls", []):
                        idx = tc.get("index", 0)
                        if idx not in tc_asm:
                            tc_asm[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.get("id"):
                            tc_asm[idx]["id"] = tc["id"]
                        func = tc.get("function", {})
                        tc_asm[idx]["name"]      += func.get("name", "") or ""
                        tc_asm[idx]["arguments"] += func.get("arguments", "") or ""

                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        except Exception as e:
            stream_error = e
            if self.on_log:
                self.on_log(f"[STREAM ERROR] {type(e).__name__}: {e}")

        self._active_response = None

        if self.on_log:
            self.on_log(f"[STREAM RESPONSE] finish_reason={finish_reason}")
            if total_chars > 0:
                self.on_log(f"Content: {total_chars} chars")
            if tc_asm:
                tool_names = [tc_asm[i]["name"] for i in sorted(tc_asm.keys())]
                self.on_log(f"Tool calls: {', '.join(tool_names)}")

        if tc_asm:
            yield {
                "type": "tool_calls",
                "tool_calls": [
                    {"function": {"name": tc_asm[i]["name"], "arguments": tc_asm[i]["arguments"]}}
                    for i in sorted(tc_asm.keys())
                ],
            }

        # Always emit finish so agent knows the model is done generating
        yield {"type": "finish", "reason": finish_reason, "stream_error": stream_error}
