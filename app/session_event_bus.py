from __future__ import annotations

import asyncio
import threading
from collections import defaultdict, deque
from typing import Any, AsyncGenerator, Deque, Dict, Set, Tuple


_subscribers: Dict[str, Set[Tuple[asyncio.Queue, asyncio.AbstractEventLoop]]] = defaultdict(set)
_recent_ephemeral: Dict[str, Deque[dict]] = defaultdict(lambda: deque(maxlen=400))
_live_delta_snapshots: Dict[str, Dict[Tuple[Any, ...], dict]] = defaultdict(dict)
_live_state_snapshots: Dict[str, Dict[Tuple[Any, ...], dict]] = defaultdict(dict)
_seq_by_session: Dict[str, int] = defaultdict(int)
_lock = threading.Lock()
_event_listeners: list = []

_SNAPSHOT_DELTA_FIELDS = {
    "llm_reasoning_delta": ("delta",),
    "llm_response_delta": ("delta",),
    "tool_call_delta": ("name_delta", "arguments_delta"),
    "tool_command_delta": ("delta", "command_delta"),
    "context_trim_delta": ("delta",),
    "context_summary_delta": ("delta",),
    "key_context_delta": ("delta",),
}

_LIVE_STATE_TYPES = {"tool_pending"}


def add_event_listener(listener) -> None:
    """Register a synchronous listener called for every published session event.

    Listeners receive ``(session_id, event_dict)`` and must be cheap; they run
    inside the publishing coroutine. Exceptions are swallowed so one faulty
    listener can never break the event bus.
    """

    with _lock:
        if listener not in _event_listeners:
            _event_listeners.append(listener)


def remove_event_listener(listener) -> None:
    with _lock:
        try:
            _event_listeners.remove(listener)
        except ValueError:
            pass


def _sid(session_id: str) -> str:
    return str(session_id or "").strip()


async def publish_session_event(session_id: str, event: Dict[str, Any]) -> None:
    sid = _sid(session_id)
    if not sid or not isinstance(event, dict):
        return
    with _lock:
        if not event.get("session_id"):
            event["session_id"] = sid
        _seq_by_session[sid] += 1
        event_bus_seq = _seq_by_session[sid]
        if event.get("seq") is not None and event.get("seq_scope") != "event_bus":
            event.setdefault("source_seq", event.get("seq"))
        event["event_bus_seq"] = event_bus_seq
        event["seq_scope"] = "event_bus"
        event["seq"] = event_bus_seq
        if event.get("ephemeral"):
            event_type = str(event.get("type") or "")
            if event_type in _SNAPSHOT_DELTA_FIELDS:
                # Delta events already have an accumulated reconnect snapshot.
                # Keeping every raw chunk in the bounded recent deque used to
                # evict the earlier tool_pending row during verbose tools.
                _clear_replayed_status_unlocked(sid)
                _accumulate_live_delta_unlocked(sid, event)
            elif event_type in _LIVE_STATE_TYPES:
                _clear_replayed_status_unlocked(sid)
                _store_live_state_unlocked(sid, event)
            else:
                if event_type == "status":
                    # A reconnect needs the current transient status, not every
                    # historical "Thinking..." heartbeat. Replaying all of
                    # them causes remove/append flicker in the frontend.
                    _clear_replayed_status_unlocked(sid)
                _recent_ephemeral[sid].append(dict(event))
        elif event.get("type") == "tool_call" and str(event.get("tool_call_id") or "").strip():
            _prune_recent_ephemeral_unlocked(
                sid,
                types={"tool_pending", "tool_call_delta", "tool_command_delta"},
                react_iter=event.get("react_iter"),
                tool_call_id=event.get("tool_call_id"),
            )
        elif event.get("type") in {"llm_reasoning", "llm_response"}:
            completed_type = (
                "llm_reasoning_delta"
                if event.get("type") == "llm_reasoning"
                else "llm_response_delta"
            )
            _prune_recent_ephemeral_unlocked(
                sid,
                types={completed_type},
                react_iter=event.get("react_iter"),
            )
        elif event.get("type") in {
            "context_trim_body",
            "context_summary_body",
            "key_context_body",
        }:
            completed_type = str(event.get("type") or "").replace("_body", "_delta")
            _prune_recent_ephemeral_unlocked(
                sid,
                types={completed_type},
                run_id=event.get("run_id") or event.get("runId"),
            )
        elif event.get("type") in {"run_finished", "run_interrupted", "run_failed"}:
            terminal_run_id = event.get("run_id") or event.get("runId")
            if str(terminal_run_id or "").strip():
                # A terminal boundary owns all transient UI state for that run.
                # Remove it before delivery so reconnect cannot resurrect an
                # abandoned tool call or partial compression row.
                _prune_recent_ephemeral_unlocked(
                    sid,
                    run_id=terminal_run_id,
                )
        subscribers = list(_subscribers.get(sid, ()))
    listeners = list(_event_listeners)
    for listener in listeners:
        try:
            listener(sid, event)
        except Exception:
            pass
    for q, loop in subscribers:
        _deliver_to_subscriber(loop, q, event)


