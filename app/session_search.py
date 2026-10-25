"""Local, rebuildable UI search. The effective history, never the cache, is authoritative."""
from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import queue
import re
import sqlite3
import threading
import time
from typing import Any
from fastapi import Request


PHASES = ("metadata", "active_content", "archived_content")
LABELS = {"title": "标题", "id": "会话 ID", "directory": "目录", "preview": "最近提问",
          "user": "用户提问", "assistant": "助手回复", "tool": "工具内容"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _text(value):
    # Rich content contributes text blocks only, not attachment/internal JSON.
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_text(v.get("text", "")) for v in value
                         if isinstance(v, dict) and v.get("type") in {"text", "input_text", "output_text"})
    return ""


def _reply(value):
    text = _text(value)
    # Match the chat renderer: think tags inside code are literal examples.
    pieces = re.split(r"(```[\s\S]*?```|`[^`]*`)", text)
    return "".join(part if i % 2 else re.sub(r"</think>", "", re.sub(
        r"<think>[\s\S]*?(?:</think>|$)", "", part, flags=re.I), flags=re.I)
        for i, part in enumerate(pieces))


def _ranges(text, terms):
    # casefold may expand characters. Keep offsets in original Unicode codepoints.
    folded, owners = "", []
    for i, ch in enumerate(text):
        part = ch.casefold()
        folded += part
        owners.extend([i] * len(part))
    spans = []
    for term in terms:
        start = 0
        while term and (pos := folded.find(term, start)) >= 0:
            spans.append([owners[pos], owners[pos + len(term) - 1] + 1])
            start = pos + len(term)
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def _snippet(content, terms, size=220):
    # Locate in a bounded prefix only after finding the first match in folded text.
    folded = content.casefold()
    positions = [folded.find(t) for t in terms if t in folded]
    anchor = min(positions, default=0)
    if len(folded) != len(content):
        position = 0
        for index, ch in enumerate(content):
            if position >= anchor:
                anchor = index
                break
            position += len(ch.casefold())
    start = max(0, anchor - 60)
    sample = ("…" if start else "") + content[start:start + size]
    if start + size < len(content):
        sample += "…"
    return sample, _ranges(sample, terms), anchor


