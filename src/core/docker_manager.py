import docker
import os
import threading
import time


CONTAINER_NAME = "quadrogent-sandbox"
IMAGE = "ubuntu:22.04"

INIT_PACKAGES = "curl wget zip unzip git python3 python3-pip nano jq psmisc"

APT_ENV = {
    "DEBIAN_FRONTEND": "noninteractive",
    "APT_LISTCHANGES_FRONTEND": "none",
    "TZ": "UTC",
}

# Packages we verify are present after bootstrap
REQUIRED_BINS = ["zip", "unzip", "python3", "pip3", "curl", "wget", "git"]


class DockerManager:
    """Manages a persistent Docker container for the agent's sandbox."""

    def __init__(self):
        self.client: docker.DockerClient | None = None
        self.container = None
        self._lock = threading.Lock()
        self._apt_lock = threading.Lock()

        # ── Bootstrap readiness ──────────────────────────
        # _ready_event is set ONLY when bootstrap has finished successfully.
        # execute() / execute_apt() wait on it so the agent can never run a
        # command before the sandbox is fully provisioned.
        self._ready_event = threading.Event()
        self._initialized = False

    # ── Connection ────────────────────────────────────────

    def connect(self) -> bool:
        try:
            self.client = docker.from_env()
            self.client.ping()
            return True
        except Exception:
            self.client = None
            return False

    # ── Container lifecycle ───────────────────────────────

    def ensure_container(self) -> bool:
        if not self.client:
            if not self.connect():
                return False

        with self._lock:
            try:
                self.container = self.client.containers.get(CONTAINER_NAME)
                if self.container.status != "running":
                    self.container.start()
                    # Wait until the container is actually running (up to 15s)
                    for _ in range(30):
                        time.sleep(0.5)
                        self.container.reload()
                        if self.container.status == "running":
                            break
                    if self.container.status != "running":
                        return False   # container refused to start
                    self._initialized = False
                    self._ready_event.clear()
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
                self._ready_event.clear()
            except Exception:
                return False

            if not self._initialized:
                self._bootstrap()

        return True

    # ── Bootstrap ─────────────────────────────────────────

    def _kill_stale_apt(self):
        """Kill any leftover apt/dpkg processes from a previous crashed run."""
        self._exec(
            "kill -9 $(lsof -t /var/lib/dpkg/lock-frontend 2>/dev/null) 2>/dev/null; "
            "kill -9 $(lsof -t /var/lib/apt/lists/lock 2>/dev/null) 2>/dev/null; "
            "rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock "
            "       /var/lib/apt/lists/lock /var/cache/apt/archives/lock; "
            "dpkg --configure -a 2>/dev/null; "
            "true",
            timeout=30,
            extra_env=APT_ENV,
        )

    def _apt(self, cmd: str, timeout: int = 300) -> tuple[int, str]:
        """Run apt-get with a global Python-side mutex so two threads can never
        call apt simultaneously, plus a lock-file cleanup before each attempt."""
        with self._apt_lock:
            self._kill_stale_apt()
            code, out = self._exec(cmd, timeout=timeout, extra_env=APT_ENV)
            if code != 0:
                time.sleep(3)
                self._kill_stale_apt()
                code, out = self._exec(cmd, timeout=timeout, extra_env=APT_ENV)
        return code, out

    def _missing_packages(self) -> list[str]:
        """Return a list of required binaries that are not on PATH."""
        missing = []
        for bin_name in REQUIRED_BINS:
            code, _ = self._exec(f"which {bin_name} 2>/dev/null", timeout=10)
            if code != 0:
                missing.append(bin_name)
        return missing

    def _bootstrap(self):
        """Install essential tools. Called inside _lock so only one thread runs it.
        Sets _ready_event when done so execute() can proceed."""
        self._ready_event.clear()

        # Check what's actually missing — skip full reinstall if everything's there
        missing = self._missing_packages()
        if missing:
            self._apt("apt-get update -qq 2>&1", timeout=180)
            self._apt(
                f"apt-get install -y --no-install-recommends --fix-missing "
                f"{INIT_PACKAGES} 2>&1",
                timeout=300,
            )
            # Second check — if still missing, try per-package
            still_missing = self._missing_packages()
            for pkg in still_missing:
                # pip3 is provided by python3-pip, zip by zip, etc. — map bin→pkg
                pkg_map = {"pip3": "python3-pip"}
                apt_pkg = pkg_map.get(pkg, pkg)
                self._apt(
                    f"apt-get install -y --no-install-recommends {apt_pkg} 2>&1",
                    timeout=120,
                )

        self._exec("mkdir -p /workspace/uploads /workspace/tmp")
        self._initialized = True
        self._ready_event.set()   # ← unblocks any waiting execute() calls

    # ── Public API ────────────────────────────────────────

    def _wait_ready(self, timeout: int = 120) -> bool:
        """Block until bootstrap is done. Returns False on timeout."""
        return self._ready_event.wait(timeout=timeout)

    def execute(self, command: str, timeout: int = 120) -> tuple[int, str]:
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        # Wait for bootstrap to finish — agent must never run before sandbox is ready
        if not self._wait_ready(timeout=120):
            return -1, "Sandbox bootstrap timed out — Docker may be unavailable"
        return self._exec(command, timeout, extra_env=APT_ENV)

    def execute_apt(self, packages: str, timeout: int = 300) -> tuple[int, str]:
        """Install apt packages safely (serialised, kills stale locks, retries)."""
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        if not self._wait_ready(timeout=120):
            return -1, "Sandbox bootstrap timed out"
        _, upd = self._apt("apt-get update -qq 2>&1", timeout=120)
        code, out = self._apt(
            f"apt-get install -y --no-install-recommends --fix-missing {packages} 2>&1",
            timeout=timeout,
        )
        return code, (upd + "\n" + out).strip() if upd.strip() else out

    # ── Low-level exec ────────────────────────────────────

    def _exec(
        self,
        command: str,
        timeout: int = 120,
        extra_env: dict | None = None,
    ) -> tuple[int, str]:
        try:
            env = dict(extra_env) if extra_env else {}
            # If container stopped unexpectedly, try to restart it once
            try:
                self.container.reload()
            except Exception:
                pass
            if self.container.status != "running":
                try:
                    self.container.start()
                    for _ in range(20):
                        time.sleep(0.5)
                        self.container.reload()
                        if self.container.status == "running":
                            break
                except Exception:
                    pass
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

    # ── Cleanup ───────────────────────────────────────────

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
                self._ready_event.clear()
        except Exception:
            pass
