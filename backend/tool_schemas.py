"""JSON Schema definitions for all tools — used in OpenAI/Ollama tool calling API."""

import asyncio
import copy
from database import async_session
from models import Setting
from sqlalchemy import select


async def _get_tool_filter_settings():
    """Load tool filter settings from DB."""
    try:
        async with async_session() as session:
            fetch_r = await session.execute(select(Setting).where(Setting.key == "web_fetch_enabled"))
            fetch_val = (fetch_r.scalar_one_or_none() or Setting(key="", value="true")).value
            return fetch_val == "true"
    except Exception:
        return True


async def _get_enabled_providers():
    """Load enabled search providers from DB."""
    try:
        async with async_session() as session:
            prov_r = await session.execute(select(Setting).where(Setting.key == "search_providers"))
            val = (prov_r.scalar_one_or_none() or Setting(key="", value="duckduckgo")).value
            return [p.strip() for p in val.split(",") if p.strip()]
    except Exception:
        return ["duckduckgo"]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command in the Linux sandbox. Run as user quadrogent with sudo access. Avoid interactive commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file or overwrite an existing one. Content can be a string or array of strings (joined with newlines).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path for the new file",
                    },
                    "content": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "description": "File content (string or array of lines)",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Overwrite an existing file with new content. Semantically implies modifying an existing file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to modify",
                    },
                    "content": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ],
                        "description": "New file content (string or array of lines)",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove",
            "description": "Remove a file or directory recursively (rm -rf). Use with caution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to remove",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "makedir",
            "description": "Create a directory and any parent directories (mkdir -p).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path for the new directory",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install",
            "description": "Install a system package (apk) or Python package (pip). For pip: if no virtualenv is specified, one is automatically created at /home/quadrogent/venv.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["apk", "pip"],
                        "description": "Package manager to use",
                    },
                    "package": {
                        "type": "string",
                        "description": "Package name to install",
                    },
                    "update": {
                        "type": "boolean",
                        "description": "Run apk update before install (apk only)",
                        "default": False,
                    },
                    "virtualenv": {
                        "type": "string",
                        "description": "Path to Python virtualenv (pip only)",
                    },
                },
                "required": ["type", "package"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "present",
            "description": "Make a file or directory available to the user for download. Directories are automatically zipped.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to file or directory to present",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zip",
            "description": "Create a zip archive from a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to archive",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output zip file path",
                    },
                },
                "required": ["path", "output_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unzip",
            "description": "Extract a zip archive to a target directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to zip file",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Extraction directory",
                    },
                },
                "required": ["path", "output_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop",
            "description": "Signal task completion. Call this when the task is fully done.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web. You can choose a specific provider (duckduckgo, google, bing, yandex) or leave empty to search all enabled providers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["duckduckgo", "google", "bing", "yandex"],
                        "description": "Search provider to use. Leave empty to search all enabled.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch the text content of a web page by URL. Follows redirects. Binary content is detected and skipped. Can be disabled in settings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL (must include https://)",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_context",
            "description": "Save ONLY important technical information to persistent memory for future conversations. Examples of what TO save: project structure, tech stack, user preferences, architectural decisions. Do NOT save: greetings, small talk, single completed tasks, obvious facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Context text to remember",
                    }
                },
                "required": ["text"],
            },
        },
    },
]


async def get_tools_for_provider(provider_type: str) -> list[dict]:
    """Return tool schemas. Same format works for both OpenAI and Ollama.
    Filters out disabled tools and makes web_search provider list dynamic."""
    fetch_enabled = await _get_tool_filter_settings()
    providers = await _get_enabled_providers()
    result = []
    for tool in TOOLS:
        name = tool["function"]["name"]
        if name == "web_fetch" and not fetch_enabled:
            continue
        if name == "web_search":
            t = copy.deepcopy(tool)
            t["function"]["parameters"]["properties"]["provider"] = {
                "type": "string",
                "enum": providers,
                "description": f"Search provider to use. Available: {', '.join(providers)}. Leave empty to search all.",
            }
            result.append(t)
            continue
        result.append(tool)
    return result
