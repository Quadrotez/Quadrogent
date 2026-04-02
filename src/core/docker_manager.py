import docker
import os
import threading


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
        self._initialized = False   # True once init packages are confirmed installed

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
                    self._initialized = False   # restarted — re-verify tools
            except docker.errors.NotFound:
                uploads_abs = os.path.abspath("uploads")
                os.makedirs(uploads_abs, exist_ok=True)
                self.container = self.client.containers.run(
                    IMAGE,
                    name=CONTAINER_NAME,
                    command="sleep infinity",
                    detach=True,
                    # "bridge" gives the container full internet access via
                    # the host's default NAT bridge (same as `docker run` default)
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
            except Exception as e:
                return False

            if not self._initialized:
                self._bootstrap()

        return True

    def _bootstrap(self):
        """Install essential tools. Blocks until done — called inside _lock."""
        # Step 1: update package lists (retry once on failure)
        code, out = self._exec(
            "apt-get update -qq 2>&1",
            timeout=180,
            extra_env=APT_ENV,
        )
        if code != 0:
            # Retry — sometimes mirrors are flaky
            code, out = self._exec(
                "apt-get update -qq 2>&1",
                timeout=180,
                extra_env=APT_ENV,
            )

        # Step 2: install packages
        install_cmd = (
            f"apt-get install -y --no-install-recommends {INIT_PACKAGES} 2>&1"
        )
        self._exec(install_cmd, timeout=300, extra_env=APT_ENV)

        # Step 3: create workspace dirs
        self._exec("mkdir -p /workspace/uploads /workspace/tmp")

        self._initialized = True

    def execute(self, command: str, timeout: int = 120) -> tuple[int, str]:
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        # Always pass APT env so agent's own apt calls are non-interactive too
        return self._exec(command, timeout, extra_env=APT_ENV)

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

            # Merge stdout + stderr so agent always sees the full output
            output = stdout
            if stderr.strip():
                output = (output + "\n[stderr]\n" + stderr).strip() if output.strip() else stderr

            # Trim very long output
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
