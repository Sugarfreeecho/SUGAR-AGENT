"""Real host invokers, caller ceilings, durable scheduling and native settings."""
import dataclasses
import json

import pytest

import builtin_host_tools  # registers the production invokers
from host_tool_registry import HostToolInvocationContext, host_tool_invokers
from session_control.configuration import filter_registry, runtime_scope, validate_config
from session_control.model_tools import TOOL_DEFINITIONS
from session_control.policy import Principal, validate_policy
from tests.test_schedule_settings import native
from tests.test_session_control import composed, new_session, run_async
from tool_registry import ToolOutcomeKind, ToolRegistry


def context(c, sid, call="create"):
    return HostToolInvocationContext(session_id=sid, run_id="user-run", tool_call_id=call,
        services={"session_manager": c.manager, "security_workspace": c.root})


async def tool(ctx, args, *, read=False):
    outcome = await host_tool_invokers.invoke("scheduled_tasks" if read else "manage_scheduled_task", ctx, args)
    assert outcome.kind is ToolOutcomeKind.COMPLETED, outcome.to_dict()
    return json.loads(outcome.content)


def definition(**overrides):
    return {"action": "create", "name": "每天整理进展", "instructions": "整理项目进展，有异常时提醒我。",
            "trigger": {"kind": "daily", "time": "09:00", "time_zone": "Asia/Shanghai"}, **overrides}


@run_async
async def test_model_created_schedule_is_visible_editable_and_executable_in_native_settings(composed, monkeypatch):
    import session_control.integration as integration
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    sid = await new_session(c)
    await c.control.start()
    ctx = context(c, sid)
    try:
        created = await tool(ctx, definition())
        assert created["target"] == {"mode": "existing", "session_id": sid}
        assert created["trigger"] == {"kind": "cron", "expression": "0 9 * * *", "time_zone": "Asia/Shanghai"}
        assert created["next_run_at_iso"].endswith("+08:00")
        assert created["notification"] == "important" and created["settings_section"] == "schedules"
        assert (await tool(ctx, definition()))["id"] == created["id"]
        page = (await native(c, "automation.list")).json()["data"]["items"]
        assert [row["id"] for row in page] == [created["id"]]
        listed = await tool(ctx, {"action": "list"}, read=True)
        assert listed["items"][0]["id"] == created["id"]
        current = await tool(ctx, {"action": "get", "id": created["id"]}, read=True)
        human_edit = await native(c, "automation.update", {"id": current["id"], "expected_revision": current["revision"], "name": "人工修改名称"})
        assert human_edit.status_code == 200
        current = await tool(ctx, {"action": "get", "id": created["id"]}, read=True)
        assert current["name"] == "人工修改名称" and current["owner"] == created["owner"]
        paused = await tool(context(c, sid, "pause"), {"action": "pause", "id": current["id"], "expected_revision": current["revision"]})
        assert not paused["enabled"]
        stale = await host_tool_invokers.invoke("manage_scheduled_task", context(c, sid, "stale"),
            {"action": "update", "id": current["id"], "expected_revision": current["revision"], "name": "过期写入"})
        assert stale.code == "revision_conflict"
        resumed = await tool(context(c, sid, "resume"), {"action": "resume", "id": paused["id"], "expected_revision": paused["revision"]})
        edited = await tool(context(c, sid, "edit"), {"action": "update", "id": resumed["id"], "expected_revision": resumed["revision"], "instructions": "生成简短报告"})
        assert edited["action"]["text"] == "生成简短报告"
        assert edited["next_run_at"] == created["next_run_at"]
        run = await tool(context(c, sid, "run"), {"action": "run", "id": created["id"]})
        result, _ = await c.service.execute(c.admin, "operation.wait", {"id": run["execution_id"], "timeout": 5})
        assert result["status"] == "succeeded" and c.calls[0][1] == "生成简短报告"
        history = await tool(ctx, {"action": "history", "id": created["id"]}, read=True)
        assert history["executions"][0]["operation_id"] == run["execution_id"]
        # Human settings can manage the same object, even though its owner is
        # the scoped Agent identity rather than native:schedules.
        deleted = await native(c, "automation.delete", {"id": edited["id"], "expected_revision": edited["revision"]})
        assert deleted.status_code == 200
        assert (await tool(ctx, {"action": "list"}, read=True))["items"] == []
    finally:
        await c.control.close()


