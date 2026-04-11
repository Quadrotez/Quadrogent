import sqlite3
import json
import os
import shutil
import threading
import time
from datetime import datetime


DB_PATH = "quadrogent.db"


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Serialise writes at the DB level — SQLite WAL still needs a mutex
        # when multiple Python threads share the same connection object
        self._create_tables()

    # ── Internal helpers ──────────────────────────────────

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.conn.execute(sql, params)

    def _executescript(self, script: str):
        with self._lock:
            cur = self.conn.cursor()
            cur.executescript(script)
            return cur

    def _commit(self):
        with self._lock:
            self.conn.commit()

    def _execute_commit(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _create_tables(self):
        self._executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chats (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL DEFAULT 'Новый чат',
                mode       TEXT NOT NULL DEFAULT 'auto',
                persistent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id  INTEGER NOT NULL,
                role     TEXT NOT NULL,
                content  TEXT NOT NULL,
                tool     TEXT,
                ts       TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id   INTEGER NOT NULL,
                filename TEXT NOT NULL,
                cache_path TEXT NOT NULL,
                FOREIGN KEY (msg_id) REFERENCES messages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS memories (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );
        """)
        # Migrations for new columns (idempotent)
        for migration in [
            "ALTER TABLE chats ADD COLUMN web_search INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE chats ADD COLUMN think_mode INTEGER NOT NULL DEFAULT 1",
        ]:
            try:
                self.conn.execute(migration)
                self.conn.commit()
            except Exception:
                pass  # Column already exists

    # ── Settings ──────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        row = self._execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self._execute_commit(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    # ── Chats ─────────────────────────────────────────────

    def create_chat(self, title: str = "Новый чат", mode: str = "auto", persistent: int = 0, web_search: int = 1, think_mode: int = 1) -> int:
        now = datetime.now().isoformat()
        cur = self._execute_commit(
            "INSERT INTO chats (title, mode, persistent, web_search, think_mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, mode, persistent, web_search, think_mode, now, now),
        )
        return cur.lastrowid

    def get_chats(self) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM chats ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_chat(self, chat_id: int) -> dict | None:
        row = self._execute(
            "SELECT * FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_chat(self, chat_id: int, **kwargs):
        allowed = {"title", "mode", "persistent", "web_search", "think_mode"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [chat_id]
        self._execute_commit(f"UPDATE chats SET {sets} WHERE id = ?", vals)

    def delete_chat(self, chat_id: int):
        self._execute_commit("DELETE FROM chats WHERE id = ?", (chat_id,))

    def touch_chat(self, chat_id: int):
        # Called inside add_message which already holds the lock via _execute_commit,
        # so we use the raw connection here — protected by _lock in add_message.
        self.conn.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), chat_id),
        )

    # ── Messages ──────────────────────────────────────────

    def add_message(
        self, chat_id: int, role: str, content: str, tool: str | None = None
    ) -> int:
        now = datetime.now().isoformat()
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO messages (chat_id, role, content, tool, ts) VALUES (?, ?, ?, ?, ?)",
                (chat_id, role, content, tool, now),
            )
            self.touch_chat(chat_id)
            self.conn.commit()
            return cur.lastrowid

    def get_messages(self, chat_id: int) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Attachments ───────────────────────────────────────

    def add_attachment(self, msg_id: int, filepath: str) -> str:
        filename = os.path.basename(filepath)
        cache_name = f"{int(time.time())}_{filename}"
        cache_path = os.path.join(".cache", cache_name)
        shutil.copy2(filepath, cache_path)
        self._execute_commit(
            "INSERT INTO attachments (msg_id, filename, cache_path) VALUES (?, ?, ?)",
            (msg_id, filename, cache_path),
        )
        return cache_path

    def get_attachments(self, msg_id: int) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM attachments WHERE msg_id = ?", (msg_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Memory ────────────────────────────────────────────

    def save_memory(self, chat_id: int, summary: str):
        now = datetime.now().isoformat()
        self._execute_commit(
            "INSERT INTO memories (chat_id, summary, created_at) VALUES (?, ?, ?)",
            (chat_id, summary, now),
        )

    def get_all_memories(self) -> list[dict]:
        rows = self._execute(
            "SELECT * FROM memories ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_memory(self, memory_id: int):
        self._execute_commit("DELETE FROM memories WHERE id = ?", (memory_id,))

    def update_memory(self, memory_id: int, summary: str):
        self._execute_commit(
            "UPDATE memories SET summary = ? WHERE id = ?", (summary, memory_id)
        )

    def get_memories_text(self) -> str:
        memories = self.get_all_memories()
        if not memories:
            return ""
        parts = []
        for m in memories:
            date = m.get("created_at", "")[:10]
            parts.append(f"- [{date}] {m['summary']}")
        return "\n".join(parts)

    def close(self):
        with self._lock:
            self.conn.close()
