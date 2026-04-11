"""
web_search.py — Multi-engine web search with configurable backends.

Engines supported: duckduckgo (default), google, bing
All engines use direct HTTP scraping — no fragile API wrappers.

Settings (from DB):
  search_engine   : "duckduckgo" | "google" | "bing"
  search_proxy    : "http://..." or "" (optional)
  search_follow   : "1" | "0"  — fetch page content for top results
  search_download : "1" | "0"  — allow file downloads
"""
from __future__ import annotations
import re
import urllib.parse


# ── HTTP session factory ───────────────────────────────────────────────────────

def _make_session(proxy: str = "") -> "requests.Session":
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s


# ── DuckDuckGo (HTML endpoint — much more stable than the API wrapper) ─────────

def _search_ddg(query: str, max_results: int, proxy: str) -> list[dict]:
    """Scrape DuckDuckGo HTML results page directly."""
    import requests
    from html.parser import HTMLParser

    class _DDGParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.results: list[dict] = []
            self._in_title = False
            self._in_snippet = False
            self._in_result = False
            self._cur: dict = {}
            self._depth = 0

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            cls = attrs.get("class", "")
            # DDG HTML result block
            if tag == "div" and "result__body" in cls:
                self._in_result = True
                self._cur = {}
            if self._in_result:
                if tag == "a" and "result__a" in cls:
                    href = attrs.get("href", "")
                    # DDG wraps URLs — extract real URL
                    if "uddg=" in href:
                        m = re.search(r"uddg=([^&]+)", href)
                        if m:
                            href = urllib.parse.unquote(m.group(1))
                    self._cur["url"] = href
                    self._in_title = True
                if tag == "a" and "result__snippet" in cls:
                    self._in_snippet = True

        def handle_endtag(self, tag):
            if tag == "a":
                self._in_title = False
                self._in_snippet = False
            if tag == "div" and self._in_result and self._cur.get("url"):
                if self._cur.get("title") or self._cur.get("snippet"):
                    self.results.append(dict(self._cur))
                    self._cur = {}
                    self._in_result = False

        def handle_data(self, data):
            if self._in_title:
                self._cur["title"] = self._cur.get("title", "") + data
            if self._in_snippet:
                self._cur["snippet"] = self._cur.get("snippet", "") + data

    s = _make_session(proxy)
    params = {"q": query, "kl": "ru-ru", "kp": "-2"}
    try:
        r = s.get("https://html.duckduckgo.com/html/", params=params, timeout=10)
        r.raise_for_status()
        parser = _DDGParser()
        parser.feed(r.text)
        results = parser.results[:max_results]
        if results:
            return results
    except Exception:
        pass

    # Fallback: try DDG API library if installed
    try:
        # Try new ddgs library first
        try:
            from ddgs import DDGS as _DDGS
        except ImportError:
            from duckduckgo_search import DDGS as _DDGS
        kwargs = {}
        if proxy:
            kwargs["proxy"] = proxy
        with _DDGS(**kwargs) as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in raw
        ]
    except Exception as e:
        return [{"title": "DDG Error", "url": "", "snippet": str(e)}]


# ── Google (lite/web scrape) ───────────────────────────────────────────────────