@run_async
async def test_new_chat_schedule_retains_tool_budget_and_explicit_keys_across_runs(composed, monkeypatch):
    import session_control.integration as integration
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    sid = await new_session(c)
    await c.control.start()
    ceiling = validate_config({"tools": {"mode": "custom", "allow": []}, "limits": {"max_tool_calls": 2}})
    ctx = context(c, sid)
    args = definition(new_chat=True, idempotency_key="daily-review")
    try:
        with runtime_scope(sid, ceiling):
            created = await tool(ctx, args)
            replay = await tool(dataclasses.replace(ctx, run_id="another-run", tool_call_id="another-call"), args)
        assert replay["id"] == created["id"] and created["target"] == {"mode": "new"}
        await native(c, "automation.update", {"id": created["id"], "expected_revision": created["revision"], "name": "Human rename"})
        for i in range(2):
            run = await tool(context(c, sid, "run-" + str(i)), {"action": "run", "id": created["id"]})
            result, _ = await c.service.execute(c.admin, "operation.wait", {"id": run["execution_id"], "timeout": 5})
            assert result["status"] == "succeeded"
        assert len({call[0] for call in c.calls}) == 2
        assert all(call[2]["tools"]["allow"] == [] and call[2]["limits"]["max_tool_calls"] == 2 for call in c.calls)
    finally:
        await c.control.close()


PAIRING_CAPABILITIES = ["read", "session.create", "session.send",
    *("automation." + action for action in ("list", "get", "history", "create", "update", "pause", "resume", "run", "delete"))]


@run_async
async def test_trusted_browser_pairing_creates_and_owns_its_schedule(composed, monkeypatch):
    import session_control.integration as integration
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    sid = await new_session(c)
    await c.control.start()
    def pairing(identity):
        return Principal(identity, policy=validate_policy({"scope": "all", "capabilities": PAIRING_CAPABILITIES},
                                                          workspace=str(c.root), current_session=sid))
    parent, other = pairing("paired-browser"), pairing("other-browser")
    try:
        with runtime_scope(sid, validate_config({}), principal=parent):
            created = await tool(context(c, sid), definition())
        assert created["owner"] == "paired-browser"
        assert created["target"] == {"mode": "existing", "session_id": sid}
        with runtime_scope(sid, validate_config({}), principal=parent):
            listed = await tool(context(c, sid, "list"), {"action": "list"}, read=True)
        assert [row["id"] for row in listed["items"]] == [created["id"]]
        with runtime_scope(sid, validate_config({}), principal=other):
            assert (await tool(context(c, sid, "other-list"), {"action": "list"}, read=True))["items"] == []
    finally:
        await c.control.close()


@run_async
async def test_revoked_creator_blocks_later_dispatch_even_after_human_edits(composed, monkeypatch):
    import session_control.integration as integration
    from session_control.errors import ControlError
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    sid = await new_session(c)
    await c.control.start()
    parent = Principal("granted-agent", policy=validate_policy({"capabilities": ["read", "automation.create", "session.send", "session.create"]}, workspace=str(c.root)))
    token = c.control.identities.issue(parent)
    parent = c.control.identities.authenticate(token)
    try:
        with runtime_scope(sid, validate_config({}), principal=parent):
            created = await tool(context(c, sid), definition())
        edited = await native(c, "automation.update", {"id": created["id"], "expected_revision": created["revision"], "name": "Human rename"})
        assert edited.status_code == 200
        c.control.identities.revoke(token)
        with pytest.raises(ControlError) as exc:
            await c.service.engine.fire(c.store.get("automations", created["id"]), "manual-test", 0., manual=True)
        assert exc.value.code == "unauthorized" and not c.calls
    finally:
        await c.control.close()


