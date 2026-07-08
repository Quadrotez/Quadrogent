from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, async_session
from models import Setting
from sqlalchemy import select

# Добавляем chats в импорт
from routers import chat, settings, models, chats, sandbox 


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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