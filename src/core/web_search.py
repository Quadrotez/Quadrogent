from duckduckgo_search import DDGS


class WebSearch:
    """Web search via DuckDuckGo."""

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ]
        except Exception as e:
            return [{"title": "Error", "url": "", "snippet": str(e)}]

    def format_results(self, results: list[dict]) -> str:
        if not results:
            return "Ничего не найдено."
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
        return "\n\n".join(parts)
