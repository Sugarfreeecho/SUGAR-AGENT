"""Server-owned parent wakeups for completed background subagents."""
from __future__ import annotations

import asyncio
import logging
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
        loop.call_soon_threadsafe(_pending.add, str(owner))
    except RuntimeError:
        pass  # The application is shutting down.


def _batch(rows):
    return frozenset(str(row.get("result_id") or (
        row.get("agent_id"), row.get("run_id"), row.get("finished_at"), row.get("result")
    )) for row in rows)


async def _continue(manager, owner):
    """Submit one durable wakeup per pending result batch."""
    from session_control.public import host_client, stable_key, register_source_lifecycle
    from session_control.errors import ControlError
    meta = await asyncio.to_thread(manager._load_metadata, owner)
    if not meta or meta.get("archived") or manager.is_interrupt_requested(owner):
        return False
    rows = await asyncio.to_thread(manager.prepare_pending_subagent_continuation, owner)
    if not rows:
        _failed_batches.pop(owner, None)
        return False
    batch = _batch(rows)
    if _failed_batches.get(owner) == batch:
        return False
    def before(sid, _run_id, _request):
        if not manager.prepare_pending_subagent_continuation(sid):
            raise ControlError("intent_obsolete", "Child results were already consumed", status=409)
    register_source_lifecycle("@runtime/subagents", before=before)
    client = host_client("@runtime/subagents", session_ids=[owner], runtime=True,
        capabilities=["session.continue", "operation.cancel"])
    try:
        operation = await client.call("session.continue", {"session_id": owner,
            "_respect_stop": True, "_continuation_source": "subagent-results",
            "_require_pending_subagents": True},
            key=stable_key("subagent-wakeup", [owner, sorted(batch)]), coalesce=True)
        if operation["status"] == "queued" and client.service.callbacks.get("pending_human", lambda _: 0)(owner):
            return True  # Backend now owns the queued wakeup.
        await client.wait(operation["operation_id"])
        remaining = await asyncio.to_thread(manager.prepare_pending_subagent_continuation, owner)
        if remaining and _batch(remaining) <= batch:
            _failed_batches[owner] = _batch(remaining)
            return False
        _failed_batches.pop(owner, None)
        return bool(remaining)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("background subagent continuation failed: %s", owner)
        _failed_batches[owner] = batch
        return False


async def start_runner(manager):
    global _runner, _loop, _manager
    await stop_runner()
    _loop = asyncio.get_running_loop()
    _manager = manager

    async def work(owner):
        try:
            if await _continue(manager, owner):
                _pending.add(owner)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("subagent wakeup admission failed: %s", owner)

    async def run():
        # Discover persisted results once. New deliveries enqueue their owner;
        # retry only those owners, rather than scanning every history each tick.
        try:
            rows = await asyncio.to_thread(manager.list_sessions, include_archived=False)
            for row in rows:
                owner = str(row.get("id") or "")
                if owner and await asyncio.to_thread(manager.has_pending_subagent_notifications, owner):
                    _pending.add(owner)
        except Exception:
            log.exception("subagent notification recovery failed")
        while True:
            for owner, task in list(_workers.items()):
                if task.done():
                    _workers.pop(owner, None)
            for owner in list(_pending):
                if owner not in _workers:
                    _pending.discard(owner)
                    _workers[owner] = asyncio.create_task(work(owner))
            # Match job wakeups: a busy parent is retried after it becomes idle.
            await asyncio.sleep(.5)

    _runner = asyncio.create_task(run())


async def stop_runner():
    global _runner, _loop, _manager
    _loop = _manager = None
    tasks = ([_runner] if _runner else []) + list(_workers.values())
    _runner = None
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _workers.clear()
    _pending.clear()
    _failed_batches.clear()
