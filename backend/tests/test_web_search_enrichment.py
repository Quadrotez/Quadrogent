import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import tool_executor


class WebSearchEnrichmentTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_page_text_removes_non_content_elements(self):
        html = """
        <html><body>
          <header>Навигация</header>
          <main><h1>Основной заголовок</h1><p>Полезный текст.</p></main>
          <script>window.secret = 'не показывать'</script>
          <footer>Подвал</footer>
        </body></html>
        """

        text = tool_executor._extract_page_text(html)

        self.assertEqual(text, "Основной заголовок Полезный текст.")

    async def test_enrichment_preserves_order_and_attaches_page_data(self):
        results = [
            {"title": "Первая", "href": "https://example.com/first"},
            {"title": "Вторая", "href": "https://example.com/second"},
        ]

        with patch.object(
            tool_executor,
            "_fetch_search_result",
            new=AsyncMock(
                side_effect=[
                    {"page_content": "Текст первой страницы", "page_content_truncated": False},
                    {"fetch_error": "Недоступна"},
                ]
            ),
        ) as fetch_result:
            enriched = await tool_executor._enrich_search_results(results, "")

        self.assertEqual(enriched[0]["title"], "Первая")
        self.assertEqual(enriched[0]["page_content"], "Текст первой страницы")
        self.assertEqual(enriched[1]["title"], "Вторая")
        self.assertEqual(enriched[1]["fetch_error"], "Недоступна")
        self.assertEqual(fetch_result.await_count, 2)


if __name__ == "__main__":
    unittest.main()
