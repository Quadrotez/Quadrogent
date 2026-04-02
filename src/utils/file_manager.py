import os
import shutil


UPLOADS_DIR = "uploads"


class FileManager:
    """Manage files in the uploads directory."""

    def __init__(self, base_dir: str = UPLOADS_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _safe_path(self, relative: str) -> str:
        full = os.path.normpath(os.path.join(self.base_dir, relative))
        if not full.startswith(os.path.abspath(self.base_dir)):
            raise ValueError("Path traversal detected")
        return full

    def read(self, path: str) -> str:
        full = self._safe_path(path)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write(self, path: str, content: str):
        full = self._safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    def delete(self, path: str):
        full = self._safe_path(path)
        if os.path.isdir(full):
            shutil.rmtree(full)
        elif os.path.exists(full):
            os.remove(full)

    def list_files(self, subdir: str = "") -> list[str]:
        target = self._safe_path(subdir) if subdir else self.base_dir
        if not os.path.isdir(target):
            return []
        result = []
        for root, dirs, files in os.walk(target):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.base_dir)
                result.append(rel)
        return result

    def exists(self, path: str) -> bool:
        return os.path.exists(self._safe_path(path))

    def copy_to_uploads(self, src_path: str, dest_name: str | None = None) -> str:
        name = dest_name or os.path.basename(src_path)
        dest = self._safe_path(name)
        shutil.copy2(src_path, dest)
        return dest
