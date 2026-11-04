"""All migrated domain observers register with the same application monitor hub."""
import asyncio
from types import SimpleNamespace

from tests.test_session_control import composed, new_session, run_async
from tests.test_sugar_bili_scroll_tasks import host
from tests.test_monitor_hub import until


@run_async
async def test_goal_restart_survives_revocation_queued_by_an_older_live_host(composed, monkeypatch):
    import agent_goal
    import session_control.integration as integration
    from session_control.monitors import MonitorKey
    from tests.test_goal_runner import _load_plugin_module

    c = composed
    monkeypatch.setattr(integration, '_application', c.control)
    monkeypatch.setattr(agent_goal, 'goal_enabled', lambda: True)
    goal = _load_plugin_module('goal_legacy_revocation_test', 'plugins/agent-goal/runner.py')
    collections = []
    async def collect():
        collections.append(1)
    monkeypatch.setattr(goal, '_tick', collect)
    state = SimpleNamespace(manager=c.manager)
    await c.control.start()
    try:
        await goal.start(state)
        hub = c.service.monitors
        key = MonitorKey.make('goal', str(c.manager.sessions_dir), namespace='agent-goal')
        old = goal._scheduler
        # Model the pre-fix hub that captures sources only on its next turn.
        def delayed_revocation():
            source = hub.sources.get(key)
            if source:
                asyncio.create_task(hub.unsubscribe(key, 'agent-goal', expected_source=source))
        asyncio.get_running_loop().call_soon(delayed_revocation)
        await goal.stop()
        await goal.start(state)
        await until(lambda: bool(collections))
        await asyncio.sleep(0)
        assert old.done() and not goal._scheduler.done()
        assert hub.sources[key] is goal._scheduler.source
    finally:
        await goal.stop()
        await c.control.close()


@run_async
async def test_domain_sources_share_scheduler_inventory_and_release_without_stopping_other_sources(composed, host, monkeypatch):
    import agent_goal
    import agent_subagent_notifications as children
    import execution_services.notifications as jobs
    import plugins.storage
    import session_control.integration as integration
    from tests.test_goal_runner import _GOAL_RUNNER as goal
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    monkeypatch.setattr(agent_goal, "goal_enabled", lambda: True)
    monkeypatch.setattr(host, "_settings", lambda *args: {"inbound_reply": False})
    monkeypatch.setattr(host, "_work_pool", lambda: c.service.resources.business)
    monkeypatch.setattr(plugins.storage, "plugin_storage_layout", lambda _: SimpleNamespace(data_dir=host._home()))
    async def noop(*args):
        pass
    original = host._load_sibling
    monkeypatch.setattr(host, "_load_sibling", lambda name: SimpleNamespace(start=noop, stop=noop) if name == "mcp_server" else original(name))
    sid = await new_session(c)
    state = SimpleNamespace(manager=c.manager, is_stopped=lambda _: False, is_active=lambda _: False, pending_human=lambda _: 0)
    reads, job_polls = [], []
    original_list = c.manager.list_sessions
    def list_sessions(**kwargs):
        reads.append(1)
        return original_list(**kwargs)
    monkeypatch.setattr(c.manager, "list_sessions", list_sessions)
    async def call(function, *args, **kwargs):
        return function(*args, **kwargs)
    execution = SimpleNamespace(manager=c.manager, call=call, recover=lambda _: None, _store=lambda: None,
                                pending_owners=lambda: job_polls.append(1) or [])
    await c.control.start()
    try:
        await goal.start(state)
        await jobs.start_runner(execution)
        await children.start_runner(c.manager)
        await host.start({}, host._runtime["plugin"])
        hub = c.service.monitors
        assert hub.snapshot()["sources"] == 6
        assert goal._scheduler.hub is jobs._runner.hub is children._runner.hub is host._runtime["task"].hub is hub
        await until(lambda: bool(job_polls) and hub.snapshot()["active"] == 0)
        assert len(reads) == 1, "the control bridge and three domain observers share one inventory read"
        await host.stop({}, host._runtime["plugin"])
        assert hub.snapshot()["sources"] == 4
        await goal.stop()
        await jobs.stop_runner()
        await children.stop_runner()
        assert hub.snapshot()["sources"] == 1 and not hub.task.done()
        assert c.manager.get_session_summary(sid)
    finally:
        await goal.stop()
        await jobs.stop_runner()
        await children.stop_runner()
        await c.control.close()
