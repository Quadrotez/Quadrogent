from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Setting, ApiKey

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    key: str
    value: Optional[str] = None


class ApiKeyUpdate(BaseModel):
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


@router.get("")
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    """Все настройки и ключи"""
    settings_result = await db.execute(select(Setting))
    keys_result = await db.execute(select(ApiKey))

    settings = {s.key: s.value for s in settings_result.scalars().all()}
    keys = {
        k.provider: {"api_key": k.api_key, "base_url": k.base_url}
        for k in keys_result.scalars().all()
    }
    return {"settings": settings, "api_keys": keys}


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
        key.api_key = payload.api_key
        key.base_url = payload.base_url
    else:
        key = ApiKey(
            provider=payload.provider,
            api_key=payload.api_key,
            base_url=payload.base_url,
        )
        db.add(key)

    await db.commit()
    return {"status": "ok", "provider": payload.provider}