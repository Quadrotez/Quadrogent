import json
from typing import AsyncIterator
import httpx
from sqlalchemy import select
from database import async_session
from models import Setting, ApiKey


DEFAULT_OLLAMA_URL = "http://localhost:11434"


async def get_ollama_url() -> str:
    async with async_session() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == "ollama_base_url")
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else DEFAULT_OLLAMA_URL


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
) -> AsyncIterator[str]:
    """Стриминг ответа от Ollama. Возвращает куски текста."""
    base_url = await get_ollama_url()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

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

                # Ollama возвращает {"message": {"content": "..."}}
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

                # Последний чанк — done=True
                if chunk.get("done"):
                    break