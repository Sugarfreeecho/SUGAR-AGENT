"""Plugin refresh must preserve unrelated execution and explicit user stops."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from execution_services.jobs import ExecutionService
from plugins import load_plugin
import plugins.host as host


@pytest.fixture
def execution_plugin(monkeypatch):
    plugin = load_plugin(ROOT / "plugins" / "execution-tools")
    module = host._module(plugin)
    service = ExecutionService()
    monkeypatch.setattr(host, "_STARTED", [])
    monkeypatch.setattr(host, "_LIFECYCLE_LOCK", asyncio.Lock())
    monkeypatch.setattr(module, "execution_service", lambda manager: service)

    async def no_runner(*args):
        pass

    monkeypatch.setattr("execution_services.notifications.start_runner", no_runner)
    monkeypatch.setattr("execution_services.notifications.stop_runner", no_runner)
    return plugin, module, service, {"session_manager": None}


@pytest.mark.parametrize("status", ["completed", "killed", "running"])
def test_unrelated_plugin_refresh_preserves_execution(execution_plugin, tmp_path, status):
    plugin, module, service, context = execution_plugin
    other = load_plugin(ROOT / "plugins" / "web-search-providers")

    async def run():
        try:
            await host.start_bundled_host_extensions([plugin, other], context)
            identifier = await service.call(service.spawn_process, "owner", {
                "argv": [sys.executable, "-c", "import time; time.sleep(30)" if status != "completed" else "print('done')"],
                "cwd": str(tmp_path), "env": dict(os.environ), "label": "refresh regression",
            }, visible=True)
            if status == "killed":
                await service.call(service.kill, "owner", identifier)
            if status != "running":
                result = await service.call(service.output, "owner", identifier, True, 5000)
                assert result["job"]["status"] == status
            thread = service._thread
            # Disabling, enabling, and repeating a no-op refresh all retain execution.
            for loaded in ([plugin], [other, plugin], [other, plugin]):
                await host.start_bundled_host_extensions(loaded, context)
                assert service._thread is thread
                assert "owner" not in service.suppressed
                assert service.jobs[identifier].status == status
            admitted = await service.call(service.admit, "owner", "process", "after refresh", visible=False)
            await service.call(service.settle, admitted)
        finally:
            await host.stop_bundled_host_extensions(context)
            await service.shutdown()

    asyncio.run(run())


@pytest.mark.parametrize("status", ["completed", "failed", "killed"])
def test_execution_disable_ignores_finished_resources(execution_plugin, status):
    plugin, module, service, context = execution_plugin

    async def run():
        try:
            job = await service.call(service.admit, "history", "process", "old job")
            await service.call(service.settle, job, status)
            await module.stop(context, plugin)
            assert "history" not in service.suppressed
            assert "history" not in service.closed_owners
        finally:
            await service.shutdown()

    asyncio.run(run())


@pytest.mark.parametrize("actor", ["model", "user"])
def test_refresh_and_disable_handle_terminals_without_jobs(execution_plugin, tmp_path, actor):
    pytest.importorskip("pyte")
    pytest.importorskip("winpty" if os.name == "nt" else "ptyprocess")
    from execution_services.terminals import terminal_manager

    plugin, _, service, context = execution_plugin
    other = load_plugin(ROOT / "plugins" / "web-search-providers")
    terminals = terminal_manager(service)

    async def run():
        try:
            await host.start_bundled_host_extensions([plugin, other], context)
            opened = await service.call(terminals.open, "owner", cwd=str(tmp_path), actor=actor)
            assert not service.jobs
            await host.start_bundled_host_extensions([plugin], context)
            session = terminals.sessions[opened["id"]]
            assert session.status == "running"
            assert session.backend.isalive()
            assert "owner" not in service.suppressed
            await host.start_bundled_host_extensions([], context)
            assert session.status == "closed"
            assert "owner" in service.suppressed
            await host.start_bundled_host_extensions([plugin], context)
            assert "owner" not in service.suppressed
            assert "owner" not in service.closed_owners
            # A later disable must ignore this now-closed historical terminal.
            await host.start_bundled_host_extensions([], context)
            assert "owner" not in service.suppressed
            assert "owner" not in service.closed_owners
        finally:
            await host.stop_bundled_host_extensions(context)
            await service.shutdown()

    asyncio.run(run())


def test_execution_disable_waits_for_terminal_startup(execution_plugin, tmp_path, monkeypatch):
    backend_module = pytest.importorskip("winpty" if os.name == "nt" else "ptyprocess")
    pytest.importorskip("pyte")
    from execution_services.terminals import terminal_manager

    plugin, module, service, context = execution_plugin
    creating, release = threading.Event(), threading.Event()
    closed = []
    backend = SimpleNamespace(close=lambda force: closed.append(force))

    def spawn(*args, **kwargs):
        creating.set()
        assert release.wait(5)
        return backend

    backend_type = backend_module.PtyProcess if os.name == "nt" else backend_module.PtyProcessUnicode
    monkeypatch.setattr(backend_type, "spawn", spawn)
    terminals = terminal_manager(service)

    async def run():
        try:
            opening = asyncio.create_task(service.call(terminals.open, "owner", cwd=str(tmp_path), actor="user"))
            assert await asyncio.to_thread(creating.wait, 3)
            stopping = asyncio.create_task(module.stop(context, plugin))
            await asyncio.sleep(.1)
            assert not stopping.done()
            release.set()
            await asyncio.wait_for(stopping, 5)
            with pytest.raises(asyncio.CancelledError):
                await opening
            assert closed == [True]
            assert not terminals.sessions
            assert not terminals.openings
            await module.start(context, plugin)
            assert "owner" not in service.suppressed
            assert "owner" not in service.closed_owners
        finally:
            release.set()
            await service.shutdown()

    asyncio.run(run())


def test_execution_reenable_retains_user_stop_with_active_terminal(execution_plugin, tmp_path):
    pytest.importorskip("pyte")
    pytest.importorskip("winpty" if os.name == "nt" else "ptyprocess")
    from execution_services.terminals import terminal_manager

    plugin, module, service, context = execution_plugin
    terminals = terminal_manager(service)

    async def run():
        try:
            opened = await service.call(terminals.open, "owner", cwd=str(tmp_path))
            await service.call(service.stop_owner, "owner")
            await module.stop(context, plugin)
            assert terminals.sessions[opened["id"]].status == "closed"
            await module.start(context, plugin)
            assert "owner" in service.suppressed
            assert "owner" not in service.closed_owners
            with pytest.raises(RuntimeError, match="stopped"):
                await service.call(terminals.open, "owner", cwd=str(tmp_path))
        finally:
            await service.shutdown()

    asyncio.run(run())


@pytest.mark.parametrize("explicit_stop", ["before_disable", "during_disable", None])
def test_execution_reenable_only_resumes_plugin_stops(execution_plugin, explicit_stop):
    plugin, module, service, context = execution_plugin

    async def run():
        try:
            await module.start(context, plugin)
            job = await service.call(service.admit, "owner", "process", "active")

            async def cancel():
                await service.settle(job, "killed")

            job.cancel = cancel
            if explicit_stop == "before_disable":
                await service.call(service.stop_owner, "owner")
            await module.stop(context, plugin)
            if explicit_stop == "during_disable":
                await service.call(service.stop_owner, "owner", close_terminals=True, reason="session_deleted")
            await module.start(context, plugin)
            assert ("owner" in service.suppressed) == bool(explicit_stop)
            assert ("owner" in service.closed_owners) == (explicit_stop == "during_disable")
            if explicit_stop:
                with pytest.raises(RuntimeError, match="stopped"):
                    await service.call(service.admit, "owner", "process", "still stopped")
            else:
                resumed = await service.call(service.admit, "owner", "process", "resumed")
                await service.call(service.settle, resumed)
            assert job.status == "killed"
        finally:
            await service.shutdown()

    asyncio.run(run())


def test_service_restart_resets_lifetime_stop_state():
    service = ExecutionService()

    async def run():
        try:
            await service.call(service.stop_owner, "old-owner", close_terminals=True)
            service.start()  # An idempotent start must retain an explicit stop.
            assert "old-owner" in service.suppressed
            await service.shutdown()
            service.start()  # A new service loop must not inherit stale stop state.
            assert not service.suppressed
            assert not service.closed_owners
            admitted = await service.call(service.admit, "old-owner", "process", "new lifetime")
            await service.call(service.settle, admitted)
        finally:
            await service.shutdown()

    asyncio.run(run())


def test_refresh_restarts_only_changed_extensions(execution_plugin, monkeypatch):
    plugin, _, _, context = execution_plugin
    other = replace(plugin, plugin_id="other", content_signature="v1")
    changed = replace(other, content_signature="v2")
    calls = []

    def module_for(item):
        key = (item.plugin_id, item.content_signature)
        return SimpleNamespace(start=lambda *_: calls.append(("start", key)),
                               stop=lambda *_: calls.append(("stop", key)))

    monkeypatch.setattr(host, "_module", module_for)

    async def run():
        await host.start_bundled_host_extensions([plugin, other], context)
        calls.clear()
        await host.start_bundled_host_extensions([changed, plugin], context)
        assert calls == [("stop", (other.plugin_id, "v1")), ("start", (other.plugin_id, "v2"))]
        calls.clear()
        await host.stop_bundled_host_extensions(context)
        assert calls == [("stop", (other.plugin_id, "v2")), ("stop", (plugin.plugin_id, plugin.content_signature))]
        assert not host._STARTED

    asyncio.run(run())


def test_failed_refresh_keeps_successful_starts_tracked(execution_plugin, monkeypatch):
    plugin, _, _, context = execution_plugin
    broken = replace(plugin, plugin_id="broken")
    calls = []

    def start(_, item):
        if item.plugin_id == "broken":
            raise RuntimeError("startup failed")
        calls.append("start")

    monkeypatch.setattr(host, "_module", lambda _: SimpleNamespace(start=start, stop=lambda *_: calls.append("stop")))

    async def run():
        with pytest.raises(RuntimeError, match="startup failed"):
            await host.start_bundled_host_extensions([plugin, broken], context)
        assert [item.plugin_id for item, _ in host._STARTED] == [plugin.plugin_id]
        await host.start_bundled_host_extensions([plugin], context)
        assert calls == ["start"]
        await host.stop_bundled_host_extensions(context)
        assert calls == ["start", "stop"]

    asyncio.run(run())


def test_concurrent_refresh_does_not_start_extensions_twice(execution_plugin, monkeypatch):
    plugin, _, _, context = execution_plugin
    calls = []

    async def start(*_):
        calls.append("start")
        await asyncio.sleep(.01)

    monkeypatch.setattr(host, "_module", lambda _: SimpleNamespace(start=start, stop=lambda *_: calls.append("stop")))

    async def run():
        await asyncio.gather(*(host.start_bundled_host_extensions([plugin], context) for _ in range(3)))
        assert calls == ["start"]
        await host.stop_bundled_host_extensions(context)
        assert calls == ["start", "stop"]

    asyncio.run(run())


def test_plugin_toggle_api_preserves_running_job(execution_plugin, monkeypatch):
    import agent_extensions
    import webui
    import workflow_extensions

    plugin, _, service, context = execution_plugin
    other = load_plugin(ROOT / "plugins" / "web-search-providers")
    state = {"enabled": True}

    def set_enabled(plugin_id, enabled):
        assert plugin_id == other.plugin_id
        state["enabled"] = enabled
        return state

    async def no_background_services(**kwargs):
        pass

    async def request_json():
        return {"enabled": False}

    monkeypatch.setattr(agent_extensions, "set_plugin_enabled", set_enabled)
    monkeypatch.setattr(agent_extensions, "load_plugins", lambda **_: SimpleNamespace(
        plugins=[plugin, other] if state["enabled"] else [plugin]))
    monkeypatch.setattr(agent_extensions, "start_plugin_background_services", no_background_services)
    monkeypatch.setattr(host, "install_bundled_host_extensions", lambda *args: None)
    monkeypatch.setattr(workflow_extensions, "activate_bundled_workflow_callbacks", lambda *args, **kwargs: None)
    monkeypatch.setattr(webui.agent_mcp, "force_reload", no_background_services)
    monkeypatch.setattr(webui, "session_manager", None)

    async def run():
        try:
            await host.start_bundled_host_extensions([plugin, other], context)
            job = await service.call(service.admit, "owner", "process", "running job")
            response = await webui.set_plugin_enabled_api(other.plugin_id, SimpleNamespace(json=request_json))
            assert response.status_code == 200, response.body
            assert state == {"enabled": False}
            assert job.status == "running"
            assert "owner" not in service.suppressed
            await service.call(service.settle, job)
        finally:
            await host.stop_bundled_host_extensions(context)
            await service.shutdown()

    asyncio.run(run())
