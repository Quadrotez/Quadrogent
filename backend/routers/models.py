from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import ApiKey
from ollama_client import list_models as list_ollama_models, get_running_models, is_configured as ollama_is_configured
import openai_client
from providers import PROVIDERS

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def get_models(db: AsyncSession = Depends(get_db)):
    """Список всех доступных моделей: локальные (Ollama) + облачные провайдеры."""
    result = []
    errors = {}

    # Получаем состояние enabled для всех провайдеров
    keys_result = await db.execute(select(ApiKey))
    enabled_map = {k.provider: bool(k.enabled) for k in keys_result.scalars().all()}

    # Ollama
    if enabled_map.get("ollama", True):
        try:
            if await ollama_is_configured():
                ollama_models = await list_ollama_models()
                for m in ollama_models:
                    result.append({**m, "provider": "ollama", "name": m.get("name")})
        except Exception as e:
            errors["ollama"] = str(e)

    # Динамические провайдеры (OpenAI-совместимые)
    for provider_name, provider_info in PROVIDERS.items():
        if provider_info["type"] != "openai":
            continue
        if not enabled_map.get(provider_name, True):
            continue
        try:
            if await openai_client.is_configured(provider_name):
                models = await openai_client.list_models(provider_name)
                for m in models:
                    result.append(
                        {
                            "id": m["id"],
                            "name": f"{provider_name}:{m['id']}",
                            "display_name": m["name"],
                            "provider": provider_name,
                        }
                    )
        except Exception as e:
            errors[provider_name] = str(e)

    return {"models": result, "errors": errors or None}


@router.get("/running")
async def get_running():
    """Список моделей, которые сейчас загружены."""
    try:
        models = await get_running_models()
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}
