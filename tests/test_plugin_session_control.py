"""Real control-store integrations, with model and channel transports replaced."""
import asyncio
from types import SimpleNamespace

import pytest

from session_control.errors import ControlError
from session_control.public import host_client, source_state, transport_service
from tests.test_session_control import composed, new_session, run_async


@run_async
async def test_host_batches_are_atomic_durable_scoped_and_replayable(composed, monkeypatch):
    import session_control.integration as integration
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    one, two, forbidden = await new_session(c), await new_session(c), await new_session(c)
    await c.control.start()
    client = host_client("batch.demo", session_ids=[one, two], capabilities=["session.send", "session.send_batch"])
    c.active[one] = "browser"
    payload = {"requests": [{"session_id": one, "message": "one"}, {"session_id": two, "message": "two"}]}
    result = await asyncio.to_thread(client.blocking, "session.send_batch", payload, key="batch")
    replay = await client.call("session.send_batch", payload, key="batch")
    assert [op["operation_id"] for op in result["operations"]] == [op["operation_id"] for op in replay["operations"]]
    with pytest.raises(ControlError, match="different arguments"):
        await client.call("session.send_batch", {"requests": payload["requests"][:1]}, key="batch")
    with pytest.raises(ControlError, match="outside"):
        await client.call("session.send_batch", {"requests": [{"session_id": forbidden, "message": "no"}]}, key="forbidden")
    assert len([op for op in c.store.operations() if op["method"] == "session.send"]) == 2
    c.active.pop(one)
    completed = await client.wait(result["operations"][0]["operation_id"])
    assert completed["status"] == "succeeded"
    events = [row async for row in client.observe(completed["operation_id"])]
    assert any(row["type"] == "final" and row["content"] == "answer:one" for row in events)
    assert events[-1]["type"] == "operation.completed"
    source_state("batch.demo", False)
    with pytest.raises(ControlError, match="revoked"):
        await client.call("session.send", {"session_id": one, "message": "after revoke"}, key="revoked")
    await c.control.close()


@run_async
async def test_operation_http_stream_auth_replay_and_exact_completion(composed):
    import json
    import httpx
    from session_control.policy import Principal, validate_policy
    from tests.test_session_control import rpc
    c = composed
    sid = await new_session(c)
    owner = Principal("owner", policy=validate_policy({"capabilities": ["read", "session.send"]}, workspace=str(c.root)))
    token = c.control.identities.issue(owner)
    response = await rpc(c, "session.send", {"session_id": sid, "message": "owned"}, key="owned", token=token)
    oid = response.json()["operation_id"]
    await rpc(c, "operation.wait", {"id": oid, "timeout": 3}, token=token)
    path = f"/api/control/v1/operations/{oid}/events"
    other = c.control.identities.issue(Principal("other", policy=owner.policy))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url="http://127.0.0.1") as client:
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers={"Authorization": "Bearer " + other})).status_code == 403
        headers = {"Authorization": "Bearer " + token}
        stream = await client.get(path, headers=headers)
        assert stream.status_code == 200
        events = [json.loads(line) for line in stream.text.splitlines()]
        final = next(row for row in events if row["type"] == "final")
        assert final["content"] == "answer:owned"
        assert events[-1]["operation"]["operation_id"] == oid
        assert events[-1]["operation"]["content"] == "answer:owned"
        replay = await client.get(path, params={"cursor": final["cursor"]}, headers=headers)
        assert [json.loads(line)["type"] for line in replay.text.splitlines()] == ["operation.completed"]
        c.control.identities.revoke(token)
        assert (await client.get(path, headers=headers)).status_code == 401
    await c.control.close()


@run_async
async def test_delegated_creation_and_approval_queries_keep_parent_scope(composed, monkeypatch):
    import tool_approval_gate
    from session_control.policy import Principal, validate_policy
    c = composed
    allowed, outside = await new_session(c), await new_session(c)
    parent_policy = validate_policy({"capabilities": ["read", "session.create", "approval.list"]}, workspace=str(c.root))
    child = Principal("child", policy={"scope": "all", "capabilities": parent_policy["capabilities"]}, delegated_policies=[parent_policy])
    with pytest.raises(ControlError, match="Workspace is outside"):
        await c.service.execute(child, "session.create", {"work_dir": str(c.root / "outside")}, idempotency_key="outside")
    scoped = Principal("scoped", policy=validate_policy({"scope": "sessions", "session_ids": [allowed], "capabilities": ["approval.list"]}))
    monkeypatch.setattr(tool_approval_gate, "list_pending_approvals", lambda sid=None: [
        {"session_id": allowed, "approval_id": "yes"}, {"session_id": outside, "approval_id": "no"}])
    result, _ = await c.service.execute(scoped, "approval.list", {})
    assert [row["approval_id"] for row in result["approvals"]] == ["yes"]
    await c.control.close()


