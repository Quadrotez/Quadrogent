import json
import logging
import re
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from ollama_client import chat_stream as ollama_chat_stream, get_ollama_url
import openai_client
from providers import get_provider_type
from database import async_session
from models import Chat, Message, Setting, ToolCall, ApiKey
from sandbox_manager import SandboxManager
from sqlalchemy import select

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("quadrogent.chat")


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    chat_id: Optional[int] = None


def _parse_provider_from_model(model_name: str) -> tuple[str, str]:
    """Извлекает имя провайдера и реальное имя модели по префиксу 'provider:model'."""
    if ":" in model_name:
        provider, real_model = model_name.split(":", 1)
        if provider:
            return provider, real_model
    return "ollama", model_name


async def _generate_title(provider_name: str, provider_type: str, real_model: str, user_message: str) -> Optional[str]:
    """Генерирует короткий заголовок чата через LLM (не более 30 символов)."""
    title_prompt = (
        "Создай короткий заголовок (не более 30 символов, на русском языке) "
        "для чата на основе первого сообщения пользователя. "
        "Ответь ТОЛЬКО заголовком, без кавычек и лишнего текста.\n\n"
        f"Сообщение: {user_message[:500]}"
    )

    try:
        if provider_type == "ollama":
            base_url = await get_ollama_url()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": real_model,
                        "messages": [{"role": "user", "content": title_prompt}],
                        "stream": False,
                        "options": {"num_predict": 50, "temperature": 0.3},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "").strip().strip('"\'')
        else:
            record = await openai_client._get_api_key_record(provider_name)
            if not record or not record.api_key:
                return None
            base_url = await openai_client.get_base_url(provider_name)
            proxy = await openai_client.get_proxy_url(provider_name)
            async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": real_model,
                        "messages": [{"role": "user", "content": title_prompt}],
                        "max_tokens": 50,
                        "temperature": 0.3,
                    },
                    headers={"Authorization": f"Bearer {record.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip().strip('"\'')
    except Exception as e:
        logger.warning(f"Не удалось сгенерировать заголовок: {e}")
        return None


async def _is_generate_titles_enabled() -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == "generate_titles")
        )
        setting = result.scalar_one_or_none()
        return setting is not None and setting.value == "true"


