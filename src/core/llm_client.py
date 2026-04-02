"""
llm_client.py — LM Studio OpenAI-compatible API client.

Key change: chat() now accepts tool_choice parameter
so the agent can pass "required" to force tool calls in work mode.
"""
import json
import requests
from typing import Generator


LM_STUDIO_URL = "http://localhost:1234/v1"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Execute a shell command in Docker (Ubuntu 22.04, root, internet). "
                "Working dir: /workspace. Uploads: /workspace/uploads/. "
                "IMPORTANT: Do NOT use for apt-get or pip — use install_packages instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run. Can be multi-line with &&, heredoc, etc."
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
                "Install packages inside Docker. "
                "Use manager='pip' for Python packages, manager='apt' for system packages. "
                "This is the ONLY correct way to install packages — never use apt-get or pip in execute_command."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "packages": {
                        "type": "string",
                        "description": "Space-separated package names, e.g. 'django pillow' or 'ffmpeg imagemagick'"
                    },
                    "manager": {
                        "type": "string",
                        "enum": ["apt", "pip"],
                        "description": "Use 'pip' for Python packages, 'apt' for system packages. Default: apt"
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
                "Deliver a file to the user as a download. "
                "The file must already exist in /workspace/uploads/. "
                "Use this as the FINAL step after creating a zip/binary file. "
                "Example: create zip via execute_command → then call deliver_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename only (e.g. 'portfolio.zip'), must exist in uploads/"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write a text file to uploads/ and deliver it to the user. "
                "Use ONLY for text files (py, js, html, txt, json, etc). "
                "For binary files (zip, png, exe) use execute_command to create them, then deliver_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename only (e.g. 'script.py')"
                    },
                    "content": {
                        "type": "string",
                        "description": "Full text content to write"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file from uploads/ directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename only (e.g. 'data.csv')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the uploads directory.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or folder from uploads/. Use '.' to clear everything.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename, folder name, or '.' to clear all"
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
            "description": "Search the web. Returns titles, URLs and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
]


class LLMClient:
    def __init__(self, base_url: str = LM_STUDIO_URL):
        self.base_url = base_url
        self.model: str | None = None
        self.session = requests.Session()
        self._active_response = None

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

    def get_models(self) -> list[str]:
        try:
            r = self.session.get(f"{self.base_url}/models", timeout=5)
            data = r.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return []

    def chat(
        self,
        messages: list[dict],
        use_tools: bool = False,
        stream: bool = True,
        temperature: float = 0.4,   # Lower temp = more predictable tool usage
        tool_choice: str = "auto",  # "auto" | "required" | "none"
    ) -> dict | Generator:
        payload: dict = {
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if self.model:
            payload["model"] = self.model
        if use_tools:
            payload["tools"] = TOOLS
            payload["tool_choice"] = tool_choice

        if stream:
            return self._stream(payload)
        else:
            return self._complete(payload)

    def _complete(self, payload: dict) -> dict:
        r = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=300,
        )
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]
        msg = choice["message"]
        return {
            "content": msg.get("content", ""),
            "tool_calls": msg.get("tool_calls"),
            "finish_reason": choice.get("finish_reason"),
        }

    def _stream(self, payload: dict) -> Generator:
        r = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            stream=True,
            timeout=300,
        )
        r.raise_for_status()
        r.encoding = "utf-8"
        self._active_response = r

        tc_asm: dict[int, dict] = {}

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

                    text = delta.get("content") or ""
                    if text:
                        yield {"type": "delta", "content": text}

                    for tc in delta.get("tool_calls", []):
                        idx = tc.get("index", 0)
                        if idx not in tc_asm:
                            tc_asm[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.get("id"):
                            tc_asm[idx]["id"] = tc["id"]
                        func = tc.get("function", {})
                        tc_asm[idx]["name"]      += func.get("name", "")      or ""
                        tc_asm[idx]["arguments"] += func.get("arguments", "") or ""

                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        except Exception:
            pass

        self._active_response = None

        if tc_asm:
            yield {
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "function": {
                            "name":      tc_asm[i]["name"],
                            "arguments": tc_asm[i]["arguments"],
                        }
                    }
                    for i in sorted(tc_asm.keys())
                ],
            }
