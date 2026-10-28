"""Host-owned, bounded ACP connection telemetry without credential payloads."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone


HEARTBEAT_SECONDS = 15
STALE_SECONDS = 50
RETAIN_SECONDS = 600
MAX_CONNECTIONS = 256
MAX_SESSIONS = 64


def _stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    return " ".join("".join(ch if ord(ch) >= 32 else " " for ch in value).split())[:limit]


class ConnectionRegistry:
    def __init__(self, *, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.rows = {}

    def _prune(self, now):
        for key, row in list(self.rows.items()):
            ended = row["disconnected_at"] or row["last_seen"]
            if now - ended > RETAIN_SECONDS:
                del self.rows[key]

    def register(self, owner, connection_id, payload):
        if not isinstance(payload, dict) or set(payload) - {"client", "protocol_version", "adapter_pid"}:
            raise ValueError("invalid connection registration")
        client = payload.get("client") or {}
        if not isinstance(client, dict) or type(payload.get("protocol_version")) is not int or payload["protocol_version"] != 1:
            raise ValueError("invalid ACP client or protocol")
        pid = payload.get("adapter_pid")
        if pid is not None and (type(pid) is not int or pid <= 0):
            raise ValueError("invalid adapter pid")
        now = self.clock()
        key = (owner, connection_id)
        with self.lock:
            self._prune(now)
            row = self.rows.get(key)
            if row is None or row["disconnected_at"] is not None:
                if len(self.rows) >= MAX_CONNECTIONS:
                    expired = [k for k, r in self.rows.items()
                               if r["disconnected_at"] is not None or now - r["last_seen"] > STALE_SECONDS]
                    if not expired:
                        raise ValueError("ACP connection registry is full")
                    del self.rows[min(expired, key=lambda k: self.rows[k]["last_seen"])]
                row = {"id": connection_id, "owner": owner, "client": {}, "protocol_version": 1,
                       "connected_at": now, "last_seen": now, "last_activity": now,
                       "activity": "connected", "disconnected_at": None, "sessions": {}, "busy": set()}
                self.rows[key] = row
            row["client"] = {field: _text(client.get(field), limit)
                             for field, limit in (("name", 160), ("title", 160), ("version", 80))}
            row["last_seen"] = now
            # The process id is intentionally not part of the public UI payload.

    def heartbeat(self, owner, connection_id, payload):
        if not isinstance(payload, dict) or set(payload) - {"busy_session_ids", "activity"}:
            raise ValueError("invalid connection heartbeat")
        busy = payload.get("busy_session_ids", [])
        activity = payload.get("activity")
        if (not isinstance(busy, list) or len(busy) > MAX_SESSIONS
                or any(not isinstance(sid, str) or not sid for sid in busy)
                or (activity is not None and (not isinstance(activity, str) or activity not in {"prompt", "configured", "completed"}))):
            raise ValueError("invalid connection activity")
        with self.lock:
            row = self.rows.get((owner, connection_id))
            if row is None or row["disconnected_at"] is not None:
                raise KeyError("connection is not registered")
            if any(sid not in row["sessions"] or not row["sessions"][sid]["attached"] for sid in busy):
                raise ValueError("busy session is not attached to this connection")
            now = self.clock()
            row["last_seen"] = now
            row["busy"] = set(busy)
            if activity is not None:
                row["last_activity"] = now
                row["activity"] = activity

    def attach(self, owner, connection_id, sid, cwd, title=""):
        with self.lock:
            row = self.rows.get((owner, connection_id))
            if row is None or row["disconnected_at"] is not None:
                return  # Old adapters have no telemetry lease.
            sessions = row["sessions"]
            if sid not in sessions and len(sessions) >= MAX_SESSIONS:
                old = next((key for key, value in sessions.items() if not value["attached"]), None)
                if old is None:
                    raise ValueError("too many sessions on this ACP connection")
                del sessions[old]
            sessions[sid] = {"session_id": sid, "cwd": str(cwd), "title": _text(title, 160), "attached": True}
            row["last_activity"] = row["last_seen"] = self.clock()
            row["activity"] = "attached"

    def detach(self, owner, connection_id, sid):
        with self.lock:
            row = self.rows.get((owner, connection_id))
            if row is None:
                return
            session = row["sessions"].get(sid)
            if session is not None:
                session["attached"] = False
            row["busy"].discard(sid)
            row["last_activity"] = row["last_seen"] = self.clock()
            row["activity"] = "detached"

    def disconnect(self, owner, connection_id):
        with self.lock:
            row = self.rows.get((owner, connection_id))
            if row is not None and row["disconnected_at"] is None:
                row["disconnected_at"] = row["last_activity"] = self.clock()
                row["activity"] = "disconnected"
                row["busy"].clear()
                for session in row["sessions"].values():
                    session["attached"] = False

    def snapshot(self, *, owner=None):
        now = self.clock()
        with self.lock:
            self._prune(now)
            connections = []
            for row in sorted(self.rows.values(), key=lambda r: r["connected_at"], reverse=True):
                if owner is not None and row["owner"] != owner:
                    continue
                status = ("disconnected" if row["disconnected_at"] is not None else
                          "stale" if now - row["last_seen"] > STALE_SECONDS else "online")
                sessions = [dict(session, busy=sid in row["busy"] and status == "online")
                            for sid, session in row["sessions"].items()]
                connections.append({"id": row["id"], "client": dict(row["client"]), "status": status,
                    "busy": bool(row["busy"]) and status == "online", "transport": "stdio", "protocol_version": 1,
                    "connected_at": _stamp(row["connected_at"]), "last_seen": _stamp(row["last_seen"]),
                    "last_activity": _stamp(row["last_activity"]), "activity": row["activity"],
                    "disconnected_at": _stamp(row["disconnected_at"]) if row["disconnected_at"] is not None else None,
                    "sessions": sessions})
            return {"connections": connections, "online_count": sum(r["status"] == "online" for r in connections),
                    "session_count": sum(s["attached"] for r in connections if r["status"] == "online" for s in r["sessions"]),
                    "observed_at": _stamp(now), "heartbeat_seconds": HEARTBEAT_SECONDS, "stale_seconds": STALE_SECONDS}


registry = ConnectionRegistry()
