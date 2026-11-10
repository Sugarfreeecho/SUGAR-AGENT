"""Tool calls that keep running after an interrupt steer restarted the turn.

An ``interrupt`` steer used to cancel whatever tool was in flight so the new
user message could start a fresh model request.  Tools that already started
have real side effects, so cancelling them is both lossy and misleading.  This
module gives such a call an isolated execution scope, keeps the task alive
after the foreground run moved on, and records its real result for the next
model request.

Isolation rules (user decision):
* only calls that already started are handed over;
* the detached call keeps its own state/emit view, so it can never touch the
  new run's history, approvals or stream;
* it finishes on its own, without interaction, and reports through one durable
  ``tool_call`` row plus a pending note claimed at the next round entry.
"""
from __future__ import annotations

import copy
import inspect
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

RESULTS_FILENAME = "background_tool_results.json"
NOTE_RESULT_LIMIT = 8000
_MAX_PENDING_ROWS = 20

_lock = threading.RLock()
_running: Dict[tuple, Dict[str, Any]] = {}
_committer: Optional[Callable[[str, Dict[str, Any]], Any]] = None


def configure_committer(committer: Optional[Callable[[str, Dict[str, Any]], Any]]) -> None:
    """Install the durable event writer (tests may replace the real one)."""
    global _committer
    _committer = committer


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class _IsolatedState(dict):
    """Forward to the live run state until the call is detached.

    After ``detach()`` every read/write goes to a snapshot, so a background
    tool cannot mutate the model history, approval flags or change-review
    buffers of the run that replaced it.  Subclassing ``dict`` keeps
    ``isinstance(state, dict)`` checks working for downstream tool code.
    """

    def __init__(self, live: Dict[str, Any]):
        super().__init__()
        self._live = live
        self._scratch: Optional[Dict[str, Any]] = None

    def _view(self) -> Dict[str, Any]:
        return self._scratch if self._scratch is not None else self._live

    def detach(self) -> None:
        if self._scratch is not None:
            return
        scratch = dict(self._live)
        for key in ("stream_events", "llm_history", "work_messages", "dialogue",
                    "chat_history", "tool_events"):
            value = scratch.get(key)
            if isinstance(value, list):
                scratch[key] = list(value)
        for key in [key for key in scratch if str(key).startswith("_change_review")]:
            try:
                scratch[key] = copy.deepcopy(scratch[key])
            except Exception:
                scratch.pop(key, None)
        # Human interaction and pause flags belong to the foreground run.
        for key in ("_pending_human_request", "_hook_pause_requested",
                    "_workflow_pause_requested", "_interaction_request",
                    # The successor run owns the process fence; keeping this
                    # reference would make the detached tool look stale (and
                    # kill its own shell) once a new control is registered.
                    "_steer_control"):
            scratch.pop(key, None)
        scratch["_background_tool"] = True
        self._scratch = scratch

    def __getitem__(self, key):
        return self._view()[key]

    def __setitem__(self, key, value):
        self._view()[key] = value

    def __delitem__(self, key):
        del self._view()[key]

    def __contains__(self, key):
        return key in self._view()

    def __iter__(self):
        return iter(self._view())

    def __len__(self):
        return len(self._view())

    def get(self, key, default=None):
        return self._view().get(key, default)

    def setdefault(self, key, default=None):
        return self._view().setdefault(key, default)

    def pop(self, key, *args):
        return self._view().pop(key, *args)

    def popitem(self):
        return self._view().popitem()

    def update(self, *args, **kwargs):
        self._view().update(*args, **kwargs)

    def clear(self):
        self._view().clear()

    def keys(self):
        return self._view().keys()

    def values(self):
        return self._view().values()

    def items(self):
        return self._view().items()

    def copy(self):
        return dict(self._view())


class _IsolatedEmit:
    """Stop forwarding UI events once the call left the foreground run."""

    def __init__(self, live: Callable[[Dict[str, Any]], Any]):
        self._live = live
        self._detached = False

    def detach(self) -> None:
        self._detached = True

    async def __call__(self, event):
        if self._detached:
            return None
        result = self._live(event)
        if inspect.isawaitable(result):
            return await result
        return result

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_live"), name)


