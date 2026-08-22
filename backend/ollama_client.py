import json
from typing import AsyncIterator
import httpx
from sqlalchemy import select
from openai_client import StreamResult
from database import async_session
from models import Setting, ApiKey


DEFAULT_OLLAMA_URL = "http://localhost:11434"


async def is_configured() -> bool:
    """Ollama всегда доступен (локальный сервер)."""
    return True


async def get_ollama_url() -> str:
    """Читает base_url Ollama: сначала из api_keys, потом из settings (backward compat)."""
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.provider == "ollama")
        )
        record = result.scalar_one_or_none()
        if record and record.base_url:
            return record.base_url.rstrip("/")

        result = await session.execute(
            select(Setting).where(Setting.key == "ollama_base_url")
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else DEFAULT_OLLAMA_URL


async def get_model_settings() -> dict:
    async with async_session() as session:
        keys = ["model_num_ctx", "model_temperature", "model_top_p", "model_max_tokens"]
        result = await session.execute(select(Setting).where(Setting.key.in_(keys)))
        settings = {s.key: s.value for s in result.scalars().all()}

        return {
            "num_ctx": int(settings.get("model_num_ctx", 8192)),
            "temperature": float(settings.get("model_temperature", 0.0)),
            "top_p": float(settings.get("model_top_p", 0.9)),
            "max_tokens": int(settings.get("model_max_tokens", 4096)),
        }


async def list_models() -> list[dict]:
    base_url = await get_ollama_url()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{base_url}/api/tags")
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])


async def get_running_models() -> list[dict]:
    base_url = await get_ollama_url()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{base_url}/api/ps")
        response.raise_for_status()
        data = response.json()
        return data.get("models", [])


async def chat_stream(
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncIterator[str | StreamResult]:
    """Стриминг ответа от Ollama.

    Yield'ит куски текста (str) для стриминга в UI.
    Последний элемент — StreamResult с полным текстом и tool_calls.
    """
    base_url = await get_ollama_url()
    model_settings = await get_model_settings()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        # Thinking-модели (например Qwen3) отдают reasoning отдельно в message.thinking.
        "think": True,
        "options": {
            "num_ctx": model_settings["num_ctx"],
            "temperature": model_settings["temperature"],
            "top_p": model_settings["top_p"],
            "num_predict": model_settings["max_tokens"],
        },
    }

    if tools:
        payload["tools"] = tools

    accumulated_text = ""
    thinking_active = False
    # Accumulate streaming tool calls by index (like OpenAI client)
    tool_call_buffers: dict[int, dict] = {}

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{base_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                message = chunk.get("message", {})

                # Thinking-модели Ollama передают reasoning отдельно от финального ответа.
                # Оборачиваем его в уже поддерживаемые UI-теги, сохраняя потоковый вывод.
                thinking = message.get("thinking", "")
                if thinking:
                    if not thinking_active:
                        thinking_active = True
                        accumulated_text += "<think>"
                        yield "<think>"
                    accumulated_text += thinking
                    yield thinking

                content = message.get("content", "")
                if content:
                    if thinking_active:
                        thinking_active = False
                        accumulated_text += "</think>\n\n"
                        yield "</think>\n\n"
                    accumulated_text += content
                    yield content

                # Ollama streams tool_calls in message.tool_calls
                stream_tool_calls = message.get("tool_calls") or []
                for tc in stream_tool_calls:
                    idx = tc.get("index", 0)
                    if idx not in tool_call_buffers:
                        tool_call_buffers[idx] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }
                    buf = tool_call_buffers[idx]

                    func = tc.get("function", {})
                    name = func.get("name", "")
                    if name:
                        buf["name"] = name
                        if not buf["id"]:
                            buf["id"] = f"call_{name}"

                    args = func.get("arguments", {})
                    if isinstance(args, dict) and args:
                        buf["arguments"] = json.dumps(args)
                    elif isinstance(args, str) and args:
                        buf["arguments"] += args

                if chunk.get("done"):
                    break

    if thinking_active:
        accumulated_text += "</think>"
        yield "</think>"

    # Build final tool_calls list
    final_tool_calls = []
    for idx in sorted(tool_call_buffers.keys()):
        buf = tool_call_buffers[idx]
        if buf["name"]:
            try:
                args = json.loads(buf["arguments"]) if buf["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            final_tool_calls.append({
                "id": buf["id"],
                "name": buf["name"],
                "arguments": args,
            })

    yield StreamResult(text=accumulated_text, tool_calls=final_tool_calls)
