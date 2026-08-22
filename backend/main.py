from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database import init_db, async_session, engine
from models import Setting
from sqlalchemy import select
from providers import PROVIDERS

# Добавляем chats в импорт
from routers import chat, settings, models, chats, sandbox


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # Миграция: добавляем proxy_url и enabled в api_keys если нет
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE api_keys ADD COLUMN proxy_url VARCHAR"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE api_keys ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"))
        except Exception:
            pass

    async with async_session() as session:
        # Ollama Base URL
        result = await session.execute(select(Setting).where(Setting.key == "ollama_base_url"))
        if not result.scalar_one_or_none():
            session.add(Setting(key="ollama_base_url", value="http://localhost:11434"))
        
        # Model Parameters
        model_params = {
            "model_num_ctx": "8192",
            "model_temperature": "0.0",
            "model_top_p": "0.9",
            "model_max_tokens": "4096"
        }
        for key, value in model_params.items():
            res = await session.execute(select(Setting).where(Setting.key == key))
            if not res.scalar_one_or_none():
                session.add(Setting(key=key, value=value))

        # Генерация заголовков (выключена по умолчанию)
        res = await session.execute(select(Setting).where(Setting.key == "generate_titles"))
        if not res.scalar_one_or_none():
            session.add(Setting(key="generate_titles", value="false"))

        # Профиль пользователя
        for key, value in [("user_name", ""), ("user_info", ""), ("system_prompt", "")]:
            res = await session.execute(select(Setting).where(Setting.key == key))
            if not res.scalar_one_or_none():
                session.add(Setting(key=key, value=value))

        # Agent behavior settings
        agent_defaults = {
            "self_context": "",        # сохранённый контекст агента
            "multi_command": "true",   # разрешить несколько tool calls за раз
            "max_consecutive_tool_calls": "15",  # предельное число инструментов в одной цепочке
            "tool_calling_mode": "native",  # native или json
        }
        for key, value in agent_defaults.items():
            res = await session.execute(select(Setting).where(Setting.key == key))
            if not res.scalar_one_or_none():
                session.add(Setting(key=key, value=value))

        # Web search settings
        web_defaults = {
            "search_providers": "duckduckgo",  # comma-separated: duckduckgo,google,yandex,bing
            "search_proxy": "",                 # proxy URL for search requests
            "web_fetch_enabled": "true",        # enable/disable web_fetch tool
            "web_search_fetch_results": "true", # fetch and extract the final search results
        }
        for key, value in web_defaults.items():
            res = await session.execute(select(Setting).where(Setting.key == key))
            if not res.scalar_one_or_none():
                session.add(Setting(key=key, value=value))

        await session.commit()
    yield


app = FastAPI(title="Quadrogent Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(settings.router)
app.include_router(models.router)
app.include_router(chats.router) # Подключаем роутер чатов
app.include_router(sandbox.router)


@app.get("/health")
async def health():
    return {"status": "ok"}