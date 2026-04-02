import docker
import os
import threading
import time


CONTAINER_NAME = "quadrogent-sandbox"
IMAGE = "ubuntu:22.04"

# Packages installed on first launch
INIT_PACKAGES = "curl wget zip unzip git python3 python3-pip nano jq"

# Environment variables that make apt-get reliable and non-interactive
APT_ENV = {
    "DEBIAN_FRONTEND": "noninteractive",
    "APT_LISTCHANGES_FRONTEND": "none",
    "TZ": "UTC",
}


class DockerManager:
    """Manages a persistent Docker container for the agent's sandbox."""

    def __init__(self):
        self.client: docker.DockerClient | None = None
        self.container = None
        self._lock = threading.Lock()
        self._apt_lock = threading.Lock()   # serialise ALL apt calls
        self._initialized = False

    def connect(self) -> bool:
        try:
            self.client = docker.from_env()
            self.client.ping()
            return True
        except Exception:
            self.client = None
            return False

    def ensure_container(self) -> bool:
        if not self.client:
            if not self.connect():
                return False

        with self._lock:
            try:
                self.container = self.client.containers.get(CONTAINER_NAME)
                if self.container.status != "running":
                    self.container.start()
                    self._initialized = False
            except docker.errors.NotFound:
                uploads_abs = os.path.abspath("uploads")
                os.makedirs(uploads_abs, exist_ok=True)
                self.container = self.client.containers.run(
                    IMAGE,
                    name=CONTAINER_NAME,
                    command="sleep infinity",
                    detach=True,
                    network_mode="bridge",
                    volumes={
                        uploads_abs: {"bind": "/workspace/uploads", "mode": "rw"}
                    },
                    working_dir="/workspace",
                    environment=APT_ENV,
                    tty=True,
                    stdin_open=True,
                )
                self._initialized = False
            except Exception:
                return False

            if not self._initialized:
                self._bootstrap()

        return True

    def _wait_apt_free(self, timeout: int = 120) -> None:
        """Wait until dpkg/apt locks are released."""
        deadline = time.monotonic() + timeout
        check = (
            "while fuser /var/lib/dpkg/lock-frontend "
            "/var/lib/apt/lists/lock >/dev/null 2>&1; do sleep 2; done"
        )
        self._exec(check, timeout=timeout, extra_env=APT_ENV)

    def _apt(self, cmd: str, timeout: int = 300) -> tuple[int, str]:
        """Run an apt-get command with global lock + lock-file wait + retry."""
        with self._apt_lock:
            self._wait_apt_free(timeout=60)
            code, out = self._exec(cmd, timeout=timeout, extra_env=APT_ENV)
            if code != 0:
                time.sleep(5)
                self._wait_apt_free(timeout=30)
                code, out = self._exec(cmd, timeout=timeout, extra_env=APT_ENV)
        return code, out

    def _bootstrap(self):
        """Install essential tools. Called inside _lock."""
        self._apt("apt-get update -qq 2>&1", timeout=180)
        self._apt(
            f"apt-get install -y --no-install-recommends --fix-missing {INIT_PACKAGES} 2>&1",
            timeout=300,
        )
        self._exec("mkdir -p /workspace/uploads /workspace/tmp")
        self._initialized = True

    def execute(self, command: str, timeout: int = 120) -> tuple[int, str]:
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        return self._exec(command, timeout, extra_env=APT_ENV)

    def execute_apt(self, packages: str, timeout: int = 300) -> tuple[int, str]:
        """Install apt packages safely (serialised, waits for lock, retries)."""
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        _, upd = self._apt("apt-get update -qq 2>&1", timeout=120)
        code, out = self._apt(
            f"apt-get install -y --no-install-recommends --fix-missing {packages} 2>&1",
            timeout=timeout,
        )
        return code, (upd + "\n" + out).strip() if upd.strip() else out

    def _exec(
        self,
        command: str,
        timeout: int = 120,
        extra_env: dict | None = None,
    ) -> tuple[int, str]:
        try:
            env = dict(extra_env) if extra_env else {}
            result = self.container.exec_run(
                ["bash", "-c", command],
                workdir="/workspace",
                environment=env,
                demux=True,
            )
            stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
            stderr = (result.output[1] or b"").decode("utf-8", errors="replace")

            output = stdout
            if stderr.strip():
                output = (output + "\n[stderr]\n" + stderr).strip() if output.strip() else stderr

            if len(output) > 20_000:
                output = output[:10_000] + "\n...[truncated]...\n" + output[-5_000:]

            return result.exit_code, output
        except Exception as e:
            return -1, str(e)

    def stop(self):
        try:
            if self.container:
                self.container.stop(timeout=5)
        except Exception:
            pass

    def remove(self):
        try:
            if self.container:
                self.container.remove(force=True)
                self.container = None
                self._initialized = False
        except Exception:
            pass
