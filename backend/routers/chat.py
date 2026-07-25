import asyncio
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
from openai_client import ProviderRateLimitError
from providers import PROVIDERS, get_provider_type
from database import async_session
from models import Chat, Message, Setting, ToolCall, ApiKey
from sandbox_manager import SandboxManager
from sqlalchemy import select

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("quadrogent.chat")


def _summarize_tool_action(tool_name: str, tool_data: dict, result: dict) -> str:
    """Генерирует краткую человекочитаемую сводку по выполненному действию."""
    success = result.get("exit_code") == 0
    status = "" if success else " [ОШИБКА]"

    if tool_name == "create_file":
        return f"Создан файл: {tool_data.get('path', '?')}{status}"
    elif tool_name == "patch_file":
        return f"Изменён файл: {tool_data.get('path', '?')}{status}"
    elif tool_name == "remove":
        return f"Удалён: {tool_data.get('path', '?')}{status}"
    elif tool_name == "makedir":
        return f"Создана папка: {tool_data.get('path', '?')}{status}"
    elif tool_name == "install":
        pkg = tool_data.get("package", "?")
        pkg_type = tool_data.get("type", "?")
        return f"Установлен пакет ({pkg_type}): {pkg}{status}"
    elif tool_name == "present":
        stdout = result.get("stdout", "")
        path_match = re.search(r"Презентовано: (.+)", stdout)
        presented = path_match.group(1).strip() if path_match else tool_data.get("path", "?")
        return f"Презентован пользователю: {presented}{status}"
    elif tool_name == "zip":
        return f"Создан архив: {tool_data.get('output_path', '?')}{status}"
    elif tool_name == "unzip":
        return f"Распакован архив: {tool_data.get('path', '?')} → {tool_data.get('output_path', '?')}{status}"
    elif tool_name == "bash":
        cmd = tool_data.get("command", "?")
        short_cmd = cmd if len(cmd) <= 80 else cmd[:77] + "..."
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        output_preview = ""
        if stdout:
            lines = stdout.strip().split("\n")
            if len(lines) > 3:
                output_preview = f" (вывод: {len(lines)} строк)"
            elif stdout.strip():
                output_preview = f" (вывод: {stdout.strip()[:100]})"
        elif stderr:
            output_preview = f" (ошибка: {stderr.strip()[:100]})"
        return f"Команда: {short_cmd}{output_preview}{status}"
    elif tool_name == "read_skill":
        return None  # не логируем чтение скиллов — шум
    elif tool_name == "web_search":
        return f"Поиск в интернете: {tool_data.get('query', '?')}{status}"
    elif tool_name == "web_fetch":
        return f"Загружен контент: {tool_data.get('url', '?')}{status}"
    else:
        return f"Инструмент {tool_name}{status}"


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
        if provider and provider in PROVIDERS:
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

        # --- Загрузка системного промпта ---
        system_prompt = ""
        async with async_session() as session:
            res = await session.execute(select(Setting).where(Setting.key == "system_prompt"))
            custom_prompt = res.scalar_one_or_none()
            if custom_prompt and custom_prompt.value and custom_prompt.value.strip():
                system_prompt = custom_prompt.value
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                backend_dir = os.path.dirname(current_dir)
                prompts_dir = os.path.join(backend_dir, "prompts")
                system_prompt_path = os.path.join(prompts_dir, "system_prompt.md")
                if os.path.exists(system_prompt_path):
                    with open(system_prompt_path, "r", encoding="utf-8") as f:
                        system_prompt = f.read()
                else:
                    logger.error(f"System prompt not found at {system_prompt_path}")

            # Добавляем информацию о пользователе
            user_parts = []
            res_name = await session.execute(select(Setting).where(Setting.key == "user_name"))
            user_name_row = res_name.scalar_one_or_none()
            if user_name_row and user_name_row.value and user_name_row.value.strip():
                user_parts.append(f"Имя пользователя: {user_name_row.value.strip()}")
            res_info = await session.execute(select(Setting).where(Setting.key == "user_info"))
            user_info_row = res_info.scalar_one_or_none()
            if user_info_row and user_info_row.value and user_info_row.value.strip():
                user_parts.append(f"Информация о пользователе: {user_info_row.value.strip()}")
            if user_parts:
                system_prompt += "\n\n# USER INFO:\n" + "\n".join(user_parts)

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
            tools_were_called = False
            actions_log = []
            
            while iteration < max_iterations:
                iteration += 1

                # Добавляем сводку выполненных действий в контекст
                if actions_log:
                    summary_lines = "\n".join(f"  {i}. {a}" for i, a in enumerate(actions_log, 1))
                    actions_summary = (
                        "--- ВЫПОЛНЕННЫЕ ДЕЙСТВИЯ ДО СЕГО МОМЕНТА ---\n"
                        f"{summary_lines}\n"
                        "--- КОНЕЦ СВОДКИ ---\n\n"
                        "Используй эту информацию. Не повторяй уже выполненные действия."
                    )
                    # Убираем предыдущую сводку, если была
                    if messages_to_send and messages_to_send[-1].get("content", "").startswith("--- ВЫПОЛНЕННЫЕ ДЕЙСТВИЯ"):
                        messages_to_send.pop()
                    messages_to_send.append({"role": "user", "content": actions_summary})

                max_retries = 5
                base_delay = 1

                for retry_attempt in range(max_retries):
                    full_response = ""
                    delay = base_delay * (2 ** retry_attempt)

                    try:
                        if provider_type == "ollama":
                            stream = ollama_chat_stream(real_model, messages_to_send)
                        else:
                            stream = openai_client.chat_stream(provider_name, real_model, messages_to_send)

                        async for chunk in stream:
                            full_response += chunk
                            yield f"data: {json.dumps(chunk)}\n\n"

                    except ProviderRateLimitError as e:
                        if retry_attempt >= max_retries - 1:
                            raise
                        wait = max(e.retry_after, delay)
                        logger.warning(f"Rate limit {provider_name}: {e.message}, повтор через {wait:.0f}с")
                        yield f"data: {json.dumps({'type': 'retry_note', 'content': f'Превышен лимит запросов {provider_name}. Повтор через {wait:.0f}с...'})}\n\n"
                        await asyncio.sleep(wait)
                        continue

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code != 429 or retry_attempt >= max_retries - 1:
                            raise
                        logger.warning(f"HTTP 429 {provider_name}, повтор через {delay}с")
                        yield f"data: {json.dumps({'type': 'retry_note', 'content': f'Превышен лимит запросов. Повтор через {delay}с...'})}\n\n"
                        await asyncio.sleep(delay)
                        continue

                    except httpx.ConnectError as e:
                        if retry_attempt >= max_retries - 1:
                            raise
                        logger.warning(f"Ошибка подключения {provider_name}: {e}, повтор через {delay}с")
                        yield f"data: {json.dumps({'type': 'retry_note', 'content': f'Ошибка подключения к {provider_name}. Повтор через {delay}с...'})}\n\n"
                        await asyncio.sleep(delay)
                        continue

                    if full_response.strip():
                        break

                    if retry_attempt < max_retries - 1:
                        logger.warning(f"Пустой ответ модели, повтор через {delay}с")
                        yield f"data: {json.dumps({'type': 'retry_note', 'content': f'Модель не вернула ответ. Повтор через {delay}с...'})}\n\n"
                        await asyncio.sleep(delay)

                if not full_response.strip():
                    logger.error(f"Модель не вернула ответ после {max_retries} попыток")
                    yield f"event: error\ndata: Модель не вернула ответ. Попробуйте позже.\n\n"
                    return

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

                        # Логируем действие в сводку
                        action_summary = _summarize_tool_action(tool_name, tool_data, result)
                        if action_summary:
                            actions_log.append(action_summary)

                        if tool_name != "stop":
                            tools_were_called = True
                        
                        if tool_name == "stop" or result.get("stop"):
                            break
                        
                        messages_to_send.append({"role": "assistant", "content": full_response})
                        messages_to_send.append({"role": "user", "content": f"Результат выполнения инструмента {tool_name}:\n{json.dumps(result)}"})
                        continue

                    if tools_were_called:
                        messages_to_send.append({"role": "assistant", "content": full_response})
                        messages_to_send.append({"role": "user", "content": "Ты начал использовать инструменты, поэтому ты не можешь просто завершить ответ в chat-режиме. Если задача решена — вызови инструмент stop. Если нет — продолжи с другим инструментом."})
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
                    if tools_were_called:
                        messages_to_send.append({"role": "assistant", "content": full_response})
                        messages_to_send.append({"role": "user", "content": "Твой ответ не удалось распарсить как JSON. Если задача решена — вызови инструмент stop. Если нет — вызови нужный инструмент."})
                        continue

                    async with async_session() as session:
                        session.add(Message(
                            chat_id=chat_id,
                            role="assistant",
                            content=full_response,
                        ))
                        await session.commit()
                    break

            yield "data: [DONE]\n\n"

        except ProviderRateLimitError as e:
            logger.error(f"Rate limit {provider_name} (исчерпаны попытки): {e.message}")
            yield f"event: error\ndata: {json.dumps({'type': 'rate_limit', 'message': e.message, 'retry_after': e.retry_after})}\n\n"
        except openai_client.httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} от {provider_name}: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"
        except openai_client.ProviderNotConfigured as e:
            logger.error(f"Провайдер не настроен: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"
        except Exception as e:
            logger.exception(f"Ошибка в чате #{chat_id}: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"
        finally:
            if full_response.strip() and chat_id:
                try:
                    async with async_session() as session:
                        exists = await session.execute(
                            select(Message).where(
                                Message.chat_id == chat_id,
                                Message.role == "assistant",
                                Message.content == full_response,
                            )
                        )
                        if not exists.scalar_one_or_none():
                            session.add(Message(
                                chat_id=chat_id,
                                role="assistant",
                                content=full_response,
                            ))
                            await session.commit()
                except Exception:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
