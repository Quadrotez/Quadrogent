"""Provider registry — определяет поддерживаемых провайдеров и их настройки по умолчанию."""

PROVIDERS = {
    "ollama": {
        "display_name": "Ollama",
        "default_base_url": "http://localhost:11434",
        "type": "ollama",
        "color": "#4ade80",
        "needs_api_key": False,
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "default_base_url": "https://openrouter.ai/api/v1",
        "type": "openai",
        "color": "#a78bfa",
        "needs_api_key": True,
    },
    "groq": {
        "display_name": "Groq",
        "default_base_url": "https://api.groq.com/openai/v1",
        "type": "openai",
        "color": "#f97316",
        "needs_api_key": True,
    },
    "opencode": {
        "display_name": "OpenCode Zen",
        "default_base_url": "https://opencode.ai/zen/v1",
        "type": "openai",
        "color": "#656363",
        "needs_api_key": False,
    },
}


def get_provider(name: str) -> dict | None:
    return PROVIDERS.get(name)


def get_provider_type(name: str) -> str | None:
    p = PROVIDERS.get(name)
    return p["type"] if p else None