class ExecutionScope:
    """Per-call isolation boundary. Cheap until ``detach()`` is called."""

    def __init__(self, state: Dict[str, Any], emit: Optional[Callable], *,
                 tool_call: Dict[str, Any], react_iter: int = 0,
                 stream_seq: Optional[int] = None):
        self.marker: Dict[str, Any] = {
            "eligible": True, "executing": False, "detached": False,
        }
        self.state = _IsolatedState(state)
        self.emit = _IsolatedEmit(emit) if emit is not None else None
        self.tool_call = dict(tool_call or {})
        self.react_iter = int(react_iter or 0)
        self.stream_seq = stream_seq

    @property
    def detached(self) -> bool:
        return bool(self.marker.get("detached"))

    def detach(self) -> bool:
        if self.marker.get("detached"):
            return False
        self.marker["detached"] = True
        self.state.detach()
        if self.emit is not None:
            self.emit.detach()
        return True


def execution_scope(state: Dict[str, Any], emit: Optional[Callable], *,
                    tool_call: Dict[str, Any], react_iter: int = 0,
                    stream_seq: Optional[int] = None) -> ExecutionScope:
    return ExecutionScope(state, emit, tool_call=tool_call, react_iter=react_iter,
                          stream_seq=stream_seq)


def register(
    *,
    session_id: str,
    run_id: str,
    session_dir: Any,
    scope: ExecutionScope,
    task: Any,
    build_event: Optional[Callable[[Dict[str, Any], int], Dict[str, Any]]] = None,
    anchor: Optional[Dict[str, Any]] = None,
) -> bool:
    """Own a detached tool task and record its real result when it finishes."""
    sid = str(session_id or "").strip()
    tool_call = scope.tool_call or {}
    tool_id = str(tool_call.get("id") or "").strip()
    if not sid or not tool_id or task is None:
        return False
    key = (sid, tool_id)
    with _lock:
        if key in _running:
            return False
        _running[key] = {
            "session_id": sid,
            "run_id": str(run_id or ""),
            "session_dir": str(session_dir or ""),
            "tool_call": tool_call,
            "tool": str(tool_call.get("name") or "tool"),
            "args": tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {},
            "tool_call_id": tool_id,
            "react_iter": int(scope.react_iter or tool_call.get("index") or 0) or 0,
            "stream_seq": scope.stream_seq,
            "status": "running",
            "started_at": _now_iso(),
            "finished_at": "",
            "build_event": build_event,
            "anchor": dict(anchor or {}),
        }
    try:
        task.add_done_callback(lambda finished: _on_done(key, finished))
    except Exception:
        logger.debug("background tool callback attach failed", exc_info=True)
        with _lock:
            _running.pop(key, None)
        return False
    logger.info("tool_moved_to_background session=%s run=%s tool=%s call=%s",
                sid, run_id, tool_call.get("name"), tool_id)
    return True


def _on_done(key: tuple, task: Any) -> None:
    entry = _running.get(key)
    if entry is None:
        return
    error: Optional[BaseException] = None
    result: Any = None
    if task.cancelled():
        _drop(key, "cancelled")
        return
    try:
        error = task.exception()
    except Exception as exc:  # pragma: no cover - defensive
        error = exc
    if error is not None:
        if type(error).__name__ == "_SteerRestartRequested":
            _drop(key, "steer_before_start")
            return
        logger.warning("background tool failed session=%s tool=%s: %s",
                       key[0], entry.get("tool"), error)
    else:
        result = task.result()
    loop = None
    try:
        loop = task.get_loop()
    except Exception:
        loop = None
    coro = _commit(key, entry, result, error)
    try:
        if loop is not None:
            loop.create_task(coro)
        else:  # pragma: no cover - defensive
            coro.close()
    except Exception:
        logger.warning("background tool result could not be scheduled", exc_info=True)
        coro.close()