@run_async
async def test_manual_run_intersects_the_current_callers_tool_budget(composed, monkeypatch):
    import session_control.integration as integration
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    sid = await new_session(c)
    await c.control.start()
    try:
        created = await tool(context(c, sid), definition())
        ceiling = validate_config({"tools": {"mode": "custom", "allow": []}, "limits": {"max_tool_calls": 2}})
        with runtime_scope(sid, ceiling):
            run = await tool(context(c, sid, "restricted-run"), {"action": "run", "id": created["id"]})
        result, _ = await c.service.execute(c.admin, "operation.wait", {"id": run["execution_id"], "timeout": 5})
        assert result["status"] == "succeeded"
        assert c.calls[0][2]["tools"]["allow"] == [] and c.calls[0][2]["limits"]["max_tool_calls"] == 2
    finally:
        await c.control.close()


@pytest.mark.parametrize("attempt", ["no_capability", "outside", "readonly", "forge", "event", "foreign_task", "revoked"])
@run_async
async def test_model_tool_cannot_expand_origin_authority(composed, monkeypatch, attempt):
    import session_control.integration as integration
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    sid = await new_session(c)
    ctx, args, parent, cfg = context(c, sid), definition(), None, validate_config({})
    await c.control.start()
    try:
        if attempt == "no_capability":
            parent = Principal("limited", policy=validate_policy({}, workspace=str(c.root), current_session=sid))
        elif attempt == "outside":
            other_dir = c.root / "outside"
            other_dir.mkdir()
            args["session_id"] = await new_session(c, work_dir=str(other_dir))
        elif attempt == "readonly":
            cfg = validate_config({"read_only": True})
        elif attempt == "forge":
            args["policy"] = {"scope": "all"}
        elif attempt == "event":
            args["trigger"] = {"kind": "event", "types": ["run.ended"]}
        elif attempt == "foreign_task":
            foreign = (await native(c, "automation.create", {"name": "Human task", "trigger": {"kind": "interval", "seconds": 3600},
                "target": {"mode": "existing", "session_id": sid}, "action": {"kind": "prompt", "text": "work"}})).json()["data"]
            args = {"action": "delete", "id": foreign["id"], "expected_revision": foreign["revision"]}
        elif attempt == "revoked":
            parent = Principal("delegated", policy=validate_policy({"capabilities": ["read", "automation.create", "session.send", "session.create"]}, workspace=str(c.root)))
            token = c.control.identities.issue(parent)
            parent = c.control.identities.authenticate(token)
            c.control.identities.revoke(token)
        with runtime_scope(sid, cfg, principal=parent):
            result = await host_tool_invokers.invoke("manage_scheduled_task", ctx, args)
        assert result.kind is ToolOutcomeKind.FAILED, result.to_dict()
        assert not [row for row in c.store.list("automations") if row["owner"].startswith("agent-schedules:")]
        if attempt == "foreign_task":
            assert not c.store.get("automations", foreign["id"]).get("deleted")
    finally:
        await c.control.close()


def test_tools_are_discoverable_and_readonly_filter_keeps_only_the_query_tool(tmp_path):
    from agent_tools import OPENAI_TOOL_DEFINITIONS
    from security.runtime import classify_tool
    from tool_search import RESIDENT_TOOLS
    from user_presentations import prepare_presentation
    registry = ToolRegistry()
    for definition in TOOL_DEFINITIONS:
        name = definition["function"]["name"]
        assert name in RESIDENT_TOOLS and definition in OPENAI_TOOL_DEFINITIONS
        registry.register_definition(definition, invocation_kind="host_service", owner="core.schedules", invoker_id=name,
                                     effect=host_tool_invokers.effect(name))
        request = classify_tool(name, {"action": "list" if name == "scheduled_tasks" else "create"}, tmp_path)
        assert request.effect == ("read" if name == "scheduled_tasks" else "workspace_write")
    filter_registry(registry, validate_config({"read_only": True}))
    assert registry.names() == {"scheduled_tasks"}
    assert prepare_presentation({"kind": "settings", "title": "定时任务", "section": "schedules"}, workspace=tmp_path)["section"] == "schedules"
