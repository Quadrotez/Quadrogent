import json
from typing import AsyncIterator, Optional

import httpx
from sqlalchemy import select

from database import async_session
from models import ApiKey

OPENROUTER_BASE_URL_DEFAULT = "https://openrouter.ai/api/v1"
PROVIDER = "openrouter"


class OpenRouterNotConfigured(Exception):
    """Ключ OpenRouter не задан в настройках."""


async def _get_api_key_record() -> Optional[ApiKey]:
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.provider == PROVIDER)
        )
        return result.scalar_one_or_none()


async def get_api_key() -> Optional[str]:
    record = await _get_api_key_record()
    return record.api_key if record else None


async def get_base_url() -> str:
    record = await _get_api_key_record()
    if record and record.base_url:
        return record.base_url.rstrip("/")
    return OPENROUTER_BASE_URL_DEFAULT


async def is_configured() -> bool:
    key = await get_api_key()
    return bool(key)


async def list_models() -> list[dict]:
    """Список моделей, доступных через OpenRouter."""
    key = await get_api_key()
    if not key:
        return []

    base_url = await get_base_url()
    headers = {"Authorization": f"Bearer {key}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{base_url}/models", headers=headers)
        response.raise_for_status()
        data = response.json()
        result = []
        for m in data.get("data", []):
            result.append(
                {
                    "id": m.get("id"),
                    "name": m.get("name") or m.get("id"),
                    "context_length": m.get("context_length"),
                }
            )
        return result


async def chat_stream(model: str, messages: list[dict]) -> AsyncIterator[str]:
    """Стриминг ответа от OpenRouter (OpenAI-совместимый формат SSE)."""
    key = await get_api_key()
    if not key:
        raise OpenRouterNotConfigured(
            "API-ключ OpenRouter не настроен. Добавьте его в настройках."
        )

    base_url = await get_base_url()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Рекомендовано OpenRouter для идентификации приложения (необязательно).
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "Quadrogent",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                raise httpx.HTTPStatusError(
                    f"OpenRouter вернул ошибку {response.status_code}: {error_body.decode(errors='ignore')}",
                    request=response.request,
                    response=response,
                )

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content
