import docker
import os
import threading
import time
from typing import Callable


CONTAINER_NAME = "quadrogent-sandbox"
IMAGE = "ubuntu:22.04"

INIT_PACKAGES = "curl wget zip unzip git python3 python3-pip python3-venv nano jq psmisc lsof"

APT_ENV = {
    "DEBIAN_FRONTEND": "noninteractive",
    "APT_LISTCHANGES_FRONTEND": "none",
    "NEEDRESTART_MODE": "a",
    "TZ": "UTC",
}

# Apt options that make it stable in resource-constrained containers
APT_OPTS = (
    '-o Acquire::http::Timeout=60 '
    '-o Acquire::Retries=3 '
    '-o Dpkg::Options::="--force-confdef" '
    '-o Dpkg::Options::="--force-confold" '
)

REQUIRED_BINS = ["zip", "unzip", "python3", "pip3", "curl", "wget", "git"]


class DockerManager:
    def __init__(self):
        self.client: docker.DockerClient | None = None
        self.container = None
        self._lock     = threading.Lock()
        self._apt_lock = threading.Lock()
        self._ready_event = threading.Event()
        self._initialized = False
        self.on_log: Callable[[str, str], None] | None = None

    def _log(self, level: str, msg: str):
        if self.on_log:
            try:
                self.on_log(level, msg)
            except Exception:
                pass

    # ── Connection ─────────────────────────────────────────

    def connect(self) -> bool:
        try:
            self.client = docker.from_env()
            self.client.ping()
            return True
        except Exception:
            self.client = None
            return False

    # ── Container lifecycle ────────────────────────────────

    def _wait_running(self, timeout_s: float = 15.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                self.container.reload()
            except Exception:
                pass
            if self.container.status == "running":
                return True
            time.sleep(0.4)
        return False

    def ensure_container(self) -> bool:
        if not self.client:
            self._log("info", "Подключение к Docker…")
            if not self.connect():
                self._log("error", "Docker недоступен. Убедитесь что Docker запущен.")
                return False
            self._log("ok", "Docker подключён.")

        with self._lock:
            try:
                self.container = self.client.containers.get(CONTAINER_NAME)

                # ── Verify volume mount is correct ──────────────────────────
                workspace_abs = os.path.abspath("workspace")
                mounts = self.container.attrs.get("Mounts", [])
                mount_ok = any(
                    os.path.normpath(m.get("Source", "")) == os.path.normpath(workspace_abs)
                    and m.get("Destination") == "/workspace"
                    for m in mounts
                )
                if not mount_ok:
                    self._log("warn",
                        f"Volume mount устарел (контейнер создан с другим путём). "
                        f"Пересоздаю контейнер…"
                    )
                    try:
                        self.container.stop(timeout=5)
                    except Exception:
                        pass
                    self.container.remove(force=True)
                    raise docker.errors.NotFound("stale mount — recreate")
                # ────────────────────────────────────────────────────────────

                if self.container.status != "running":
                    self._log("info", f"Контейнер найден (статус: {self.container.status}). Запускаю…")
                    self.container.start()
                    if not self._wait_running(15):
                        self._log("error", "Контейнер не запустился за 15 секунд.")
                        return False
                    self._log("ok", "Контейнер запущен.")
                    self._initialized = False
                    self._ready_event.clear()
                else:
                    self._log("info", "Контейнер уже запущен.")
            except docker.errors.NotFound:
                self._log("info", f"Создаю новый контейнер ({IMAGE})…")
                workspace_abs = os.path.abspath("workspace")
                os.makedirs(workspace_abs, exist_ok=True)
                self.container = self.client.containers.run(
                    IMAGE,
                    name=CONTAINER_NAME,
                    command="sleep infinity",
                    detach=True,
                    network_mode="bridge",
                    dns=["8.8.8.8", "1.1.1.1"],   # explicit DNS — avoids host DNS misconfiguration
                    volumes={workspace_abs: {"bind": "/workspace", "mode": "rw"}},
                    working_dir="/workspace",
                    environment=APT_ENV,
                    tty=True,
                    stdin_open=True,
                )
                if not self._wait_running(10):
                    self._log("error", "Новый контейнер не стартовал.")
                    return False
                self._log("ok", "Контейнер создан.")
                self._initialized = False
                self._ready_event.clear()
            except Exception as e:
                self._log("error", f"Ошибка Docker: {e}")
                return False

            if not self._initialized:
                self._bootstrap()

        return True

    # ── Bootstrap ──────────────────────────────────────────

    def _ensure_running(self) -> bool:
        """Restart container if it stopped; return True if running."""
        try:
            self.container.reload()
        except Exception:
            pass
        if self.container.status == "running":
            return True
        self._log("warn", "Контейнер остановился — перезапускаю…")
        try:
            self.container.start()
            return self._wait_running(15)
        except Exception as e:
            self._log("error", f"Не удалось перезапустить: {e}")
            return False

    def _kill_stale_apt(self):
        """Kill leftover apt/dpkg processes and remove stale lock files."""
        self._exec(
            # lsof might not be installed yet — fall back to fuser, then brute-force
            "{ lsof -t /var/lib/dpkg/lock-frontend 2>/dev/null | xargs -r kill -9; } 2>/dev/null; "
            "{ lsof -t /var/lib/apt/lists/lock      2>/dev/null | xargs -r kill -9; } 2>/dev/null; "
            "{ fuser -k /var/lib/dpkg/lock-frontend 2>/dev/null; } 2>/dev/null; "
            "rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock "
            "      /var/lib/apt/lists/lock /var/cache/apt/archives/lock; "
            "dpkg --configure -a --force-confdef 2>/dev/null; true",
            timeout=30, extra_env=APT_ENV,
        )

    def _apt(self, cmd: str, timeout_s: int = 300) -> tuple[int, str]:
        """Serialised apt call with lock cleanup, timeout wrapper, and 137-recovery."""
        with self._apt_lock:
            for attempt in range(3):
                if not self._ensure_running():
                    return -1, "Контейнер не запущен"

                self._kill_stale_apt()

                # Wrap with shell timeout so a hung apt doesn't block forever
                wrapped = f"timeout {timeout_s} bash -c {repr(cmd)}"
                code, out = self._exec(wrapped, timeout=timeout_s + 30, extra_env=APT_ENV)

                if code == 124:
                    self._log("warn", f"apt превысил лимит {timeout_s}с (попытка {attempt+1}/3)")
                    time.sleep(5)
                    continue

                if code == 137:
                    # SIGKILL — container OOM'd or was stopped; restart and retry
                    self._log("warn", f"apt убит сигналом KILL (OOM?) — перезапускаю контейнер (попытка {attempt+1}/3)…")
                    try:
                        self.container.restart(timeout=10)
                        self._wait_running(15)
                    except Exception:
                        pass
                    time.sleep(5)
                    continue

                if code != 0 and attempt < 2:
                    self._log("warn", f"apt завершился с кодом {code}, повтор через 3 сек…")
                    time.sleep(3)
                    continue

                return code, out

        return code, out

    def _missing_packages(self) -> list[str]:
        missing = []
        for b in REQUIRED_BINS:
            code, _ = self._exec(f"which {b} 2>/dev/null", timeout=10)
            if code != 0:
                missing.append(b)
        return missing

    def _bootstrap(self):
        self._ready_event.clear()
        self._log("info", "─── Проверка окружения ───────────────────────")

        # ── Network diagnostics (bash built-ins only — no tools required) ──
        self._log("info", "─── Проверка сети ────────────────────────────")

        # DNS config
        code, out = self._exec("cat /etc/resolv.conf 2>/dev/null | grep nameserver | head -2", timeout=5)
        dns_info = out.strip() or "(DNS не настроен)"
        self._log("info", f"DNS: {dns_info}")

        # TCP reachability via bash /dev/tcp — works on bare ubuntu with zero tools
        code, _ = self._exec(
            "timeout 4 bash -c 'echo >/dev/tcp/8.8.8.8/53' 2>/dev/null", timeout=8)
        net_ok = (code == 0)
        self._log("ok" if net_ok else "error",
                  f"TCP 8.8.8.8:53: {'доступен' if net_ok else 'НЕДОСТУПЕН — нет интернета!'}")

        code, _ = self._exec(
            "timeout 5 bash -c 'echo >/dev/tcp/archive.ubuntu.com/80' 2>/dev/null", timeout=9)
        apt_ok = (code == 0)
        self._log("ok" if apt_ok else "error",
                  f"TCP archive.ubuntu.com:80: {'доступен' if apt_ok else 'НЕДОСТУПЕН!'}")

        if not net_ok:
            self._log("error", "Нет доступа к сети. Проверь настройки Docker:")
            self._log("out", "  sudo iptables -L DOCKER-USER -n   (не должно быть DROP)")
            self._log("out", "  sudo sysctl net.ipv4.ip_forward   (должно быть = 1)")
            self._log("out", "  sudo systemctl restart docker")

        self._log("info", "─── Проверка пакетов ─────────────────────────")

        missing = self._missing_packages()
        if not missing:
            self._log("ok", "Все необходимые пакеты уже установлены.")
        else:
            self._log("warn", f"Не найдены: {', '.join(missing)}")

            pkg_str = INIT_PACKAGES
            self._log("cmd", "apt-get update")
            code, out = self._apt("apt-get update -qq 2>&1", timeout_s=120)
            if out.strip():
                self._log("out", out.strip())
            if code == 0:
                self._log("ok", "Индексы пакетов обновлены.")
            else:
                self._log("warn", f"apt update завершился с кодом {code}. Пробую установить напрямую…")

            self._log("cmd", f"apt-get install {pkg_str}")
            code, out = self._apt(
                f"apt-get install -y --no-install-recommends --fix-missing "
                f"{APT_OPTS} {pkg_str} 2>&1",
                timeout_s=300,
            )
            if out.strip():
                self._log("out", out.strip())
            if code == 0:
                self._log("ok", "Пакеты установлены.")
            else:
                self._log("warn", f"Установка завершилась с кодом {code}. Пробую поштучно…")
                for pkg in self._missing_packages():
                    apt_pkg = {"pip3": "python3-pip"}.get(pkg, pkg)
                    self._log("cmd", f"apt-get install {apt_pkg}")
                    c, o = self._apt(
                        f"apt-get install -y --no-install-recommends {APT_OPTS} {apt_pkg} 2>&1",
                        timeout_s=120,
                    )
                    if o.strip():
                        self._log("out", o.strip())
                    self._log("ok" if c == 0 else "error",
                               f"{apt_pkg}: {'установлен' if c == 0 else f'ОШИБКА (код {c})'}")

        # Ensure workspace dirs exist, clean up stale uploads/ from old versions
        self._exec("mkdir -p /workspace/tmp && rm -rf /workspace/uploads")

        self._log("info", "─── Проверка установленных инструментов ──────")
        all_ok = True
        for b in REQUIRED_BINS:
            code, path = self._exec(f"which {b} 2>/dev/null", timeout=10)
            if code == 0:
                self._log("ok", f"  ✓ {b:<10} {path.strip()}")
            else:
                self._log("error", f"  ✗ {b:<10} не найден!")
                all_ok = False

        if all_ok:
            self._log("ok", "─── Контейнер готов к работе ─────────────────")
        else:
            self._log("warn", "─── Контейнер готов (с предупреждениями) ─────")

        self._initialized = True
        self._ready_event.set()

    # ── Public API ─────────────────────────────────────────

    def _wait_ready(self, timeout: int = 180) -> bool:
        return self._ready_event.wait(timeout=timeout)

    def execute(self, command: str, timeout: int = 120) -> tuple[int, str]:
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        if not self._wait_ready(timeout=180):
            return -1, "Sandbox bootstrap timed out"
        return self._exec(command, timeout, extra_env=APT_ENV)

    def execute_apt(self, packages: str, timeout: int = 300) -> tuple[int, str]:
        if not self.container:
            if not self.ensure_container():
                return -1, "Docker container is not available"
        if not self._wait_ready(timeout=180):
            return -1, "Sandbox bootstrap timed out"
        _, upd = self._apt("apt-get update -qq 2>&1", timeout_s=120)
        code, out = self._apt(
            f"apt-get install -y --no-install-recommends --fix-missing {APT_OPTS} {packages} 2>&1",
            timeout_s=timeout,
        )
        return code, (upd + "\n" + out).strip() if upd.strip() else out

    # ── Low-level exec ─────────────────────────────────────

    def _exec(
        self,
        command: str,
        timeout: int = 120,
        extra_env: dict | None = None,
    ) -> tuple[int, str]:
        try:
            env = dict(extra_env) if extra_env else {}
            try:
                self.container.reload()
            except Exception:
                pass
            if self.container.status != "running":
                try:
                    self.container.start()
                    self._wait_running(15)
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

    # ── Cleanup ────────────────────────────────────────────

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

    def copy_from_container(self, container_path: str, host_dest: str) -> bool:
        """Copy a single file from Docker to the host filesystem.

        Uses the Docker SDK get_archive (tar stream) — works even when
        the bind mount is missing or was created against a stale path.
        Returns True on success, False on any failure.
        """
        import io
        import tarfile
        try:
            bits, _ = self.container.get_archive(container_path)
            buf = io.BytesIO()
            for chunk in bits:
                buf.write(chunk)
            buf.seek(0)
            with tarfile.open(fileobj=buf) as tf:
                members = tf.getmembers()
                if not members:
                    return False
                member = members[0]
                member.name = os.path.basename(host_dest)
                tf.extract(member, path=os.path.dirname(os.path.abspath(host_dest)))
            return os.path.exists(host_dest)
        except Exception:
            return False
