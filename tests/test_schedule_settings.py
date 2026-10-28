"""Native schedule settings use the durable service without browser credentials."""
import asyncio
import time
from datetime import datetime

import httpx
import pytest

from tests.test_session_control import composed, new_session, run_async


async def native(c, method, params=None, key=None, headers=None, host="127.0.0.1"):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app, client=(host, 12345)), base_url="http://127.0.0.1") as client:
        return await client.post("/api/settings/session-control", headers={"Origin": "http://127.0.0.1", "X-MyAgent-Settings": "schedules", **(headers or {})},
            json={"method": method, "params": params or {}, "idempotency_key": key or method + ":" + str(time.time_ns())})


@run_async
async def test_settings_adapter_requires_local_same_origin_and_limits_methods(composed):
    c = composed
    for headers, host in [({"Origin": "https://evil.example"}, "127.0.0.1"),
                          ({"X-Forwarded-For": "10.0.0.1"}, "127.0.0.1"), ({}, "10.0.0.1"),
                          ({"X-MyAgent-Settings": ""}, "127.0.0.1")]:
        assert (await native(c, "automation.list", headers=headers, host=host)).status_code == 403
    assert (await native(c, "session.delete", {"session_id": "anything"})).status_code == 403
    assert (await native(c, "automation.list", {"_principal": {"admin": True}})).status_code == 400
    assert (await native(c, "automation.list")).json()["data"] == {"items": []}
    await c.control.close()


@run_async
async def test_dispatch_failure_is_visible_and_notified_once(composed):
    c = composed
    sid = await new_session(c)
    task = (await native(c, "automation.create", {"name": "Deleted target", "notification": "important",
        "trigger": {"kind": "interval", "seconds": 3600}, "target": {"mode": "existing", "session_id": sid},
        "action": {"kind": "prompt", "text": "work"}})).json()["data"]
    c.store.put("automations", task["id"], {**c.store.get("automations", task["id"]), "next_run_at": time.time() - 1})
    c.manager.delete_session(sid)
    notices = []
    c.service.callbacks["notify_automation"] = lambda *args: notices.append(args)
    await c.service.engine.tick()
    assert c.store.get("automations", task["id"])["enabled"] is False
    assert c.store.get("automations", task["id"])["last_error"]
    assert len(notices) == 1 and notices[0][1]["status"] == "failed"
    await c.service.engine.tick()
    assert len(notices) == 1
    await c.control.close()


@run_async
async def test_schedule_settings_share_cli_store_config_and_execution(composed):
    c = composed
    sid = await new_session(c)
    definition = {"name": "Daily review", "trigger": {"kind": "daily", "time": "09:00", "time_zone": "Asia/Shanghai"},
        "target": {"mode": "existing", "session_id": sid}, "action": {"kind": "prompt", "text": "Review work"},
        "notification": "important", "runtime_override": {"system_prompt": {"mode": "replace", "text": "Review charter"},
        "tools": {"mode": "custom", "allow": []}, "read_only": True, "limits": {"max_tool_calls": 2}},
        "end_local": {"local_at": "2030-04-01T09:00", "time_zone": "Asia/Shanghai"}}
    response = await native(c, "automation.create", definition, key="create")
    assert response.status_code == 200, response.text
    task = response.json()["data"]
    assert c.store.get("automations", task["id"])["notification"] == "important"
    assert datetime.fromtimestamp(task["end_at"]).timestamp() == datetime.fromisoformat("2030-04-01T09:00+08:00").timestamp()
    shared, _ = await c.service.execute(c.admin, "automation.list", {"kind_filter": "schedule"})
    assert shared["items"][0]["id"] == task["id"]
    run = await native(c, "automation.run", {"id": task["id"]}, key="manual")
    oid = run.json()["data"]["execution_id"]
    result, _ = await c.service.execute(c.admin, "operation.wait", {"id": oid, "timeout": 3})
    assert result["status"] == "succeeded"
    assert c.calls[0][2]["system_prompt"]["text"] == "Review charter"
    assert c.calls[0][2]["tools"]["allow"] == [] and c.calls[0][2]["read_only"]
    assert c.store.get("automations", task["id"])["next_run_at"] == task["next_run_at"]
    conflict = await native(c, "automation.update", {"id": task["id"], "expected_revision": 0, "name": "stale"})
    assert conflict.status_code == 409
    paused = await native(c, "automation.pause", {"id": task["id"], "expected_revision": task["revision"]})
    assert paused.json()["data"]["enabled"] is False
    resumed = await native(c, "automation.resume", {"id": task["id"], "expected_revision": paused.json()["data"]["revision"]})
    assert resumed.json()["data"]["enabled"] is True
    for i in range(105):
        unrelated, _ = c.store.admit("other", "unrelated-" + str(i), "session.notice", {})
        c.store.update_operation(unrelated["id"], status="succeeded")
    history = await native(c, "automation.history", {"id": task["id"]})
    assert history.json()["data"]["executions"][0]["operation_id"] == oid
    assert history.json()["data"]["executions"][0]["created_at"] > 0
    await native(c, "automation.delete", {"id": task["id"]})
    assert (await native(c, "automation.list")).json()["data"]["items"] == []
    await c.control.close()