def _search_google(query: str, max_results: int, proxy: str) -> list[dict]:
    """Scrape Google search results."""
    import requests
    s = _make_session(proxy)
    params = {"q": query, "num": max_results, "hl": "ru", "gl": "ru"}
    try:
        r = s.get("https://www.google.com/search", params=params, timeout=10)
        r.raise_for_status()
        html = r.text
        results = []
        # Extract result blocks
        blocks = re.findall(
            r'<div class="[^"]*tF2Cxc[^"]*".*?</div>\s*</div>\s*</div>',
            html, re.DOTALL
        )
        if not blocks:
            # Simpler pattern
            blocks = re.findall(r'<h3[^>]*>(.*?)</h3>.*?<a href="(https?://[^"]+)"', html, re.DOTALL)
            for title_html, url in blocks[:max_results]:
                title = re.sub(r"<[^>]+>", "", title_html).strip()
                if title and url and "google.com" not in url:
                    results.append({"title": title, "url": url, "snippet": ""})
            return results
        for block in blocks[:max_results]:
            title_m = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.DOTALL)
            url_m   = re.search(r'<a href="(https?://[^"]+)"', block)
            snip_m  = re.search(r'<span[^>]*class="[^"]*VwiC3b[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
            if title_m and url_m:
                title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
                url   = url_m.group(1).split("&")[0]
                snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip() if snip_m else ""
                results.append({"title": title, "url": url, "snippet": snippet})
        return results
    except Exception as e:
        return [{"title": "Google Error", "url": "", "snippet": str(e)}]


# ── Bing ──────────────────────────────────────────────────────────────────────

def _search_bing(query: str, max_results: int, proxy: str) -> list[dict]:
    """Scrape Bing search results."""
    import requests
    s = _make_session(proxy)
    params = {"q": query, "count": max_results, "setlang": "ru", "mkt": "ru-RU"}
    try:
        r = s.get("https://www.bing.com/search", params=params, timeout=10)
        r.raise_for_status()
        html = r.text
        results = []
        # Extract result blocks
        for m in re.finditer(
            r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL
        ):
            block = m.group(1)
            title_m = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.DOTALL)
            url_m   = re.search(r'<a[^>]+href="(https?://[^"]+)"', block)
            snip_m  = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if title_m and url_m:
                title   = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
                url     = url_m.group(1).split("?")[0]
                snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip() if snip_m else ""
                if "bing.com" not in url and "microsoft.com" not in url:
                    results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        return [{"title": "Bing Error", "url": "", "snippet": str(e)}]


# ── Page fetcher ───────────────────────────────────────────────────────────────

def _fetch_page(url: str, proxy: str = "", max_chars: int = 2000) -> str:
    """Fetch and strip a web page to plain text."""
    import requests
    s = _make_session(proxy)
    try:
        r = s.get(url, timeout=8, allow_redirects=True)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "text" not in content_type:
            return f"[Binary content: {content_type}]"
        text = r.text
        # Strip scripts/styles/tags
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>",  " ", text, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"[Error fetching page: {e}]"


# ── Main WebSearch class ───────────────────────────────────────────────────────

class WebSearch:
    def __init__(self, db=None):
        self._db = db

    def _settings(self):
        if not self._db:
            return {}
        return {
            "engine":   self._db.get_setting("search_engine",   "duckduckgo"),
            "proxy":    self._db.get_setting("search_proxy",    ""),
            "follow":   self._db.get_setting("search_follow",   "0") == "1",
            "download": self._db.get_setting("search_download", "0") == "1",
        }

    def search(self, query: str, max_results: int = 6) -> list[dict]:
        cfg     = self._settings()
        engine  = cfg.get("engine", "duckduckgo")
        proxy   = cfg.get("proxy", "")
        follow  = cfg.get("follow", False)

        if engine == "google":
            results = _search_google(query, max_results, proxy)
        elif engine == "bing":
            results = _search_bing(query, max_results, proxy)
        else:
            results = _search_ddg(query, max_results, proxy)

        # If primary engine returned only errors, try DDG as fallback
        real = [r for r in results if r.get("url")]
        if not real and engine != "duckduckgo":
            results = _search_ddg(query, max_results, proxy)

        # Optionally enrich results with page content
        if follow:
            for r in results[:3]:
                if r.get("url"):
                    page_text = _fetch_page(r["url"], proxy)
                    if page_text and not page_text.startswith("[Error"):
                        r["snippet"] = (r.get("snippet", "") + "\n\n" + page_text[:600]).strip()

        return results

    def format_results(self, results: list[dict]) -> str:
        if not results:
            return "Ничего не найдено."
        parts = []
        for i, r in enumerate(results, 1):
            title   = r.get("title", "")
            url     = r.get("url", "")
            snippet = r.get("snippet", "")
            line = f"{i}. {title}"
            if url:
                line += f"\n   {url}"
            if snippet:
                line += f"\n   {snippet[:300]}"
            parts.append(line)
        return "\n\n".join(parts)
