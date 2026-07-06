import subprocess
import logging
import os
import shutil

logger = logging.getLogger("quadrogent.sandbox")

IMAGE_NAME = "quadrogent-sandbox"
CONTAINER_NAME = "quadrogent-runtime"

class SandboxManager:
    @staticmethod
    def ensure_image():
        """Проверяет наличие образа, если нет - пытается собрать (хотя в этой среде мы предполагаем он есть или мы его создали)."""
        try:
            subprocess.run(["docker", "inspect", IMAGE_NAME], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.info(f"Образ {IMAGE_NAME} не найден. Сборка...")
            # В реальности тут должен быть путь к Dockerfile
            pass

    @staticmethod
    def run_command(command: str, timeout: int = 60):
        """Выполняет команду в контейнере."""
        # Убеждаемся, что контейнер запущен
        SandboxManager.ensure_container_running()
        
        full_cmd = ["docker", "exec", "-u", "quadrogent", CONTAINER_NAME, "bash", "-c", command]
        try:
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Timeout expired", "exit_code": -1}
        except Exception as e:
            return {"error": str(e), "exit_code": -1}

    @staticmethod
    def ensure_container_running():
        """Запускает контейнер, если он не запущен."""
        result = subprocess.run(["docker", "ps", "-a", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.State}}"], capture_output=True, text=True)
        state = result.stdout.strip()
        
        if state == "running":
            return
        
        if state:
            # Контейнер существует, но не запущен
            subprocess.run(["docker", "start", CONTAINER_NAME])
        else:
            # Создаем новый
            subprocess.run([
                "docker", "run", "-d",
                "--name", CONTAINER_NAME,
                "--network", "bridge",
                IMAGE_NAME,
                "tail", "-f", "/dev/null"
            ])

    @staticmethod
    def write_file(path: str, content: str):
        # Используем docker exec для записи файла (простой способ для небольших файлов)
        # Для надежности лучше использовать временный файл и docker cp
        temp_file = "/tmp/quadrogent_temp"
        with open(temp_file, "w") as f:
            f.write(content)
        
        subprocess.run(["docker", "cp", temp_file, f"{CONTAINER_NAME}:{path}"])
        subprocess.run(["docker", "exec", "-u", "root", CONTAINER_NAME, "chown", "quadrogent:quadrogent", path])
        os.remove(temp_file)

    @staticmethod
    def read_file(path: str):
        result = subprocess.run(["docker", "exec", CONTAINER_NAME, "cat", path], capture_output=True, text=True)
        return result.stdout

    @staticmethod
    def cleanup_output():
        subprocess.run(["docker", "exec", "-u", "quadrogent", CONTAINER_NAME, "rm", "-rf", "/home/quadrogent/output/*"])
