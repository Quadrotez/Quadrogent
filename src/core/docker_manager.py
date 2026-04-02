import docker
import os
import threading


CONTAINER_NAME = "quadrogent-sandbox"
IMAGE = "ubuntu:22.04"


class DockerManager:
    """Manages a persistent Docker container for the agent's sandbox."""

    def __init__(self):
        self.client: docker.DockerClient | None = None
        self.container = None
        self._lock = threading.Lock()

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
            except docker.errors.NotFound:
                uploads_abs = os.path.abspath("uploads")
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
                    tty=True,
                    stdin_open=True,
                )
                # Install basic tools
                self._exec("apt-get update && apt-get install -y curl wget zip unzip git python3 python3-pip nano")
            except Exception:
                return False
        return True

    def execute(self, command: str, timeout: int = 120) -> tuple[int, str]:
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        return self._exec(command, timeout)

    def _exec(self, command: str, timeout: int = 120) -> tuple[int, str]:
        try:
            result = self.container.exec_run(
                ["bash", "-c", command],
                workdir="/workspace",
                demux=True,
            )
            stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
            stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
            output = stdout
            if stderr:
                output += f"\n[stderr]\n{stderr}" if output else stderr
            # Trim very long output
            if len(output) > 20000:
                output = output[:10000] + "\n...[truncated]...\n" + output[-5000:]
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
        except Exception:
            pass