class SearchError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class SessionSearch:
    def __init__(self, manager, *, use_fts=True):
        self.manager = manager
        self.path = Path(manager.sessions_dir) / ".session-search.sqlite3"
        self.lock = threading.RLock()
        self.db = None
        self.use_fts = use_fts
        self.fts = False
        self.pending = set()
        self.work = queue.Queue()
        self.worker = None
        self.revision = 0
        self.maintenance_stop = threading.Event()

    def _connect(self):
        if self.db is not None:
            return self.db
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                db = sqlite3.connect(self.path, check_same_thread=False, timeout=2)
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE IF NOT EXISTS sources(sid TEXT PRIMARY KEY, version TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, sid TEXT, ref TEXT, role TEXT, "
                           "content TEXT, folded TEXT, ui_index INTEGER, turn_index INTEGER, version TEXT)")
                db.execute("CREATE INDEX IF NOT EXISTS docs_sid ON docs(sid)")
                if self.use_fts:
                    try:
                        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(folded, tokenize='trigram')")
                        self.fts = True
                    except sqlite3.OperationalError:
                        self.fts = False
                self.db = db
                return db
            except sqlite3.DatabaseError:
                if 'db' in locals():
                    db.close()
                if attempt:
                    raise
                # Only this disposable cache is removed, never history files.
                for suffix in ("", "-wal", "-shm"):
                    Path(str(self.path) + suffix).unlink(missing_ok=True)

    def close(self):
        self.maintenance_stop.set()
        self.work.put(None)
        if self.worker is not None:
            self.worker.join(timeout=.5)
        with self.lock:
            if self.db:
                self.db.close()
                self.db = None

    def _session_dir(self, sid):
        return Path(self.manager._resolve_session_path(sid))

    def _signature(self, sid):
        root = self._session_dir(sid)
        paths = [root / n for n in ("events.jsonl", "ui_events.json", "metadata.json")]
        paths += sorted((root / "history_context_archives").glob("*.jsonl"))
        stamps = []
        for path in paths:
            try:
                s = path.stat()
                stamps.append((str(path), s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns))
            except FileNotFoundError:
                stamps.append((str(path), None))
        return _digest([3, stamps])

    def sessions(self):
        return [s for s in self.manager.list_sessions(include_archived=True)
                if s.get("id") and not s.get("draft") and not s.get("is_subagent")]

    def invalidate(self, sid, *_args):
        with self.lock:
            self.revision += 1
            if self.worker is None or not self.worker.is_alive() or self.maintenance_stop.is_set() or not sid or sid in self.pending:
                return
            self.pending.add(sid)
            self.work.put(sid)

    def warm(self, sessions):
        with self.lock:
            if self.worker is not None and self.worker.is_alive():
                return
            if self.maintenance_stop.is_set():
                self.maintenance_stop.clear()
                self.work = queue.Queue()
                self.pending.clear()
            self.worker = threading.Thread(target=self._maintain, daemon=True, name="session-search-index")
            self.worker.start()
        for s in sessions:
            with self.lock:
                sid = s["id"]
                if sid not in self.pending:
                    self.pending.add(sid)
                    self.work.put(sid)

    def _maintain(self):
        next_audit = time.monotonic() + 30
        while not self.maintenance_stop.is_set():
            try:
                sid = self.work.get(timeout=1)
            except queue.Empty:
                if time.monotonic() >= next_audit:
                    try:
                        self._audit_sources()
                    except Exception:
                        pass
                    next_audit = time.monotonic() + 30
                continue
            if sid is None:
                self.work.task_done()
                return
            with self.lock:
                self.pending.discard(sid)
            try:
                summary = self.manager.get_session_summary(sid)
                if summary and not summary.get("draft"):
                    self.ensure(sid, self.maintenance_stop)
                else:
                    with self.lock:
                        self._remove(sid)
                        self._connect().commit()
            except Exception:
                # A query retries from the source and reports failures to the user.
                pass
            finally:
                self.work.task_done()

    def _audit_sources(self):
        # Covers history edits/imports from non-WebUI callers without making
        # every fact append depend on search. Unchanged files are never parsed.
        sessions = self.sessions()
        with self.lock:
            known = dict(self._connect().execute("SELECT sid,version FROM sources"))
        for session in sessions:
            if self.maintenance_stop.is_set():
                return
            sid = session["id"]
            if known.pop(sid, None) != self._signature(sid):
                self.invalidate(sid)
        for sid in known:
            self.invalidate(sid)

    def _remove(self, sid):
        db = self._connect()
        if self.fts:
            db.execute("DELETE FROM docs_fts WHERE rowid IN (SELECT id FROM docs WHERE sid=?)", (sid,))
        db.execute("DELETE FROM docs WHERE sid=?", (sid,))
        db.execute("DELETE FROM sources WHERE sid=?", (sid,))

    @staticmethod
    def _ui_text(row):
        typ = row.get("type")
        if typ in {"user", "user_steer"}:
            return "user", _text(row.get("content"))
        if typ == "final":
            return "assistant", _reply(row.get("content"))
        if typ in {"tool_call", "tool_result", "tool_finished", "tool_started"}:
            # Explicit fields only: no reasoning/system/internal JSON dumps.
            parts = [str(row.get("tool") or row.get("name") or "")]
            for key in ("args", "arguments", "arguments_raw", "result", "output", "stdout", "stderr", "content"):
                v = row.get(key)
                if isinstance(v, (dict, list)) and key in {"args", "arguments"}:
                    parts.append(json.dumps(v, ensure_ascii=False))
                else:
                    parts.append(_text(v))
            return "tool", "\n".join(p for p in parts if p)
        return "", ""

    def _documents(self, sid, stop):
        root = self._session_dir(sid)
        obsolete = set()
        primary_v2 = getattr(self.manager, "_runtime_v2_primary", lambda: True)()
        executions = []
        if (root / "events.jsonl").exists():
            from runtime_v2.ui_projection import RuntimeUiProjection
            projection = RuntimeUiProjection(self.manager.sessions_dir, path_resolver=self.manager._resolve_session_path)
            rows = projection.read_ui_events(sid) if primary_v2 else self.manager.get_ui_events_for_display(sid)
            from runtime_v2.execution_journal import ExecutionJournal
            executions = ExecutionJournal(self.manager.sessions_dir, self.manager._resolve_session_path).read(sid)["execution_records"]
            history = []
            # Only explicit destructive edits suppress archive copies. A compacted
            # snapshot may drop UI rows while their compressed originals remain valid.
            for event in projection.event_log.iter_events(sid):
                if stop.is_set():
                    return
                if event.type == "runtime_snapshot_compacted":
                    history = list((event.payload or {}).get("ui_events") or [])
                    continue
                if event.type in {"message_deleted", "message_rewritten", "visible_range_changed", "legacy_truncate_observed"}:
                    history = projection._normalize_before_history_op(history)
                    before = {(r.get("runtime_seq"), *self._ui_text(r)) for r in history}
                    if event.type in {"message_deleted", "message_rewritten"}:
                        history = projection._apply_history_op_to_projected_events(history, event)
                    elif event.type == "visible_range_changed":
                        history = projection._apply_visible_range_to_projected_events(history, event.payload or {})
                    else:
                        payload = event.payload or {}
                        size = payload.get("new_event_count", payload.get("before_index"))
                        if size is not None:
                            history = history[:max(0, int(size))]
                    after = {(r.get("runtime_seq"), *self._ui_text(r)) for r in history}
                    obsolete.update((role, text) for seq, role, text in before - after if role and text)
                    continue
                raw = projection._event_to_ui(sid, event)
                if raw:
                    history.append(raw)
        else:
            rows = self.manager.get_ui_events_for_display(sid)
        seen = set()
        turn = None
        for index, row in enumerate(rows):
            if stop.is_set():
                return
            role, content = self._ui_text(row)
            if role == "user":
                turn = index
            if not role or not content.strip():
                continue
            seen.add((role, content))
            seq = row.get("runtime_seq")
            ref = f"history:{sid}:event:{seq}" if seq else f"ui:{sid}:{index}"
            yield ref, role, content, index, turn
        turns = {str(row.get("runtime_seq")): index for index, row in enumerate(rows) if row.get("type") == "user"}
        for record in executions:
            if stop.is_set():
                return
            kind = record.get("kind")
            if kind not in {"tool", "llm_response"}:
                continue
            role, content = self._ui_text({**record, "type": "tool_call" if kind == "tool" else "final"})
            if content.strip() and (role, content) not in seen:
                seen.add((role, content))
                turn = turns.get(str(record.get("turn_id")))
                yield f"execution:{sid}:{record['execution_id']}", role, content, turn, turn
        for path in sorted((root / "history_context_archives").glob("*.jsonl"), reverse=True):
            with path.open(encoding="utf-8") as source:
                for line in source:
                    if stop.is_set():
                        return
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    role = row.get("role")
                    if row.get("kind") != "message" or role not in {"user", "assistant", "tool"}:
                        continue
                    content = _reply(row.get("content")) if role == "assistant" else _text(row.get("content"))
                    item_id = str(row.get("item_id") or "")
                    if item_id and role == "assistant" and (role, content) not in obsolete:
                        for i, call in enumerate(row.get("tool_calls") or []):
                            if not isinstance(call, dict):
                                continue
                            _, tool_text = self._ui_text({**call, "type": "tool_call"})
                            if tool_text.strip() and ("tool", tool_text) not in seen:
                                seen.add(("tool", tool_text))
                                yield f"history:{sid}:archive:{path.stem}:item:{item_id}:tool:{i}", "tool", tool_text, None, None
                    if not content.strip() or (role, content) in seen or (role, content) in obsolete:
                        continue
                    seen.add((role, content))
                    if item_id:
                        yield f"history:{sid}:archive:{path.stem}:item:{item_id}", role, content, None, None

    def ensure(self, sid, stop):
        version = self._signature(sid)
        with self.lock:
            saved = self._connect().execute("SELECT version FROM sources WHERE sid=?", (sid,)).fetchone()
            if saved and saved[0] == version:
                return version
        docs = list(self._documents(sid, stop))
        if stop.is_set():
            return None
        if version != self._signature(sid):
            raise SearchError("会话内容已变化，请重试该阶段", 409)
        with self.lock, self._connect():
            self._remove(sid)
            db = self._connect()
            for ref, role, content, index, turn in docs:
                result = db.execute("INSERT INTO docs(sid,ref,role,content,folded,ui_index,turn_index,version) "
                                    "VALUES(?,?,?,?,?,?,?,?)",
                                    (sid, ref, role, content, content.casefold(), index, turn, version))
                if self.fts:
                    db.execute("INSERT INTO docs_fts(rowid,folded) VALUES(?,?)", (result.lastrowid, content.casefold()))
            db.execute("INSERT INTO sources VALUES(?,?)", (sid, version))
        return version

    def hits(self, sid, terms, tools, stop, offset=0, limit=3):
        version = self.ensure(sid, stop)
        if not version or stop.is_set():
            return [], False
        sql = "SELECT ref,role,content,version FROM docs WHERE sid=?"
        args: list[Any] = [sid]
        if not tools:
            sql += " AND role IN ('user','assistant')"
        if self.fts and (longest := max(terms, key=len)) and len(longest) >= 3:
            sql += " AND id IN (SELECT rowid FROM docs_fts WHERE docs_fts MATCH ? AND rowid BETWEEN "
            sql += "(SELECT min(id) FROM docs WHERE sid=?) AND (SELECT max(id) FROM docs WHERE sid=?))"
            args.extend(['"' + longest.replace('"', '""') + '"', sid, sid])
        for term in terms:
            sql += " AND instr(folded,?)>0"
            args.append(term)
        sql += " ORDER BY id LIMIT ? OFFSET ?"
        args.extend([limit + 1, offset])
        with self.lock:
            db = self._connect()
            db.set_progress_handler(lambda: int(stop.is_set()), 1000)
            try:
                found = db.execute(sql, args).fetchall()
            finally:
                db.set_progress_handler(None, 0)
        result = []
        for ref, role, content, version in found[:limit]:
            snippet, ranges, offset = _snippet(content, terms)
            result.append(dict(ref=ref, source=role, label=LABELS[role], snippet=snippet,
                               highlights=ranges, source_version=version, match_offset=offset))
        return result, len(found) > limit

    @staticmethod
    def metadata(s, terms, aliases):
        path = str(s.get("work_dir") or "").replace("\\", "/").rstrip("/").lower()
        key = "workdir:__default__" if s.get("work_dir_is_default") or not path else "workdir:" + path
        fields = [("title", str(s.get("name") or "")), ("id", str(s["id"])),
                  ("directory", " ".join(str(v or "") for v in
                   (s.get("work_dir"), s.get("work_dir_label"), aliases.get(key)))),
                  ("preview", str(s.get("last_user_preview") or ""))]
        hay = " ".join(text for _, text in fields).casefold()
        if not all(term in hay for term in terms):
            return None
        source, text = next((k, v) for k, v in fields if any(t in v.casefold() for t in terms))
        title = fields[0][1].casefold()
        query = " ".join(terms)
        rank = 0 if title == query else 1 if title.startswith(query) else 2 if all(t in title for t in terms) else 3 if source != "preview" else 4
        snippet, ranges, _ = _snippet(text, terms)
        return rank, dict(source=source, label=LABELS[source], snippet=snippet, highlights=ranges)

    def prepare(self, payload):
        if not isinstance(payload, dict):
            raise SearchError("搜索请求必须为对象")
        q = payload.get("q", "")
        if not isinstance(q, str) or not q.strip() or len(q) > 120:
            raise SearchError("请输入 1–120 个字符的搜索词")
        phase = payload.get("phase", "all")
        scope = payload.get("scope", "all")
        if not isinstance(phase, str) or not isinstance(scope, str) or phase not in (*PHASES, "all") or scope not in {"all", "active", "archived"}:
            raise SearchError("无效的搜索范围或阶段")
        if not isinstance(payload.get("include_tools", False), bool):
            raise SearchError("无效的工具搜索选项")
        aliases = payload.get("workdir_aliases") or {}
        if not isinstance(aliases, dict) or len(aliases) > 2000 or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 200 for k, v in aliases.items()):
            raise SearchError("无效的工作区名称映射")
        sessions = self.sessions()
        def activity(s):
            try:
                return datetime.fromisoformat(str(s.get("last_activity_at") or s.get("updated_at") or s.get("created_at") or "").replace("Z", "+00:00")).timestamp()
            except (ValueError, OSError, OverflowError):
                return 0
        sessions.sort(key=lambda s: (activity(s), s["id"]), reverse=True)
        if scope != "all":
            sessions = [s for s in sessions if bool(s.get("archived")) == (scope == "archived")]
        terms = list(dict.fromkeys(q.casefold().split()))
        revision = _digest([(s["id"], s.get("name"), s.get("archived"), s.get("work_dir"),
                             s.get("last_activity_at"), s.get("updated_at"), s.get("last_user_preview")) for s in sessions])
        fingerprint = _digest([terms, scope, bool(payload.get("include_tools")), aliases, revision, self.revision])
        sid = payload.get("session_id")
        if sid:
            sessions = [s for s in sessions if s["id"] == sid]
            if not sessions:
                raise SearchError("会话不存在", 404)
        cursor = None
        if payload.get("cursor"):
            try:
                cursor = json.loads(base64.urlsafe_b64decode(str(payload["cursor"]).encode()))
                if cursor["key"] != fingerprint or cursor["phase"] != phase:
                    raise ValueError()
                if cursor.get("sid") != sid:
                    raise ValueError()
                if not isinstance(cursor["offset"], int) or cursor["offset"] < 0:
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise SearchError("搜索结果已变化，请重新搜索", 409)
        return dict(sessions=sessions, terms=terms, phase=phase, scope=scope, aliases=aliases,
                    tools=bool(payload.get("include_tools")), sid=sid, key=fingerprint, cursor=cursor)

    @staticmethod
    def cursor(ctx, phase, offset, version=None, sid=None):
        return base64.urlsafe_b64encode(json.dumps(dict(key=ctx["key"], phase=phase, offset=offset,
                                                      version=version, sid=sid or ctx["sid"])).encode()).decode()

    def search(self, ctx, stop):
        sessions = ctx["sessions"]
        phases = PHASES if ctx["phase"] == "all" else (ctx["phase"],)
        for phase in phases:
            if stop.is_set():
                return
            if phase == "active_content" and ctx["scope"] == "archived" or phase == "archived_content" and ctx["scope"] == "active":
                yield "phase_done", dict(phase=phase, cursor=None, scanned=0, total=0)
                continue
            candidates = sessions if phase == "metadata" else [s for s in sessions if bool(s.get("archived")) == (phase == "archived_content")]
            meta = {}
            if phase == "metadata":
                for s in candidates:
                    match = self.metadata(s, ctx["terms"], ctx["aliases"])
                    if match:
                        meta[s["id"]] = match
                candidates = sorted([s for s in candidates if s["id"] in meta], key=lambda s: meta[s["id"]][0])
            offset = ctx["cursor"]["offset"] if ctx["cursor"] else 0
            yield "progress", dict(phase=phase, scanned=0, total=len(candidates))
            count = 0
            failures = []
            try:
                candidate_offset = 0 if ctx["sid"] else offset
                for pos, s in enumerate(candidates[candidate_offset:], candidate_offset):
                    if stop.is_set():
                        return
                    if phase == "metadata":
                        hits, more = [meta[s["id"]][1]], False
                    else:
                        hit_offset = offset if ctx["sid"] else 0
                        if ctx["sid"]:
                            expected = (ctx["cursor"] or {}).get("version")
                            if expected and expected != self._signature(s["id"]):
                                raise SearchError("会话内容已变化，请重新搜索", 409)
                        try:
                            hits, more = self.hits(s["id"], ctx["terms"], ctx["tools"], stop, offset=hit_offset)
                        except Exception as exc:
                            if ctx["sid"]:
                                raise
                            failures.append(exc)
                            continue
                    if hits:
                        # The 21st match is a lookahead, not a consumed result.
                        if count == 20 and not ctx["sid"]:
                            yield "phase_done", dict(phase=phase, cursor=self.cursor(ctx, phase, pos), scanned=pos, total=len(candidates))
                            break
                        hit_cursor = self.cursor(ctx, phase, (offset if ctx["sid"] else 0) + len(hits), hits[0].get("source_version"), s["id"]) if more else None
                        yield "upsert", dict(phase=phase, session=s, hits=hits, hit_cursor=hit_cursor)
                        count += 1
                    if (pos + 1) % 10 == 0:
                        yield "progress", dict(phase=phase, scanned=pos + 1, total=len(candidates))
                else:
                    if not failures:
                        yield "phase_done", dict(phase=phase, cursor=None, scanned=len(candidates), total=len(candidates))
                if failures:
                    yield "error", dict(phase=phase, message=f"{len(failures)} 个会话尚未完成检索（内容变化或暂不可读），请重试", status=409)
            except Exception as exc:
                if stop.is_set():
                    return
                yield "error", dict(phase=phase, message=str(exc) if isinstance(exc, SearchError) else "该阶段检索失败，请重试", status=getattr(exc, "status", 500))
        if not stop.is_set():
            yield "done", {}

    def resolve(self, sid, ref, version, offset=0):
        if not any(s["id"] == sid for s in self.sessions()):
            raise SearchError("会话不存在", 404)
        stop = threading.Event()
        current = self.ensure(sid, stop)
        if not version or version != current:
            raise SearchError("会话内容已变化，请重新搜索", 409)
        with self.lock:
            row = self._connect().execute("SELECT content,ui_index,turn_index,role FROM docs WHERE sid=? AND ref=?", (sid, ref)).fetchone()
        if not row:
            raise SearchError("命中内容已失效，请重新搜索", 409)
        start = max(0, min(max(0, offset), len(row[0])) - 500)
        return dict(ref=ref, content=row[0][start:start + 50000], has_more=start + 50000 < len(row[0]), content_offset=start,
                    ui_index=row[1], turn_index=row[2], source=row[3], archive=row[1] is None,
                    execution_id=ref.split(":", 2)[2] if ref.startswith("execution:") else None)


