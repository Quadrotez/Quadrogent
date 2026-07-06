import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from ollama_client import chat_stream as ollama_chat_stream
import openrouter_client
from openrouter_client import OpenRouterNotConfigured
from database import async_session
from models import Chat, Message, ToolCall

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("quadrogent.chat")

OPENROUTER_PREFIX = "openrouter:"


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    chat_id: Optional[int] = None


@router.post("")
async def chat(request: ChatRequest):
    """Стриминг ответа через SSE с сохранением истории в БД."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    is_openrouter = request.model.startswith(OPENROUTER_PREFIX)
    real_model = request.model[len(OPENROUTER_PREFIX):] if is_openrouter else request.model

    async def event_generator():
        chat_id = request.chat_id
        full_response = ""

        try:
            # --- Создаём/находим чат и сохраняем сообщение пользователя ---
            async with async_session() as session:
                if chat_id:
                    chat_obj = await session.get(Chat, chat_id)
                    if not chat_obj:
                        # Если передан несуществующий ID — создаём новый
                        chat_obj = Chat(id=chat_id, title="Новый чат")
                        session.add(chat_obj)
                        await session.flush()
                else:
                    # Новый чат: заголовок = первые 50 символов последнего user-сообщения
                    title = "Новый чат"
                    for m in reversed(messages):
                        if m["role"] == "user":
                            title = m["content"][:50].replace("\n", " ").strip() or "Новый чат"
                            break
                    chat_obj = Chat(title=title)
                    session.add(chat_obj)
                    await session.flush()

                chat_id = chat_obj.id

                # Сохраняем сообщение пользователя
                last_user_msg = next((m for m in reversed(messages) if m["role"] == "user"), None)
                if last_user_msg:
                    session.add(Message(
                        chat_id=chat_id,
                        role="user",
                        content=last_user_msg["content"],
                    ))

                await session.commit()
                logger.info(f"Чат #{chat_id}: сохранено сообщение пользователя")

            # --- Отправляем ID чата на фронт ---
            yield f"event: chat_id\ndata: {chat_id}\n\n"

            # --- Подготовка системного промпта ---
            with open("prompts.txt", "r") as f:
                system_prompt = f.read()
            
            # Добавляем системный промпт в начало, если его еще нет
            if not any(m["role"] == "system" for m in messages):
                messages.insert(0, {"role": "system", "content": system_prompt})

            # --- Цикл обработки (для tool-calling) ---
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                full_response = ""
                
                if is_openrouter:
                    stream = openrouter_client.chat_stream(real_model, messages)
                else:
                    stream = ollama_chat_stream(real_model, messages)

                async for chunk in stream:
                    full_response += chunk
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Пытаемся распарсить JSON ответ для проверки на tool_calling
                try:
                    # Модель может вернуть текст + JSON или просто JSON
                    # Ищем JSON в ответе
                    start_idx = full_response.find('{')
                    end_idx = full_response.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_str = full_response[start_idx:end_idx+1]
                        tool_data = json.loads(json_str)
                        
                        if tool_data.get("mode") == "tool_calling":
                            tool_name = tool_data.get("tool")
                            
                            # Сохраняем сообщение ассистента с вызовом инструмента
                            async with async_session() as session:
                                assistant_msg = Message(chat_id=chat_id, role="assistant", content=full_response)
                                session.add(assistant_msg)
                                await session.flush()
                                
                                tool_call = ToolCall(
                                    message_id=assistant_msg.id,
                                    tool=tool_name,
                                    input=json.dumps(tool_data)
                                )
                                session.add(tool_call)
                                await session.commit()
                                
                                tool_call_id = tool_call.id

                            # Выполняем инструмент
                            from tool_executor import ToolExecutor
                            result = await ToolExecutor.execute(tool_name, tool_data)
                            
                            # Обновляем результат в БД
                            async with async_session() as session:
                                tc = await session.get(ToolCall, tool_call_id)
                                tc.output = json.dumps(result)
                                tc.status = "success" if result.get("exit_code") == 0 else "error"
                                await session.commit()

                            # Отправляем результат на фронт
                            yield f"event: tool_result\ndata: {json.dumps({'tool': tool_name, 'result': result})}\n\n"
                            
                            if tool_name == "stop" or result.get("stop"):
                                break
                            
                            # Добавляем результат в контекст для следующей итерации.
                            # Используем роль 'user' для передачи результата инструмента, 
                            # так как многие модели (особенно через OpenRouter/Nvidia) 
                            # ожидают роль 'tool' только при использовании Native Tool Calling API, 
                            # а мы используем текстовый формат JSON.
                            messages.append({"role": "assistant", "content": full_response})
                            messages.append({"role": "user", "content": f"Результат выполнения инструмента {tool_name}:\n{json.dumps(result)}"})
                            continue # Следующая итерация для получения ответа от модели на результат инструмента
                except Exception as e:
                    logger.warning(f"Ошибка парсинга tool_calling: {e}")

                # Если это был обычный чат или ошибка парсинга - сохраняем и выходим
                async with async_session() as session:
                    session.add(Message(
                        chat_id=chat_id,
                        role="assistant",
                        content=full_response,
                    ))
                    await session.commit()
                break

            yield "data: [DONE]\n\n"

        except openrouter_client.httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP Error {e.response.status_code}: {e.response.text}")
            # Если это 429, прокидываем статус и тело ошибки фронтенду
            if e.response.status_code == 429:
                yield f"event: error\ndata: {e.response.text}\n\n"
            else:
                yield f"event: error\ndata: {str(e)}\n\n"
        except OpenRouterNotConfigured as e:
            logger.error(f"OpenRouter не настроен: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"
        except Exception as e:
            logger.exception(f"Ошибка в чате #{chat_id}: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )