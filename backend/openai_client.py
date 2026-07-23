"""Unified client for OpenAI-compatible providers (OpenRouter, Groq, etc.)."""

import json
from typing import AsyncIterator, Optional

import httpx
from sqlalchemy import select

from database import async_session
from models import ApiKey, Setting
from providers import PROVIDERS


class ProviderNotConfigured(Exception):
    """API-ключ провайдера не задан в настройках."""


async def _get_api_key_record(provider: str) -> Optional[ApiKey]:
    async with async_session() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.provider == provider)
        )
        return result.scalar_one_or_none()


async def is_configured(provider: str) -> bool:
    record = await _get_api_key_record(provider)
    return bool(record and record.api_key)


async def get_base_url(provider: str) -> str:
    record = await _get_api_key_record(provider)
    if record and record.base_url:
        return record.base_url.rstrip("/")
    default = PROVIDERS.get(provider, {}).get("default_base_url", "")
    return default.rstrip("/") if default else ""


async def get_proxy_url(provider: str) -> Optional[str]:
    record = await _get_api_key_record(provider)
    if record and record.proxy_url:
        return record.proxy_url.strip() or None
    return None


async def get_model_settings() -> dict:
    async with async_session() as session:
        keys = ["model_temperature", "model_top_p", "model_max_tokens"]
        result = await session.execute(select(Setting).where(Setting.key.in_(keys)))
        settings = {s.key: s.value for s in result.scalars().all()}

        return {
            "temperature": float(settings.get("model_temperature", 0.0)),
            "top_p": float(settings.get("model_top_p", 0.9)),
            "max_tokens": int(settings.get("model_max_tokens", 4096)),
        }


async def list_models(provider: str) -> list[dict]:
    """Список моделей, доступных через OpenAI-совместимый API."""
    record = await _get_api_key_record(provider)
    if not record or not record.api_key:
        return []

    base_url = await get_base_url(provider)
    proxy = await get_proxy_url(provider)
    headers = {"Authorization": f"Bearer {record.api_key}"}

    async with httpx.AsyncClient(timeout=15.0, proxy=proxy) as client:
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


async def chat_stream(
    provider: str, model: str, messages: list[dict]
) -> AsyncIterator[str]:
    """Стриминг ответа от OpenAI-совместимого провайдера (SSE)."""
    record = await _get_api_key_record(provider)
    if not record or not record.api_key:
        raise ProviderNotConfigured(
            f"API-ключ провайдера '{provider}' не настроен. "
            "Добавьте его через управление провайдерами."
        )

    base_url = await get_base_url(provider)
    proxy = await get_proxy_url(provider)
    headers = {
        "Authorization": f"Bearer {record.api_key}",
        "Content-Type": "application/json",
    }
    model_settings = await get_model_settings()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": model_settings["temperature"],
        "top_p": model_settings["top_p"],
        "max_tokens": model_settings["max_tokens"],
    }

    async with httpx.AsyncClient(timeout=None, proxy=proxy) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                raise httpx.HTTPStatusError(
                    f"{provider} вернул ошибку {response.status_code}: "
                    f"{error_body.decode(errors='ignore')}",
                    request=response.request,
                    response=response,
                )

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data_str = line[len("data:") :].strip()
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
