import asyncio
import json
import logging
import os
import re
import httpx
from bs4 import BeautifulSoup
from sandbox_manager import SandboxManager
from database import async_session
from models import Setting
from sqlalchemy import select

logger = logging.getLogger("quadrogent.tools")


async def _get_search_settings():
    """Load web search settings from DB."""
    try:
        async with async_session() as session:
            providers_r = await session.execute(select(Setting).where(Setting.key == "search_providers"))
            proxy_r = await session.execute(select(Setting).where(Setting.key == "search_proxy"))
            fetch_r = await session.execute(select(Setting).where(Setting.key == "web_fetch_enabled"))
            search_fetch_r = await session.execute(
                select(Setting).where(Setting.key == "web_search_fetch_results")
            )
            providers = (providers_r.scalar_one_or_none() or Setting(key="", value="duckduckgo")).value
            proxy = (proxy_r.scalar_one_or_none() or Setting(key="", value="")).value
            fetch_enabled = (fetch_r.scalar_one_or_none() or Setting(key="", value="true")).value
            search_fetch_enabled = (
                search_fetch_r.scalar_one_or_none() or Setting(key="", value="true")
            ).value
            return (
                [p.strip() for p in providers.split(",") if p.strip()],
                proxy,
                fetch_enabled == "true",
                search_fetch_enabled == "true",
            )
    except Exception:
        return ["duckduckgo"], "", True, True


