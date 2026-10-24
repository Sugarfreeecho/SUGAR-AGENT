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
    """Return whether a busy or newly updated parent needs another attempt."""
    import webui

    run_id = "subagent-wakeup-" + uuid.uuid4().hex
    token = await webui._reserve_session_chat_start_off_loop(owner, run_id)
    if not token:
        return True
    batch = None
    try:
        meta = await asyncio.to_thread(manager._load_metadata, owner)
        if not meta or meta.get("archived") or manager.is_interrupt_requested(owner):
            return False
        if await asyncio.to_thread(webui._session_pending_human_count, owner):
            return True
        rows = await asyncio.to_thread(manager.prepare_pending_subagent_continuation, owner)
        if not rows:
            _failed_batches.pop(owner, None)
            return False
        batch = _batch(rows)
        if _failed_batches.get(owner) == batch or manager.is_interrupt_requested(owner):
            return False
        from agent_loop import astream_events_continuation
        async for _event in astream_events_continuation(
            owner, run_id=run_id,
            should_stop=lambda sid: manager.is_interrupt_requested(sid, run_id),
        ):
            pass
        remaining = await asyncio.to_thread(manager.prepare_pending_subagent_continuation, owner)
        if remaining and _batch(remaining) <= batch:
            # Empty model history or an early hook can leave delivery pending.
            # Keep the output available without automatically retrying forever.
            _failed_batches[owner] = _batch(remaining)
            return False
        _failed_batches.pop(owner, None)
        return bool(remaining)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("background subagent continuation failed: %s", owner)
        if batch is not None:
            _failed_batches[owner] = batch
        return False
    finally:
        webui._release_session_chat_start(owner, token)


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
