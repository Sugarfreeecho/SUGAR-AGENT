"""Durable admissions and control documents; Runtime V2 still owns transcripts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .errors import ControlError


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


class ControlStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self._ready = False

    @contextmanager
    def transaction(self):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path), timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA busy_timeout=10000")
                if not self._ready:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.executescript('''
                    CREATE TABLE IF NOT EXISTS operations (
                      id TEXT PRIMARY KEY, principal TEXT NOT NULL, idem TEXT NOT NULL,
                      method TEXT NOT NULL, digest TEXT NOT NULL, request TEXT NOT NULL,
                      status TEXT NOT NULL, delivery TEXT NOT NULL, session_id TEXT NOT NULL,
                      run_id TEXT NOT NULL, result TEXT, error TEXT, snapshot TEXT,
                      created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(principal,idem));
                    CREATE INDEX IF NOT EXISTS operations_pending ON operations(status,created);
                    CREATE INDEX IF NOT EXISTS operations_session_pending ON operations(session_id,status,created);
                    CREATE INDEX IF NOT EXISTS operations_automation ON operations(json_extract(request,'$._automation_id'),created);
                    CREATE TABLE IF NOT EXISTS operation_events (
                      seq INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT NOT NULL, body TEXT NOT NULL);
                    CREATE INDEX IF NOT EXISTS operation_events_owner ON operation_events(operation_id,seq);
                    CREATE TABLE IF NOT EXISTS automation_notices (
                      id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, kind TEXT NOT NULL,
                      status TEXT NOT NULL DEFAULT 'pending', error TEXT NOT NULL DEFAULT '');
                    CREATE INDEX IF NOT EXISTS automation_notices_pending ON automation_notices(status);
                    CREATE TABLE IF NOT EXISTS documents (
                      family TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
                      body TEXT NOT NULL, PRIMARY KEY(family,id));
                    CREATE TABLE IF NOT EXISTS events (
                      seq INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
                      event_id TEXT NOT NULL, digest TEXT NOT NULL, body TEXT NOT NULL,
                      created REAL NOT NULL, UNIQUE(source,event_id));
                    CREATE TABLE IF NOT EXISTS cursors (id TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS receipts (
                      session_id TEXT NOT NULL, operation_id TEXT NOT NULL,
                      body TEXT NOT NULL, PRIMARY KEY(session_id,operation_id));
                    CREATE TABLE IF NOT EXISTS grants (
                      token_hash TEXT PRIMARY KEY, principal TEXT NOT NULL,
                      policy TEXT NOT NULL, expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
                    ''')
                    self._ready = True
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()

    @staticmethod
    def operation(row):
        if row is None:
            return None
        value = dict(row)
        for key in ("request", "result", "error", "snapshot"):
            value[key] = json.loads(value[key]) if value[key] is not None else None
        return value

    def admit(self, principal, idem, method, params):
        with self.transaction() as db:
            return self._admit(db, principal, idem, method, params)

    def admit_many(self, principal, idem, requests):
        if not isinstance(idem, str) or not idem or len(idem) > 190:
            raise ControlError("idempotency_key_required", "A batch key of 1-190 characters is required")
        with self.transaction() as db:
            parent, replay = self._admit(db, principal, idem, "session.send_batch", {
                "requests": [{k: v for k, v in request.items() if k != "_principal"} for request in requests]})
            if replay:
                return [self.operation(db.execute("SELECT * FROM operations WHERE id=?", (oid,)).fetchone()) for oid in parent["result"]["operation_ids"]]
            operations = [self._admit(db, principal, idem + ":" + str(i), "session.send", request)[0]
                          for i, request in enumerate(requests)]
            db.execute("UPDATE operations SET status='succeeded',delivery='committed',result=? WHERE id=?",
                (encoded({"operation_ids": [op["id"] for op in operations]}), parent["id"]))
            return operations

    def _admit(self, db, principal, idem, method, params):
        if not isinstance(idem, str) or not idem or len(idem) > 200:
            raise ControlError("idempotency_key_required", "A key of 1-200 characters is required")
        def business(request):
            value = {k: v for k, v in request.items() if k != "_principal"}
            if value.get("_source"):
                value["_source"] = {"id": value["_source"]["id"]}
            return value
        semantic = business(params)
        if method == "session.send_batch":
            semantic["requests"] = [business(row) for row in semantic["requests"]]
        fingerprint = digest({"method": method, "params": semantic})
        now = time.time()
        row = db.execute("SELECT * FROM operations WHERE principal=? AND idem=?", (principal, idem)).fetchone()
        if row:
            if row["digest"] != fingerprint:
                raise ControlError("idempotency_conflict", "Key already belongs to different arguments", status=409)
            return self.operation(row), True
        if params.get("_coalesce_key"):
            active = db.execute("SELECT * FROM operations WHERE principal=? AND status IN ('queued','running','cancelling') AND json_extract(request,'$._coalesce_key')=? ORDER BY created LIMIT 1",
                (principal, params["_coalesce_key"])).fetchone()
            if active:
                return self.operation(active), True
        oid = str(uuid.uuid4())
        db.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,?,?)",
                   (oid, principal, idem, method, fingerprint, encoded(params), "queued", "pending",
                    str(params.get("session_id") or ""), "control-" + oid, now, now))
        return self.operation(db.execute("SELECT * FROM operations WHERE id=?", (oid,)).fetchone()), False

    def source_operations(self, source_id):
        with self.transaction() as db:
            return [self.operation(row) for row in db.execute("SELECT * FROM operations WHERE status IN ('queued','running','cancelling') AND json_extract(request,'$._source.id')=?", (source_id,))]

    def get_operation(self, oid):
        with self.transaction() as db:
            return self.operation(db.execute("SELECT * FROM operations WHERE id=?", (oid,)).fetchone())

    def append_operation_event(self, operation_id, event):
        with self.transaction() as db:
            seq = db.execute("INSERT INTO operation_events(operation_id,body) VALUES (?,?)", (operation_id, encoded(event))).lastrowid
            if event.get("type") in {"approval_requested", "tool_approval_required", "question_requested"}:
                row = db.execute("SELECT request FROM operations WHERE id=?", (operation_id,)).fetchone()
                if row and json.loads(row[0]).get("_automation_id"):
                    identity = str(event.get("approval_id") or event.get("question_id") or event.get("tool_call_id") or seq)
                    db.execute("INSERT OR IGNORE INTO automation_notices(id,operation_id,kind) VALUES (?,?,'pending_human')",
                               (operation_id + ":human:" + identity, operation_id))
            return seq

    def operation_events(self, operation_id, after=0, limit=100):
        with self.transaction() as db:
            return [{**json.loads(row[1]), "cursor": row[0]} for row in db.execute(
                "SELECT seq,body FROM operation_events WHERE operation_id=? AND seq>? ORDER BY seq LIMIT ?",
                (operation_id, int(after), min(500, max(1, int(limit)))))]

    def find_operation(self, principal, key):
        with self.transaction() as db:
            return self.operation(db.execute("SELECT * FROM operations WHERE principal=? AND idem=?", (principal, key)).fetchone())

    def operation_for_run(self, sid, run_id):
        with self.transaction() as db:
            return self.operation(db.execute("SELECT * FROM operations WHERE session_id=? AND run_id=? ORDER BY created DESC LIMIT 1", (sid, run_id)).fetchone())

    def pending_heads(self):
        with self.transaction() as db:
            return [self.operation(row) for row in db.execute("""
                SELECT op.* FROM operations op WHERE status='queued'
                AND method IN ('session.send','session.continue','session.recover')
                AND NOT EXISTS (SELECT 1 FROM operations earlier WHERE earlier.session_id=op.session_id
                    AND earlier.status='queued' AND earlier.method IN ('session.send','session.continue','session.recover')
                    AND (earlier.created < op.created OR (earlier.created=op.created AND earlier.id<op.id)))
                ORDER BY created LIMIT 1000""")]

    def operations(self, *, status=None, session_id=None, automation_id=None, limit=100, newest=False):
        clauses, values = [], []
        if status:
            clauses.append("status=?")
            values.append(status)
        if session_id:
            clauses.append("session_id=?")
            values.append(session_id)
        if automation_id:
            clauses.append("json_extract(request,'$._automation_id')=?")
            values.append(automation_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.transaction() as db:
            return [self.operation(r) for r in db.execute("SELECT * FROM operations" + where + " ORDER BY created " + ("DESC" if newest else "ASC") + " LIMIT ?",
                                                         (*values, min(max(int(limit), 1), 1000)))]

    def update_operation(self, oid, *, expected=None, **fields):
        allowed = {"status", "delivery", "session_id", "result", "error", "snapshot"}
        if not fields or set(fields) - allowed:
            raise ValueError("invalid operation update")
        data = {k: encoded(v) if k in {"result", "error", "snapshot"} else v for k, v in fields.items()}
        data["updated"] = time.time()
        with self.transaction() as db:
            sql = "UPDATE operations SET " + ",".join(k + "=?" for k in data) + " WHERE id=?"
            values = [*data.values(), oid]
            if expected is not None:
                sql += " AND status=?"
                values.append(expected)
            changed = db.execute(sql, values).rowcount == 1
            if changed and fields.get("status") in {"succeeded", "failed", "stopped", "interrupted", "unknown", "cancelled", "rejected"}:
                row = db.execute("SELECT request FROM operations WHERE id=?", (oid,)).fetchone()
                if row and json.loads(row[0]).get("_automation_id"):
                    db.execute("INSERT OR IGNORE INTO automation_notices(id,operation_id,kind) VALUES (?,?,'terminal')", (oid + ":terminal", oid))
            return changed

    def get(self, family, identity):
        with self.transaction() as db:
            row = db.execute("SELECT body FROM documents WHERE family=? AND id=?", (family, identity)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, family):
        with self.transaction() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT body FROM documents WHERE family=? ORDER BY id", (family,))]

    def put(self, family, identity, body, *, expected=None):
        with self.transaction() as db:
            row = db.execute("SELECT revision,body FROM documents WHERE family=? AND id=?", (family, identity)).fetchone()
            revision = row[0] if row else 0
            if expected is not None and expected != revision:
                raise ControlError("revision_conflict", "Configuration changed; reload before saving", status=409,
                                   details={"revision": revision})
            value = {**body, "id": identity, "revision": revision + 1}
            db.execute("INSERT INTO documents VALUES (?,?,?,?) ON CONFLICT(family,id) DO UPDATE SET revision=excluded.revision,body=excluded.body",
                       (family, identity, revision + 1, encoded(value)))
            return value

    def delete(self, family, identity):
        with self.transaction() as db:
            return db.execute("DELETE FROM documents WHERE family=? AND id=?", (family, identity)).rowcount == 1

    def append_event(self, event, *, cursor=None, transport_time=False):
        fingerprint = digest({k: v for k, v in event.items() if not (transport_time and k == "time")})
        with self.transaction() as db:
            row = db.execute("SELECT seq,digest,body FROM events WHERE source=? AND event_id=?", (event["source"], event["id"])).fetchone()
            if row and transport_time:
                old = json.loads(row["body"])
                old_digest = digest({k: v for k, v in old.items() if k != "time"})
            else:
                old_digest = row["digest"] if row else None
            if row and old_digest != fingerprint:
                raise ControlError("event_conflict", "Event identity already has different content", status=409)
            if row:
                seq, duplicate = row["seq"], True
            else:
                seq = db.execute("INSERT INTO events(source,event_id,digest,body,created) VALUES (?,?,?,?,?)",
                                 (event["source"], event["id"], fingerprint, encoded(event), time.time())).lastrowid
                duplicate = False
            if cursor:
                db.execute("INSERT OR REPLACE INTO cursors VALUES (?,?)", (cursor[0], encoded(cursor[1])))
            return seq, duplicate

    def events(self, after=0, *, limit=200):
        with self.transaction() as db:
            return [{"cursor": r[0], **json.loads(r[1])} for r in db.execute(
                "SELECT seq,body FROM events WHERE seq>? ORDER BY seq LIMIT ?", (after, min(limit, 1000)))]

    def cursor(self, name, default=None):
        with self.transaction() as db:
            row = db.execute("SELECT value FROM cursors WHERE id=?", (name,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_cursor(self, name, value):
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO cursors VALUES (?,?)", (name, encoded(value)))

    def set_cursors(self, values):
        """Advance related consumer watermarks in one durable transaction."""
        with self.transaction() as db:
            db.executemany("INSERT OR REPLACE INTO cursors VALUES (?,?)",
                           [(name, encoded(value)) for name, value in values.items()])

    def receipt(self, sid, oid, value=None):
        with self.transaction() as db:
            if value is not None:
                db.execute("INSERT OR REPLACE INTO receipts VALUES (?,?,?)", (sid, oid, encoded(value)))
            row = db.execute("SELECT body FROM receipts WHERE session_id=? AND operation_id=?", (sid, oid)).fetchone()
            return json.loads(row[0]) if row else None
