import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import ollama_client
from openai_client import StreamResult


class FakeOllamaResponse:
    def __init__(self, lines):
        self.lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeOllamaClient:
    requests = []
    response_lines = []

    def __init__(self, **kwargs):
        self.options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, "options": self.options, **kwargs})
        return FakeOllamaResponse(self.response_lines)


class OllamaThinkingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeOllamaClient.requests = []
        FakeOllamaClient.response_lines = [
            json.dumps({"message": {"thinking": "Проверяю условие. "}, "done": False}),
            json.dumps({"message": {"thinking": "Формирую вывод."}, "done": False}),
            json.dumps({"message": {"content": "Готовый ответ."}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]

    async def test_thinking_chunks_are_streamed_as_think_tags(self):
        with (
            patch.object(ollama_client, "get_ollama_url", new=AsyncMock(return_value="http://ollama.test")),
            patch.object(
                ollama_client,
                "get_model_settings",
                new=AsyncMock(return_value={"num_ctx": 8192, "temperature": 0.0, "top_p": 0.9, "max_tokens": 4096}),
            ),
            patch.object(ollama_client.httpx, "AsyncClient", FakeOllamaClient),
        ):
            chunks = [
                chunk
                async for chunk in ollama_client.chat_stream(
                    "qwen3:27b",
                    [{"role": "user", "content": "Реши задачу"}],
                )
            ]

        streamed_text = "".join(chunk for chunk in chunks if isinstance(chunk, str))
        result = chunks[-1]

        self.assertEqual(
            streamed_text,
            "<think>Проверяю условие. Формирую вывод.</think>\n\nГотовый ответ.",
        )
        self.assertIsInstance(result, StreamResult)
        self.assertEqual(result.text, streamed_text)
        self.assertTrue(FakeOllamaClient.requests[0]["json"]["think"])


if __name__ == "__main__":
    unittest.main()
