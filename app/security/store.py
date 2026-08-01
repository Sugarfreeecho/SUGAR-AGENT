from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable


CURRENT_POLICY_VERSION = 2


def security_state_dir() -> Path:
    override = str(os.getenv("MYAGENT_SECURITY_HOME") or "").strip()
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "MyAgent" / "security"
    else:
        root = Path(os.getenv("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "myagent" / "security"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


class SecurityStore:
    """SQLite state outside the model-writable workspace."""

    def __init__(self, path: Path | None = None):
        self.path = (path or security_state_dir() / "security.sqlite3").resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS security_meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO security_meta(key, value) VALUES('policy_version', '2');
                CREATE TABLE IF NOT EXISTS grants(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    consumed_at REAL,
                    UNIQUE(session_id, request_digest, scope)
                );
                CREATE TABLE IF NOT EXISTS permission_rules(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL DEFAULT '',
                    workspace TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    behavior TEXT NOT NULL,
                    action TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    UNIQUE(session_id, workspace, source, behavior, action, pattern)
                );
                CREATE TABLE IF NOT EXISTS audit_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    session_id TEXT,
                    event_type TEXT NOT NULL,
                    request_digest TEXT,
                    outcome TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS security_settings(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS session_modes(
                    session_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                INSERT OR IGNORE INTO security_settings(key, value)
                    VALUES('auto_review_enabled', 'false');
                INSERT OR IGNORE INTO security_settings(key, value)
                    VALUES('permission_mode', 'ask_for_approval');
                """
            )
            row = db.execute(
                "SELECT value FROM security_meta WHERE key='policy_version'"
            ).fetchone()
            try:
                stored_version = int(row["value"] if row else 0)
            except (TypeError, ValueError):
                stored_version = 0
            if stored_version < CURRENT_POLICY_VERSION:
                db.execute(
                    "UPDATE security_meta SET value=? WHERE key='policy_version'",
                    (str(CURRENT_POLICY_VERSION),),
                )

    def policy_version(self) -> int:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM security_meta WHERE key='policy_version'"
            ).fetchone()
        return max(1, int(row["value"] if row else 1))

    def add_grant(
        self,
        session_id: str,
        request_digest: str,
        scope: str,
        *,
        ttl_seconds: float | None,
    ) -> None:
        now = time.time()
        expires = None if ttl_seconds is None else now + max(1.0, float(ttl_seconds))
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO grants(session_id, request_digest, scope, decision, created_at, expires_at, consumed_at)
                VALUES(?, ?, ?, 'allow', ?, ?, NULL)
                ON CONFLICT(session_id, request_digest, scope) DO UPDATE SET
                    decision='allow', created_at=excluded.created_at,
                    expires_at=excluded.expires_at, consumed_at=NULL
                """,
                (session_id, request_digest, scope, now, expires),
            )

    def consume_matching_grant(self, session_id: str, request_digest: str) -> str | None:
        now = time.time()
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                """
                SELECT * FROM grants
                WHERE request_digest=? AND decision='allow'
                  AND (session_id=? OR scope='always')
                  AND (expires_at IS NULL OR expires_at>?)
                  AND (scope!='once' OR consumed_at IS NULL)
                ORDER BY CASE scope WHEN 'once' THEN 0 WHEN 'session' THEN 1 ELSE 2 END
                """,
                (request_digest, session_id, now),
            ).fetchall()
            if not rows:
                db.execute("COMMIT")
                return None
            row = rows[0]
            if row["scope"] == "once":
                updated = db.execute(
                    "UPDATE grants SET consumed_at=? WHERE id=? AND consumed_at IS NULL",
                    (now, row["id"]),
                ).rowcount
                if updated != 1:
                    db.execute("ROLLBACK")
                    return None
            db.execute("COMMIT")
            return str(row["scope"])

    def add_permission_rule(
        self,
        *,
        source: str,
        behavior: str,
        action: str,
        pattern: str,
        session_id: str = "",
        workspace: str = "",
        ttl_seconds: float | None = None,
    ) -> int:
        """Insert (or refresh) a durable pattern rule and return its id."""
        source = str(source or "user").strip().lower()
        if source not in {"user", "project", "session"}:
            raise ValueError(f"invalid rule source: {source!r}")
        behavior = str(behavior or "").strip().lower()
        if behavior not in {"allow", "deny", "ask"}:
            raise ValueError(f"invalid rule behavior: {behavior!r}")
        action = str(action or "").strip().lower()
        pattern = str(pattern or "").strip()
        if not action or not pattern:
            raise ValueError("action and pattern are required")
        now = time.time()
        expires = None if ttl_seconds is None else now + max(1.0, float(ttl_seconds))
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO permission_rules(
                    session_id, workspace, source, behavior, action, pattern,
                    created_at, expires_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, workspace, source, behavior, action, pattern)
                DO UPDATE SET created_at=excluded.created_at, expires_at=excluded.expires_at
                """,
                (session_id, workspace, source, behavior, action, pattern, now, expires),
            )
            row = db.execute(
                """
                SELECT id FROM permission_rules
                WHERE session_id=? AND workspace=? AND source=? AND behavior=?
                  AND action=? AND pattern=?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, workspace, source, behavior, action, pattern),
            ).fetchone()
            return int(row["id"] if row else 0)

    def active_permission_rules(
        self,
        *,
        session_id: str = "",
        workspace: str = "",
    ) -> list[dict[str, Any]]:
        """Rules that apply to the given session/workspace right now."""
        now = time.time()
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM permission_rules
                WHERE (expires_at IS NULL OR expires_at > ?)
                  AND (
                        source='user'
                     OR (source='session' AND session_id=?)
                     OR (source='project' AND workspace=?)
                  )
                ORDER BY id
                """,
                (now, str(session_id or "").strip(), str(workspace or "").strip()),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_permission_rules(
        self,
        *,
        session_id: str = "",
        workspace: str = "",
    ) -> list[dict[str, Any]]:
        """All relevant rules (including expired) for the settings page."""
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM permission_rules
                WHERE source='user'
                   OR (source='session' AND session_id=?)
                   OR (source='project' AND workspace=?)
                ORDER BY created_at DESC, id DESC
                """,
                (str(session_id or "").strip(), str(workspace or "").strip()),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_permission_rule(self, rule_id: object) -> bool:
        try:
            rid = int(rule_id)
        except (TypeError, ValueError):
            return False
        with self._lock, self._connect() as db:
            cur = db.execute("DELETE FROM permission_rules WHERE id=?", (rid,))
            return cur.rowcount > 0

    def clear_session_permission_rules(self, session_id: str) -> int:
        with self._lock, self._connect() as db:
            cur = db.execute(
                "DELETE FROM permission_rules WHERE source='session' AND session_id=?",
                (str(session_id or "").strip(),),
            )
            return cur.rowcount

    def audit(
        self,
        *,
        session_id: str,
        event_type: str,
        request_digest: str = "",
        outcome: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        safe_payload = _redact(payload or {})
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO audit_events(created_at, session_id, event_type, request_digest, outcome, payload_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    session_id,
                    event_type,
                    request_digest,
                    outcome,
                    json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"), default=str),
                ),
            )

    def expire_stale(self) -> int:
        now = time.time()
        with self._lock, self._connect() as db:
            return int(
                db.execute(
                    "DELETE FROM grants WHERE expires_at IS NOT NULL AND expires_at<=?",
                    (now,),
                ).rowcount
            )

    def get_setting(self, key: str, default: bool = False) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM security_settings WHERE key=?", (str(key),)
            ).fetchone()
        if not row:
            return bool(default)
        return str(row["value"]).strip().lower() in {"1", "true", "yes", "on"}

    def set_setting(self, key: str, value: bool) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO security_settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(key), "true" if value else "false"),
            )

    def get_text_setting(self, key: str, default: str = "") -> str:
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM security_settings WHERE key=?", (str(key),)
            ).fetchone()
        return str(row["value"]) if row else str(default)

    def set_text_setting(self, key: str, value: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO security_settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(key), str(value)),
            )

    def get_global_permission_mode(self) -> str:
        """The single permission mode shared by every session."""
        with self._connect() as db:
            row = db.execute(
                "SELECT value FROM security_settings WHERE key='permission_mode'"
            ).fetchone()
        value = str(row["value"]) if row else ""
        if value not in {"ask_for_approval", "approve_for_me", "full_access"}:
            return "ask_for_approval"
        return value

    def set_global_permission_mode(self, mode: str) -> None:
        normalized = str(mode or "").strip().lower().replace("-", "_")
        if normalized not in {"ask_for_approval", "approve_for_me", "full_access"}:
            raise ValueError(f"invalid permission mode: {mode!r}")
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO security_settings(key, value) VALUES('permission_mode', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (normalized,),
            )

    def get_session_mode(self, session_id: str) -> str:
        # Permission modes are global: every session shares one security
        # standard. Kept as a session-shaped API for callers that pass a
        # session id (subagent inheritance, webui endpoints).
        return self.get_global_permission_mode()

    def set_session_mode(self, session_id: str, mode: str) -> None:
        self.set_global_permission_mode(mode)


def _redact(value: Any) -> Any:
    markers: Iterable[str] = ("token", "secret", "password", "cookie", "api_key", "authorization")
    if isinstance(value, dict):
        return {
            str(k): ("[REDACTED]" if any(m in str(k).lower() for m in markers) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value
