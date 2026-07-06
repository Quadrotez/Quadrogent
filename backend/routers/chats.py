from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Chat, Message, ToolCall

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("")
async def list_chats(db: AsyncSession = Depends(get_db)):
    """Список всех чатов, отсортированный по дате обновления"""
    result = await db.execute(select(Chat).order_by(Chat.updated_at.desc()))
    chats = result.scalars().all()
    return {
        "chats": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in chats
        ]
    }


@router.get("/{chat_id}")
async def get_chat(chat_id: int, db: AsyncSession = Depends(get_db)):
    """Получить чат со всеми сообщениями"""
    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    result = await db.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    
    # Получаем вызовы инструментов для всех сообщений чата
    message_ids = [m.id for m in messages]
    tool_calls = []
    if message_ids:
        tc_result = await db.execute(
            select(ToolCall).where(ToolCall.message_id.in_(message_ids))
        )
        tool_calls = tc_result.scalars().all()

    return {
        "id": chat.id,
        "title": chat.title,
        "messages": [{"id": m.id, "role": m.role, "content": m.content} for m in messages],
        "tool_calls": [
            {
                "id": tc.id,
                "message_id": tc.message_id,
                "tool": tc.tool,
                "input": tc.input,
                "output": tc.output,
                "status": tc.status
            }
            for tc in tool_calls
        ]
    }


@router.delete("/{chat_id}")
async def delete_chat(chat_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить чат и все его сообщения"""
    await db.execute(delete(Message).where(Message.chat_id == chat_id))
    await db.execute(delete(Chat).where(Chat.id == chat_id))
    await db.commit()
    return {"status": "ok"}