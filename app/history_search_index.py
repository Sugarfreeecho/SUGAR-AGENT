"""Rebuildable semantic search indexes; source JSONL always remains authoritative."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import logging
from pathlib import Path
import queue
import sqlite3
import threading

from file_read_signature import signature, stat_signature


_VERSION = 1
logger = logging.getLogger(__name__)
_guard = threading.Lock()
_pending = set()
_queue = queue.Queue(maxsize=8)
_worker = None


def _signature(info):
    return list(stat_signature(info))


def _db_path(path):
    return path.parent / '.history-search' / (path.name + '.sqlite3')


def _prefix_hash(source, size):
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        data = source.read(min(1024 * 1024, remaining))
        if not data:
            raise ValueError('history source shrank')
        digest.update(data)
        remaining -= len(data)
    return digest


def _update(db, path, render):
    db.execute('CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS rows (offset INTEGER PRIMARY KEY, end_offset INTEGER, ref TEXT, content TEXT, folded TEXT)')
    row = db.execute('SELECT value FROM meta WHERE id=1').fetchone()
    meta = json.loads(row[0]) if row else {}
    if (not isinstance(meta, dict) or not isinstance(meta.get('signature'), list)
            or type(meta.get('offset')) is not int or meta['offset'] < 0):
        meta = {}
    with path.open('rb', buffering=256 * 1024) as source:
        opened = signature(source)
        if opened is None:
            raise ValueError('unknown history source identity')
        before = list(opened)
        if meta.get('version') == _VERSION and meta.get('signature') == before:
            return before
        offset = int(meta.get('offset', 0))
        compatible = (meta.get('version') == _VERSION and before[1] != 0
                      and meta.get('signature', [])[:2] == before[:2]
                      and 0 <= offset <= before[2])
        # A larger file alone is not proof of append-only growth. Verify every
        # byte in the indexed prefix before reusing it after any source change.
        digest = _prefix_hash(source, offset) if compatible else hashlib.sha256()
        if not compatible or digest.hexdigest() != meta.get('digest'):
            db.execute('DELETE FROM rows')
            source.seek(0)
            offset = 0
            digest = hashlib.sha256()
        # Binary byte accounting avoids a Windows file-position syscall (and
        # GIL handoff) for every JSONL row during background projection.
        while offset < before[2]:
            start = offset
            raw = source.readline(before[2] - start)
            if not raw.endswith(b'\n'):
                raise ValueError('history source has an unfinished line')
            digest.update(raw)
            offset += len(raw)
            try:
                value = json.loads(raw.decode('utf-8', errors='replace'))
                if not isinstance(value, dict):
                    continue
            except (ValueError, TypeError):
                continue
            ref, content = render(value)
            if content:
                db.execute('INSERT OR REPLACE INTO rows VALUES(?,?,?,?,?)',
                           (start, offset, str(ref), content, content.casefold()))
        # Do not publish a projection of a source replaced/rewritten mid-read.
        if list(signature(source) or ()) != before or _signature(path.stat()) != before[:5]:
            raise ValueError('history source changed during indexing')
        db.execute('INSERT OR REPLACE INTO meta VALUES(1,?)', (json.dumps({
            'version': _VERSION, 'signature': before, 'offset': offset,
            'digest': digest.hexdigest(),
        }),))
        return before


def _connect(path):
    db = sqlite3.connect(str(_db_path(path)), timeout=.005)
    try:
        db.execute('PRAGMA synchronous=OFF')  # Derived cache; no durability obligation.
    except BaseException:
        db.close()
        raise
    return db


def _build(path, render):
    try:
        _db_path(path).parent.mkdir(exist_ok=True)
        with closing(_connect(path)) as db, db:
            _update(db, path, render)
    except sqlite3.DatabaseError as exc:
        logger.debug('History index build unavailable (%s)', type(exc).__name__, exc_info=True)
        if 'not a database' in str(exc) or 'malformed' in str(exc):
            try:
                _db_path(path).unlink(missing_ok=True)
            except OSError:
                pass
    except (OSError, ValueError, TypeError) as exc:
        logger.debug('History index build deferred (%s)', type(exc).__name__, exc_info=True)
    finally:
        with _guard:
            _pending.discard(str(path))


def schedule(path, render):
    global _worker

    key = str(path)
    with _guard:
        if key in _pending or len(_pending) >= 8:
            return
        _pending.add(key)
        try:
            _queue.put_nowait((path, render))
        except queue.Full:
            _pending.discard(key)
            return
        if _worker is None or not _worker.is_alive():
            # A disposable index must not delay process shutdown. An unfinished
            # SQLite transaction is recovered/rebuilt on the next use.
            _worker = threading.Thread(target=_work, name='history-index', daemon=True)
            _worker.start()


def _work():
    while True:
        path, render = _queue.get()
        try:
            _build(path, render)
        except Exception:
            # An extension's unexpected legacy row must not kill precomputation.
            logger.debug('History index worker skipped a source', exc_info=True)
        finally:
            _queue.task_done()


def search(path: Path, terms: list[str], render, *, limit: int, seen: set[str]):
    """Return cached matches, or None to use the original streaming search.

    Cold scans keep their existing early-return behavior and schedule one
    bounded background worker. A warm index reconciles changed sources before
    searching, and verifies raw-line terms too, preserving JSONL search rules.
    """
    if not _db_path(path).is_file():
        return None
    try:
        with closing(_connect(path)) as db, db:
            stamp = _update(db, path, render)
            rows = db.execute(
                'SELECT offset,end_offset,ref,content FROM rows WHERE '
                + ' AND '.join('instr(folded,?)>0' for _ in terms) + ' ORDER BY offset', terms,
            )
            result = []
            dedup = set(seen)
            with path.open('rb') as source:
                if list(signature(source) or ()) != stamp:
                    return None
                for start, end, ref, content in rows:
                    key = ' '.join(content.split()).casefold()
                    if key in dedup:
                        continue
                    source.seek(start)
                    raw = source.read(end - start).decode('utf-8', errors='replace').casefold()
                    if all(term in raw for term in terms):
                        result.append((ref, content))
                        dedup.add(key)
                        if len(result) >= limit:
                            break
                if list(signature(source) or ()) != stamp or _signature(path.stat()) != stamp[:5]:
                    return None
        return result
    except (OSError, ValueError, TypeError, sqlite3.Error):
        logger.debug('History index search fell back to source', exc_info=True)
        return None
