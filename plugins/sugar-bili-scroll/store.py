"""Transactional duty observations, incoming jobs, run policy and send receipts."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

HOST_SERVICES = {}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, home):
        self.home = Path(home)
        self.path = self.home / "runtime.sqlite3"

    @contextmanager
    def db(self):
        self.home.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS kv(name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(
                    key TEXT PRIMARY KEY, event TEXT NOT NULL, status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL,
                    lease REAL NOT NULL DEFAULT 0, session_id TEXT NOT NULL DEFAULT '',
                    run_id TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
                    updated REAL NOT NULL, result TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS outbox(
                    key TEXT PRIMARY KEY, job_key TEXT NOT NULL, run_id TEXT NOT NULL,
                    kind TEXT NOT NULL, target TEXT NOT NULL, body TEXT NOT NULL,
                    status TEXT NOT NULL, receipt TEXT NOT NULL DEFAULT '{}', updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(
                    run_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, policy TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, comments INTEGER NOT NULL DEFAULT 0,
                    pictures INTEGER NOT NULL DEFAULT 0, emotes INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS bindings(
                    kind TEXT NOT NULL, key TEXT NOT NULL, session_id TEXT NOT NULL,
                    PRIMARY KEY(kind,key));
                CREATE TABLE IF NOT EXISTS observations(
                    task_id TEXT NOT NULL, day TEXT NOT NULL, bvid TEXT NOT NULL,
                    picked INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(task_id,day,bvid));
                CREATE TABLE IF NOT EXISTS seen(bvid TEXT PRIMARY KEY, task_id TEXT NOT NULL, day TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS admissions(key TEXT PRIMARY KEY, uid TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS accounts(
                    uid TEXT PRIMARY KEY, credential TEXT NOT NULL, updated REAL NOT NULL,
                    error TEXT NOT NULL DEFAULT '');
            """)
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, name, default=None):
        if not self.path.exists():
            return default
        with self.db() as db:
            row = db.execute("SELECT value FROM kv WHERE name=?", (name,)).fetchone()
            return json.loads(row[0]) if row else default

    def put(self, name, value):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (name, dumps(value)))

    def save_account(self, uid, credential):
        uid = str(uid or "")
        if not uid.isdigit() or int(uid) <= 0 or not str(credential.get("sessdata") or "").strip():
            raise ValueError("账号 UID 或登录凭证无效")
        payload = dumps(credential)
        with self.db() as db:
            old = db.execute("SELECT credential FROM accounts WHERE uid=?", (uid,)).fetchone()
            if not old:
                db.execute("INSERT INTO accounts(uid,credential,updated) VALUES(?,?,?)", (uid, payload, time.time()))
            elif json.loads(old[0]) != credential:
                db.execute("UPDATE accounts SET credential=?,updated=?,error='' WHERE uid=?", (payload, time.time(), uid))

    def account(self, uid):
        with self.db() as db:
            row = db.execute("SELECT credential FROM accounts WHERE uid=?", (str(uid),)).fetchone()
            return json.loads(row[0]) if row else None

    def accounts(self):
        """Only metadata may leave the credential store."""
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT uid,updated,error FROM accounts ORDER BY updated DESC,uid")]

    def account_error(self, uid, error):
        with self.db() as db:
            db.execute("UPDATE accounts SET error=? WHERE uid=?", (str(error), str(uid)))

    def remove_account(self, uid):
        with self.db() as db:
            return bool(db.execute("DELETE FROM accounts WHERE uid=?", (str(uid),)).rowcount)

    def activate_account(self, uid):
        """Keep old receipts, but never carry pending work or cursors into another account."""
        uid = str(uid or "")
        if not uid.isdigit():
            return False
        with self.db() as db:
            row = db.execute("SELECT value FROM kv WHERE name='account_uid'").fetchone()
            previous = json.loads(row[0]) if row else uid
            if row and previous == uid:
                return False
            if not row:
                for binding in db.execute("SELECT kind,key,session_id FROM bindings").fetchall():
                    db.execute("INSERT OR IGNORE INTO bindings VALUES(?,?,?)",
                               (binding["kind"], previous+":"+binding["key"], binding["session_id"]))
            # Attribute pre-account-isolation jobs before a possible switch.
            for job in db.execute("SELECT key,event FROM jobs").fetchall():
                event = json.loads(job["event"])
                if not event.get("account_uid"):
                    event["account_uid"] = previous
                    db.execute("UPDATE jobs SET event=? WHERE key=?", (dumps(event), job["key"]))
            changed = previous != uid
            if changed:
                old = db.execute("SELECT value FROM kv WHERE name='inbound'").fetchone()
                if old:
                    db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", ("inbound_archive:"+previous, old[0]))
                db.execute("INSERT OR REPLACE INTO kv VALUES('inbound',?)", (dumps({"account_uid": uid}),))
                db.execute("UPDATE jobs SET status='skipped',lease=0,error=?,updated=? WHERE status IN ('pending','linked')",
                           ("登录账号已切换，旧账号任务停止", time.time()))
                db.execute("DELETE FROM admissions")
            db.execute("INSERT OR REPLACE INTO kv VALUES('account_uid',?)", (dumps(uid),))
            return changed

    def poll_commit(self, state, events):
        """Commit source cursors and durable jobs together; retain send counters."""
        now = time.time()
        with self.db() as db:
            old = db.execute("SELECT value FROM kv WHERE name='inbound' ").fetchone()
            merged = json.loads(old[0]) if old else dict(state)
            for key in ("dm", "at", "reply", "channels_ready", "bootstrapped", "last_poll_at", "version",
                        "last_errors", "auth_error", "credential_stamp", "account_uid"):
                if key in state:
                    merged[key] = state[key]
            db.execute("INSERT OR REPLACE INTO kv VALUES('inbound',?)", (dumps(merged),))
            for event in events:
                db.execute("INSERT OR IGNORE INTO jobs(key,event,status,available,updated) VALUES(?,?,'pending',?,?)",
                           (event["key"], dumps(event), now, now))

    def jobs(self, *, ready=False, limit=100):
        with self.db() as db:
            clause = "WHERE status='pending' AND available<=?" if ready else ""
            values = (time.time(), limit) if ready else (limit,)
            rows = db.execute(f"SELECT * FROM jobs {clause} ORDER BY updated {'ASC' if ready else 'DESC'} LIMIT ?", values)
            return [self._job(row) for row in rows]

    @staticmethod
    def _job(row):
        return {**dict(row), "event": json.loads(row["event"]), "result": json.loads(row["result"])}

    def job(self, key):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone()
            return self._job(row) if row else None

    def claim(self, key, session_id="", run_id=""):
        now = time.time()
        with self.db() as db:
            return bool(db.execute("UPDATE jobs SET status='processing',attempts=attempts+1,lease=?,session_id=?,run_id=?,updated=? "
                                   "WHERE key=? AND status='pending' AND available<=?",
                                   (now+4200, session_id, run_id, now, key, now)).rowcount)

    def finish(self, key, status, error="", result=None, *, retry_delay=60):
        with self.db() as db:
            row = db.execute("SELECT attempts FROM jobs WHERE key=?", (key,)).fetchone()
            if status == "retry":
                status = "pending" if row and row[0] < 3 else "failed"
            db.execute("UPDATE jobs SET status=?,error=?,result=?,available=?,lease=0,updated=? WHERE key=?",
                       (status, str(error)[:1000], dumps(result or {}), time.time()+retry_delay, time.time(), key))
            if status not in {"pending", "processing", "linked", "unknown"}:
                for child in db.execute("SELECT key,result FROM jobs WHERE status='linked'").fetchall():
                    if json.loads(child["result"]).get("coalesced_into") == key:
                        db.execute("UPDATE jobs SET status=?,error=?,updated=? WHERE key=?", (status, str(error)[:1000], time.time(), child["key"]))

    def retry(self, key):
        with self.db() as db:
            # Unknown external writes require inspection, never automatic resend.
            changed = bool(db.execute("UPDATE jobs SET status='pending',attempts=0,available=?,error='',updated=? "
                                   "WHERE key=? AND status IN ('failed','skipped')",
                                   (time.time(), time.time(), key)).rowcount)
            if changed:
                db.execute("UPDATE outbox SET status='prepared' WHERE job_key=? AND status='failed'", (key,))
            return changed

    def annotate(self, key, values=None, session_id="", run_id=""):
        with self.db() as db:
            row = db.execute("SELECT result FROM jobs WHERE key=?", (key,)).fetchone()
            if not row:
                return
            result = {**json.loads(row[0]), **(values or {})}
            db.execute("UPDATE jobs SET result=?, session_id=CASE WHEN ?='' THEN session_id ELSE ? END, "
                       "run_id=CASE WHEN ?='' THEN run_id ELSE ? END WHERE key=?",
                       (dumps(result), session_id, session_id, run_id, run_id, key))

    def resolve(self, key, sent):
        with self.db() as db:
            row = db.execute("SELECT status FROM jobs WHERE key=?", (key,)).fetchone()
            if not row or row[0] != "unknown":
                return False
            db.execute("UPDATE outbox SET status=? WHERE job_key=? AND status IN ('sending','unknown')", ("sent" if sent else "prepared", key))
            statuses = {item[0] for item in db.execute("SELECT status FROM outbox WHERE job_key=?", (key,))}
            status = "pending" if "prepared" in statuses else ("failed" if "failed" in statuses else "sent")
            db.execute("UPDATE jobs SET status=?, available=?, error='',updated=? WHERE key=?", (status, time.time(), time.time(), key))
            if status != "pending":
                for child in db.execute("SELECT key,result FROM jobs WHERE status='linked'").fetchall():
                    if json.loads(child["result"]).get("coalesced_into") == key:
                        db.execute("UPDATE jobs SET status=?,error='',updated=? WHERE key=?", (status, time.time(), child["key"]))
            return True

    def defer(self, key, seconds, reason=""):
        with self.db() as db:
            db.execute("UPDATE jobs SET available=?,error=?,updated=? WHERE key=? AND status='pending'",
                       (time.time()+seconds, reason, time.time(), key))

    def admit(self, key, uid, cooldown, per_hour, *, outgoing=False):
        now = time.time()
        if outgoing:
            key = "out:" + key
        pattern = "out:%" if outgoing else "model:%"
        if not outgoing:
            key = "model:" + key
        with self.db() as db:
            if db.execute("SELECT 1 FROM admissions WHERE key=?", (key,)).fetchone():
                return True
            db.execute("DELETE FROM admissions WHERE at<?", (now-86400,))
            last = db.execute("SELECT MAX(at) FROM admissions WHERE uid=? AND key LIKE ?", (uid, pattern)).fetchone()[0]
            count = db.execute("SELECT COUNT(*) FROM admissions WHERE at>? AND key LIKE ?", (now-3600, pattern)).fetchone()[0]
            if (cooldown and last and now-last < cooldown*60) or (per_hour and count >= per_hour):
                return False
            db.execute("INSERT INTO admissions VALUES(?,?,?)", (key, uid, now))
            return True

    def note_sent(self, uid, receipt_key=""):
        with self.db() as db:
            if receipt_key and not db.execute("INSERT OR IGNORE INTO kv VALUES(?, 'true')", ("sent:"+receipt_key,)).rowcount:
                return
            row = db.execute("SELECT value FROM kv WHERE name='inbound'").fetchone()
            state = json.loads(row[0]) if row else {}
            now = time.time()
            state["recent"] = [x for x in state.get("recent", []) if x > now-10800] + [now]
            state.setdefault("last_uid", {})[str(uid)] = now
            db.execute("INSERT OR REPLACE INTO kv VALUES('inbound',?)", (dumps(state),))

    def bind(self, kind, key, session_id=None):
        with self.db() as db:
            if session_id is not None:
                db.execute("INSERT OR REPLACE INTO bindings VALUES(?,?,?)", (kind, key, session_id))
            row = db.execute("SELECT session_id FROM bindings WHERE kind=? AND key=?", (kind, key)).fetchone()
            return row[0] if row else ""

    def start_run(self, run_id, session_id, policy):
        with self.db() as db:
            db.execute("INSERT INTO runs(run_id,session_id,policy,created) VALUES(?,?,?,?)",
                       (run_id, session_id, dumps(policy), time.time()))

    def run(self, run_id="", session_id=""):
        if not self.path.exists():
            return None
        with self.db() as db:
            row = db.execute("SELECT * FROM runs WHERE run_id=? AND active=1", (run_id,)).fetchone() if run_id else None
            if not row and not run_id and session_id:
                row = db.execute("SELECT * FROM runs WHERE session_id=? AND active=1 ORDER BY created DESC LIMIT 1", (session_id,)).fetchone()
            return {**dict(row), "policy": json.loads(row["policy"])} if row else None

    def end_run(self, run_id):
        with self.db() as db:
            db.execute("UPDATE runs SET active=0 WHERE run_id=?", (run_id,))

    def reserve(self, run_id, field, limit):
        if field not in {"pictures", "comments", "emotes"}:
            raise ValueError("invalid run counter")
        with self.db() as db:
            return bool(db.execute(f"UPDATE runs SET {field}={field}+1 WHERE run_id=? AND active=1 AND {field}<?",
                                   (run_id, limit)).rowcount)

    def prepare_send(self, key, job_key, run_id, kind, target, body):
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO outbox(key,job_key,run_id,kind,target,body,status,updated) VALUES(?,?,?,?,?,?,'prepared',?)",
                       (key, job_key, run_id, kind, dumps(target), body, time.time()))
            row = db.execute("SELECT * FROM outbox WHERE key=?", (key,)).fetchone()
            return dict(row)

    def prepare_batch(self, rows):
        with self.db() as db:
            db.executemany("INSERT OR IGNORE INTO outbox(key,job_key,run_id,kind,target,body,status,updated) VALUES(?,?,?,?,?,?,'prepared',?)",
                           [(key, job_key, run_id, kind, dumps(target), body, time.time())
                            for key, job_key, run_id, kind, target, body in rows])

    def deliveries(self, job_key="", run_id=""):
        with self.db() as db:
            column, value = ("job_key", job_key) if job_key else ("run_id", run_id)
            return [dict(row) for row in db.execute(f"SELECT * FROM outbox WHERE {column}=? ORDER BY rowid", (value,))]

    def sending(self, key):
        with self.db() as db:
            return bool(db.execute("UPDATE outbox SET status='sending',updated=? WHERE key=? AND status='prepared'",
                                   (time.time(), key)).rowcount)

    def receipt(self, key, status, value):
        with self.db() as db:
            db.execute("UPDATE outbox SET status=?,receipt=?,updated=? WHERE key=?", (status, dumps(value), time.time(), key))

    def recover(self):
        """Called once at host startup, before workers are started."""
        with self.db() as db:
            db.execute("UPDATE outbox SET status='unknown' WHERE status='sending'")
            rows = db.execute("SELECT key,result FROM jobs WHERE status='processing'").fetchall()
            for row in rows:
                details = json.loads(row[1])
                parent = details.get("coalesced_into")
                statuses = {item[0] for item in db.execute("SELECT status FROM outbox WHERE job_key=?", (parent or row[0],))}
                status = "unknown" if "unknown" in statuses else ("pending" if not statuses or "prepared" in statuses else ("failed" if "failed" in statuses else "sent"))
                if parent and statuses:
                    status = "linked"
                db.execute("UPDATE jobs SET status=?,lease=0,available=?,updated=? WHERE key=?",
                           (status, time.time(), time.time(), row[0]))
            # A receipt may have committed before the worker updated either job.
            # Resolve linked steers even when their parent needs no more work.
            for child in db.execute("SELECT key,result FROM jobs WHERE status='linked'").fetchall():
                parent = json.loads(child["result"]).get("coalesced_into")
                outcome = db.execute("SELECT status,error FROM jobs WHERE key=?", (parent,)).fetchone() if parent else None
                if outcome and outcome[0] not in {"pending", "processing", "linked", "unknown"}:
                    db.execute("UPDATE jobs SET status=?,error=?,updated=? WHERE key=?", (outcome[0], outcome[1], time.time(), child["key"]))
            db.execute("UPDATE runs SET active=0")

    def observations(self, task_id, day=""):
        with self.db() as db:
            sql = "SELECT payload FROM observations WHERE task_id=?" + (" AND day=?" if day else "") + " ORDER BY rowid"
            values = (task_id, day) if day else (task_id,)
            return [json.loads(row[0]) for row in db.execute(sql, values)]

    def record(self, task_id, day, data, quota, legacy_picks=0):
        bvid = data["bvid"]
        with self.db() as db:
            old = db.execute("SELECT payload FROM observations WHERE task_id=? AND day=? AND bvid=?", (task_id, day, bvid)).fetchone()
            if old:
                return {"ok": True, "duplicate": True, "item": json.loads(old[0])}
            seen = db.execute("SELECT 1 FROM seen WHERE bvid=?", (bvid,)).fetchone()
            if seen:
                return {"ok": False, "error": "其他任务已经看过这条视频"}
            count = db.execute("SELECT COUNT(*) FROM observations WHERE task_id=? AND day=? AND picked=1", (task_id, day)).fetchone()[0]
            if data.get("picked") and count + legacy_picks >= quota:
                return {"ok": False, "error": "本任务今日额度已用完"}
            db.execute("INSERT INTO observations VALUES(?,?,?,?,?)", (task_id, day, bvid, int(data.get("picked", False)), dumps(data)))
            db.execute("INSERT INTO seen VALUES(?,?,?)", (bvid, task_id, day))
            return {"ok": True, "duplicate": False, "item": data}
