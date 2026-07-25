from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from database import get_db
from models import Setting, ApiKey
from providers import PROVIDERS, get_provider_type

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    key: str
    value: Optional[str] = None


class ApiKeyUpdate(BaseModel):
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    proxy_url: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("")
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    """Все настройки и ключи"""
    settings_result = await db.execute(select(Setting))
    keys_result = await db.execute(select(ApiKey))

    settings = {s.key: s.value for s in settings_result.scalars().all()}
    keys = {
        k.provider: {
            "api_key": k.api_key,
            "base_url": k.base_url,
            "proxy_url": k.proxy_url,
            "enabled": bool(k.enabled),
        }
        for k in keys_result.scalars().all()
    }
    return {"settings": settings, "api_keys": keys}


@router.get("/providers")
async def get_providers(db: AsyncSession = Depends(get_db)):
    """Список провайдеров с их конфигурацией."""
    keys_result = await db.execute(select(ApiKey))
    configured = {k.provider: k for k in keys_result.scalars().all()}

    result = []
    for name, info in PROVIDERS.items():
        record = configured.get(name)
        needs_api_key = info.get("needs_api_key", True)
        result.append({
            "name": name,
            "display_name": info["display_name"],
            "type": info["type"],
            "color": info["color"],
            "default_base_url": info["default_base_url"],
            "needs_api_key": needs_api_key,
            "configured": True if not needs_api_key else bool(record and record.api_key),
            "enabled": bool(record.enabled if record else 1),
            "base_url": record.base_url if record else None,
            "proxy_url": record.proxy_url if record else None,
        })
    return {"providers": result}


@router.put("/setting")
async def update_setting(payload: SettingUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting).where(Setting.key == payload.key))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = payload.value
    else:
        setting = Setting(key=payload.key, value=payload.value)
        db.add(setting)

    await db.commit()
    return {"status": "ok", "key": payload.key, "value": payload.value}


@router.put("/api-key")
async def update_api_key(payload: ApiKeyUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiKey).where(ApiKey.provider == payload.provider))
    key = result.scalar_one_or_none()

    if key:
        if payload.api_key is not None:
            key.api_key = payload.api_key
        if payload.base_url is not None:
            key.base_url = payload.base_url or None
        if payload.proxy_url is not None:
            key.proxy_url = payload.proxy_url or None
        if payload.enabled is not None:
            key.enabled = 1 if payload.enabled else 0
    else:
        key = ApiKey(
            provider=payload.provider,
            api_key=payload.api_key,
            base_url=payload.base_url,
            proxy_url=payload.proxy_url,
            enabled=1 if (payload.enabled is None or payload.enabled) else 0,
        )
        db.add(key)

    await db.commit()
    return {"status": "ok", "provider": payload.provider}


@router.post("/providers/{name}/test")
async def test_provider(name: str, db: AsyncSession = Depends(get_db)):
    """Проверка подключения к провайдеру."""
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Неизвестный провайдер: {name}")

    provider_info = PROVIDERS[name]
    provider_type = provider_info["type"]

    # Получаем конфигурацию из api_keys
    result = await db.execute(select(ApiKey).where(ApiKey.provider == name))
    record = result.scalar_one_or_none()

    if provider_type == "ollama":
        # Для Ollama: проверяем базовый URL (из api_keys или дефолтный)
        base_url = (record.base_url if record and record.base_url else None) or provider_info["default_base_url"]
        proxy = (record.proxy_url if record and record.proxy_url else None) or None
        try:
            async with httpx.AsyncClient(timeout=5.0, proxy=proxy) as client:
                resp = await client.get(f"{base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                model_count = len(data.get("models", []))
                return {
                    "status": "ok",
                    "message": f"Подключение успешно. Найдено моделей: {model_count}",
                }
        except httpx.ConnectError:
            return {"status": "error", "message": f"Не удалось подключиться к {base_url}"}
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"Сервер вернул ошибку {e.response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        # OpenAI-совместимые провайдеры
        api_key = record.api_key if record and record.api_key else None
        if not api_key and name == "opencode":
            api_key = "public"
        if not api_key:
            return {"status": "error", "message": "API ключ не задан"}

        base_url = (record.base_url if record and record.base_url else None) or provider_info["default_base_url"]
        proxy = (record.proxy_url if record and record.proxy_url else None) or None
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with httpx.AsyncClient(timeout=10.0, proxy=proxy) as client:
                resp = await client.get(f"{base_url}/models", headers=headers)
                resp.raise_for_status()
                data = resp.json()
                model_count = len(data.get("data", []))
                return {
                    "status": "ok",
                    "message": f"Подключение успешно. Доступно моделей: {model_count}",
                }
        except httpx.ConnectError:
            return {"status": "error", "message": f"Не удалось подключиться к {base_url}"}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {"status": "error", "message": "Неверный API ключ (401 Unauthorized)"}
            return {"status": "error", "message": f"Сервер вернул ошибку {e.response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
