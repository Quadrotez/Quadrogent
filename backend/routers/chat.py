import asyncio
import json
import logging
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from ollama_client import chat_stream as ollama_chat_stream, get_ollama_url
import openai_client
from openai_client import ProviderRateLimitError, StreamResult, ProviderNotConfigured
from providers import PROVIDERS, get_provider_type
from database import async_session
from models import Chat, Message, Setting, ToolCall, ApiKey
from tool_schemas import get_tools_for_provider
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
        import re
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
    elif tool_name == "save_context":
        return f"Контекст сохранён{status}"
    elif tool_name == "web_search":
        return f"Поиск в интернете: {tool_data.get('query', '?')}{status}"
    elif tool_name == "web_fetch":
        return f"Загружен контент: {tool_data.get('url', '?')}{status}"
    else:
        return f"Инструмент {tool_name}{status}"


class ChatMessage(BaseModel):
    role: str
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

        record = await openai_client._get_api_key_record(provider_name)
        api_key = record.api_key if record and record.api_key else None
        # OpenCode использует публичный ключ по умолчанию — так же, как основной клиент.
        if not api_key and provider_name == "opencode":
            api_key = "public"
        if not api_key:
            logger.warning("Не удалось сгенерировать заголовок: провайдер %s не настроен", provider_name)
            return None

        base_url = await openai_client.get_base_url(provider_name)
        proxy_url = getattr(record, "proxy_url", None) or None
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0, proxy=proxy_url) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": real_model,
                    "messages": [{"role": "user", "content": title_prompt}],
                    "max_tokens": 50,
                    "temperature": 0.3,
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip().strip('"\'')

    except Exception as e:
        logger.warning(f"Ошибка генерации заголовка: {e}")
        return None


async def _is_generate_titles_enabled() -> bool:
    async with async_session() as session:
        res = await session.execute(select(Setting).where(Setting.key == "generate_titles"))
        row = res.scalar_one_or_none()
        return row and row.value == "true"


async def _get_self_context() -> str:
    """Читает сохранённый контекст из настроек."""
    async with async_session() as session:
        res = await session.execute(select(Setting).where(Setting.key == "self_context"))
        row = res.scalar_one_or_none()
        return (row.value or "").strip() if row else ""


async def _save_self_context(text: str):
    """Сохраняет контекст в настройки (дописывает с новой строки)."""
    async with async_session() as session:
        res = await session.execute(select(Setting).where(Setting.key == "self_context"))
        row = res.scalar_one_or_none()
        new_entry = text.strip()
        if not new_entry:
            return
        if row:
            existing = (row.value or "").strip()
            if existing:
                row.value = existing + "\n" + new_entry
            else:
                row.value = new_entry
        else:
            session.add(Setting(key="self_context", value=new_entry))
        await session.commit()


async def _is_multi_command_enabled() -> bool:
    async with async_session() as session:
        res = await session.execute(select(Setting).where(Setting.key == "multi_command"))
        row = res.scalar_one_or_none()
        return row.value != "false" if row and row.value else True


async def _get_tool_calling_mode() -> str:
    """Читает режим tool calling: 'native' или 'json'."""
    async with async_session() as session:
        res = await session.execute(select(Setting).where(Setting.key == "tool_calling_mode"))
        row = res.scalar_one_or_none()
        return row.value if row and row.value else "native"


