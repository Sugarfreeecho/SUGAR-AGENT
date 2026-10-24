"""Isolated regressions for the Bilibili duty scheduler and task lifecycle.

No real sessions, credentials, model requests, or Bilibili writes are used.
"""
import asyncio
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "sugar-bili-scroll"


@pytest.fixture
def host(monkeypatch, tmp_path):
    name = "test_sugar_bili_scroll_host"
    spec = importlib.util.spec_from_file_location(name, PLUGIN_ROOT / "host.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.store_mod, "HOST_SERVICES", {})
    module._runtime["home"] = tmp_path / "data"
    module._runtime["plugin"] = SimpleNamespace(plugin_id=module.PLUGIN_ID)
    module._home().mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "_settings", lambda *args: {"daily_quota": 3})
    return module


def test_scheduler_executes_due_task_after_reserving_busy(host, monkeypatch):
    row = host.tasks_mod.new_row(name="教程", valley_windows="00:00-23:59")
    host.tasks_mod.save(host._home(), [row])
    monkeypatch.setattr(host, "datetime", SimpleNamespace(now=lambda: datetime(2026, 10, 23, 12)))
    monkeypatch.setattr(host, "bili_client", SimpleNamespace(load_credential=lambda home: object()))
    import plugins.host as plugin_host
    monkeypatch.setattr(plugin_host, "bundled_host_plugin_enabled", lambda pid: True)
    calls = []

    def run_once(**kwargs):
        assert host._runtime["busy"] is True
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(host, "run_once", run_once)

    async def one_tick():
        sleeps = 0

        async def sleep(seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps > 1:
                raise asyncio.CancelledError

        monkeypatch.setattr(host.asyncio, "sleep", sleep)
        with pytest.raises(asyncio.CancelledError):
            await host._scheduler()

    asyncio.run(one_tick())
    assert calls == [{"manual": False, "task_id": row["id"]}]
    assert host._runtime["busy"] is False


def test_scan_does_not_start_another_round_while_busy(host):
    host.tasks_mod.save(host._home(), [host.tasks_mod.new_row(valley_windows="00:00-23:59")])
    host._runtime["busy"] = True
    calls = []
    result = host.scan_tasks(now=datetime(2026, 10, 23, 12), runner=lambda tid: calls.append(tid))
    assert result["ran"] == ""
    assert calls == []


def test_task_session_is_saved_and_reused_on_next_round(host, monkeypatch):
    row = host.tasks_mod.new_row(name="教程")
    host.tasks_mod.save(host._home(), [row])
    created = []
    contexts = []

    def create(*args, **kwargs):
        sid = "session-" + str(len(created) + 1)
        created.append(sid)
        return (sid, None)

    manager = SimpleNamespace(
        get_session_summary=lambda sid: {"id": sid} if sid in created else None,
        get_or_create_session=create,
        set_session_name=lambda *args: None,
        set_session_system_context=lambda *args, **kwargs: contexts.append(args),
    )
    monkeypatch.setitem(sys.modules, "agent_harness", SimpleNamespace(session_manager=manager))
    monkeypatch.setattr(host, "build_system_context", lambda task_home=None: "固定章程")
    first = host._ensure_task_session(host._task_row(row["id"]), {})
    saved = host._task_row(row["id"])
    assert saved["session_id"] == first
    second = host._ensure_task_session(saved, {})
    assert second == first
    assert created == [first]
    assert "本条任务" in contexts[-1][1]


def test_deleting_last_task_does_not_recreate_legacy_task(host):
    host.tasks_mod.migrate_from_settings(host._home(), {"keywords": "旧关键词"})
    host.tasks_mod.save(host._home(), [])
    assert host._task_rows() == []
    assert json.loads(host.tasks_mod.tasks_file(host._home()).read_text(encoding="utf-8")) == {"tasks": []}


@pytest.mark.parametrize("task_id,disabled", [("missing", False), ("", True)])
def test_missing_or_disabled_task_never_runs_a_different_task(host, monkeypatch, task_id, disabled):
    host.tasks_mod.save(host._home(), [host.tasks_mod.new_row(name="别的任务", enabled=not disabled)])
    calls = []
    monkeypatch.setattr(host, "_ensure_task_session", lambda *args: calls.append(args) or "unwanted-session")
    monkeypatch.setattr(host, "_run_round_blocking", lambda *args, **kwargs: calls.append(args))
    result = host.run_once(manual=True, task_id=task_id)
    assert result["ok"] is False
    assert calls == []


def test_legacy_migration_preserves_zero_quota_and_interval(host):
    rows = host.tasks_mod.migrate_from_settings(host._home(), {
        "daily_quota": 0, "min_interval_minutes": 0, "keywords": "测试",
    })
    assert rows[0]["daily_quota"] == 0
    assert rows[0]["min_interval_minutes"] == 0


def test_cold_tool_instance_uses_host_storage(host, monkeypatch, tmp_path):
    monkeypatch.setenv("PLUGIN_STORAGE_DIR", str(tmp_path / "storage"))
    host._runtime.update(home=None, plugin=None)
    calls = []

    async def search(keyword, num, order):
        calls.append((keyword, num, order))
        return {"videos": [], "count": 0}

    monkeypatch.setattr(host, "bili_client", SimpleNamespace(search_videos=search, dumps=json.dumps))
    context = SimpleNamespace(service=lambda key: "bili_search")
    result = asyncio.run(host._invoke(context, {"keyword": "测试"}))
    assert calls == [("测试", 10, "totalrank")]
    assert host._home() == tmp_path / "storage" / host.PLUGIN_ID / "data"
    assert result.kind.value == "completed"