@run_async
async def test_feishu_outbox_recovers_admission_and_delivery_after_disconnect(composed, monkeypatch):
    import session_control.integration as integration
    from tests.test_feishu_adapter import _FakeSDK, _config
    from feishu_transport.adapter import FeishuTransportAdapter
    from feishu_transport.store import FeishuStateStore
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    sid = await new_session(c)
    await c.control.start()
    service = transport_service("feishu-transport")
    store = FeishuStateStore(c.root / "feishu")
    principal = {"device_id": "feishu:person", "name": "Feishu", "scopes": ["read", "write", "approvals"], "credential_kind": "feishu"}
    body = {"session_id": sid, "text": "durable", "operation_id": "", "cursor": 0, "principal": principal}
    store.track_delivery("message", body)
    from remote_control.store import DevicePrincipal
    p = DevicePrincipal(**{**principal, "scopes": frozenset(principal["scopes"])})
    receipt, _ = await service.execute(p, "session.send", {"session_id": sid, "message": "durable", "mode": "queue"}, idempotency_key="message")
    await service.execute(p, "operation.wait", {"id": receipt["operation_id"], "timeout": 5})
    sdk = _FakeSDK()
    sdk_reply = sdk.reply_text
    failures = [True]
    def reply(mid, text, **kwargs):
        if text == "answer:durable" and failures and failures.pop():
            raise OSError("channel disconnected")
        return sdk_reply(mid, text, **kwargs)
    sdk.reply_text = reply
    adapter = FeishuTransportAdapter(_config(c.root / "feishu"), service, store, sdk_transport=sdk)
    await adapter.pump_deliveries()
    assert len(c.calls) == 1
    # Restart the channel adapter, retain the same operation and pending reply.
    await asyncio.sleep(1.1)
    restored = FeishuTransportAdapter(_config(c.root / "feishu"), service, store, sdk_transport=sdk)
    await restored.pump_deliveries()
    assert [r[1] for r in sdk.replies] == ["已收到，正在处理。", "answer:durable"]
    assert not store.pending_deliveries()
    assert len(c.calls) == 1
    await c.control.close()


@run_async
async def test_business_binding_and_tool_override_share_backend_lifecycle(composed, monkeypatch):
    import session_control.integration as integration
    from session_control.public import ensure_host_session, register_source_lifecycle
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    await c.control.start()
    options = {"key": "business-thread", "name": "Business", "prompt": "private charter", "workspace": str(c.root)}
    sid = await asyncio.to_thread(ensure_host_session, "business", "", **options)
    assert await asyncio.to_thread(ensure_host_session, "business", sid, **options) == sid
    assert len(c.manager.list_sessions()) == 1
    before, after = [], []
    register_source_lifecycle("business", before=lambda sid, rid, p: before.append((sid, rid, p["_run_scope_context"])),
        after=lambda sid, rid, op: after.append((sid, rid, op["status"])))
    client = host_client("business", session_ids=[sid], capabilities=["session.send", "operation.cancel"])
    result = await client.run(sid, "work", key="business-message", allow=["read_file"], context={"mode": "reply"})
    replay = await client.run(sid, "different transport text after recovery", key="business-message", allow=[])
    assert result["operation_id"] == replay["operation_id"]
    assert len(c.calls) == 1 and c.calls[0][2]["system_prompt"]["text"] == "private charter"
    assert [ref["name"] for ref in c.calls[0][2]["tools"]["allow"]] == ["read_file"]
    await c.control.close()
    assert before == [(sid, result["run_id"], {"mode": "reply"})]
    assert after == [(sid, result["run_id"], "succeeded")]


