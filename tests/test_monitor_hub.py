"""Source reference counting, wake coalescing and bounded monitor concurrency."""
import asyncio
from types import SimpleNamespace

from session_control.monitors import MonitorKey, SharedMonitorHub
from session_control.resources import ControlResources
from tests.test_control_resources import until
from tests.test_session_control import run_async


@run_async
async def test_shared_collection_is_once_and_last_subscriber_releases_resource():
    resources = ControlResources()
    hub = SharedMonitorHub(resources)
    calls, received, cleaned = [], [], []
    key = MonitorKey.make("directory", "/shared", namespace="plugin", options={"recursive": True})
    async def collect():
        calls.append(1)
        return len(calls)
    await hub.start()
    a = hub.subscribe(key, "a", collect, consume=lambda value: received.append(("a", value)), interval=60, cleanup=lambda: cleaned.append(1))
    b = hub.subscribe(key, "b", collect, consume=lambda value: received.append(("b", value)), interval=60)
    try:
        await until(lambda: len(received) == 2)
        assert calls == [1] and hub.snapshot()["sources"] == 1
        assert set(received) == {("a", 1), ("b", 1)}
        await a.close()
        assert hub.snapshot()["subscriptions"] == 1 and not cleaned
        for _ in range(100):
            b.wake()
        await until(lambda: len(received) == 3)
        assert len(calls) == 2
        await b.close()
        assert cleaned == [1] and hub.snapshot()["sources"] == 0
    finally:
        await hub.close()
        resources.close()


@run_async
async def test_slow_sources_cannot_create_unbounded_work_and_revocation_stops_acquisition():
    resources = ControlResources()
    enabled = {"a": True, "b": True, "c": True}
    hub = SharedMonitorHub(resources, enabled=lambda name: enabled[name])
    hub.limit = 2
    release, calls = asyncio.Event(), []
    await hub.start()
    async def collect(name):
        calls.append(name)
        await release.wait()
    subscriptions = []
    for name in enabled:
        async def callback(name=name):
            await collect(name)
        subscriptions.append(hub.subscribe(MonitorKey.make("poll", "same-url", namespace=name), name, callback, interval=60))
    try:
        await until(lambda: len(calls) == 2)
        assert hub.snapshot()["active"] == 2 and hub.snapshot()["sources"] == 3
        enabled["c"] = False
        release.set()
        await until(lambda: hub.snapshot()["active"] == 0)
        assert calls == ["a", "b"]
        assert hub.snapshot()["deadlines"] <= 12
        enabled["c"] = True
        subscriptions[-1].wake()
        await until(lambda: "c" in calls)
    finally:
        release.set()
        await hub.close()
        resources.close()


@run_async
async def test_inventory_reads_are_single_flight_and_source_revocation_releases_handles(tmp_path):
    resources = ControlResources()
    hub = SharedMonitorHub(resources)
    reads, released = [], []
    def list_sessions(**kwargs):
        reads.append(kwargs)
        return [{"id": "visible"}, {"id": "archived", "archived": True}]
    manager = SimpleNamespace(sessions_dir=tmp_path, list_sessions=list_sessions)
    await hub.start()
    key = MonitorKey.make("poll", "account-endpoint", namespace="plugin")
    subscription = hub.subscribe(key, "plugin", lambda: None, interval=60, cleanup=lambda: released.append(1))
    try:
        one, two = await asyncio.gather(hub.sessions(manager), hub.sessions(manager, include_archived=True))
        assert len(reads) == 1
        assert len(one) == 1 and len(two) == 2
        hub.revoke_namespace("plugin")
        await until(lambda: hub.snapshot()["sources"] == 0 and released == [1])
        assert subscription.done()
        replacement = hub.subscribe(key, "plugin", lambda: None, interval=60, immediate=False)
        await subscription.close()
        assert released == [1] and not replacement.done()
        assert hub.snapshot()["sources"] == 1
        await replacement.close()
    finally:
        await hub.close()
        resources.close()


@run_async
async def test_same_turn_revocation_cannot_remove_a_restarted_monitor():
    resources = ControlResources()
    hub = SharedMonitorHub(resources)
    key = MonitorKey.make('goal', '/sessions', namespace='agent-goal')
    await hub.start()
    old = hub.subscribe(key, 'agent-goal', lambda: None, interval=60, immediate=False)
    try:
        hub.revoke_namespace('agent-goal')
        # An idle subscription closes without yielding to the loop.
        await old.close()
        replacement = hub.subscribe(key, 'agent-goal', lambda: None, interval=60, immediate=False)
        await asyncio.sleep(0)
        await until(lambda: not hub._revocations)
        assert not replacement.done(), 'A queued old revocation removed the new Goal scheduler'
        assert hub.sources[key] is replacement.source
    finally:
        await hub.close()
        resources.close()


@run_async
async def test_namespace_revocation_remains_safe_from_a_worker_thread():
    resources = ControlResources()
    hub = SharedMonitorHub(resources)
    await hub.start()
    subscription = hub.subscribe(MonitorKey.make('goal', '/sessions', namespace='agent-goal'),
        'agent-goal', lambda: None, interval=60, immediate=False)
    try:
        await asyncio.to_thread(hub.revoke_namespace, 'agent-goal')
        await until(subscription.done)
        assert not hub.sources
    finally:
        await hub.close()
        resources.close()


@run_async
async def test_failed_cleanup_does_not_prevent_other_sources_from_being_revoked():
    resources = ControlResources()
    hub = SharedMonitorHub(resources)
    cleaned = []
    await hub.start()
    def failing_cleanup():
        raise OSError("failed resource cleanup")
    first = hub.subscribe(MonitorKey.make("poll", "one", namespace="plugin"), "one", lambda: None,
                          interval=60, immediate=False, cleanup=failing_cleanup)
    second = hub.subscribe(MonitorKey.make("poll", "two", namespace="plugin"), "two", lambda: None,
                           interval=60, immediate=False, cleanup=lambda: cleaned.append("two"))
    try:
        hub.revoke_namespace("plugin")
        await until(lambda: first.done() and second.done() and cleaned == ["two"])
        assert not hub.snapshot()["sources"]
    finally:
        await hub.close()
        resources.close()


@run_async
async def test_consumer_can_close_its_own_subscription():
    resources = ControlResources()
    hub = SharedMonitorHub(resources)
    closed = []
    await hub.start()
    async def consume(value):
        await subscription.close()
        closed.append(value)
    subscription = hub.subscribe(MonitorKey.make("poll", "once", namespace="plugin"), "plugin",
                                 lambda: "result", consume=consume, interval=60)
    try:
        await until(lambda: closed == ["result"])
        assert subscription.done() and not hub.sources
    finally:
        await hub.close()
        resources.close()


@run_async
async def test_busy_namespace_cannot_occupy_every_monitor_slot():
    resources = ControlResources()
    hub = SharedMonitorHub(resources)
    hub.limit, hub.per_namespace = 2, 1
    release, calls = asyncio.Event(), []
    await hub.start()
    async def collect(name):
        calls.append(name)
        await release.wait()
    for i, namespace in enumerate(("busy", "busy", "busy", "other")):
        async def callback(name=f"{namespace}-{i}"):
            await collect(name)
        hub.subscribe(MonitorKey.make("poll", str(i), namespace=namespace), str(i), callback, interval=60)
    try:
        await until(lambda: len(calls) == 2)
        assert calls == ["busy-0", "other-3"]
        assert hub.snapshot()["active"] == 2
    finally:
        release.set()
        await hub.close()
        resources.close()
