import json
from typing import AsyncIterator
import httpx
from sqlalchemy import select
from database import async_session
from models import Setting, ApiKey


DEFAULT_OLLAMA_URL = "http://localhost:11434"


async def is_configured() -> bool:
    """Ollama всегда доступен (локальный сервер)."""
    return True


async def get_ollama_url() -> str:
    """Читает base_url Ollama: сначала из api_keys, потом из settings (backward compat)."""
    async with async_session() as session:
        # Приоритет: api_keys таблица (ProviderManager)
        result = await session.execute(
            select(ApiKey).where(ApiKey.provider == "ollama")
        )
        record = result.scalar_one_or_none()
        if record and record.base_url:
            return record.base_url.rstrip("/")

        # Fallback: settings таблица (старый формат)
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
            "max_tokens": int(settings.get("model_max_tokens", 4096))
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
) -> AsyncIterator[str]:
    """Стриминг ответа от Ollama. Возвращает куски текста."""
    base_url = await get_ollama_url()
    model_settings = await get_model_settings()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "num_ctx": model_settings["num_ctx"],
            "temperature": model_settings["temperature"],
            "top_p": model_settings["top_p"],
            "num_predict": model_settings["max_tokens"],
        }
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