@run_async
async def test_restored_domain_inputs_wait_for_lifecycle_and_refresh_keeps_other_sources(composed, monkeypatch):
    import session_control.integration as integration
    from session_control.public import register_source_lifecycle
    from plugin_host_services import release_all_plugin_leases
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    one, two = await new_session(c), await new_session(c)
    c.active.update({one: "browser", two: "browser"})
    c.service.callbacks["source_enabled"] = lambda source: source != "disabled"
    register_source_lifecycle("domain", before=lambda *args: None)
    await c.control.start()
    domain = host_client("domain", session_ids=[one], capabilities=["session.send"])
    operation = await domain.call("session.send", {"session_id": one, "message": "wait for domain"}, key="domain")
    source_state("disabled", True)
    c.service.callbacks.pop("source_enabled")
    disabled = host_client("disabled", session_ids=[two], capabilities=["session.send"])
    cancelled = await disabled.call("session.send", {"session_id": two, "message": "disabled"}, key="disabled")
    c.service.callbacks["source_enabled"] = lambda source: source != "disabled"
    assert release_all_plugin_leases() == 1
    assert c.store.get_operation(cancelled["operation_id"])["status"] == "cancelled"
    c.service.callbacks["source_before_run"].clear()
    c.active.clear()
    await asyncio.sleep(.65)
    assert c.store.get_operation(operation["operation_id"])["status"] == "queued" and not c.calls
    register_source_lifecycle("domain", before=lambda *args: None)
    assert (await domain.wait(operation["operation_id"]))["status"] == "succeeded"
    await c.control.close()


def test_acp_delegation_never_inherits_personal_credentials_without_task_token(monkeypatch):
    from acp_bridge.client import AgentTarget
    monkeypatch.setenv("MYAGENT_CONTROL_TOKEN", "personal-token-must-not-leak")
    environment = AgentTarget("external", "python").environment()
    assert environment["MYAGENT_CONTROL_TASK"] == "1"
    assert "MYAGENT_CONTROL_TOKEN" not in environment


@run_async
async def test_rpc_batch_cannot_inject_host_fields_and_atomic_conflict_rolls_back(composed):
    from tests.test_session_control import rpc
    c = composed
    one, two = await new_session(c), await new_session(c)
    rejected = await rpc(c, "session.send_batch", {"requests": [{"session_id": one, "message": "x", "_source": {"id": "forged"}}]}, key="forged")
    assert rejected.status_code == 400
    request = [{"session_id": one, "message": "one"}, {"session_id": two, "message": "two"}]
    c.active.update({one: "browser", two: "browser"})
    first = await rpc(c, "session.send_batch", {"requests": request}, key="atomic")
    assert first.status_code == 200, first.text
    changed = await rpc(c, "session.send_batch", {"requests": [request[0], {**request[1], "message": "changed"}]}, key="atomic")
    assert changed.status_code == 409
    assert len([op for op in c.store.operations() if op["method"] == "session.send"]) == 2
    c.active.clear()
    await c.control.close()


@run_async
async def test_plugin_delegation_preserves_parent_scope_tools_and_revocation(composed, monkeypatch):
    import session_control.integration as integration
    from session_control.configuration import runtime_scope, validate_config
    from session_control.policy import Principal, validate_policy
    c = composed
    monkeypatch.setattr(integration, "_application", c.control)
    one, other = await new_session(c), await new_session(c)
    await c.control.start()
    parent = host_client("parent", session_ids=[one], capabilities=["session.send", "session.create"])
    with runtime_scope(one, validate_config({"tools": {"mode": "custom", "allow": []}, "read_only": True}), principal=parent.principal):
        child = host_client("child", session_ids=[one, other], capabilities=["session.send"])
    with pytest.raises(ControlError, match="outside"):
        await child.call("session.send", {"session_id": other, "message": "outside"}, key="outside")
    receipt = await child.call("session.send", {"session_id": one, "message": "inside"}, key="inside")
    await child.wait(receipt["operation_id"])
    assert c.calls[-1][2]["tools"]["allow"] == [] and c.calls[-1][2]["read_only"] is True
    source_state("parent", False)
    with pytest.raises(ControlError, match="revoked"):
        await child.call("session.send", {"session_id": one, "message": "after revoke"}, key="after")
    await c.control.close()