def _deliver_to_subscriber(
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    event: dict | None,
) -> None:
    def put_nowait() -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    try:
        if loop.is_closed():
            return
        if current_loop is loop:
            put_nowait()
        else:
            loop.call_soon_threadsafe(put_nowait)
    except RuntimeError:
        pass


def _live_delta_key(event: Dict[str, Any]) -> Tuple[Any, ...] | None:
    event_type = str(event.get("type") or "")
    if event_type not in _SNAPSHOT_DELTA_FIELDS:
        return None
    if event_type == "tool_call_delta":
        identity = event.get("index") if event.get("index") is not None else event.get("tool_call_index")
    else:
        identity = event.get("tool_call_id") or event.get("id") or event.get("index") or event.get("tool_call_index") or ""
    return (
        event_type,
        event.get("run_id") or event.get("runId") or "",
        event.get("react_iter"),
        event.get("stream_seq"),
        identity,
    )


def _accumulate_live_delta_unlocked(sid: str, event: Dict[str, Any]) -> None:
    key = _live_delta_key(event)
    if key is None:
        return
    snapshot = _live_delta_snapshots[sid].get(key)
    if snapshot is None:
        snapshot = dict(event)
        snapshot["_delta_parts"] = {
            field: [] for field in _SNAPSHOT_DELTA_FIELDS[str(event.get("type") or "")]
        }
        _live_delta_snapshots[sid][key] = snapshot
    else:
        for field, value in event.items():
            if field != "_delta_parts" and value not in (None, ""):
                snapshot[field] = value
    parts = snapshot["_delta_parts"]
    for field in _SNAPSHOT_DELTA_FIELDS[str(event.get("type") or "")]:
        value = event.get(field)
        if value not in (None, ""):
            parts[field].append(str(value))


def _live_state_key(event: Dict[str, Any]) -> Tuple[Any, ...] | None:
    event_type = str(event.get("type") or "")
    if event_type not in _LIVE_STATE_TYPES:
        return None
    identity = (
        event.get("tool_call_id")
        or event.get("id")
        or event.get("tool_call_index")
        or event.get("index")
        or ""
    )
    return (
        event_type,
        event.get("run_id") or event.get("runId") or "",
        event.get("react_iter"),
        identity,
    )


def _store_live_state_unlocked(sid: str, event: Dict[str, Any]) -> None:
    key = _live_state_key(event)
    if key is not None:
        _live_state_snapshots[sid][key] = dict(event)


def _clear_replayed_status_unlocked(sid: str) -> None:
    bucket = _recent_ephemeral.get(sid)
    if not bucket:
        return
    kept = [ev for ev in bucket if str(ev.get("type") or "") != "status"]
    bucket.clear()
    bucket.extend(kept)


def _live_delta_replay_unlocked(sid: str) -> list[dict]:
    replay: list[dict] = []
    snapshots = list(_live_delta_snapshots.get(sid, {}).values())
    snapshots.sort(key=lambda row: int(row.get("event_bus_seq") or row.get("seq") or 0))
    for snapshot in snapshots:
        public = {key: value for key, value in snapshot.items() if key != "_delta_parts"}
        for field, parts in snapshot.get("_delta_parts", {}).items():
            public[field] = "".join(parts)
        public["replayed_snapshot"] = True
        replay.append(public)
    return replay


def _live_state_replay_unlocked(sid: str) -> list[dict]:
    return [dict(event) for event in _live_state_snapshots.get(sid, {}).values()]


