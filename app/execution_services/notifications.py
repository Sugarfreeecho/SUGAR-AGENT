"""Server-owned wakeups using the existing session single-writer reservation."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

log = logging.getLogger(__name__)
_runner = None
_workers = {}

# 会话面板只有在对应扩展命名空间存在后才会被投影（见 app/plugins/ui.py），
# 新会话因此需要一次初始化写入。初始化以「命名空间状态」为准，而不是「每次宿主
# 启动都写一遍」：追加到旧会话事件日志里的控制事件会被侧栏的活动时间回填当成新的
# 对话活动，把所有会话顶成「今天」并打乱顺序。
_PANEL_PLUGIN_ID = "execution-tools"
_PANEL_NAMESPACE = "panel"


async def _initialize_owner(service, owner):
    """恢复一个会话的执行资源，并在缺失时补齐会话面板状态（幂等）。"""
    await service.call(service.recover, owner)
    store = service._store()
    if store is None:
        return
    try:
        row = await asyncio.to_thread(store.get, owner, _PANEL_PLUGIN_ID, _PANEL_NAMESPACE)
    except Exception:
        log.debug("session panel state probe failed: %s", owner, exc_info=True)
        return
    if isinstance(row, dict) and row.get("value") is not None:
        return
    await service.call(service.persist, owner, _PANEL_NAMESPACE, {"enabled": True})


async def _continue(service, owner):
    import webui
    run_id = "job-wakeup-" + uuid.uuid4().hex
    token = webui._reserve_session_chat_start(owner, run_id)
    if not token:
        return
    try:
        if not await service.call(service.notices, owner):
            return
        if service.manager.is_interrupt_requested(owner) or webui._session_pending_human_count(owner):
            return
        from agent_loop import astream_events_continuation
        async for _event in astream_events_continuation(owner,
            should_stop=lambda sid: service.manager.is_interrupt_requested(sid, run_id),
            require_pending_subagents=False, run_id=run_id, continuation_source="tool-jobs"):
            pass
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("background job continuation failed: %s", owner)
        # Avoid repeatedly retrying a failed automatic run. Records/output are
        # still available, and the next human turn can handle pending notices.
        await service.call(service.stop_owner, owner, reason="job_wakeup_failed")
    finally:
        webui._release_session_chat_start(owner, token)


async def start_runner(service):
    global _runner
    await stop_runner()
    async def run():
        initialized = set()
        next_scan = 0
        while True:
            try:
                if time.monotonic() >= next_scan:
                    next_scan = time.monotonic() + 5
                    rows = await asyncio.to_thread(service.manager.list_sessions, include_archived=False)
                    for row in rows:
                        owner = str(row.get("id") or "")
                        if owner and owner not in initialized:
                            await _initialize_owner(service, owner)
                            initialized.add(owner)
                for owner in await service.call(service.pending_owners):
                    task = _workers.get(owner)
                    if not task or task.done():
                        _workers[owner] = asyncio.create_task(_continue(service, owner))
                # Retry busy-to-idle delivery without relying on one edge event.
                await asyncio.sleep(.5)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("execution notification reconciliation failed")
                await asyncio.sleep(2)
    _runner = asyncio.create_task(run())


async def stop_runner():
    global _runner
    tasks = ([ _runner ] if _runner else []) + list(_workers.values())
    _runner = None
    _workers.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
