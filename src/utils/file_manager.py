import os
import shutil


UPLOADS_DIR = "uploads"


class FileManager:
    """Manage files in the uploads directory."""

    def __init__(self, base_dir: str = UPLOADS_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _safe_path(self, relative: str) -> str:
        """Resolve path safely, preventing traversal outside base_dir."""
        base_abs = os.path.abspath(self.base_dir)
        # If the caller already passes an absolute path, use it directly (still check)
        if os.path.isabs(relative):
            full = os.path.normpath(relative)
        else:
            full = os.path.abspath(os.path.join(self.base_dir, relative))
        if not (full == base_abs or full.startswith(base_abs + os.sep)):
            raise ValueError(f"Path traversal detected: {relative!r}")
        return full

    def read(self, path: str) -> str:
        full = self._safe_path(path)
        # Try text first; for binary files (PDF, etc.) return a notice
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except IsADirectoryError:
            raise ValueError(f"'{path}' is a directory, not a file")

    def write(self, path: str, content: str) -> str:
        """Write file and return its absolute path."""
        full = self._safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return full

    def delete(self, path: str):
        full = self._safe_path(path)
        if os.path.isdir(full):
            shutil.rmtree(full)
        elif os.path.exists(full):
            os.remove(full)

    def list_files(self, subdir: str = "") -> list[str]:
        target = self._safe_path(subdir) if subdir else os.path.abspath(self.base_dir)
        if not os.path.isdir(target):
            return []
        result = []
        for root, dirs, files in os.walk(target):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.base_dir)
                result.append(rel)
        return result

    def exists(self, path: str) -> bool:
        try:
            return os.path.exists(self._safe_path(path))
        except ValueError:
            return False

    def copy_to_uploads(self, src_path: str, dest_name: str | None = None) -> str:
        name = dest_name or os.path.basename(src_path)
        dest = self._safe_path(name)
        shutil.copy2(src_path, dest)
        return dest