def install_session_search(app, manager, add_event_listener=None):
    """Register before the parameterized /sessions/{session_id} routes."""
    import asyncio
    from fastapi.responses import JSONResponse, StreamingResponse

    service = SessionSearch(manager)
    slots = asyncio.Semaphore(2)
    app.router.add_event_handler("shutdown", service.close)
    if callable(getattr(manager, "add_session_state_listener", None)):
        manager.add_session_state_listener(service.invalidate)
    if add_event_listener:
        add_event_listener(lambda sid, ev: service.invalidate(sid) if ev.get("type") in
                           {"user", "final", "run_finished", "run_interrupted", "run_failed", "history_invalidated"} else None)

    @app.post("/sessions/search")
    async def search_sessions(request: Request):
        try:
            payload = await request.json()
            ctx = await asyncio.to_thread(service.prepare, payload)
        except (SearchError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=getattr(exc, "status", 400))
        stop = threading.Event()
        events = queue.Queue(maxsize=16)

        def produce():
            try:
                for event in service.search(ctx, stop):
                    while not stop.is_set():
                        try:
                            events.put(event, timeout=.1)
                            break
                        except queue.Full:
                            pass
                    if stop.is_set():
                        return
            finally:
                while not stop.is_set():
                    try:
                        events.put(None, timeout=.1)
                        break
                    except queue.Full:
                        pass

        async def stream_content():
            producer = asyncio.create_task(asyncio.to_thread(produce))
            try:
                while not stop.is_set():
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.to_thread(events.get, True, .25)
                    except queue.Empty:
                        continue
                    if event is None:
                        break
                    name, data = event
                    yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            finally:
                stop.set()
                # Worker checks stop between documents, batches and SQLite operations.
                producer.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
                # Warmup must not invalidate cursors issued by this query.
                service.warm(ctx["sessions"])

        async def stream():
            async with slots:
                async for frame in stream_content():
                    yield frame

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.get("/sessions/{session_id}/search-hit")
    async def resolve_search_hit(session_id: str, ref: str, source_version: str, offset: int = 0):
        try:
            return await asyncio.to_thread(service.resolve, session_id, ref, source_version, offset)
        except SearchError as exc:
            return JSONResponse({"error": str(exc)}, status_code=exc.status)

    return service
