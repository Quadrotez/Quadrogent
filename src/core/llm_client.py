import json
import requests
from typing import Generator


LM_STUDIO_URL = "http://localhost:1234/v1"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a Linux command inside the Docker sandbox with root privileges and internet access. "
                           "Working directory is /workspace. The uploads folder is mounted at /workspace/uploads. "
                           "Use for running scripts, compiling code, installing packages, complex file operations, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Returns top results with titles, URLs and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the uploads directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File name only (e.g. 'report.pdf'), relative to the uploads directory"
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
            "description": "Write content to a file in the uploads directory and deliver it to the user as a download.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File name only (e.g. '123.py'), relative to the uploads directory"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
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
            "description": "Delete a file or folder from the uploads directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or folder name relative to uploads directory. "
                                       "Use '.' or '' to clear all contents of uploads."
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
    }
]


class LLMClient:
    """Client for LM Studio OpenAI-compatible API."""

    def __init__(self, base_url: str = LM_STUDIO_URL):
        self.base_url = base_url
        self.session = requests.Session()

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
        temperature: float = 0.7,
    ) -> dict | Generator:
        payload = {
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if use_tools:
            payload["tools"] = TOOLS
            payload["tool_choice"] = "auto"

        if stream:
            return self._stream(payload)
        else:
            return self._complete(payload)

    def _complete(self, payload: dict) -> dict:
        """Non-streaming call, used for summarize_chat."""
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
        """
        Stream response. Yields dicts of two types:
          {"type": "delta",      "content": str}          — text chunk
          {"type": "tool_calls", "tool_calls": list[dict]} — assembled tool calls (end of stream)
        """
        r = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            stream=True,
            timeout=300,
        )
        r.raise_for_status()
        r.encoding = "utf-8"  # Force UTF-8 — prevents Cyrillic/emoji mojibake

        # Assemble tool-call fragments: index -> {id, name, arguments}
        tc_asm: dict[int, dict] = {}

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

                # ── Content delta ──────────────────────────────
                text = delta.get("content") or ""
                if text:
                    yield {"type": "delta", "content": text}

                # ── Tool-call fragments ────────────────────────
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

        # Yield assembled tool calls (if any)
        if tc_asm:
            tool_calls = [
                {
                    "function": {
                        "name":      tc_asm[i]["name"],
                        "arguments": tc_asm[i]["arguments"],
                    }
                }
                for i in sorted(tc_asm.keys())
            ]
            yield {"type": "tool_calls", "tool_calls": tool_calls}
