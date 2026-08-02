from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable


CURRENT_POLICY_VERSION = 3


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
                    enabled INTEGER NOT NULL DEFAULT 1,
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
                CREATE TABLE IF NOT EXISTS extension_trust(
                    kind TEXT NOT NULL,
                    extension_id TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    content_digest TEXT NOT NULL,
                    config_digest TEXT NOT NULL DEFAULT '',
                    capabilities_json TEXT NOT NULL DEFAULT '{}',
                    decision TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(kind, extension_id)
                );
                INSERT OR IGNORE INTO security_settings(key, value)
                    VALUES('auto_review_enabled', 'false');
                INSERT OR IGNORE INTO security_settings(key, value)
                    VALUES('permission_mode', 'ask_for_approval');
                INSERT OR IGNORE INTO security_settings(key, value)
                    VALUES('permission_mode_updated_at', '0');
                """
            )
            columns = {
                str(item["name"])
                for item in db.execute("PRAGMA table_info(permission_rules)").fetchall()
            }
            if "enabled" not in columns:
                db.execute(
                    "ALTER TABLE permission_rules ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
                )
            row = db.execute(
                "SELECT value FROM security_meta WHERE key='policy_version'"
            ).fetchone()
            try:
                stored_version = int(row["value"] if row else 0)
            except (TypeError, ValueError):
                stored_version = 0
            if stored_version < CURRENT_POLICY_VERSION:
                disabled = db.execute(
                    """
                    UPDATE permission_rules SET enabled=0
                    WHERE source='project' AND behavior='allow' AND enabled=1
                    """
                ).rowcount
                db.execute("DELETE FROM grants")
                db.execute("DROP TABLE IF EXISTS session_modes")
                db.execute(
                    "UPDATE security_meta SET value=? WHERE key='policy_version'",
                    (str(CURRENT_POLICY_VERSION),),
                )
                db.execute(
                    """
                    INSERT INTO audit_events(
                        created_at, session_id, event_type, request_digest,
                        outcome, payload_json
                    ) VALUES(?, '', 'policy_migration', '', 'allow', ?)
                    """,
                    (
                        time.time(),
                        json.dumps(
                            {
                                "from_version": stored_version,
                                "to_version": CURRENT_POLICY_VERSION,
                                "grants_cleared": True,
                                "project_allow_rules_disabled": int(disabled),
                                "global_permission_mode_preserved": True,
                            },
                            separators=(",", ":"),
                        ),
                    ),
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
        if source == "project" and behavior == "allow":
            raise ValueError("project rules may only ask or deny; they cannot widen permissions")
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
                    created_at, expires_at, enabled
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(session_id, workspace, source, behavior, action, pattern)
                DO UPDATE SET created_at=excluded.created_at,
                    expires_at=excluded.expires_at, enabled=1
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
                  AND enabled=1
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

    def get_global_permission_mode_updated_at(self) -> float:
        raw = self.get_text_setting("permission_mode_updated_at", "0")
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return 0.0

    def set_global_permission_mode(self, mode: str) -> None:
        normalized = str(mode or "").strip().lower().replace("-", "_")
        if normalized not in {"ask_for_approval", "approve_for_me", "full_access"}:
            raise ValueError(f"invalid permission mode: {mode!r}")
        with self._lock, self._connect() as db:
            updated_at = time.time()
            db.execute(
                """
                INSERT INTO security_settings(key, value) VALUES('permission_mode', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (normalized,),
            )
            db.execute(
                """
                INSERT INTO security_settings(key, value)
                VALUES('permission_mode_updated_at', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(updated_at),),
            )

    def get_session_mode(self, session_id: str) -> str:
        # Permission modes are global: every session shares one security
        # standard. Kept as a session-shaped API for callers that pass a
        # session id (subagent inheritance, webui endpoints).
        return self.get_global_permission_mode()

    def set_session_mode(self, session_id: str, mode: str) -> None:
        self.set_global_permission_mode(mode)

    def set_extension_trust(
        self,
        *,
        kind: str,
        extension_id: str,
        source: str,
        content_digest: str,
        config_digest: str = "",
        capabilities: dict[str, Any] | None = None,
        decision: str = "trusted",
    ) -> None:
        kind = str(kind or "").strip().lower()
        extension_id = str(extension_id or "").strip()
        decision = str(decision or "").strip().lower()
        if kind not in {"plugin", "mcp"} or not extension_id:
            raise ValueError("invalid extension trust identity")
        if decision not in {"trusted", "revoked"}:
            raise ValueError("invalid extension trust decision")
        now = time.time()
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO extension_trust(
                    kind, extension_id, source, content_digest, config_digest,
                    capabilities_json, decision, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(kind, extension_id) DO UPDATE SET
                    source=excluded.source,
                    content_digest=excluded.content_digest,
                    config_digest=excluded.config_digest,
                    capabilities_json=excluded.capabilities_json,
                    decision=excluded.decision,
                    updated_at=excluded.updated_at
                """,
                (
                    kind,
                    extension_id,
                    str(source or ""),
                    str(content_digest or ""),
                    str(config_digest or ""),
                    json.dumps(
                        capabilities or {}, ensure_ascii=False,
                        separators=(",", ":"), default=str,
                    ),
                    decision,
                    now,
                    now,
                ),
            )

    def extension_is_trusted(
        self,
        *,
        kind: str,
        extension_id: str,
        content_digest: str,
        config_digest: str = "",
    ) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM extension_trust WHERE kind=? AND extension_id=?",
                (str(kind or "").strip().lower(), str(extension_id or "").strip()),
            ).fetchone()
        return bool(
            row
            and row["decision"] == "trusted"
            and str(row["content_digest"]) == str(content_digest or "")
            and str(row["config_digest"]) == str(config_digest or "")
        )

    def get_extension_trust(
        self,
        *,
        kind: str,
        extension_id: str,
    ) -> dict[str, Any] | None:
        """Return the stored decision for an extension identity.

        Callers must still compare the stored digests with the current
        descriptor. A decision for an older MCP configuration must never be
        treated as approval for a changed command, URL, environment, or cwd.
        """
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM extension_trust WHERE kind=? AND extension_id=?",
                (str(kind or "").strip().lower(), str(extension_id or "").strip()),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        try:
            item["capabilities"] = json.loads(
                item.pop("capabilities_json") or "{}"
            )
        except (TypeError, ValueError):
            item["capabilities"] = {}
        return item

    def list_extension_trust(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM extension_trust ORDER BY kind, extension_id"
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["capabilities"] = json.loads(
                    item.pop("capabilities_json") or "{}"
                )
            except (TypeError, ValueError):
                item["capabilities"] = {}
            result.append(item)
        return result

    def revoke_extension_trust(self, kind: str, extension_id: str) -> bool:
        with self._lock, self._connect() as db:
            cur = db.execute(
                """
                UPDATE extension_trust SET decision='revoked', updated_at=?
                WHERE kind=? AND extension_id=?
                """,
                (
                    time.time(),
                    str(kind or "").strip().lower(),
                    str(extension_id or "").strip(),
                ),
            )
            return cur.rowcount > 0


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
    if isinstance(value, str):
        text = re.sub(
            r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s\"']+",
            r"\1[REDACTED]",
            value,
        )
        text = re.sub(
            r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|cookie)"
            r"(\s*[:=]\s*)[^\s;&|\"']+",
            r"\1\2[REDACTED]",
            text,
        )
        text = re.sub(
            r"(?i)(https?://[^\s?#]+\?)[^\s#]+",
            r"\1[REDACTED]",
            text,
        )
        return text
    return value


def redact_security_value(value: Any) -> Any:
    """Return the same shape with credentials and URL query values removed."""
    return _redact(value)
