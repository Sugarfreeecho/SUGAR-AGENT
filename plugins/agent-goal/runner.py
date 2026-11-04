"""Server-side continuation scheduler owned by the Goal workflow plugin."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger(__name__)
_POLL_SECONDS = max(0.5, float(os.getenv("GOAL_RUNNER_POLL_SECONDS", "2")))
_scheduler: asyncio.Task | None = None
_workers: dict[str, asyncio.Task] = {}
_host: Any = None
_next_full_scan = 0.
_candidate_offset = 0
_progress: dict[str, dict] = {}
_progress_lock = threading.RLock()
_event_listener = None
_PROGRESS_LABELS = {
    'waiting': '等待下一轮', 'queued': '续跑已排队', 'preparing': '准备下一轮',
    'model_wait': '正在请求模型', 'running': '正在执行', 'finishing': '本轮收尾',
    'retry': '等待重试', 'waiting_user': '等待你的处理', 'stopped': '已停止，等待继续',
    'paused': '自动续跑已暂停', 'blocked': '目标已阻塞', 'completed': '等待目标验收',
    'cancelled': '目标已取消', 'error': '续跑调度暂不可用',
}


def _set_progress(sid, phase, *, run_id='', **extra):
    with _progress_lock:
        previous = _progress.get(sid, {})
        if phase == 'queued' and previous.get('phase') != 'queued':
            previous = {}
        same = previous.get('phase') == phase and (not run_id or previous.get('run_id') == run_id)
        _progress[sid] = {**previous, 'phase': phase,
                          'since': previous.get('since', time.time()) if same else time.time(),
                          **({'run_id': run_id} if run_id else {}), **extra}
        if len(_progress) > 128:
            removable = next((key for key, row in _progress.items()
                              if key != sid and row.get('phase') in {'waiting', 'finishing', 'error'}), None)
            _progress.pop(removable or next(iter(_progress)), None)
    if not same:
        logger.info('goal_handoff_phase session=%s run=%s phase=%s', sid, run_id or '-', phase)


def _observe_progress(sid, event):
    with _progress_lock:
        row = dict(_progress.get(sid, {}))
    if not row or not row.get('run_id') or event.get('run_id') != row['run_id']:
        return
    kind = event.get('type')
    if kind in {'final', 'run_finished', 'run_failed', 'run_interrupted'}:
        if row.get('phase') == 'waiting':
            return  # A duplicate terminal notification cannot rewind the clock.
        _set_progress(sid, 'finishing', run_id=row['run_id'])
    elif kind == 'run_started':
        _set_progress(sid, 'preparing', run_id=row['run_id'])
    elif kind == 'status' and event.get('content') == '正在思考中...' and row.get('phase') in {'queued', 'preparing', 'finishing'}:
        _set_progress(sid, 'model_wait', run_id=row['run_id'])
    elif kind in {'llm_reasoning_delta', 'llm_response_delta', 'llm_reasoning', 'llm_response', 'tool_call_delta', 'tool_pending'}:
        _set_progress(sid, 'running', run_id=row['run_id'])


def progress_snapshot(sid, goal):
    """Small, payload-free view; callers perform the host checks off the UI loop."""
    with _progress_lock:
        row = dict(_progress.get(sid, {}))
    phase = row.get('phase', 'waiting')
    if not goal or goal.get('status') != 'active':
        phase = (goal or {}).get('status') or 'waiting'
    elif _host and _host.is_stopped(sid):
        phase = 'stopped'
    elif _host and _host.pending_human(sid) > 0:
        phase = 'waiting_user'
    elif goal.get('next_retry_at'):
        try:
            due = datetime.fromisoformat(goal['next_retry_at'].replace('Z', '+00:00'))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due > datetime.now(timezone.utc):
                phase = 'retry'
            elif phase == 'retry':
                phase = 'waiting'
        except (TypeError, ValueError):
            pass
    if goal and goal.get('status') == 'active' and phase not in {'stopped', 'waiting_user', 'retry'}:
        if phase == 'finishing' and not goal.get('current_run_id') and not (_host and _host.is_active(sid)):
            phase = 'waiting'
        elif not row and _host and _host.is_active(sid):
            phase = 'running'
        elif not row and goal.get('current_run_id'):
            phase = 'preparing'
    if phase == 'waiting' and row.get('phase') == 'finishing':
        with _progress_lock:
            if _progress.get(sid) == row:
                _set_progress(sid, 'waiting', run_id=row.get('run_id', ''))
                row = dict(_progress[sid])
    since = row.get('since') if phase == row.get('phase') else None
    return {'phase': phase, 'label': _PROGRESS_LABELS.get(phase, '等待下一轮'), 'since': since,
            'run_id': (goal or {}).get('current_run_id') or row.get('run_id', ''),
            'operation_id': row.get('operation_id', ''), 'retry_at': (goal or {}).get('next_retry_at')}
_RECOVERY_GRACE_SECONDS = max(
    5.0,
    float(os.getenv("GOAL_RUNNER_RECOVERY_GRACE_SECONDS", "30")),
)


def _parse_iso_age_seconds(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


def _reconcile_incomplete_run(manager: Any, session_id: str) -> bool:
    """Account an abandoned continuation before allowing a replacement.

    Returns True only when no continuation lease remains. A locally active or
    still-running durable row is never taken over.
    """

    getter = getattr(manager, "get", None)
    if not callable(getter):
        return True
    goal = getter(session_id) or {}
    current_run_id = str(goal.get("current_run_id") or "").strip()
    if not current_run_id:
        return True
    if _host.is_active(session_id):
        return False

    status = ""
    try:
        import runtime_observability

        rows = runtime_observability.snapshot(session_id).get("runs") or []
        row = next(
            (
                item for item in reversed(rows)
                if isinstance(item, dict)
                and str(item.get("run_id") or "").strip() == current_run_id
            ),
            None,
        )
        status = str((row or {}).get("status") or "").strip().lower()
    except Exception:
        logger.debug("Goal run reconciliation could not read observability", exc_info=True)

    if status == "running":
        return False
    if not status:
        age = _parse_iso_age_seconds(goal.get("last_continuation_started_at"))
        if age is None or age < _RECOVERY_GRACE_SECONDS:
            return False

    recorder = getattr(manager, "record_run", None)
    if not callable(recorder):
        return False
    recorder(
        session_id,
        0,
        continuation=True,
        run_id=current_run_id,
        outcome="failed" if status in {"failed", "error"} else "interrupted",
        error=f"abandoned_continuation:{status or 'missing_observability'}",
    )
    # record_run pauses failed runs and applies backoff to interruptions;
    # discovery must not immediately start a replacement.
    return False


def _discover(candidate_session_ids: list[str] | None = None) -> list[str]:
    from agent_goal import goal_enabled, manager_for

    if not goal_enabled():
        return []
    manager = manager_for(_host.manager)
    rows = (
        _host.manager.list_sessions(include_archived=True)
        if candidate_session_ids is None
        else ({"id": value} for value in candidate_session_ids)
    )
    runnable = []
    for row in rows:
        sid = str((row or {}).get("id") or "").strip()
        if not sid:
            continue
        try:
            if _host.is_stopped(sid):
                continue
            if not _reconcile_incomplete_run(manager, sid):
                continue
            if manager.should_continue(sid) and _host.pending_human(sid) <= 0:
                runnable.append(sid)
        except Exception:
            logger.debug("Goal workflow discovery failed for %s", sid, exc_info=True)
    return runnable


def _register_control_hooks():
    from agent_goal import manager_for
    from session_control.public import register_source_lifecycle
    from session_control.errors import ControlError

    def before(sid, run_id, _request):
        manager = manager_for(_host.manager)
        if not manager.should_continue(sid) or _host.is_stopped(sid):
            raise ControlError("intent_obsolete", "Goal no longer requests continuation", status=409)
        _set_progress(sid, 'preparing', run_id=run_id)
        manager.mark_continuation_started(sid, run_id=run_id)

    def after(sid, run_id, operation):
        manager = manager_for(_host.manager)
        if (manager.get(sid) or {}).get("current_run_id") != run_id:
            return  # Runtime hooks already accounted this run and its usage.
        outcome = "failed" if operation["status"] in {"failed", "unknown"} else "interrupted"
        manager.record_run(sid, 0, continuation=True, run_id=run_id, outcome=outcome,
            error=str((operation.get("error") or {}).get("message") or "continuation_produced_no_events"))
    register_source_lifecycle("agent-goal", before=before, after=after)


async def _continue(session_id: str, *, wait: bool = True) -> None:
    from agent_goal import manager_for
    from session_control.public import host_client, stable_key

    sid = str(session_id or "").strip()
    manager = manager_for(_host.manager)
    if not manager.should_continue(sid) or _host.is_stopped(sid):
        return
    if _host.pending_human(sid) > 0:
        return
    _register_control_hooks()
    current = manager.get(sid) or {}
    _set_progress(sid, 'queued')
    client = host_client("agent-goal", session_ids=[sid],
        capabilities=["session.continue", "operation.cancel"])
    try:
        operation = await client.call("session.continue", {"session_id": sid,
            "_respect_stop": True, "_continuation_source": "agent-goal",
            "_recovery_reason": "process_or_network_interruption" if current.get("current_run_id") else ""},
            key=stable_key("goal", [sid, current]), coalesce=True)
    except Exception:
        _set_progress(sid, 'error')
        raise
    with _progress_lock:
        state = _progress.get(sid, {})
        _progress[sid] = {**state, 'operation_id': operation['operation_id'],
                          'run_id': state.get('run_id') if state.get('phase') != 'queued' else operation.get('run_id', '')}
    result = await client.wait(operation["operation_id"]) if wait else operation
    if result["status"] == "failed" and not (manager.get(sid) or {}).get("current_run_id"):
        manager.record_run(sid, 0, continuation=True, run_id=result["run_id"], outcome="failed",
            error=str((result.get("error") or {}).get("message") or "continuation_failed"))


async def _tick() -> None:
    from agent_local_timing import LocalOperationTrace
    trace = LocalOperationTrace('goal_scheduler')
    try:
        await _tick_traced(trace)
    finally:
        trace.finish(slow_ms=100)


async def _tick_traced(trace) -> None:
    global _next_full_scan, _candidate_offset
    from agent_goal import active_goal_session_ids
    from session_control.public import control_application
    now = time.monotonic()
    control = control_application().service
    # A just-finished Goal must not queue behind a periodic inventory scan of
    # every archived/inactive conversation. Keep the scan as a recovery path.
    known = active_goal_session_ids()
    candidates = list(known)
    dispatched = 0
    while True:
        with trace.step('known_discovery' if candidates == known else 'cold_discovery'):
            runnable = await control.resources.io.run("agent-goal", _discover, candidates) if candidates else []
        if runnable:
            offset = _candidate_offset % len(runnable)
            runnable = runnable[offset:] + runnable[:offset]
            _candidate_offset += 32
        for sid in runnable[:32 - dispatched]:
            if not _host.is_active(sid):
                with trace.step('admit_continuation'):
                    await _continue(sid, wait=False)
                trace.mark('first_admission')
                dispatched += 1
        if now < _next_full_scan:
            break
        _next_full_scan = now + 60.
        known_ids = set(known)
        with trace.step('full_inventory'):
            candidates = [row["id"] for row in await control.monitors.sessions(_host.manager, include_archived=True)
                          if row["id"] not in known_ids]


async def start(host_module: Any = None) -> bool:
    global _host, _scheduler, _next_full_scan, _event_listener
    from agent_goal import goal_enabled

    from session_control.public import HostRuntimeState
    _host = host_module or HostRuntimeState()
    if not goal_enabled() or (_scheduler and not _scheduler.done()):
        return False
    from session_control.public import host_monitors
    from session_control.monitors import MonitorKey
    hub = await host_monitors()
    # Older live hosts queue namespace revocation for the next loop turn.
    # Let it capture the retired generation before registering its replacement.
    await asyncio.sleep(0)
    _next_full_scan = 0.
    _scheduler = hub.subscribe(MonitorKey.make("goal", str(_host.manager.sessions_dir), namespace="agent-goal"),
        "agent-goal", _tick, interval=_POLL_SECONDS,
        events=("run_finished", "run_failed", "run_interrupted", "interaction_resolved", "extension_state_changed"))
    from session_event_bus import add_event_listener
    _event_listener = _observe_progress
    add_event_listener(_event_listener)
    return True


async def stop() -> None:
    global _scheduler, _event_listener
    if _event_listener:
        from session_event_bus import remove_event_listener
        remove_event_listener(_event_listener)
        _event_listener = None
    scheduler, _scheduler = _scheduler, None
    if scheduler:
        await scheduler.close()
    _workers.clear()


__all__ = ["start", "stop"]
