from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class FeishuStateStore:
    """Durable Feishu conversation bindings and inbound-message deduplication."""

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "feishu.sqlite3"
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_bindings (
                    conversation_key TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    sender_open_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS seen_messages (
                    message_id TEXT PRIMARY KEY,
                    received_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_seen_messages_received_at
                    ON seen_messages(received_at);
                """
            )

    def claim_message(self, message_id: str, *, retention_seconds: int = 604800) -> bool:
        mid = str(message_id or "").strip()
        if not mid:
            return False
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM seen_messages WHERE received_at < ?",
                (now - max(3600, int(retention_seconds)),),
            )
            inserted = conn.execute(
                "INSERT OR IGNORE INTO seen_messages(message_id, received_at) VALUES (?, ?)",
                (mid, now),
            ).rowcount
        return inserted == 1

    def release_message(self, message_id: str) -> bool:
        """Release a failed claim so an explicit redelivery can be processed."""
        with self._lock, self._connect() as conn:
            return conn.execute(
                "DELETE FROM seen_messages WHERE message_id=?",
                (str(message_id or "").strip(),),
            ).rowcount == 1

    def get_binding(self, conversation_key: str) -> str:
        key = str(conversation_key or "").strip()
        if not key:
            return ""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT session_id FROM conversation_bindings WHERE conversation_key=?",
                (key,),
            ).fetchone()
        return str(row["session_id"] if row else "")

    def bind(
        self,
        conversation_key: str,
        session_id: str,
        *,
        chat_id: str = "",
        sender_open_id: str = "",
    ) -> None:
        key = str(conversation_key or "").strip()
        sid = str(session_id or "").strip()
        if not key or not sid:
            raise ValueError("conversation_key and session_id are required")
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_bindings(
                    conversation_key, session_id, chat_id, sender_open_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(conversation_key) DO UPDATE SET
                    session_id=excluded.session_id,
                    chat_id=excluded.chat_id,
                    sender_open_id=excluded.sender_open_id,
                    updated_at=excluded.updated_at
                """,
                (key, sid, str(chat_id or ""), str(sender_open_id or ""), now, now),
            )

    def unbind(self, conversation_key: str) -> bool:
        with self._lock, self._connect() as conn:
            return conn.execute(
                "DELETE FROM conversation_bindings WHERE conversation_key=?",
                (str(conversation_key or "").strip(),),
            ).rowcount == 1