def _parse_json_tool_calls(text: str) -> list[dict]:
    """Парсит JSON tool calls из текста модели (JSON-режим).

    Ищет блоки ```json ... ``` или одиночные JSON-объекты с полем "tool" или "action".
    Возвращает список {name, arguments, id}.
    """
    import re
    tool_calls = []

    # Ищем блоки ```json ... ```
    json_blocks = re.findall(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    for block in json_blocks:
        try:
            parsed = json.loads(block.strip())
            if isinstance(parsed, dict):
                tool_name = parsed.pop("tool", None) or parsed.pop("action", None)
                if tool_name:
                    tool_args = {k: v for k, v in parsed.items()}
                    tool_calls.append({
                        "id": f"json_call_{tool_name}_{len(tool_calls)}",
                        "name": tool_name,
                        "arguments": tool_args,
                    })
        except (json.JSONDecodeError, AttributeError):
            continue

    # Если не нашли в блоках — ищем голые JSON-объекты
    if not tool_calls:
        for match in re.finditer(r'\{[^{}]*"(?:tool|action)"\s*:\s*"[^"]+"[^{}]*\}', text):
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    tool_name = parsed.pop("tool", None) or parsed.pop("action", None)
                    if tool_name:
                        tool_args = {k: v for k, v in parsed.items()}
                        tool_calls.append({
                            "id": f"json_call_{tool_name}_{len(tool_calls)}",
                            "name": tool_name,
                            "arguments": tool_args,
                        })
            except (json.JSONDecodeError, AttributeError):
                continue

    # XML format parsing
    TAG_FUNC = "function"
    TAG_PARAM = "parameter"
    func_re = re.compile(
        r"<" + TAG_FUNC + r"=(\w+)>(.*?)</" + TAG_FUNC + r">",
        re.DOTALL,
    )
    param_re = re.compile(
        r"<" + TAG_PARAM + r"=(\w+)>(.*?)</" + TAG_PARAM + r">",
        re.DOTALL,
    )
    if not tool_calls:
        for match in func_re.finditer(text):
            fn_name = match.group(1)
            params_block = match.group(2)
            fn_args = {}
            for pmatch in param_re.finditer(params_block):
                fn_args[pmatch.group(1)] = pmatch.group(2).strip()
            tool_calls.append({
                "id": f"xml_call_{fn_name}_{len(tool_calls)}",
                "name": fn_name,
                "arguments": fn_args,
            })

    return tool_calls


async def _build_json_tool_schemas_text() -> str:
    from tool_schemas import TOOLS, _get_tool_filter_settings, _get_enabled_providers
    fetch_enabled = await _get_tool_filter_settings()
    enabled_providers = await _get_enabled_providers()
    lines = [
        "# AVAILABLE TOOLS (JSON FORMAT):\n",
        "You can call tools by outputting a JSON code block.\n",
        'Format: ```json\n{"tool": "tool_name", "param1": "value1", ...}\n```\n',
        'IMPORTANT: The key must be "tool", not "action" or other names.\n',
        "You can output multiple tool calls in separate JSON blocks.\n",
        "After all tools are called, explain the results in plain text.\n\n",
        "Available tools:\n",
    ]
    for t in TOOLS:
        fn = t["function"]
        if fn["name"] == "web_fetch" and not fetch_enabled:
            continue
        params = fn["parameters"]["properties"]
        required = fn["parameters"].get("required", [])
        param_parts = []
        for pname, pinfo in params.items():
            req = " (required)" if pname in required else ""
            desc = pinfo.get('description', '')
            if pname == "provider" and fn["name"] == "web_search":
                desc = f"Search provider: {', '.join(enabled_providers)}. Leave empty for all."
            param_parts.append(f"    - {pname}: {desc}{req}")
        lines.append(f"- **{fn['name']}**: {fn['description']}")
        if param_parts:
            lines.append("\n".join(param_parts))
        lines.append("")
    return "\n".join(lines)


async def _reconstruct_messages_from_db(chat_id: int, system_prompt: str, tool_calling_mode: str, provider_type: str) -> list[dict]:
    """Восстанавливает историю сообщений из БД с tool calls для модели."""
    async with async_session() as session:
        result = await session.execute(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.id)
        )
        db_messages = result.scalars().all()

        msg_ids = [m.id for m in db_messages if m.role == "assistant"]
        tc_map = {}
        if msg_ids:
            tc_result = await session.execute(
                select(ToolCall).where(ToolCall.message_id.in_(msg_ids))
            )
            for tc in tc_result.scalars().all():
                tc_map.setdefault(tc.message_id, []).append(tc)

    messages_to_send = [{"role": "system", "content": system_prompt}]
    for db_msg in db_messages:
        if db_msg.role == "user":
            messages_to_send.append({"role": "user", "content": db_msg.content})
        elif db_msg.role == "assistant":
            tcs = tc_map.get(db_msg.id, [])
            if tcs and tool_calling_mode == "native":
                tool_calls_list = []
                for tc in tcs:
                    try:
                        tc_input = json.loads(tc.input) if tc.input else {}
                    except json.JSONDecodeError:
                        tc_input = {}
                    tc_input.pop("tool", None)
                    tc_id = f"call_{tc.tool}_{tc.id}"
                    if provider_type == "ollama":
                        func_args = tc_input
                    else:
                        func_args = json.dumps(tc_input)
                    tool_calls_list.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc.tool, "arguments": func_args},
                    })
                messages_to_send.append({
                    "role": "assistant",
                    "content": db_msg.content or "",
                    "tool_calls": tool_calls_list,
                })
                for tc in tcs:
                    tc_id = f"call_{tc.tool}_{tc.id}"
                    tc_result_data = json.loads(tc.output) if tc.output else {}
                    messages_to_send.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": json.dumps(tc_result_data),
                    })
            elif tcs and tool_calling_mode == "json":
                messages_to_send.append({"role": "assistant", "content": db_msg.content or ""})
                tool_results_text = "\n".join(
                    f"Tool {tc.tool} результат:\n{(tc.output or '{}')}"
                    for tc in tcs if tc.tool != "stop"
                )
                if tool_results_text:
                    messages_to_send.append({
                        "role": "user",
                        "content": f"Результаты выполнения инструментов:\n\n{tool_results_text}",
                    })
            else:
                messages_to_send.append({"role": "assistant", "content": db_msg.content})

    return messages_to_send