def _extract_page_text(html: str) -> str:
    """Returns readable text from an HTML document without scripts or navigation clutter."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"]):
        element.decompose()
    return " ".join(soup.stripped_strings)


async def _fetch_search_result(url: str, proxy: str) -> dict:
    """Fetches one search result and returns compact, model-ready page text."""
    max_content_chars = 8_000
    try:
        parsed_url = httpx.URL(url)
        if parsed_url.scheme not in {"http", "https"}:
            return {"fetch_error": "Поддерживаются только HTTP(S)-ссылки."}

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            proxy=proxy or None,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "html" in content_type:
            content = _extract_page_text(response.text)
        elif any(media_type in content_type for media_type in ("text", "json", "xml")):
            content = response.text
        else:
            return {"fetch_error": f"Пропущен нетекстовый ответ: {content_type or 'unknown'}"}

        content = content.strip()
        if not content:
            return {"fetch_error": "Страница не вернула извлекаемый текст."}

        truncated = len(content) > max_content_chars
        return {
            "page_content": content[:max_content_chars],
            "page_content_truncated": truncated,
        }
    except Exception as exc:
        logger.info("Не удалось загрузить результат поиска %s: %s", url, exc)
        return {"fetch_error": f"Ошибка загрузки: {exc}"}


async def _enrich_search_results(results: list[dict], proxy: str) -> list[dict]:
    """Fetches all selected search results concurrently while retaining their order."""
    fetched = await asyncio.gather(
        *[_fetch_search_result(result.get("href", ""), proxy) for result in results]
    )
    return [{**result, **page_data} for result, page_data in zip(results, fetched)]


class ToolExecutor:
    REQUIRED_PARAMS = {
        "bash": ["command"],
        "create_file": ["path", "content"],
        "patch_file": ["path", "content"],
        "remove": ["path"],
        "makedir": ["path"],
        "install": ["type", "package"],
        "present": ["path"],
        "zip": ["path", "output_path"],
        "unzip": ["path", "output_path"],
        "web_search": ["query"],
        "web_fetch": ["url"],
        "save_context": ["text"],
    }

    @staticmethod
    async def execute(tool_name: str, args: dict):
        logger.info(f"Выполнение инструмента: {tool_name} с аргументами {args}")

        required = ToolExecutor.REQUIRED_PARAMS.get(tool_name, [])
        missing = [p for p in required if not args.get(p)]
        if missing:
            return {
                "error": f"Отсутствуют обязательные параметры: {', '.join(missing)}. Вызови инструмент снова со всеми параметрами.",
                "exit_code": 1,
            }

        if tool_name == "bash":
            return await SandboxManager.run_command(args.get("command", ""))

        elif tool_name == "create_file":
            path = args.get("path")
            content_raw = args.get("content", "")

            if isinstance(content_raw, list):
                content = "\n".join([str(line) for line in content_raw])
            else:
                content = str(content_raw)

            await SandboxManager.write_file(path, content)
            return {"stdout": f"Файл успешно создан: {path}", "exit_code": 0}

        elif tool_name == "patch_file":
            path = args.get("path")
            content_raw = args.get("content", "")

            if isinstance(content_raw, list):
                content = "\n".join([str(line) for line in content_raw])
            else:
                content = str(content_raw)

            await SandboxManager.write_file(path, content)
            return {"stdout": f"Файл успешно изменён: {path}", "exit_code": 0}

        elif tool_name == "remove":
            path = args.get("path")
            return await SandboxManager.run_command(f"rm -rf {path}")

        elif tool_name == "makedir":
            path = args.get("path")
            return await SandboxManager.run_command(f"mkdir -p {path}")

        elif tool_name == "install":
            pkg_type = args.get("type")
            package = args.get("package")
            venv = args.get("virtualenv")
            should_update = args.get("update", False)

            if pkg_type == "apk":
                update_cmd = "apk update && " if should_update else ""
                cmd = f"{update_cmd}apk add --no-cache {package}"
                return await SandboxManager.run_command(cmd, timeout=120, user="root")
            elif pkg_type == "pip":
                default_venv = "/home/quadrogent/venv"
                if not venv:
                    venv = default_venv
                    create_res = await SandboxManager.run_command(f"python3 -m venv {venv}", timeout=30)
                    if create_res.get("exit_code") != 0:
                        return await SandboxManager.run_command(f"pip install --break-system-packages {package}", timeout=300)
                pip_cmd = f"{venv}/bin/pip"
                return await SandboxManager.run_command(f"{pip_cmd} install {package}", timeout=300)
            return {"error": f"Unknown install type: {pkg_type}", "exit_code": 1}

        elif tool_name == "present":
            path = args.get("path")
            await SandboxManager.run_command("mkdir -p /home/quadrogent/output")

            check_dir = await SandboxManager.run_command(f"test -d {path}")
            is_dir = check_dir.get("exit_code") == 0

            filename = os.path.basename(path.rstrip("/"))

            if is_dir:
                zip_filename = f"{filename}.zip"
                dest = f"/home/quadrogent/output/{zip_filename}"
                await SandboxManager.run_command(f"rm -rf {dest}")
                parent_dir = os.path.dirname(path.rstrip("/")) or "."
                base_name = os.path.basename(path.rstrip("/"))
                res = await SandboxManager.run_command(f"cd {parent_dir} && zip -r {dest} {base_name}", timeout=120)
                if res.get("exit_code") == 0:
                    return {"stdout": f"Презентовано: {dest}", "exit_code": 0}
                return res
            else:
                dest = f"/home/quadrogent/output/{filename}"
                await SandboxManager.run_command(f"rm -rf {dest}")
                res = await SandboxManager.run_command(f"cp {path} {dest}")

            if res.get("exit_code") == 0:
                return {"stdout": f"Презентовано: {dest}", "exit_code": 0}
            return res

        elif tool_name == "zip":
            path = args.get("path")
            output_path = args.get("output_path")
            res = await SandboxManager.run_command(f"zip -r {output_path} {path}", timeout=120)
            if res.get("exit_code") == 0:
                return {"stdout": "Файл успешно запакован", "exit_code": 0}
            return res

        elif tool_name == "unzip":
            path = args.get("path")
            output_path = args.get("output_path")
            res = await SandboxManager.run_command(f"unzip {path} -d {output_path}", timeout=120)
            if res.get("exit_code") == 0:
                return {"stdout": "Файл успешно распакован", "exit_code": 0}
            return res

        elif tool_name == "stop":
            return {"stdout": "Работа завершена", "exit_code": 0, "stop": True}

        elif tool_name == "web_search":
            query = args.get("query", "")
            max_results = int(args.get("max_results", 5))
            chosen_provider = args.get("provider", "").strip().lower()
            enabled_providers, proxy, fetch_enabled, search_fetch_enabled = await _get_search_settings()

            # If model chose a specific provider and it's enabled — use only it
            # If not specified or invalid — use all enabled providers
            if chosen_provider and chosen_provider in enabled_providers:
                active_providers = [chosen_provider]
            else:
                active_providers = enabled_providers

            all_results = []

            # --- DuckDuckGo ---
            if "duckduckgo" in active_providers:
                try:
                    from duckduckgo_search import DDGS
                    loop = asyncio.get_event_loop()
                    raw = await loop.run_in_executor(
                        None, lambda: list(DDGS(proxy=proxy or None).text(query, max_results=max_results))
                    )
                    for r in raw:
                        all_results.append({
                            "provider": "duckduckgo",
                            "title": r.get("title", ""),
                            "href": r.get("href", ""),
                            "body": r.get("body", ""),
                        })
                except Exception as e:
                    logger.warning(f"DuckDuckGo search failed: {e}")

            # --- Google ---
            if "google" in active_providers:
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    async with httpx.AsyncClient(timeout=15, follow_redirects=True, proxy=proxy or None) as client:
                        resp = await client.get(
                            f"https://www.google.com/search?q={httpx.URL(query)}&num={max_results}",
                            headers=headers,
                        )
                        resp.raise_for_status()
                        text = resp.text
                        for m in re.finditer(r'<a href="/url\?q=([^"&]+).*?<h3[^>]*>(.*?)</h3>', text, re.DOTALL):
                            url = m.group(1)
                            title = re.sub(r'<[^>]+>', '', m.group(2))
                            all_results.append({
                                "provider": "google",
                                "title": title,
                                "href": url,
                                "body": "",
                            })
                            if len(all_results) >= max_results:
                                break
                except Exception as e:
                    logger.warning(f"Google search failed: {e}")

            # --- Bing ---
            if "bing" in active_providers:
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    async with httpx.AsyncClient(timeout=15, follow_redirects=True, proxy=proxy or None) as client:
                        resp = await client.get(
                            f"https://www.bing.com/search?q={httpx.URL(query)}&count={max_results}",
                            headers=headers,
                        )
                        resp.raise_for_status()
                        text = resp.text
                        for m in re.finditer(r'<a href="(https?://[^"]+)"[^>]*><h2[^>]*>(.*?)</h2>', text, re.DOTALL):
                            url = m.group(1)
                            title = re.sub(r'<[^>]+>', '', m.group(2))
                            all_results.append({
                                "provider": "bing",
                                "title": title,
                                "href": url,
                                "body": "",
                            })
                            if len(all_results) >= max_results:
                                break
                except Exception as e:
                    logger.warning(f"Bing search failed: {e}")

            # --- Yandex ---
            if "yandex" in active_providers:
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    async with httpx.AsyncClient(timeout=15, follow_redirects=True, proxy=proxy or None) as client:
                        resp = await client.get(
                            f"https://yandex.ru/search/?text={httpx.URL(query)}&numdoc={max_results}",
                            headers=headers,
                        )
                        resp.raise_for_status()
                        text = resp.text
                        for m in re.finditer(r'<a[^>]+class="[^"]*OrganicTitle[^"]*"[^>]*href="([^"]+)"[^>]*>.*?<span[^>]*>(.*?)</span>', text, re.DOTALL):
                            url = m.group(1)
                            title = re.sub(r'<[^>]+>', '', m.group(2))
                            all_results.append({
                                "provider": "yandex",
                                "title": title,
                                "href": url,
                                "body": "",
                            })
                            if len(all_results) >= max_results:
                                break
                except Exception as e:
                    logger.warning(f"Yandex search failed: {e}")

            if all_results:
                selected_results = all_results[:max_results]
                # Автоматическое извлечение включается отдельно и уважает общий запрет web_fetch.
                if fetch_enabled and search_fetch_enabled:
                    selected_results = await _enrich_search_results(selected_results, proxy)
                return {
                    "stdout": json.dumps(selected_results, ensure_ascii=False, indent=2),
                    "exit_code": 0,
                }
            return {"stdout": "", "stderr": "Поиск не дал результатов. Проверьте настройки провайдеров поиска.", "exit_code": 1}

        elif tool_name == "web_fetch":
            url = args.get("url", "")
            _, proxy, fetch_enabled, _ = await _get_search_settings()
            if not fetch_enabled:
                return {"stdout": "", "stderr": "Инструмент web_fetch отключён в настройках.", "exit_code": 1}
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, proxy=proxy or None) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")
                    if "text" in content_type or "json" in content_type or "xml" in content_type or "html" in content_type:
                        content = resp.text
                    else:
                        content = f"[{content_type}] Content is binary, length: {len(resp.content)} bytes"

                return {"stdout": content, "exit_code": 0}
            except Exception as e:
                return {"stdout": "", "stderr": f"Ошибка загрузки: {e}", "exit_code": 1}

        return {"error": f"Unknown tool: {tool_name}", "exit_code": 1}
