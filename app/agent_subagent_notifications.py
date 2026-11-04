"""Server-owned parent wakeups for completed background subagents."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

log = logging.getLogger(__name__)
_runner = None
_loop = None
_manager = None
_pending = set()
_workers = {}
_failed_batches = {}


def notify_pending(manager, owner):
    """Called after persistence, including from the subagent's worker loop."""
    loop = _loop
    if manager is not _manager or loop is None or loop.is_closed():
        return
    try:
        def wake():
            _pending.add(str(owner))
            if _runner:
                _runner.wake()
        loop.call_soon_threadsafe(wake)
    except RuntimeError:
        pass  # The application is shutting down.


def _batch(rows):
    return frozenset(str(row.get("result_id") or (
        row.get("agent_id"), row.get("run_id"), row.get("finished_at"), row.get("result")
    )) for row in rows)


async def _continue(manager, owner, *, wait=True, io=None):
    """Submit one durable wakeup per pending result batch."""
    from session_control.public import host_client, stable_key, register_source_lifecycle
    from session_control.errors import ControlError
    async def read(function, *args):
        return await io.run("@runtime/subagents", function, *args) if io else await asyncio.to_thread(function, *args)
    meta = await read(manager._load_metadata, owner)
    if not meta or meta.get("archived") or manager.is_interrupt_requested(owner):
        return False
    rows = await read(manager.prepare_pending_subagent_continuation, owner)
    if not rows:
        _failed_batches.pop(owner, None)
        return False
    batch = _batch(rows)
    if _failed_batches.get(owner) == batch:
        return False
    def before(sid, _run_id, _request):
        if not manager.prepare_pending_subagent_continuation(sid):
            raise ControlError("intent_obsolete", "Child results were already consumed", status=409)
    def after(sid, _run_id, operation):
        remaining = manager.prepare_pending_subagent_continuation(sid)
        if remaining:
            accepted = frozenset(operation["request"].get("_subagent_batch", []))
            if _batch(remaining) <= accepted:
                _failed_batches[sid] = _batch(remaining)
            else:
                notify_pending(manager, sid)
    register_source_lifecycle("@runtime/subagents", before=before, after=after)
    client = host_client("@runtime/subagents", session_ids=[owner], runtime=True,
        capabilities=["session.continue", "operation.cancel"])
    try:
        operation = await client.call("session.continue", {"session_id": owner,
            "_respect_stop": True, "_continuation_source": "subagent-results",
            "_require_pending_subagents": True, "_subagent_batch": sorted(batch)},
            key=stable_key("subagent-wakeup", [owner, sorted(batch)]), coalesce=True)
        if not wait:
            if operation["status"] in {"failed", "unknown", "stopped", "cancelled", "interrupted"}:
                _failed_batches[owner] = batch
            return False
        if operation["status"] == "queued" and client.service.callbacks.get("pending_human", lambda _: 0)(owner):
            return True  # Backend now owns the queued wakeup.
        await client.wait(operation["operation_id"])
        remaining = await read(manager.prepare_pending_subagent_continuation, owner)
        if remaining and _batch(remaining) <= batch:
            _failed_batches[owner] = _batch(remaining)
            return False
        _failed_batches.pop(owner, None)
        return bool(remaining)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if getattr(exc, "code", "") in {"queue_full", "work_pool_full"}:
            _pending.add(owner)
            return False
        log.exception("background subagent continuation failed: %s", owner)
        _failed_batches[owner] = batch
        return False


async def start_runner(manager):
    global _runner, _loop, _manager
    await stop_runner()
    _loop = asyncio.get_running_loop()
    _manager = manager

    from session_control.public import host_monitors
    from session_control.monitors import MonitorKey
    hub = await host_monitors()
    state = {"next_scan": 0.}
    def discover(rows):
        return [str(row["id"]) for row in rows
                if row.get("id") and manager.has_pending_subagent_notifications(row["id"])]
    async def tick():
        if time.monotonic() >= state["next_scan"]:
            rows = await hub.sessions(manager)
            _pending.update(await hub.resources.io.run("@runtime/subagents", discover, rows))
            state["next_scan"] = time.monotonic() + 30.
        for owner in list(_pending)[:32]:
            _pending.discard(owner)
            try:
                await _continue(manager, owner, wait=False, io=hub.resources.io)
            except Exception:
                _pending.add(owner)
                log.exception("subagent wakeup admission failed: %s", owner)
    _runner = hub.subscribe(MonitorKey.make("subagent-results", str(manager.sessions_dir), namespace="@runtime/subagents"),
        "@runtime/subagents", tick, interval=.5, events=("subagent_finished", "subagent_failed", "run_finished", "interaction_resolved"))


async def stop_runner():
    global _runner, _loop, _manager
    _loop = _manager = None
    subscription = _runner
    _runner = None
    if subscription:
        await subscription.close()
    _workers.clear()
    _pending.clear()
    _failed_batches.clear()