@router.post("")
async def chat(request: ChatRequest):
    """Стриминг ответа через SSE с нативным tool calling."""
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

        # Добавляем сохранённый контекст (self-managed context)
        self_context = await _get_self_context()
        if self_context:
            system_prompt += f"\n\n# SAVED CONTEXT:\nТы ранее сохранил этот контекст. Используй его:\n\n{self_context}"

        # Получаем настройки
        multi_command = await _is_multi_command_enabled()
        tool_calling_mode = await _get_tool_calling_mode()

        # Схемы инструментов для API (только для native режима)
        tools = await get_tools_for_provider(provider_type) if tool_calling_mode == "native" else None

        # Для JSON режима — добавляем описания инструментов в системный промпт
        if tool_calling_mode == "json":
            system_prompt += "\n\n" + await _build_json_tool_schemas_text()

        try:
            # --- Создаём/находим чат и сохраняем сообщение пользователя ---
            is_new_chat = False
            async with async_session() as session:
                if request.chat_id:
                    chat_obj = await session.get(Chat, request.chat_id)
                else:
                    chat_obj = Chat(title="Новый чат")
                    session.add(chat_obj)
                    await session.flush()
                    is_new_chat = True

                if is_new_chat:
                    from sandbox_manager import SandboxManager
                    SandboxManager.cleanup_output()

                chat_id = chat_obj.id
                last_user_msg = next((m for m in reversed(messages) if m["role"] == "user"), None)
                if last_user_msg:
                    session.add(Message(chat_id=chat_id, role="user", content=last_user_msg["content"]))

                await session.commit()

            # Восстанавливаем историю из БД с tool calls
            messages_to_send = await _reconstruct_messages_from_db(
                chat_id, system_prompt, tool_calling_mode, provider_type
            )

            yield f"event: chat_id\ndata: {chat_id}\n\n"

            # --- Генерация заголовка ---
            generate_titles = await _is_generate_titles_enabled()
            if generate_titles and is_new_chat and last_user_msg:
                user_msg_text = last_user_msg["content"]
                title = await _generate_title(provider_name, provider_type, real_model, user_msg_text)
                if title:
                    title = title[:30]
                    async with async_session() as session:
                        chat_obj = await session.get(Chat, chat_id)
                        if chat_obj:
                            chat_obj.title = title
                            await session.commit()
                    yield f"event: title\ndata: {json.dumps({'chat_id': chat_id, 'title': title})}\n\n"

            # --- Цикл tool calling ---
            max_iterations = 15
            iteration = 0
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
                    if messages_to_send and messages_to_send[-1].get("content", "").startswith("--- ВЫПОЛНЕННЫЕ ДЕЙСТВИЯ"):
                        messages_to_send.pop()
                    messages_to_send.append({"role": "user", "content": actions_summary})

                max_retries = 5
                base_delay = 1
                stream_result = None

                for retry_attempt in range(max_retries):
                    full_response = ""
                    delay = base_delay * (2 ** retry_attempt)

                    try:
                        if provider_type == "ollama":
                            stream = ollama_chat_stream(real_model, messages_to_send, tools=tools)
                        else:
                            stream = openai_client.chat_stream(provider_name, real_model, messages_to_send, tools=tools)

                        async for chunk in stream:
                            if isinstance(chunk, StreamResult):
                                stream_result = chunk
                                full_response = chunk.text
                            else:
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
                        if e.response.status_code not in (429, 500, 502, 503) or retry_attempt >= max_retries - 1:
                            raise
                        logger.warning(f"HTTP {e.response.status_code} {provider_name}, повтор через {delay}с")
                        yield f"data: {json.dumps({'type': 'retry_note', 'content': f'Сервер вернул ошибку {e.response.status_code}. Повтор через {delay}с...'})}\n\n"
                        await asyncio.sleep(delay)
                        continue

                    except httpx.ConnectError as e:
                        if retry_attempt >= max_retries - 1:
                            raise
                        logger.warning(f"Ошибка подключения {provider_name}: {e}, повтор через {delay}с")
                        yield f"data: {json.dumps({'type': 'retry_note', 'content': f'Ошибка подключения к {provider_name}. Повтор через {delay}с...'})}\n\n"
                        await asyncio.sleep(delay)
                        continue

                    if full_response.strip() or (stream_result and stream_result.tool_calls):
                        break

                    if retry_attempt < max_retries - 1:
                        logger.warning(f"Пустой ответ модели, повтор через {delay}с")
                        yield f"data: {json.dumps({'type': 'retry_note', 'content': f'Модель не вернула ответ. Повтор через {delay}с...'})}\n\n"
                        await asyncio.sleep(delay)

                if not full_response.strip() and not (stream_result and stream_result.tool_calls):
                    logger.error(f"Модель не вернула ответ после {max_retries} попыток")
                    yield f"event: error\ndata: Модель не вернула ответ. Попробуйте позже.\n\n"
                    return

                # --- Обработка tool calls ---
                tool_calls = stream_result.tool_calls if stream_result else []

                # JSON-режим: парсим tool calls из текста если нативных нет
                if not tool_calls and tool_calling_mode == "json" and full_response.strip():
                    tool_calls = _parse_json_tool_calls(full_response)

                if tool_calls:
                    # Сохраняем ОДИН ответ ассистента (с текстом, если есть)
                    async with async_session() as session:
                        assistant_msg = Message(
                            chat_id=chat_id, role="assistant", content=full_response or "",
                        )
                        session.add(assistant_msg)
                        await session.flush()
                        assistant_msg_id = assistant_msg.id
                        await session.commit()

                    # Выполняем все tool calls и собираем результаты
                    # Если multi_command выключен — только первый вызов
                    if not multi_command:
                        tool_calls = tool_calls[:1]
                    tool_results = {}
                    should_stop = False
                    for tc in tool_calls:
                        tool_name = tc["name"]
                        tool_args = tc["arguments"]
                        tool_call_id = tc.get("id", f"call_{tool_name}")

                        # Сохраняем tool call, привязанный к ОДНОМУ сообщению ассистента
                        async with async_session() as session:
                            tool_call_record = ToolCall(
                                message_id=assistant_msg_id,
                                tool=tool_name,
                                input=json.dumps({"tool": tool_name, **tool_args}),
                            )
                            session.add(tool_call_record)
                            await session.commit()
                            tc_db_id = tool_call_record.id

                        # save_context — special: store to settings
                        if tool_name == "save_context":
                            await _save_self_context(tool_args.get("text", ""))
                            result = {"stdout": "Контекст сохранён", "exit_code": 0}
                        else:
                            # Отправляем событие начала выполнения (для UI-индикатора)
                            yield f"event: tool_executing\ndata: {json.dumps({'tool': tool_name, 'input': tool_args})}\n\n"
                            from tool_executor import ToolExecutor
                            result = await ToolExecutor.execute(tool_name, tool_args)

                        tool_results[tool_call_id] = result

                        # Обновляем result в БД
                        async with async_session() as session:
                            tc_record = await session.get(ToolCall, tc_db_id)
                            if tc_record:
                                tc_record.output = json.dumps(result)
                                tc_record.status = "success" if result.get("exit_code") == 0 else "error"
                                await session.commit()

                        yield f"event: tool_result\ndata: {json.dumps({'tool': tool_name, 'input': tool_args, 'result': result})}\n\n"

                        # Логируем действие
                        action_summary = _summarize_tool_action(tool_name, tool_args, result)
                        if action_summary:
                            actions_log.append(action_summary)

                        tools_were_called = True

                        if tool_name == "stop" or result.get("stop"):
                            # Сохраняем текст модели перед выходом (fix: stop removes text)
                            if full_response.strip():
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
                            should_stop = True
                            break

                    if should_stop:
                        break

                    # Добавляем tool results в историю для следующей итерации
                    if tool_calling_mode == "json":
                        # JSON-режим: plain text для совместимости с Ollama
                        tool_results_text = "\n".join(
                            f"Tool {tool_results[tc_id].get('tool', tc['name'])} результат:\n"
                            f"{json.dumps(tool_results.get(tc_id, {}), ensure_ascii=False, indent=2)}"
                            for tc in tool_calls
                            if (tc_id := tc.get("id", f"call_{tc['name']}")) != "stop"
                        )
                        if tool_results_text:
                            messages_to_send.append({
                                "role": "user",
                                "content": f"Результаты выполнения инструментов:\n\n{tool_results_text}",
                            })
                    else:
                        for tc in tool_calls:
                            tool_name = tc["name"]
                            tc_id = tc.get("id", f"call_{tool_name}")
                            if tool_name == "stop":
                                continue
                            # Ollama expects arguments as dict, OpenAI as string
                            if provider_type == "ollama":
                                func_args = tc["arguments"]
                            else:
                                func_args = json.dumps(tc["arguments"])
                            messages_to_send.append({
                                "role": "assistant",
                                "content": full_response or "",
                                "tool_calls": [{
                                    "id": tc_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": func_args,
                                    },
                                }],
                            })
                            messages_to_send.append({
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "content": json.dumps(tool_results.get(tc_id, {})),
                            })

                    continue

                # --- Нет tool calls: текстовый ответ ---
                if tools_were_called:
                    # Модель уже вызывала инструменты, теперь отвечает текстом —
                    # это финальный ответ. Сохраняем и выходим.
                    async with async_session() as session:
                        session.add(Message(
                            chat_id=chat_id, role="assistant", content=full_response,
                        ))
                        await session.commit()
                    break

                # Обычный текстовый ответ (без инструментов)
                async with async_session() as session:
                    session.add(Message(
                        chat_id=chat_id, role="assistant", content=full_response,
                    ))
                    await session.commit()
                break

            yield "data: [DONE]\n\n"

        except ProviderRateLimitError as e:
            logger.error(f"Rate limit {provider_name} (исчерпаны попытки): {e.message}")
            yield f"event: error\ndata: {json.dumps({'type': 'rate_limit', 'message': e.message, 'retry_after': e.retry_after})}\n\n"
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} от {provider_name}: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"
        except ProviderNotConfigured as e:
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