@run_async
async def test_one_shot_timezone_and_dst_gap_validation(composed):
    c = composed
    sid = await new_session(c)
    body = {"name": "once", "target": {"mode": "existing", "session_id": sid}, "action": {"kind": "prompt", "text": "work"}}
    good = await native(c, "automation.create", {**body, "trigger": {"kind": "at", "local_at": "2030-04-01T09:00", "time_zone": "Asia/Shanghai"}})
    assert good.status_code == 200, good.text
    assert good.json()["data"]["trigger"]["at"] == "2030-04-01T09:00:00+08:00"
    for trigger in [{"kind": "at", "local_at": "2030-03-10T02:30", "time_zone": "America/New_York"}, {"kind": "at", "local_at": "2030-04-01T09:00", "time_zone": "invalid"}]:
        assert (await native(c, "automation.create", {**body, "trigger": trigger})).status_code == 400
    await c.control.close()


@pytest.mark.parametrize("mode,status,expected", [("always", "succeeded", 1), ("important", "succeeded", 0), ("important", "failed", 1), ("never", "failed", 0)])
@run_async
async def test_notification_policy_is_durable_and_does_not_repeat(composed, mode, status, expected):
    from session_control.notifications import deliver_notifications
    c = composed
    sid = await new_session(c)
    task = (await native(c, "automation.create", {"name": "notify", "notification": mode,
        "trigger": {"kind": "interval", "seconds": 3600}, "target": {"mode": "existing", "session_id": sid},
        "action": {"kind": "prompt", "text": "work"}})).json()["data"]
    c.active[sid] = "browser"
    receipt = (await native(c, "automation.run", {"id": task["id"]})).json()["data"]
    c.store.update_operation(receipt["execution_id"], status=status)
    notices = []
    c.service.callbacks["notify_automation"] = lambda *args: notices.append(args)
    await deliver_notifications(c.service)
    await deliver_notifications(c.service)
    assert len(notices) == expected
    c.active.clear()
    await c.control.close()


@run_async
async def test_new_chat_runs_are_independent_and_waiting_notifications_survive_startup(composed):
    from session_control.notifications import deliver_notifications
    c = composed
    await c.control.start()
    task = (await native(c, "automation.create", {"name": "Fresh research", "notification": "always",
        "trigger": {"kind": "interval", "seconds": 3600}, "target": {"mode": "new"}, "workspace": str(c.root),
        "action": {"kind": "prompt", "text": "work"}, "runtime_override": {"tools": {"mode": "custom", "allow": []}}})).json()["data"]
    notices = []
    c.service.callbacks["notification_ready"] = lambda: False
    c.service.callbacks["notify_automation"] = lambda *args: notices.append(args)
    for attempt in range(2):
        run = (await asyncio.wait_for(native(c, "automation.run", {"id": task["id"]}, key=f"fresh-{attempt}"), 5)).json()["data"]
        result, _ = await c.service.execute(c.admin, "operation.wait", {"id": run["execution_id"], "timeout": 3})
        assert result["status"] == "succeeded"
    assert len(c.manager.list_sessions()) == 2
    assert len({call[0] for call in c.calls}) == 2
    assert all(call[2]["tools"]["allow"] == [] for call in c.calls)
    await deliver_notifications(c.service)
    assert not notices
    c.service.callbacks["notification_ready"] = lambda: True
    await deliver_notifications(c.service)
    assert len(notices) == 2
    await deliver_notifications(c.service)
    assert len(notices) == 2
    await c.control.close()


@run_async
async def test_important_notifications_cover_approval_but_skip_already_finished_requests(composed):
    from session_control.notifications import deliver_notifications
    c = composed
    sid = await new_session(c)
    task = (await native(c, "automation.create", {"name": "Needs approval", "notification": "important",
        "trigger": {"kind": "interval", "seconds": 3600}, "target": {"mode": "existing", "session_id": sid},
        "action": {"kind": "prompt", "text": "work"}})).json()["data"]
    c.active[sid] = "browser"
    run = (await native(c, "automation.run", {"id": task["id"]})).json()["data"]
    oid = run["execution_id"]
    c.store.append_operation_event(oid, {"type": "approval_requested", "approval_id": "approval-1"})
    c.store.append_operation_event(oid, {"type": "tool_approval_required", "approval_id": "approval-1"})
    notices = []
    c.service.callbacks["pending_human"] = lambda _: 1
    c.service.callbacks["notify_automation"] = lambda *args: notices.append(args)
    await deliver_notifications(c.service)
    assert len(notices) == 1 and notices[0][2] == "pending_human"
    c.store.append_operation_event(oid, {"type": "approval_requested", "approval_id": "already-resolved"})
    c.store.update_operation(oid, status="succeeded")
    await deliver_notifications(c.service)
    assert len(notices) == 1
    c.active.clear()
    await c.control.close()
