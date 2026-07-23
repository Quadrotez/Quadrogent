import os
import base64
import logging
import httpx

logger = logging.getLogger("quadrogent.sandbox")

SANDBOX_API_URL = os.getenv("SANDBOX_API_URL", "http://localhost:5000")


class SandboxManager:
    @staticmethod
    def run_command(command: str, timeout: int = 60, user: str = "quadrogent"):
        try:
            resp = httpx.post(
                f"{SANDBOX_API_URL}/exec",
                json={"command": command, "timeout": timeout, "user": user},
                timeout=timeout + 5,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            return {"stdout": "", "stderr": "Timeout expired", "exit_code": -1}
        except Exception as e:
            logger.error(f"Sandbox API error: {e}")
            return {"stdout": "", "stderr": str(e), "exit_code": -1}

    @staticmethod
    def write_file(path: str, content: str):
        try:
            resp = httpx.post(
                f"{SANDBOX_API_URL}/write",
                json={"path": path, "content": content},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Sandbox write error: {e}")

    @staticmethod
    def write_file_binary(path: str, content: bytes):
        try:
            resp = httpx.post(
                f"{SANDBOX_API_URL}/write-binary",
                json={"path": path, "content": base64.b64encode(content).decode()},
                timeout=30,
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
