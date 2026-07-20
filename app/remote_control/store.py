from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ALLOWED_SCOPES = frozenset({"read", "write", "approvals", "admin"})
DEFAULT_DEVICE_SCOPES = ("read", "write", "approvals")


class RemoteStoreError(RuntimeError):
    pass


class PairingCodeError(RemoteStoreError):
    pass


class IdempotencyConflict(RemoteStoreError):
    pass


@dataclass(frozen=True)
class DevicePrincipal:
    device_id: str
    name: str
    scopes: frozenset[str]
    credential_kind: str = "device"

    def permits(self, scope: str) -> bool:
        return scope in self.scopes or "admin" in self.scopes


def _normalise_scopes(scopes: Iterable[str] | None) -> tuple[str, ...]:
    values = {str(item).strip().lower() for item in (scopes or DEFAULT_DEVICE_SCOPES)}
    values.discard("")
    unknown = values - ALLOWED_SCOPES
    if unknown:
        raise ValueError(f"unknown scopes: {', '.join(sorted(unknown))}")
    if not values:
        raise ValueError("at least one scope is required")
    return tuple(sorted(values))


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _pairing_hash(code: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", str(code).strip().upper().encode("utf-8"), salt, 120_000
    )


class RemoteControlStore:
    """Small durable store for devices, pairings, idempotency and audit."""

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "remote-control.sqlite3"
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    scopes_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_seen_at REAL,
                    revoked_at REAL
                );
                CREATE TABLE IF NOT EXISTS pairings (
                    pairing_id TEXT PRIMARY KEY,
                    code_salt BLOB NOT NULL,
                    code_hash BLOB NOT NULL,
                    label TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    principal_id TEXT NOT NULL,
                    idem_key TEXT NOT NULL,
                    method TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (principal_id, idem_key)
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_id TEXT PRIMARY KEY,
                    occurred_at REAL NOT NULL,
                    principal_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_occurred_at ON audit_log(occurred_at);
                """
            )

    def create_pairing(
        self,
        *,
        label: str = "Mobile device",
        scopes: Iterable[str] | None = None,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        normalised = _normalise_scopes(scopes)
        # 60 bits of entropy while remaining short enough to type from a phone.
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "".join(secrets.choice(alphabet) for _ in range(12))
        pretty_code = f"{code[:4]}-{code[4:8]}-{code[8:]}"
        canonical = pretty_code.replace("-", "")
        salt = secrets.token_bytes(16)
        now = time.time()
        pairing_id = str(uuid.uuid4())
        expires_at = now + max(60, min(int(ttl_seconds), 3600))
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM pairings WHERE expires_at < ? OR consumed_at IS NOT NULL", (now,))
            conn.execute(
                "INSERT INTO pairings VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                (
                    pairing_id,
                    salt,
                    _pairing_hash(canonical, salt),
                    str(label or "Mobile device")[:120],
                    json.dumps(normalised),
                    now,
                    expires_at,
                ),
            )
        return {
            "pairing_id": pairing_id,
            "code": pretty_code,
            "expires_at": expires_at,
            "scopes": list(normalised),
        }

    def consume_pairing(self, code: str, *, device_name: str = "Mobile device") -> dict[str, Any]:
        canonical = str(code or "").strip().upper().replace("-", "").replace(" ", "")
        if not canonical:
            raise PairingCodeError("missing pairing code")
        now = time.time()
        match: sqlite3.Row | None = None
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pairings WHERE consumed_at IS NULL AND expires_at >= ?", (now,)
            ).fetchall()
            for row in rows:
                actual = _pairing_hash(canonical, bytes(row["code_salt"]))
                if hmac.compare_digest(actual, bytes(row["code_hash"])):
                    match = row
                    break
            if match is None:
                raise PairingCodeError("invalid or expired pairing code")
            updated = conn.execute(
                "UPDATE pairings SET consumed_at=? WHERE pairing_id=? AND consumed_at IS NULL",
                (now, match["pairing_id"]),
            ).rowcount
            if updated != 1:
                raise PairingCodeError("pairing code was already used")
            token = "rc1_" + secrets.token_urlsafe(36)
            device_id = str(uuid.uuid4())
            name = str(device_name or match["label"] or "Mobile device").strip()[:120]
            conn.execute(
                "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (
                    device_id,
                    name,
                    _token_hash(token),
                    match["scopes_json"],
                    now,
                    now,
                ),
            )
        return {
            "device_id": device_id,
            "device_name": name,
            "device_token": token,
            "scopes": json.loads(match["scopes_json"]),
        }

    def authenticate_device(self, token: str) -> DevicePrincipal | None:
        value = str(token or "").strip()
        if not value:
            return None
        now = time.time()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM devices WHERE token_hash=? AND revoked_at IS NULL",
                (_token_hash(value),),
            ).fetchone()
            if row is None:
                return None
            conn.execute("UPDATE devices SET last_seen_at=? WHERE device_id=?", (now, row["device_id"]))
        return DevicePrincipal(
            device_id=row["device_id"],
            name=row["name"],
            scopes=frozenset(json.loads(row["scopes_json"])),
        )

    def list_devices(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT device_id, name, scopes_json, created_at, last_seen_at, revoked_at "
                "FROM devices ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "device_id": row["device_id"],
                "name": row["name"],
                "scopes": json.loads(row["scopes_json"]),
                "created_at": row["created_at"],
                "last_seen_at": row["last_seen_at"],
                "revoked_at": row["revoked_at"],
            }
            for row in rows
        ]

    def revoke_device(self, device_id: str) -> bool:
        with self._lock, self._connect() as conn:
            return conn.execute(
                "UPDATE devices SET revoked_at=? WHERE device_id=? AND revoked_at IS NULL",
                (time.time(), str(device_id or "").strip()),
            ).rowcount == 1

    def get_idempotent(self, principal_id: str, key: str, method: str) -> dict[str, Any] | None:
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM idempotency WHERE expires_at < ?", (now,))
            row = conn.execute(
                "SELECT method, response_json FROM idempotency WHERE principal_id=? AND idem_key=?",
                (principal_id, key),
            ).fetchone()
        if row is None:
            return None
        if row["method"] != method:
            raise IdempotencyConflict("idempotency key was already used for another method")
        return json.loads(row["response_json"])

    def put_idempotent(
        self,
        principal_id: str,
        key: str,
        method: str,
        response: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        now = time.time()
        encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT method FROM idempotency WHERE principal_id=? AND idem_key=?",
                (principal_id, key),
            ).fetchone()
            if existing is not None and existing["method"] != method:
                raise IdempotencyConflict("idempotency key was already used for another method")
            conn.execute(
                "INSERT OR REPLACE INTO idempotency VALUES (?, ?, ?, ?, ?, ?)",
                (principal_id, key, method, encoded, now, now + ttl_seconds),
            )

    def audit(
        self,
        *,
        principal_id: str,
        action: str,
        target: str = "",
        outcome: str = "ok",
        details: dict[str, Any] | None = None,
    ) -> str:
        audit_id = str(uuid.uuid4())
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    audit_id,
                    time.time(),
                    str(principal_id or "unknown"),
                    str(action or "unknown")[:160],
                    str(target or "")[:240],
                    str(outcome or "unknown")[:40],
                    json.dumps(details or {}, ensure_ascii=False, separators=(",", ":")),
                ),
            )
        return audit_id

    def list_audit(self, *, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 1000))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY occurred_at DESC LIMIT ?", (safe_limit,)
            ).fetchall()
        return [
            {
                "audit_id": row["audit_id"],
                "occurred_at": row["occurred_at"],
                "principal_id": row["principal_id"],
                "action": row["action"],
                "target": row["target"],
                "outcome": row["outcome"],
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]
