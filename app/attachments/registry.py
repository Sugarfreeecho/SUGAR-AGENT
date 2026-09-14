"""Durable grants and queue pins; neither contains image bytes or URL credentials."""
import sqlite3
import time
from contextlib import contextmanager

from .local import checked_id
from .locking import attachment_lock


class AttachmentRegistry:
    def __init__(self, store):
        self.path = store.root.parent / "registry.sqlite3"
        self.store = store

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Serialize initial WAL transition; ordinary readers/writers use SQLite's
        # own coordination after schema setup.
        with attachment_lock(self.path.parent, "registry-schema"):
            db = sqlite3.connect(self.path, timeout=30)
            try:
                if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                    db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE IF NOT EXISTS grants (owner TEXT, attachment TEXT, created REAL, PRIMARY KEY(owner, attachment))")
                db.execute("CREATE TABLE IF NOT EXISTS pins (owner TEXT, scope TEXT, attachment TEXT, PRIMARY KEY(owner, scope, attachment))")
                db.execute("CREATE TABLE IF NOT EXISTS leases (attachment TEXT PRIMARY KEY, expires REAL)")
                db.commit()
            except Exception:
                db.close()
                raise
        try:
            with db:
                yield db
        finally:
            db.close()

    def grant(self, owner, identities, lease_seconds=7 * 86400):
        ids = list(dict.fromkeys(identities))
        for identity in ids:
            checked_id(identity)
        with attachment_lock(self.store.root.parent, "catalog"), self.connection() as db:
            for identity in ids:
                self.store.ref_by_id(identity)
            db.executemany("INSERT OR IGNORE INTO grants VALUES (?,?,?)", [(owner, i, time.time()) for i in ids])
            db.executemany("INSERT INTO leases VALUES (?,?) ON CONFLICT(attachment) DO UPDATE SET expires=max(expires,excluded.expires)",
                           [(i, time.time() + lease_seconds) for i in ids])

    def allowed(self, owner, identity):
        checked_id(identity)
        with self.connection() as db:
            return db.execute("SELECT 1 FROM grants WHERE owner=? AND attachment=?", (owner, identity)).fetchone() is not None

    def pin(self, owner, scope, identities):
        ids = list(dict.fromkeys(identities))
        for identity in ids:
            checked_id(identity)
        with attachment_lock(self.store.root.parent, "catalog"), self.connection() as db:
            for identity in ids:
                self.store.ref_by_id(identity)
            db.execute("DELETE FROM pins WHERE owner=? AND scope=?", (owner, scope))
            db.executemany("INSERT INTO pins VALUES (?,?,?)", [(owner, scope, i) for i in ids])

    def protected(self):
        with self.connection() as db:
            pins = {r[0] for r in db.execute("SELECT attachment FROM pins")}
            pins.update(r[0] for r in db.execute("SELECT attachment FROM leases WHERE expires>?", (time.time(),)))
            return pins

    def forget(self, identity):
        with self.connection() as db:
            for table in ("grants", "pins", "leases"):
                db.execute(f"DELETE FROM {table} WHERE attachment=?", (identity,))