def _drop(key: tuple, reason: str) -> None:
    with _lock:
        entry = _running.pop(key, None)
    if entry is not None:
        logger.info("background tool dropped session=%s tool=%s reason=%s",
                    key[0], entry.get("tool"), reason)


def _minimal_result(entry: Dict[str, Any], *, text: str, failed: bool) -> Dict[str, Any]:
    return {
        "type": "tool",
        "tool_name": entry.get("tool") or "tool",
        "tool_args": entry.get("args") or {},
        "tool_id": entry.get("tool_call_id") or "",
        "tool_call_index": (entry.get("tool_call") or {}).get("index"),
        "result": text,
        "tool_detail_llm": text,
        "tool_detail_ui": text,
        "tool_failed": failed,
        "execution_status": "failed" if failed else "completed",
        "tool_status": {"duration_ms": _duration_ms(entry), "ok": not failed},
        "execution_react_iter": entry.get("react_iter"),
    }


def _duration_ms(entry: Dict[str, Any]) -> int:
    try:
        started = datetime.fromisoformat(str(entry.get("started_at") or "").replace("Z", "+00:00"))
        return int(max(0.0, (datetime.now(timezone.utc) - started).total_seconds() * 1000))
    except Exception:
        return 0


async def _commit(key: tuple, entry: Dict[str, Any], result: Any,
                  error: Optional[BaseException]) -> None:
    failed = error is not None or bool(
        isinstance(result, dict) and result.get("tool_failed"))
    if isinstance(result, dict) and result.get("type") == "tool":
        payload = dict(result)
    elif error is not None:
        payload = _minimal_result(
            entry, text=f"后台工具执行失败：{error}", failed=True)
    else:
        text = result if isinstance(result, str) else json.dumps(
            result, ensure_ascii=False, default=str) if result is not None else ""
        payload = _minimal_result(entry, text=str(text), failed=False)
    payload["execution_status"] = "failed" if failed else "completed"
    payload.setdefault("execution_react_iter", entry.get("react_iter"))

    build_event = entry.get("build_event")
    event: Dict[str, Any]
    try:
        event = dict(build_event(payload, entry.get("react_iter") or 0)) if build_event else {}
    except Exception:
        event = {}
    event.setdefault("type", "tool_call")
    event["session_id"] = entry["session_id"]
    event["run_id"] = entry.get("run_id") or ""
    event["tool_call_id"] = entry.get("tool_call_id") or ""
    event["execution_status"] = "failed" if failed else "completed"
    event["background_execution"] = True
    for name in ("execution_id", "process_group_id", "turn_id"):
        value = (entry.get("anchor") or {}).get(name)
        if value:
            event.setdefault(name, value)
    if entry.get("stream_seq") is not None:
        event.setdefault("stream_seq", entry["stream_seq"])

    try:
        if _committer is not None:
            await _committer(entry["session_id"], dict(event))
        else:
            from agent_harness import session_manager
            from agent_subagent_events import persist_execution_event
            from session_event_bus import publish_session_event

            committed = await persist_execution_event(
                session_manager, entry["session_id"], dict(event), commit_ui=True)
            public = {name: value for name, value in committed.items()
                      if name != "_runtime_v2_committed"}
            await publish_session_event(entry["session_id"], public)
    except Exception:
        logger.warning("background tool result could not be committed session=%s tool=%s",
                       entry["session_id"], entry.get("tool"), exc_info=True)

    result_text = event.get("result") or payload.get("tool_detail_ui") or payload.get("result") or ""
    if isinstance(result_text, list):
        from agent_openai import normalize_content_text
        result_text = normalize_content_text(result_text)
    _write_pending_note(entry.get("session_dir"), {
        "id": entry.get("tool_call_id") or "",
        "tool": entry.get("tool") or "tool",
        "args": entry.get("args") or {},
        "result": str(result_text or ""),
        "status": "failed" if failed else "completed",
        "duration_ms": _duration_ms(entry),
        "run_id": entry.get("run_id") or "",
        "react_iter": entry.get("react_iter") or 0,
        "finished_at": _now_iso(),
    })
    with _lock:
        current = _running.get(key)
        if current is not None:
            current["status"] = "finished"
            current["finished_at"] = _now_iso()


