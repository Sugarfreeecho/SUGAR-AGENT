"""Hot reload must replace plugin HTTP handlers instead of stacking them.

``include_router`` copies route objects and FastAPI matches the first
registered path, so a reloaded adapter used to leave the previous handler in
front of the new one: the file changed, the HTTP behaviour did not. Each
bundled adapter is therefore installed twice under two content digests and
every path must stay registered exactly once.
"""
import asyncio
import inspect
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

RELOADED_ADAPTERS = (
    "acp-agents",
    "agent-goal",
    "agent-team",
    "change-review",
    "computer-use",
    "execution-tools",
    "thread-monitor",
)


class _SessionManager:
    """Only the attributes install() resolves eagerly; handlers stay unused."""

    def _resolve_session_path(self, session_id):
        return ROOT / "_unused_session"

    def _load_metadata(self, session_id):
        return {}

    def get_session_summary(self, session_id):
        return None

    def get_subagent_parent_id(self, session_id):
        return None

    def list_sessions(self, **_kwargs):
        return []


def _install_twice(plugin_id: str, work_dir: Path) -> set[str]:
    from plugins import load_plugin
    import plugins.host as hosts

    plugin = load_plugin(ROOT / "plugins" / plugin_id)
    app = FastAPI()
    context = {
        "session_manager": _SessionManager(),
        "project_root": ROOT,
        "work_dir": work_dir,
        "app": app,
    }
    for signature in ("digest-one", "digest-two"):
        changed = replace(plugin, content_signature=signature)
        hosts._module(changed).install(app, context, changed)
    # One path may legitimately carry several methods (GET + DELETE), so a
    # duplicate is the same path *and* the same method set.
    keys = [
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", ()) or ())))
        for route in app.routes
    ]
    return {key[0] for key in keys if keys.count(key) > 1}


@pytest.mark.parametrize("plugin_id", RELOADED_ADAPTERS)
def test_reload_replaces_plugin_routes(plugin_id, tmp_path, monkeypatch):
    monkeypatch.setenv("EXTENSION_REGISTRATION_APPROVAL_ENABLED", "0")
    assert _install_twice(plugin_id, tmp_path) == set()


def test_voice_adapter_rebuilds_service_and_routes_on_new_digest(tmp_path, monkeypatch):
    from plugins import load_plugin
    import plugins.host as hosts

    plugin = load_plugin(ROOT / "plugins" / "voice-input")
    monkeypatch.setattr(hosts, "bundled_host_plugin_enabled", lambda _plugin_id: True)
    app = FastAPI()
    context = {"app": app, "work_dir": tmp_path}

    first = replace(plugin, content_signature="digest-one")
    module = hosts._module(first)
    module.install(app, context, first)
    service = app.state.voice_input_service
    assert service is not None

    # Same digest: idempotent, no rebuild and no second route.
    module.install(app, context, first)
    assert app.state.voice_input_service is service
    assert sum(getattr(route, "path", "") == "/api/speech/status" for route in app.routes) == 1

    # New digest: rebuilt service, still exactly one route per path.
    module.install(app, context, replace(first, content_signature="digest-two"))
    assert app.state.voice_input_service is not service
    keys = [
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", ()) or ())))
        for route in app.routes
    ]
    assert keys.count(("/api/speech/status", ("GET",))) == 1
    assert all(keys.count(key) == 1 for key in keys)


def test_execution_tools_reload_keeps_running_jobs(tmp_path, monkeypatch):
    """A code reload must not close other sessions' jobs and terminals."""

    import execution_services.notifications as notifications
    import plugins.host as hosts
    from plugins import load_plugin

    stopped = []

    class _Service:
        jobs = {}
        terminals = SimpleNamespace(
            sessions={"t1": SimpleNamespace(owner="session-1", status="running")},
            openings={},
        )

        async def call(self, function, *args, **kwargs):
            result = function(*args, **kwargs)
            return await result if inspect.isawaitable(result) else result

        async def stop_owner(self, owner, **_kwargs):
            stopped.append(owner)

    async def _noop():
        return None

    plugin = load_plugin(ROOT / "plugins" / "execution-tools")
    module = hosts._module(replace(plugin, content_signature="digest-one"))
    context = {"session_manager": _SessionManager(), "app": FastAPI()}

    # The adapter binds execution_service at import time, so patch the module
    # global it actually reads rather than the execution_services attribute.
    monkeypatch.setattr(notifications, "stop_runner", _noop)
    monkeypatch.setattr(module, "execution_service", lambda _manager: _Service())

    # A newer digest already installed itself: this stop is a reload, keep jobs.
    context["app"].state.execution_tools_route_signature = "newer-digest"
    asyncio.run(module.stop(context, plugin))
    assert stopped == []

    # No newer adapter took over: this is a disable/uninstall, close owners.
    context["app"].state.execution_tools_route_signature = plugin.content_signature
    asyncio.run(module.stop(context, plugin))
    assert stopped == ["session-1"]
