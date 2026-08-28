"""Server-side continuation scheduler owned by the Goal workflow plugin."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any


logger = logging.getLogger(__name__)
_POLL_SECONDS = max(0.5, float(os.getenv("GOAL_RUNNER_POLL_SECONDS", "2")))
_scheduler: asyncio.Task | None = None
_workers: dict[str, asyncio.Task] = {}
_host: Any = None


def _discover(candidate_session_ids: list[str] | None = None) -> list[str]:
    from agent_goal import goal_enabled, manager_for

    if not goal_enabled():
        return []
    manager = manager_for(_host.session_manager)
    rows = (
        _host.session_manager.list_sessions(include_archived=True)
        if candidate_session_ids is None
        else ({"id": value} for value in candidate_session_ids)
    )
    runnable = []
    for row in rows:
        sid = str((row or {}).get("id") or "").strip()
        if not sid:
            continue
        try:
            if _host._session_was_manually_stopped(sid):
                continue
            if manager.should_continue(sid) and _host._session_pending_human_count(sid) <= 0:
                runnable.append(sid)
        except Exception:
            logger.debug("Goal workflow discovery failed for %s", sid, exc_info=True)
    return runnable


async def _continue(session_id: str) -> None:
    from agent_goal import manager_for

    sid = str(session_id or "").strip()
    run_id = "workflow-runner-" + uuid.uuid4().hex
    token = _host._reserve_session_chat_start(sid, run_id) or ""
    if not token:
        return
    manager = manager_for(_host.session_manager)
    saw_event = False
    try:
        if not manager.should_continue(sid) or _host._session_was_manually_stopped(sid):
            return
        if _host._session_pending_human_count(sid) > 0:
            return
        current = manager.get(sid) or {}
        recovery_reason = "process_or_network_interruption" if current.get("current_run_id") else ""
        manager.mark_continuation_started(sid, run_id=run_id)

        def should_stop(value: str) -> bool:
            return _host.session_manager.is_interrupt_requested(value)

        async for _event in _host.astream_events_continuation(
            sid,
            should_stop=should_stop,
            require_pending_subagents=False,
            recovery_reason=recovery_reason,
            run_id=run_id,
            continuation_source="agent-goal",
        ):
            saw_event = True
        if not saw_event:
            manager.record_run(
                sid,
                0,
                continuation=True,
                run_id=run_id,
                outcome="failed",
                error="continuation_produced_no_events",
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("Goal workflow continuation failed for %s: %s", sid, exc)
        try:
            manager.record_run(
                sid,
                0,
                continuation=True,
                run_id=run_id,
                outcome="failed",
                error=str(exc),
            )
        except Exception:
            logger.debug("Goal workflow fallback accounting failed", exc_info=True)
    finally:
        _host._release_session_chat_start(sid, token)


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
                    if _host._has_local_worker_activity(sid):
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


async def start(host_module: Any) -> bool:
    global _host, _scheduler
    from agent_goal import goal_enabled

    _host = host_module
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
