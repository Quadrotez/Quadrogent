import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from routers import chat


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Краткий заголовок"}}]}


class FakeAsyncClient:
    requests = []

    def __init__(self, **kwargs):
        self.options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, **kwargs):
        self.requests.append({"url": url, "options": self.options, **kwargs})
        return FakeResponse()


class TitleGenerationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeAsyncClient.requests = []

    async def test_opencode_title_uses_public_authorization(self):
        with (
            patch.object(chat.openai_client, "_get_api_key_record", new=AsyncMock(return_value=None)),
            patch.object(chat.openai_client, "get_base_url", new=AsyncMock(return_value="https://opencode.test/v1")),
            patch.object(chat.httpx, "AsyncClient", FakeAsyncClient),
        ):
            title = await chat._generate_title("opencode", "openai", "opencode-model", "Создай файл")

        self.assertEqual(title, "Краткий заголовок")
        self.assertEqual(len(FakeAsyncClient.requests), 1)
        self.assertEqual(
            FakeAsyncClient.requests[0]["headers"]["Authorization"],
            "Bearer public",
        )

    async def test_unconfigured_cloud_provider_skips_title_request(self):
        with (
            patch.object(chat.openai_client, "_get_api_key_record", new=AsyncMock(return_value=None)),
            patch.object(chat.openai_client, "get_base_url", new=AsyncMock()) as get_base_url,
            patch.object(chat.httpx, "AsyncClient", FakeAsyncClient),
        ):
            title = await chat._generate_title("openrouter", "openai", "model", "Создай файл")

        self.assertIsNone(title)
        self.assertEqual(FakeAsyncClient.requests, [])
        get_base_url.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
