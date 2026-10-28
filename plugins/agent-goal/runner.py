"""Server-side continuation scheduler owned by the Goal workflow plugin."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger(__name__)
_POLL_SECONDS = max(0.5, float(os.getenv("GOAL_RUNNER_POLL_SECONDS", "2")))
_scheduler: asyncio.Task | None = None
_workers: dict[str, asyncio.Task] = {}
_host: Any = None
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
        manager.mark_continuation_started(sid, run_id=run_id)

    def after(sid, run_id, operation):
        manager = manager_for(_host.manager)
        if (manager.get(sid) or {}).get("current_run_id") != run_id:
            return  # Runtime hooks already accounted this run and its usage.
        outcome = "failed" if operation["status"] in {"failed", "unknown"} else "interrupted"
        manager.record_run(sid, 0, continuation=True, run_id=run_id, outcome=outcome,
            error=str((operation.get("error") or {}).get("message") or "continuation_produced_no_events"))
    register_source_lifecycle("agent-goal", before=before, after=after)


async def _continue(session_id: str) -> None:
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
    client = host_client("agent-goal", session_ids=[sid],
        capabilities=["session.continue", "operation.cancel"])
    operation = await client.call("session.continue", {"session_id": sid,
        "_respect_stop": True, "_continuation_source": "agent-goal",
        "_recovery_reason": "process_or_network_interruption" if current.get("current_run_id") else ""},
        key=stable_key("goal", [sid, current]), coalesce=True)
    result = await client.wait(operation["operation_id"])
    if result["status"] == "failed" and not (manager.get(sid) or {}).get("current_run_id"):
        manager.record_run(sid, 0, continuation=True, run_id=result["run_id"], outcome="failed",
            error=str((result.get("error") or {}).get("message") or "continuation_failed"))


async def _loop() -> None:
    from agent_goal import active_goal_session_ids, subscribe_goal_activity

    activity, unsubscribe = subscribe_goal_activity(asyncio.get_running_loop())
    next_full_scan = 0.0
    try:
        while True:
            try:
                now = time.monotonic()
                candidates = None if now >= next_full_scan else active_goal_session_ids()
                if candidates is None:
                    next_full_scan = now + 60.0
                for sid in await asyncio.to_thread(_discover, candidates):
                    existing = _workers.get(sid)
                    if existing and not existing.done():
                        continue
                    if _host.is_active(sid):
                        continue
                    task = asyncio.create_task(_continue(sid), name=f"workflow-agent-goal-{sid}")
                    _workers[sid] = task
                    task.add_done_callback(
                        lambda done, value=sid: _workers.pop(value, None)
                        if _workers.get(value) is done
                        else None
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Goal workflow scheduling tick failed")
            try:
                await asyncio.wait_for(activity.wait(), timeout=_POLL_SECONDS)
                activity.clear()
            except asyncio.TimeoutError:
                pass
    finally:
        unsubscribe()


async def start(host_module: Any = None) -> bool:
    global _host, _scheduler
    from agent_goal import goal_enabled

    from session_control.public import HostRuntimeState
    _host = host_module or HostRuntimeState()
    if not goal_enabled() or (_scheduler and not _scheduler.done()):
        return False
    _scheduler = asyncio.create_task(_loop(), name="workflow-agent-goal-scheduler")
    return True


async def stop() -> None:
    global _scheduler
    scheduler, _scheduler = _scheduler, None
    pending = [task for task in [scheduler, *_workers.values()] if task and not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    _workers.clear()


__all__ = ["start", "stop"]
