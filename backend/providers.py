"""Provider registry — определяет поддерживаемых провайдеров и их настройки по умолчанию."""

PROVIDERS = {
    "ollama": {
        "display_name": "Ollama",
        "default_base_url": "http://localhost:11434",
        "type": "ollama",
        "color": "#4ade80",
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "default_base_url": "https://openrouter.ai/api/v1",
        "type": "openai",
        "color": "#a78bfa",
    },
    "groq": {
        "display_name": "Groq",
        "default_base_url": "https://api.groq.com/openai/v1",
        "type": "openai",
        "color": "#f97316",
    },
}


def get_provider(name: str) -> dict | None:
    return PROVIDERS.get(name)


def get_provider_type(name: str) -> str | None:
    p = PROVIDERS.get(name)
    return p["type"] if p else None
