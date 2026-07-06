from fastapi import APIRouter, HTTPException
from ollama_client import list_models as list_ollama_models, get_running_models
import openrouter_client

router = APIRouter(prefix="/models", tags=["models"])

OPENROUTER_PREFIX = "openrouter:"


@router.get("")
async def get_models():
    """Список всех доступных моделей: локальные (Ollama) + OpenRouter"""
    result = []
    errors = {}

    try:
        ollama_models = await list_ollama_models()
        for m in ollama_models:
            result.append({**m, "provider": "ollama", "name": m.get("name")})
    except Exception as e:
        errors["ollama"] = str(e)

    try:
        if await openrouter_client.is_configured():
            or_models = await openrouter_client.list_models()
            for m in or_models:
                result.append(
                    {
                        "id": m["id"],
                        "name": f"{OPENROUTER_PREFIX}{m['id']}",
                        "display_name": m["name"],
                        "provider": "openrouter",
                    }
                )
    except Exception as e:
        errors["openrouter"] = str(e)

    return {"models": result, "errors": errors or None}


@router.get("/running")
async def get_running():
    """Список моделей, которые сейчас загружены)"""
    try:
        models = await get_running_models()
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}