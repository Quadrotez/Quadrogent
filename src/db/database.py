import sqlite3
import json
import os
import shutil
import time
from datetime import datetime


DB_PATH = "quadrogent.db"


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
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
        self.conn.commit()

    # ── Settings ──────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    # ── Chats ─────────────────────────────────────────────

    def create_chat(self, title: str = "Новый чат", mode: str = "auto") -> int:
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO chats (title, mode, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, mode, now, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_chats(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM chats ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_chat(self, chat_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_chat(self, chat_id: int, **kwargs):
        allowed = {"title", "mode", "persistent"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [chat_id]
        self.conn.execute(f"UPDATE chats SET {sets} WHERE id = ?", vals)
        self.conn.commit()

    def delete_chat(self, chat_id: int):
        self.conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        self.conn.commit()

    def touch_chat(self, chat_id: int):
        self.conn.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), chat_id),
        )
        self.conn.commit()

    # ── Messages ──────────────────────────────────────────

    def add_message(self, chat_id: int, role: str, content: str, tool: str | None = None) -> int:
        now = datetime.now().isoformat()
        cur = self.conn.execute(
            "INSERT INTO messages (chat_id, role, content, tool, ts) VALUES (?, ?, ?, ?, ?)",
            (chat_id, role, content, tool, now),
        )
        self.touch_chat(chat_id)
        self.conn.commit()
        return cur.lastrowid

    def get_messages(self, chat_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Attachments ───────────────────────────────────────

    def add_attachment(self, msg_id: int, filepath: str) -> str:
        filename = os.path.basename(filepath)
        cache_name = f"{int(time.time())}_{filename}"
        cache_path = os.path.join(".cache", cache_name)
        shutil.copy2(filepath, cache_path)
        self.conn.execute(
            "INSERT INTO attachments (msg_id, filename, cache_path) VALUES (?, ?, ?)",
            (msg_id, filename, cache_path),
        )
        self.conn.commit()
        return cache_path

    def get_attachments(self, msg_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM attachments WHERE msg_id = ?", (msg_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Memory ────────────────────────────────────────────

    def save_memory(self, chat_id: int, summary: str):
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO memories (chat_id, summary, created_at) VALUES (?, ?, ?)",
            (chat_id, summary, now),
        )
        self.conn.commit()

    def get_all_memories(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM memories ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_memories_text(self) -> str:
        memories = self.get_all_memories()
        if not memories:
            return ""
        parts = [f"- {m['summary']}" for m in memories]
        return "Воспоминания из прошлых диалогов:\n" + "\n".join(parts)

    def close(self):
        self.conn.close()