@router.post("")
async def chat(request: ChatRequest):
    """Стриминг ответа через SSE с сохранением истории в БД."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    provider_name, real_model = _parse_provider_from_model(request.model)
    provider_type = get_provider_type(provider_name) or "openai"

    # Проверяем, включён ли провайдер
    async with async_session() as session:
        key_result = await session.execute(select(ApiKey).where(ApiKey.provider == provider_name))
        key_record = key_result.scalar_one_or_none()
        if key_record and not key_record.enabled:
            async def disabled_error():
                yield f"data: {json.dumps({'type': 'error', 'content': f'Провайдер {provider_name} отключён. Включите его в настройках.'})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(disabled_error(), media_type="text/event-stream")

    async def event_generator():
        chat_id = request.chat_id
        full_response = ""

        # --- Загрузка базового системного промпта ---
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        prompts_dir = os.path.join(backend_dir, "prompts")
        
        system_prompt_path = os.path.join(prompts_dir, "system_prompt.md")
        system_prompt = ""
        if os.path.exists(system_prompt_path):
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        else:
            logger.error(f"System prompt not found at {system_prompt_path}")
        
        messages_to_send = [m for m in messages if m["role"] != "system"]
        messages_to_send.insert(0, {"role": "system", "content": system_prompt})

        try:
            # --- Создаём/находим чат и сохраняем сообщение пользователя ---
            is_new_chat = False
            async with async_session() as session:
                if chat_id:
                    chat_obj = await session.get(Chat, chat_id)
                    if not chat_obj:
                        chat_obj = Chat(id=chat_id, title="Новый чат")
                        session.add(chat_obj)
                        await session.flush()
                        is_new_chat = True
                else:
                    title = "Новый чат"
                    for m in reversed(messages):
                        if m["role"] == "user":
                            title = m["content"][:50].replace("\n", " ").strip() or "Новый чат"
                            break
                    chat_obj = Chat(title=title)
                    session.add(chat_obj)
                    await session.flush()
                    is_new_chat = True

                if is_new_chat:
                    SandboxManager.cleanup_output()

                chat_id = chat_obj.id
                last_user_msg = next((m for m in reversed(messages) if m["role"] == "user"), None)
                if last_user_msg:
                    session.add(Message(chat_id=chat_id, role="user", content=last_user_msg["content"]))

                await session.commit()

            yield f"event: chat_id\ndata: {chat_id}\n\n"

            # --- Генерация заголовка (если включено и новый чат) ---
            generate_titles = await _is_generate_titles_enabled()
            if generate_titles and is_new_chat and last_user_msg:
                user_msg_text = last_user_msg["content"]
                title = await _generate_title(provider_name, provider_type, real_model, user_msg_text)
                if title:
                    # Обрезаем до 30 символов
                    title = title[:30]
                    async with async_session() as session:
                        chat_obj = await session.get(Chat, chat_id)
                        if chat_obj:
                            chat_obj.title = title
                            await session.commit()
                    yield f"event: title\ndata: {json.dumps(title)}\n\n"

            # --- Цикл обработки (для tool-calling) ---
            max_iterations = 10
            iteration = 0
            read_skills = set()
            
            while iteration < max_iterations:
                iteration += 1
                full_response = ""
                
                if provider_type == "ollama":
                    stream = ollama_chat_stream(real_model, messages_to_send)
                else:
                    stream = openai_client.chat_stream(provider_name, real_model, messages_to_send)

                async for chunk in stream:
                    full_response += chunk
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Пытаемся распарсить JSON ответ для проверки на tool_calling
                try:
                    tool_data = None
                    markdown_json_match = re.search(r"```(?:json)?\n([\s\S]*?)\n```", full_response)
                    if markdown_json_match:
                        try:
                            tool_data = json.loads(markdown_json_match.group(1))
                        except json.JSONDecodeError:
                            pass
                    
                    if not tool_data:
                        start_idx = full_response.find("{")
                        end_idx = full_response.rfind("}")
                        if start_idx != -1 and end_idx != -1:
                            json_str = full_response[start_idx:end_idx+1]
                            try:
                                tool_data = json.loads(json_str)
                            except json.JSONDecodeError:
                                pass

                    if tool_data and tool_data.get("mode") == "tool_calling":
                        tool_name = tool_data.get("tool")
                        
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

                        from tool_executor import ToolExecutor
                        
                        if tool_name == "read_skill":
                            skill_name = tool_data.get("name")
                            if skill_name:
                                read_skills.add(skill_name)

                        raw_result = await ToolExecutor.execute(tool_name, tool_data, read_skills=read_skills)
                        result = ToolExecutor.wrap_result(raw_result)
                        
                        async with async_session() as session:
                            tc = await session.get(ToolCall, tool_call_id)
                            tc.output = json.dumps(result)
                            tc.status = "success" if result.get("exit_code") == 0 else "error"
                            await session.commit()

                        yield f"event: tool_result\ndata: {json.dumps({'tool': tool_name, 'result': result})}\n\n"
                        
                        if tool_name == "stop" or result.get("stop"):
                            break
                        
                        messages_to_send.append({"role": "assistant", "content": full_response})
                        messages_to_send.append({"role": "user", "content": f"Результат выполнения инструмента {tool_name}:\n{json.dumps(result)}"})
                        continue

                    async with async_session() as session:
                        session.add(Message(
                            chat_id=chat_id,
                            role="assistant",
                            content=full_response,
                        ))
                        await session.commit()
                    break

                except Exception as e:
                    logger.warning(f"Ошибка парсинга tool_calling: {e}")
                    async with async_session() as session:
                        session.add(Message(
                            chat_id=chat_id,
                            role="assistant",
                            content=full_response,
                        ))
                        await session.commit()
                    break

            yield "data: [DONE]\n\n"

        except openai_client.httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code}: {e.response.text}")
            if e.response.status_code == 429:
                yield f"event: error\ndata: {e.response.text}\n\n"
            else:
                yield f"event: error\ndata: {str(e)}\n\n"
        except openai_client.ProviderNotConfigured as e:
            logger.error(f"Провайдер не настроен: {e}")
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
