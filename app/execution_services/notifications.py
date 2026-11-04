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


async def _initialize_owner(service, owner, *, io=None):
    """恢复一个会话的执行资源，并在缺失时补齐会话面板状态（幂等）。"""
    await service.call(service.recover, owner)
    store = service._store()
    if store is None:
        return
    try:
        row = await io.run("execution-tools", store.get, owner, _PANEL_PLUGIN_ID, _PANEL_NAMESPACE) if io else await asyncio.to_thread(store.get, owner, _PANEL_PLUGIN_ID, _PANEL_NAMESPACE)
    except Exception:
        log.debug("session panel state probe failed: %s", owner, exc_info=True)
        return
    if isinstance(row, dict) and row.get("value") is not None:
        return
    await service.call(service.persist, owner, _PANEL_NAMESPACE, {"enabled": True})


async def _continue(service, owner, *, wait=True):
    from session_control.public import host_client, stable_key, register_source_lifecycle
    from session_control.errors import ControlError
    notices = await service.call(service.notices, owner)
    if not notices or service.manager.is_interrupt_requested(owner):
        return
    def before(sid, _run_id, _request):
        if not asyncio.run(service.call(service.notices, sid)):
            raise ControlError("intent_obsolete", "Background results were already consumed", status=409)
    def after(sid, _run_id, operation):
        if operation["status"] in {"failed", "unknown"}:
            asyncio.run(service.call(service.stop_owner, sid, reason="job_wakeup_failed"))
    register_source_lifecycle("execution-tools", before=before, after=after)
    client = host_client("execution-tools", session_ids=[owner],
        capabilities=["session.continue", "operation.cancel"])
    try:
        operation = await client.call("session.continue", {"session_id": owner,
            "_respect_stop": True, "_continuation_source": "tool-jobs"},
            key=stable_key("job-wakeup", [owner, notices]), coalesce=True)
        result = await client.wait(operation["operation_id"]) if wait else operation
        if result["status"] in {"failed", "unknown"}:
            await service.call(service.stop_owner, owner, reason="job_wakeup_failed")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if getattr(exc, "code", "") in {"queue_full", "work_pool_full"}:
            return
        log.exception("background job continuation failed: %s", owner)
        await service.call(service.stop_owner, owner, reason="job_wakeup_failed")


async def start_runner(service):
    global _runner
    await stop_runner()
    from session_control.public import host_monitors
    from session_control.monitors import MonitorKey
    hub = await host_monitors()
    initialized = set()
    state = {"scan_at": 0., "owners": [], "offset": 0}
    async def tick():
        if time.monotonic() >= state["scan_at"]:
            state["scan_at"] = time.monotonic() + 5
            rows = await hub.sessions(service.manager)
            state["owners"] = [str(row["id"]) for row in rows if row.get("id") and row["id"] not in initialized]
        for owner in state["owners"][:32]:
            await _initialize_owner(service, owner, io=hub.resources.io)
            initialized.add(owner)
        del state["owners"][:32]
        owners = list(await service.call(service.pending_owners))
        if owners:
            offset = state["offset"] % len(owners)
            owners = owners[offset:] + owners[:offset]
            state["offset"] += 32
        for owner in owners[:32]:
            await _continue(service, owner, wait=False)
    _runner = hub.subscribe(MonitorKey.make("job-results", str(service.manager.sessions_dir), namespace="execution-tools"),
        "execution-tools", tick, interval=.5, events=("extension_state_changed", "run_finished", "run_failed", "interaction_resolved"))


async def stop_runner():
    global _runner
    subscription = _runner
    _runner = None
    _workers.clear()
    if subscription:
        await subscription.close()