def _prune_recent_ephemeral_unlocked(
    sid: str,
    *,
    types: set[str] | None = None,
    react_iter: Any = None,
    tool_call_id: Any = None,
    run_id: Any = None,
) -> None:
    bucket = _recent_ephemeral.get(sid)
    wanted_types = set(types or ())
    iter_filter = None
    try:
        if react_iter is not None:
            iter_filter = int(react_iter)
    except (TypeError, ValueError):
        iter_filter = None
    tool_filter = str(tool_call_id or "").strip()
    run_filter = str(run_id or "").strip()

    kept = []
    for ev in bucket or ():
        ev_type = str(ev.get("type") or "")
        if wanted_types and ev_type not in wanted_types:
            kept.append(ev)
            continue
        if run_filter:
            ev_run_id = str(ev.get("run_id") or ev.get("runId") or "").strip()
            if ev_run_id != run_filter:
                kept.append(ev)
                continue
        if iter_filter is not None:
            try:
                if int(ev.get("react_iter")) != iter_filter:
                    kept.append(ev)
                    continue
            except (TypeError, ValueError):
                kept.append(ev)
                continue
        if tool_filter:
            ev_tool_id = str(ev.get("tool_call_id") or ev.get("id") or "").strip()
            if ev_tool_id and ev_tool_id != tool_filter:
                kept.append(ev)
                continue
        continue

    if bucket is not None:
        bucket.clear()
        bucket.extend(kept)

    live_states = _live_state_snapshots.get(sid)
    if live_states:
        for key, ev in list(live_states.items()):
            ev_type = str(ev.get("type") or "")
            if wanted_types and ev_type not in wanted_types:
                continue
            if run_filter:
                ev_run_id = str(ev.get("run_id") or ev.get("runId") or "").strip()
                if ev_run_id != run_filter:
                    continue
            if iter_filter is not None:
                try:
                    if int(ev.get("react_iter")) != iter_filter:
                        continue
                except (TypeError, ValueError):
                    continue
            if tool_filter:
                ev_tool_id = str(ev.get("tool_call_id") or ev.get("id") or "").strip()
                if ev_tool_id and ev_tool_id != tool_filter:
                    continue
            live_states.pop(key, None)
        if not live_states:
            _live_state_snapshots.pop(sid, None)

    snapshots = _live_delta_snapshots.get(sid)
    if not snapshots:
        return
    for key, ev in list(snapshots.items()):
        ev_type = str(ev.get("type") or "")
        if wanted_types and ev_type not in wanted_types:
            continue
        if run_filter:
            ev_run_id = str(ev.get("run_id") or ev.get("runId") or "").strip()
            if ev_run_id != run_filter:
                continue
        if iter_filter is not None:
            try:
                if int(ev.get("react_iter")) != iter_filter:
                    continue
            except (TypeError, ValueError):
                continue
        if tool_filter:
            ev_tool_id = str(ev.get("tool_call_id") or ev.get("id") or "").strip()
            if ev_tool_id and ev_tool_id != tool_filter:
                continue
        snapshots.pop(key, None)
    if not snapshots:
        _live_delta_snapshots.pop(sid, None)


async def prune_session_ephemeral(
    session_id: str,
    *,
    types: set[str] | None = None,
    react_iter: Any = None,
    tool_call_id: Any = None,
    run_id: Any = None,
) -> None:
    sid = _sid(session_id)
    if not sid:
        return
    with _lock:
        _prune_recent_ephemeral_unlocked(
            sid,
            types=types,
            react_iter=react_iter,
            tool_call_id=tool_call_id,
            run_id=run_id,
        )


async def close_session_stream(session_id: str) -> None:
    sid = _sid(session_id)
    if not sid:
        return
    with _lock:
        subscribers = list(_subscribers.get(sid, ()))
        _recent_ephemeral.pop(sid, None)
        _live_delta_snapshots.pop(sid, None)
        _live_state_snapshots.pop(sid, None)
    for q, loop in subscribers:
        _deliver_to_subscriber(loop, q, None)


async def subscribe_session_events(
    session_id: str,
    replay_recent: bool = True,
) -> AsyncGenerator[dict | None, None]:
    sid = _sid(session_id)
    if not sid:
        return
    q: asyncio.Queue = asyncio.Queue(maxsize=1000)
    loop = asyncio.get_running_loop()
    subscriber = (q, loop)
    with _lock:
        if replay_recent:
            snapshot_types = set(_SNAPSHOT_DELTA_FIELDS)
            replay = _live_delta_replay_unlocked(sid)
            replay.extend(_live_state_replay_unlocked(sid))
            replay.extend(
                ev
                for ev in list(_recent_ephemeral.get(sid, ()))
                if str(ev.get("type") or "") not in snapshot_types | _LIVE_STATE_TYPES
            )
            replay.sort(key=lambda row: int(row.get("event_bus_seq") or row.get("seq") or 0))
            for ev in replay:
                q.put_nowait(ev)
        _subscribers[sid].add(subscriber)
    try:
        while True:
            item = await q.get()
            yield item
            if item is None:
                break
    finally:
        with _lock:
            bucket = _subscribers.get(sid)
            if bucket:
                bucket.discard(subscriber)
                if not bucket:
                    _subscribers.pop(sid, None)