def is_backgrounded(session_id: str, tool_call_id: str) -> bool:
    if not session_id or not tool_call_id:
        return False
    with _lock:
        return (str(session_id), str(tool_call_id)) in _running


def background_ids(session_id: str) -> set:
    sid = str(session_id or "").strip()
    if not sid:
        return set()
    with _lock:
        return {key[1] for key in _running if key[0] == sid}


def _results_path(session_dir: Any) -> Optional[Path]:
    if not session_dir:
        return None
    return Path(session_dir) / RESULTS_FILENAME


def _read_rows(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception:
        logger.warning("background tool notes unreadable: %s", path, exc_info=True)
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(rows[-_MAX_PENDING_ROWS:], ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)


def _write_pending_note(session_dir: Any, row: Dict[str, Any]) -> None:
    path = _results_path(session_dir)
    if path is None:
        return
    with _lock:
        try:
            rows = _read_rows(path)
            rows.append(row)
            _write_rows(path, rows)
        except Exception:
            logger.warning("background tool note could not be stored: %s", path,
                           exc_info=True)


def claim_notes(session_id: str, session_dir: Any) -> List[Dict[str, Any]]:
    """Take pending background results once, before the next model request."""
    path = _results_path(session_dir)
    if path is None:
        return []
    sid = str(session_id or "").strip()

    def drop_finished() -> None:
        # Running calls keep their entry: their completion still owns the
        # durable result and the next pending note.
        for key in [key for key in _running
                    if key[0] == sid and _running[key].get("status") == "finished"]:
            _running.pop(key, None)

    with _lock:
        rows = _read_rows(path)
        if not rows:
            drop_finished()
            return []
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            logger.warning("background tool notes could not be claimed: %s", path,
                           exc_info=True)
            return []
        drop_finished()
    return rows


def pending_exists(session_dir: Any) -> bool:
    """Cheap round-entry probe; avoids read+exception on the hot path."""
    path = _results_path(session_dir)
    try:
        return bool(path is not None and path.exists())
    except OSError:
        return False


def restore_notes(session_dir: Any, rows: List[Dict[str, Any]]) -> None:
    """Put claimed rows back when the model commit failed."""
    path = _results_path(session_dir)
    if path is None or not rows:
        return
    with _lock:
        try:
            _write_rows(path, [*_read_rows(path), *rows])
        except Exception:
            logger.warning("background tool notes could not be restored: %s", path,
                           exc_info=True)


def _brief_args(args: Any) -> str:
    if not isinstance(args, dict) or not args:
        return ""
    try:
        text = json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        text = str(args)
    return text if len(text) <= 300 else text[:300] + "…"


def note_lines(rows: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for row in rows:
        tool = str(row.get("tool") or "tool")
        status = "失败" if row.get("status") == "failed" else "已完成"
        result = str(row.get("result") or "").strip()
        if len(result) > NOTE_RESULT_LIMIT:
            result = result[:NOTE_RESULT_LIMIT] + "\n…（已截断，完整结果见工具记录）"
        header = f"- {tool}({_brief_args(row.get('args'))}) 后台执行{status}"
        lines.append(header + ("\n" + result if result else ""))
    return lines


def has_running(session_id: str) -> bool:
    sid = str(session_id or "").strip()
    if not sid:
        return False
    with _lock:
        return any(key[0] == sid and entry.get("status") == "running"
                   for key, entry in _running.items())


def clear_session(session_id: str) -> None:
    sid = str(session_id or "").strip()
    with _lock:
        for key in [key for key in _running if key[0] == sid]:
            _running.pop(key, None)


__all__ = [
    "ExecutionScope",
    "background_ids",
    "claim_notes",
    "clear_session",
    "configure_committer",
    "execution_scope",
    "has_running",
    "is_backgrounded",
    "note_lines",
    "pending_exists",
    "register",
    "restore_notes",
]
