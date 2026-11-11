"""Cross-session trigram index for global history search.

Per-file caches answer current-scope reads; a global query would otherwise
re-read every ``events.jsonl``. This index keeps one folded row per rendered
event (plus the source line offsets needed for verification), so a global scan
becomes a trigram lookup followed by a stat-only freshness check.

The source JSONL stays authoritative: every hit is re-read from its byte range
and re-rendered before it is returned. Any failure falls back to the original
streaming scan.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import logging
from pathlib import Path
import queue
import sqlite3
import threading

_NAME = ".history-search-global.sqlite3"
_VERSION = 3
_SKIP_BYTES = 256 * 1024 * 1024
_CHUNK = 1024 * 1024

_guard = threading.Lock()
_pending: set[str] = set()
_queue: queue.Queue = queue.Queue(maxsize=256)
_worker = None
logger = logging.getLogger(__name__)


def db_path(root) -> Path:
    return Path(root) / _NAME


def _connect(root) -> sqlite3.Connection:
    db = sqlite3.connect(str(db_path(root)), timeout=2, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")  # Derived cache; no durability promise.
    db.execute("CREATE TABLE IF NOT EXISTS meta(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    row = db.execute("SELECT value FROM meta WHERE id=1").fetchone()
    version = json.loads(row[0]).get("version") if row else None
    if version != _VERSION:
        if version == 2:
            # Keep the projection and only adopt boundary-checked appends.
            try:
                db.execute("ALTER TABLE files ADD COLUMN boundary TEXT")
            except sqlite3.OperationalError:
                pass
            for path, offset in db.execute("SELECT path,offset FROM files").fetchall():
                try:
                    boundary = _hash_tail(Path(path), int(offset or 0))
                except OSError:
                    boundary = ""
                db.execute("UPDATE files SET boundary=? WHERE path=?", (boundary, path))
        else:
            db.execute("DROP TABLE IF EXISTS docs")
            db.execute("DROP TABLE IF EXISTS docs_fts")
            db.execute("DROP TABLE IF EXISTS files")
        db.execute("INSERT OR REPLACE INTO meta VALUES(1,?)", (json.dumps({"version": _VERSION}),))
    db.execute(
        "CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER, "
        "ctime INTEGER, offset INTEGER, digest TEXT, docs INTEGER, skipped INTEGER, boundary TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, path TEXT, start INTEGER, "
        "end INTEGER, ref TEXT, folded TEXT, content TEXT)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS docs_path ON docs(path)")
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(folded, tokenize='trigram')")
    except sqlite3.OperationalError:
        pass
    return db


def _stamp(path: Path) -> tuple[int, int, int]:
    st = path.stat()
    return st.st_size, st.st_mtime_ns, st.st_ctime_ns


def _hash_tail(path: Path, offset: int, window: int = 64 * 1024) -> str:
    """Digest of the last bounded bytes of the indexed prefix."""
    start = max(0, offset - window)
    with path.open("rb") as handle:
        handle.seek(start)
        return hashlib.sha256(handle.read(offset - start)).hexdigest()


def _drop(db, path: str) -> None:
    db.execute("DELETE FROM docs_fts WHERE rowid IN (SELECT id FROM docs WHERE path=?)", (path,))
    db.execute("DELETE FROM docs WHERE path=?", (path,))


def _index_file(db, path: Path, render, render_ui=None) -> None:
    key = str(path)
    size, mtime, ctime = _stamp(path)
    row = db.execute(
        "SELECT size,mtime,ctime,offset,digest,docs,skipped,boundary FROM files WHERE path=?", (key,)
    ).fetchone()
    if size > _SKIP_BYTES or (row and row[6] and render_ui is None):
        _drop(db, key)
        db.execute(
            "INSERT OR REPLACE INTO files VALUES(?,?,?,?,0,'',0,1,'')", (key, size, mtime, ctime)
        )
        return
    if (row and row[0] == size and row[1] == mtime and row[2] == ctime
            and (not row[6] or render_ui is None)):
        # A skipped row is only final when no UI renderer could improve it.
        return
    offset = 0
    if row and size > row[3] and row[3] > 0:
        # Re-hashing a multi-hundred-MB prefix on every append dominated the
        # build. Verify the indexed boundary instead: O(64 KB) per append.
        try:
            if _hash_tail(path, row[3]) == row[7]:
                offset = row[3]
        except OSError:
            offset = 0
    if offset == 0:
        _drop(db, key)
        docs = 0
    else:
        docs = int(row[5] or 0)
    with path.open("rb") as handle:
        handle.seek(offset)
        while True:
            start = handle.tell()
            raw = handle.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                raise ValueError("history source has an unfinished line")
            try:
                event = json.loads(raw.decode("utf-8", errors="replace"))
            except (TypeError, ValueError):
                continue
            if not isinstance(event, dict):
                continue
            if str(event.get("type") or "") == "runtime_snapshot_compacted":
                rows = (event.get("payload") or {}).get("ui_events")
                if render_ui is None or not isinstance(rows, list):
                    # Without a UI renderer the raw scan keeps this dialogue.
                    _drop(db, key)
                    db.execute(
                        "INSERT OR REPLACE INTO files VALUES(?,?,?,?,0,'',0,1,'')",
                        (key, size, mtime, ctime),
                    )
                    return
                # A snapshot is the compacted session's only dialogue: index
                # each retained row, pointing at the whole line for verification.
                _drop(db, key)
                docs = 0
                seq = int(event.get("seq") or 0)
                for ui_index, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    content = render_ui(row)
                    if not content:
                        continue
                    folded = content.casefold()
                    cursor = db.execute(
                        "INSERT INTO docs(path,start,end,ref,folded,content) VALUES(?,?,?,?,?,?)",
                        (key, start, start + len(raw), f"{seq}:{ui_index}", folded, content),
                    )
                    db.execute(
                        "INSERT INTO docs_fts(rowid,folded) VALUES(?,?)",
                        (cursor.lastrowid, folded),
                    )
                    docs += 1
                continue
            ref, content = render(event)
            if not content:
                continue
            folded = content.casefold()
            cursor = db.execute(
                "INSERT INTO docs(path,start,end,ref,folded,content) VALUES(?,?,?,?,?,?)",
                (key, start, start + len(raw), str(ref), folded, None),
            )
            db.execute("INSERT INTO docs_fts(rowid,folded) VALUES(?,?)", (cursor.lastrowid, folded))
            docs += 1
        offset = handle.tell()
    db.execute(
        "INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,'',?,0,?)",
        (key, size, mtime, ctime, offset, docs, _hash_tail(path, offset)),
    )


def _build(root, path: Path, render, render_ui=None, db=None) -> None:
    try:
        if db is None:
            with closing(_connect(root)) as own, own:
                _index_file(own, path, render, render_ui)
        else:
            _index_file(db, path, render, render_ui)
            db.commit()
    except (OSError, ValueError, sqlite3.Error) as exc:
        if db is not None:
            try:
                db.rollback()
            except sqlite3.Error:
                pass
        logger.debug("Global history index skipped a source (%s)", type(exc).__name__, exc_info=True)
    except Exception:
        if db is not None:
            try:
                db.rollback()
            except sqlite3.Error:
                pass
        logger.debug("Global history index worker skipped a source", exc_info=True)
    finally:
        with _guard:
            _pending.discard(str(path))


def _work(root) -> None:
    db = None
    while True:
        path, render, render_ui = _queue.get()
        try:
            if db is None:
                try:
                    db = _connect(root)
                except (OSError, sqlite3.Error):
                    logger.debug("Global history index unavailable", exc_info=True)
                    with _guard:
                        _pending.discard(str(path))
                    continue
            _build(root, path, render, render_ui, db=db)
        finally:
            _queue.task_done()


def warm(root, entries, *, budget_bytes: int = 200 * 1024 * 1024) -> int:
    """Queue files lacking a current projection, newest first, bounded by bytes."""
    global _worker
    try:
        with closing(_connect(root)) as db:
            known = {
                path: (size, mtime, ctime)
                for path, size, mtime, ctime in db.execute(
                    "SELECT path,size,mtime,ctime FROM files WHERE skipped=0"
                )
            }
    except (OSError, sqlite3.Error):
        known = {}
    queued = total = 0
    for path, render, render_ui in entries:
        if total >= budget_bytes:
            break
        try:
            stamp = _stamp(path)
        except OSError:
            continue
        if known.get(str(path)) == stamp:
            continue
        size = stamp[0]
        if size > _SKIP_BYTES:
            continue
        total += size
        key = str(path)
        with _guard:
            if key in _pending or len(_pending) >= 256:
                continue
            _pending.add(key)
            try:
                _queue.put_nowait((path, render, render_ui))
            except queue.Full:
                _pending.discard(key)
                break
            if _worker is None or not _worker.is_alive():
                _worker = threading.Thread(target=_work, args=(root,), name="history-global-index", daemon=True)
                _worker.start()
        queued += 1
    return queued


def indexed_paths(root) -> set[str]:
    """Paths whose projection matches the file on disk right now."""
    ready: set[str] = set()
    try:
        with closing(_connect(root)) as db:
            rows = db.execute("SELECT path,size,mtime,ctime,skipped FROM files").fetchall()
    except (OSError, sqlite3.Error):
        return ready
    for path, size, mtime, ctime, skipped in rows:
        if skipped:
            continue
        try:
            if _stamp(Path(path)) == (size, mtime, ctime):
                ready.add(path)
        except OSError:
            continue
    return ready


def path_is_indexed(root, path) -> bool:
    """True when this one file has a current projection and is not skipped."""
    try:
        stamp = _stamp(Path(path))
    except OSError:
        return False
    try:
        with closing(_connect(root)) as db:
            row = db.execute(
                "SELECT size,mtime,ctime,skipped FROM files WHERE path=?", (str(path),)
            ).fetchone()
    except (OSError, sqlite3.Error):
        return False
    return bool(row) and not row[3] and (row[0], row[1], row[2]) == stamp


def warm_recent(
    sessions_dir,
    *,
    budget_bytes: int = 512 * 1024 * 1024,
    limit: int = 400,
) -> int:
    """Queue the newest sessions once, bounded by total bytes."""
    from history_context import _archive_renderer, _render_event_row, _ui_row_text

    root = Path(sessions_dir)
    candidates: list[tuple[int, Path]] = []
    try:
        for pattern in ("*/events.jsonl", "*/history_context_archives/*.jsonl"):
            for path in root.glob(pattern):
                try:
                    candidates.append((path.stat().st_mtime_ns, path))
                except OSError:
                    continue
    except OSError:
        return 0
    candidates.sort(reverse=True)
    entries = []
    for _modified, path in candidates[:limit]:
        if path.parent.name == "history_context_archives":
            entries.append((path, _archive_renderer(path), None))
        else:
            entries.append((path, _render_event_row, _ui_row_text))
    return warm(root, entries, budget_bytes=budget_bytes)


def search(
    root, terms, *, limit: int, path: str | None = None
) -> list[tuple[str, int, int, str, str, str | None]] | None:
    """Return candidates ``(path, start, end, ref, folded_text, stored_text)``."""
    longest = max(terms, key=len)
    args: list = []
    if len(longest) >= 3:
        match = '"' + longest.replace('"', '""') + '"'
        query = (
            "SELECT d.path,d.start,d.end,d.ref,d.folded,d.content FROM docs d "
            "JOIN docs_fts f ON f.rowid=d.id WHERE docs_fts MATCH ?"
        )
        args.append(match)
    else:
        # A trigram cannot answer two-character terms (common in Chinese);
        # scanning the folded column is still far cheaper than raw JSONL.
        query = "SELECT d.path,d.start,d.end,d.ref,d.folded,d.content FROM docs d WHERE 1"
    for term in terms:
        query += " AND instr(d.folded,?)>0"
        args.append(term)
    if path is not None:
        query += " AND d.path=?"
        args.append(str(path))
    query += " ORDER BY d.id LIMIT ?"
    args.append(max(1, int(limit)))
    try:
        with closing(_connect(root)) as db:
            return db.execute(query, args).fetchall()
    except (OSError, sqlite3.Error):
        logger.debug("Global history index query failed", exc_info=True)
        return None


def gc(root) -> int:
    """Forget projections whose source file disappeared."""
    removed = 0
    try:
        with closing(_connect(root)) as db, db:
            for (path,) in db.execute("SELECT path FROM files").fetchall():
                if Path(path).is_file():
                    continue
                _drop(db, path)
                db.execute("DELETE FROM files WHERE path=?", (path,))
                removed += 1
    except (OSError, sqlite3.Error):
        return removed
    return removed
