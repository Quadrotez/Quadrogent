import os
import base64
import logging
import httpx

logger = logging.getLogger("quadrogent.sandbox")

SANDBOX_API_URL = os.getenv("SANDBOX_API_URL", "http://localhost:5000")


class SandboxManager:
    @staticmethod
    async def run_command(command: str, timeout: int = 60, user: str = "quadrogent"):
        try:
            async with httpx.AsyncClient(timeout=timeout + 30) as client:
                resp = await client.post(
                    f"{SANDBOX_API_URL}/exec",
                    json={"command": command, "timeout": timeout, "user": user},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            return {"stdout": "", "stderr": "Timeout expired", "exit_code": -1}
        except Exception as e:
            logger.error(f"Sandbox API error: {e}")
            return {"stdout": "", "stderr": str(e), "exit_code": -1}

    @staticmethod
    async def write_file(path: str, content: str):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SANDBOX_API_URL}/write",
                    json={"path": path, "content": content},
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error(f"Sandbox write error: {e}")

    @staticmethod
    async def write_file_binary(path: str, content: bytes):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SANDBOX_API_URL}/write-binary",
                    json={"path": path, "content": base64.b64encode(content).decode()},
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error(f"Sandbox write-binary error: {e}")

    @staticmethod
    def read_file(path: str) -> str:
        try:
            resp = httpx.get(
                f"{SANDBOX_API_URL}/read",
                params={"path": path},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["content"]
        except Exception as e:
            logger.error(f"Sandbox read error: {e}")
            return ""

    @staticmethod
    def read_file_binary(path: str) -> bytes:
        try:
            resp = httpx.get(
                f"{SANDBOX_API_URL}/read-binary",
                params={"path": path},
                timeout=30,
            )
            resp.raise_for_status()
            return base64.b64decode(resp.json()["content"])
        except Exception as e:
            logger.error(f"Sandbox read-binary error: {e}")
            return b""

    @staticmethod
    def cleanup_output():
        try:
            resp = httpx.post(f"{SANDBOX_API_URL}/cleanup", timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Sandbox cleanup error: {e}")
