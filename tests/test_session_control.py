"""Control-plane composition tests: real store, session manager, HTTP and CLI."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from functools import wraps

import httpx
import pytest
from fastapi import FastAPI

from session_control.api import register_control
from session_control.configuration import (ConfigRepository, constrain_call, from_metadata, resolve_config,
                                            runtime_scope, tool_ref, validate_config)
from session_control.errors import ControlError
from session_control.policy import Principal, validate_policy
from session_control.scheduling import match_condition, next_time, validate_trigger
from session_control.store import ControlStore, digest
from tool_registry import ToolDescriptor, ToolRegistry


def run_async(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return wrapped


def descriptor(name="read_file"):
    return ToolDescriptor.from_openai_definition({"type": "function", "function": {"name": name,
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"], "additionalProperties": False}}},
        invocation_kind="host", owner="test", effect="read")


@pytest.fixture
def composed(tmp_path, monkeypatch):
    import agent_harness as harness
    from remote_control.store import RemoteControlStore
    monkeypatch.setattr(harness, "WORK_DIR", tmp_path)
    manager = harness.SessionManager(tmp_path / "sessions", tmp_path / "index.json")
    active, calls = {}, []
    lock = threading.Lock()
    def reserve(sid, run_id):
        with lock:
            if sid in active:
                return None
            active[sid] = run_id
            return run_id
    def release(sid, token):
        with lock:
            if active.get(sid) == token:
                active.pop(sid, None)
    async def stream(message, *, session_id, run_id, user_operation_id="", **kwargs):
        from runtime_v2 import RuntimeHistoryOps
        from session_control.configuration import active_config
        calls.append((session_id, message, active_config(session_id)))
        ops = RuntimeHistoryOps(manager.sessions_dir, path_resolver=manager._resolve_session_path)
        ops.commit_user_turn(session_id, message, operation_id=user_operation_id, run_id=run_id)
        yield {"type": "user", "content": message}
        await asyncio.sleep(.05)
        if manager.is_interrupt_requested(session_id, run_id):
            return
        ops.commit_assistant_final(session_id, "answer:" + message, operation_id="final:" + user_operation_id, run_id=run_id)
        yield {"type": "final", "content": "answer:" + message}
    async def catalog(*args, **kwargs):
        registry = ToolRegistry()
        registry.register(descriptor())
        registry.register(descriptor("write_file"))
        return registry
    dependencies = SimpleNamespace(session_manager=manager, astream_events=stream, reserve_start=reserve,
                                   release_start=release, is_stream_active=lambda sid: sid in active)
    app = FastAPI()
    control = register_control(app, dependencies, tmp_path / "control", RemoteControlStore(tmp_path / "remote"),
                               callbacks={"catalog": catalog, "pending_human": lambda _: 0})
    admin = Principal("test-admin", "Test administrator", True)
    token = control.identities.issue(admin)
    return SimpleNamespace(app=app, control=control, service=control.service, store=control.store,
                           manager=manager, admin=admin, token=token, active=active, calls=calls, root=tmp_path)


async def rpc(c, method, params=None, key=None, token=None):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url="http://127.0.0.1") as client:
        return await client.post("/api/control/v1/rpc", headers={"Authorization": "Bearer " + (token or c.token)},
            json={"method": method, "params": params or {}, "idempotency_key": key or str(time.time_ns())})


async def new_session(c, **kwargs):
    response = await rpc(c, "session.create", {"work_dir": str(c.root), **kwargs})
    assert response.status_code == 200, response.text
    return response.json()["data"]["session_id"]


def test_store_survives_restart_and_rejects_changed_arguments(tmp_path):
    first = ControlStore(tmp_path / "control.db")
    op, duplicate = first.admit("a", "key", "session.send", {"message": "一"})
    assert not duplicate
    second = ControlStore(first.path)
    same, duplicate = second.admit("a", "key", "session.send", {"message": "一"})
    assert duplicate and same["id"] == op["id"]
    with pytest.raises(ControlError, match="different arguments"):
        second.admit("a", "key", "session.send", {"message": "二"})
    first.append_event({"source": "source", "id": "event", "data": {}}, cursor=("producer", {"seq": 3}))
    assert second.cursor("producer") == {"seq": 3}
    assert second.events()[0]["id"] == "event"


@run_async
async def test_authenticated_creation_idempotency_and_no_remote_gateway(composed):
    c = composed
    response = await rpc(c, "session.create", {"name": "hello", "work_dir": str(c.root)}, key="create")
    assert response.status_code == 200, response.text
    first = response.json()["data"]
    second = await rpc(c, "session.create", {"name": "hello", "work_dir": str(c.root)}, key="create")
    assert second.json()["data"]["session_id"] == first["session_id"]
    assert len(c.manager.list_sessions()) == 1
    changed = await rpc(c, "session.create", {"name": "different"}, key="create")
    assert changed.status_code == 409
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url="http://127.0.0.1") as client:
        denied = await client.post("/api/control/v1/rpc", json={"method": "session.list"})
        assert denied.status_code == 401
        assert (await client.get("/api/remote/v1/status")).status_code == 404


@run_async
async def test_persistent_config_cas_empty_tools_and_temporary_prompt(composed):
    c = composed
    sid = await new_session(c)
    cfg = {"system_prompt": {"mode": "replace", "text": "固定角色"}, "tools": {"mode": "custom", "allow": []}}
    response = await rpc(c, "session.config.update", {"session_id": sid, "config": cfg, "expected_revision": 0})
    assert response.status_code == 200, response.text
    assert c.service.configs.get(sid)["config"]["system_prompt"]["text"] == "固定角色"
    conflict = await rpc(c, "session.config.update", {"session_id": sid, "config": {}, "expected_revision": 0})
    assert conflict.status_code == 409
    result = await rpc(c, "session.send", {"session_id": sid, "message": "work", "runtime_override": {"system_prompt": {"mode": "append", "text": "本轮约束"}}})
    oid = result.json()["operation_id"]
    done = await rpc(c, "operation.wait", {"id": oid, "timeout": 3})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "succeeded"
    assert "本轮约束" in c.calls[0][2]["system_prompt"]["text"]
    assert "本轮约束" not in c.service.configs.get(sid)["config"]["system_prompt"]["text"]
    await c.control.close()


@run_async
async def test_busy_session_queues_and_worker_continues_without_client(composed):
    c = composed
    sid = await new_session(c)
    c.active[sid] = "human-run"
    response = await rpc(c, "session.send", {"session_id": sid, "message": "queued"}, key="send")
    oid = response.json()["operation_id"]
    await asyncio.sleep(.65)
    assert not c.calls and c.store.get_operation(oid)["status"] == "queued"
    c.active.clear()
    await rpc(c, "operation.wait", {"id": oid, "timeout": 3})
    assert len(c.calls) == 1
    again = await rpc(c, "session.send", {"session_id": sid, "message": "queued"}, key="send")
    assert again.json()["operation_id"] == oid and len(c.calls) == 1
    await c.control.close()


def test_constraints_defaults_fixed_hook_mutation_and_alias_identity(tmp_path):
    tool = descriptor()
    binding = {"tool_ref": tool_ref(tool), "defaults": {"limit": 10}, "fixed": {"path": str(tmp_path / "safe.txt")},
               "constraints": [{"pointer": "/path", "kind": "path", "roots": [str(tmp_path)]},
                               {"pointer": "/limit", "kind": "number", "min": 1, "max": 20}]}
    cfg = validate_config({"tools": {"mode": "custom", "allow": [tool_ref(tool)], "bindings": [binding]}})
    with runtime_scope("sid", cfg):
        args = constrain_call("sid", tool, {}, tmp_path)
        assert args["limit"] == 10
        with pytest.raises(ControlError, match="Fixed parameter"):
            constrain_call("sid", tool, {**args, "path": str(tmp_path.parent / "escape")}, tmp_path, inject=False)
        with pytest.raises(ControlError, match="was removed"):
            constrain_call("sid", tool, {"limit": 10}, tmp_path, inject=False)
        with pytest.raises(ControlError, match="number constraint"):
            constrain_call("sid", tool, {**args, "limit": 21}, tmp_path, inject=False)
        registry = ToolRegistry()
        registry.register(tool)
        registry.rename_tools({"read_file": "renamed"})
        assert constrain_call("sid", registry.resolve("renamed"), args, tmp_path) == args
    from session_control.configuration import validate_arguments
    shell_path = {"tool_ref": {"kind": "host", "owner": "core.tools", "name": "run_shell"},
                  "constraints": [{"pointer": "/workdir", "kind": "path", "roots": [str(tmp_path)]}]}
    with pytest.raises(ControlError, match="path constraint"):
        validate_arguments({"workdir": "/"}, shell_path, tmp_path)


@run_async
async def test_task_scope_and_configuration_cannot_escalate(composed):
    c = composed
    sid = await new_session(c)
    other = c.root / "other"
    other.mkdir()
    elsewhere = await new_session(c, work_dir=str(other))
    task = Principal("task", policy=validate_policy({}, workspace=str(c.root)))
    token = c.control.identities.issue(task)
    listing = await rpc(c, "session.list", token=token)
    assert [x["id"] for x in listing.json()["data"]["sessions"]] == [sid]
    assert (await rpc(c, "session.history", {"session_id": elsewhere}, token=token)).status_code == 403
    assert (await rpc(c, "session.config.update", {"session_id": sid, "config": {}, "expected_revision": 0}, token=token)).status_code == 403
    assert (await rpc(c, "session.create", {"work_dir": str(other)}, token=token)).status_code == 403
    history = await rpc(c, "automation.history", {"limit": 10})
    assert history.status_code == 200
    rows = history.json()["data"]["executions"]
    assert rows and rows[0]["status"] == "failed"
    assert rows[0]["error"]["code"] == "scope_denied"


def test_calendar_intervals_dst_and_predicates():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    trigger, first = validate_trigger({"kind": "interval", "seconds": 420}, now)
    assert first == now + 420 and next_time(trigger, now + 841) == now + 1260
    rule, first = validate_trigger({"kind": "daily", "time": "09:00", "time_zone": "Asia/Shanghai"}, now)
    assert datetime.fromtimestamp(first, timezone.utc).hour == 1
    spring = datetime(2026, 3, 7, 8, tzinfo=timezone.utc).timestamp()
    rule, first = validate_trigger({"kind": "cron", "expression": "30 2 * * *", "time_zone": "America/New_York"}, spring)
    assert datetime.fromtimestamp(first, timezone.utc).day == 9
    assert match_condition({"all": [{"field": "data.status", "op": "eq", "value": "done"}]}, {"data": {"status": "done"}})
    with pytest.raises(ControlError):
        validate_trigger({"kind": "interval", "seconds": 0}, now)


@run_async
async def test_schedule_manual_run_and_webhook_dedup(composed):
    c = composed
    sid = await new_session(c)
    definition = {"name": "daily", "trigger": {"kind": "interval", "seconds": 60},
                  "target": {"mode": "existing", "session_id": sid}, "action": {"kind": "prompt", "text": "summarize"}}
    created = await rpc(c, "automation.create", definition)
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    before = task["next_run_at"]
    manual = await rpc(c, "automation.run", {"id": task["id"]})
    assert manual.status_code == 200, manual.text
    assert c.store.get("automations", task["id"])["next_run_at"] == before
    definition.update(name="hook", trigger={"kind": "event", "types": ["webhook.received"]})
    rule = (await rpc(c, "automation.create", definition)).json()["data"]
    source_response = await rpc(c, "event_source.create", {"name": "CI", "allowed_rules": [rule["id"]]})
    assert source_response.status_code == 200, source_response.text
    source = source_response.json()["data"]
    timestamp, body = str(time.time()), b'{"status":"passed"}'
    sig = hmac.new(source["secret"].encode(), (timestamp + "\nevent-1\n").encode() + body, hashlib.sha256).hexdigest()
    headers = {"X-Sugar-Timestamp": timestamp, "X-Sugar-Event-Id": "event-1", "X-Sugar-Signature": sig}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url="http://127.0.0.1") as client:
        first = await client.post(source["endpoint"], content=body, headers=headers)
        second = await client.post(source["endpoint"], content=body, headers=headers)
        assert first.status_code == 202 and second.status_code == 200
        assert second.json()["data"]["duplicate"]
        fresh_time = str(float(timestamp) + 1)
        fresh_sig = hmac.new(source["secret"].encode(), (fresh_time + "\nevent-1\n").encode() + body, hashlib.sha256).hexdigest()
        retried = await client.post(source["endpoint"], content=body, headers={**headers, "X-Sugar-Timestamp": fresh_time, "X-Sugar-Signature": fresh_sig})
        assert retried.status_code == 200 and retried.json()["data"]["duplicate"]
        assert (await client.post(source["endpoint"], content=body, headers={**headers, "X-Sugar-Signature": "bad"})).status_code == 401
    assert "secret" not in (await rpc(c, "event_source.get", {"id": source["id"]})).json()["data"]
    await asyncio.sleep(1.2)
    assert any("External event data" in call[1] for call in c.calls)
    await c.control.close()


def test_cli_runs_outside_repo_and_never_falls_back_for_task(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "MYAGENT_SESSION_CREDENTIAL_DIR": str(tmp_path), "MYAGENT_CONTROL_TASK": "1"}
    env.pop("MYAGENT_CONTROL_TOKEN", None)
    result = subprocess.run([sys.executable, str(root / "agent-session-control.py"), "session", "list"], cwd=tmp_path,
                            env=env, text=True, capture_output=True, timeout=20)
    assert result.returncode == 3, result.stderr
    value = json.loads(result.stdout)
    assert value["schema_version"] == 1 and value["error"]["code"] == "unauthorized"
    help_result = subprocess.run([sys.executable, str(root / "agent-session-control.py"), "schedule", "create", "--help"],
                                 cwd=tmp_path, env=env, text=True, capture_output=True, timeout=20)
    assert help_result.returncode == 0 and "--file" in help_result.stdout


@run_async
async def test_restart_preserves_unstarted_input_and_never_replays_committed_input(composed):
    c = composed
    sid = await new_session(c)
    c.active[sid] = "busy"
    response = await rpc(c, "session.send", {"session_id": sid, "message": "after restart"})
    oid = response.json()["operation_id"]
    await c.control.close()
    c.active.clear()
    await c.control.start()
    done = await rpc(c, "operation.wait", {"id": oid, "timeout": 3})
    assert done.json()["data"]["status"] == "succeeded"
    assert len(c.calls) == 1
    await c.control.close()
    op, _ = c.store.admit(c.admin.id, "lost-reply", "session.send", {"session_id": sid, "message": "already committed",
                                                               "_principal": __import__("dataclasses").asdict(c.admin)})
    from runtime_v2 import RuntimeHistoryOps
    RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path).commit_user_turn(
        sid, "already committed", operation_id=op["id"], run_id=op["run_id"])
    await c.control.start()
    await asyncio.sleep(.8)
    assert c.store.get_operation(op["id"])["status"] == "unknown"
    assert len(c.calls) == 1
    await c.control.close()


@run_async
async def test_wait_timeout_does_not_cancel_and_config_bindings_are_checked(composed):
    c = composed
    sid = await new_session(c)
    c.active[sid] = "busy"
    response = await rpc(c, "session.send", {"session_id": sid, "message": "later"})
    oid = response.json()["operation_id"]
    waiting = await rpc(c, "operation.wait", {"id": oid, "timeout": .01})
    assert waiting.status_code == 408 and c.store.get_operation(oid)["status"] == "queued"
    ref = tool_ref(descriptor())
    cfg = {"tools": {"mode": "custom", "allow": [ref], "bindings": [
        {"tool_ref": ref, "fixed": {"limit": "bad"}}]}}
    invalid = await rpc(c, "session.config.update", {"session_id": sid, "config": cfg, "expected_revision": 0})
    assert invalid.status_code == 400
    assert c.service.configs.get(sid)["revision"] == 0
    c.active.clear()
    assert (await rpc(c, "operation.wait", {"id": oid, "timeout": 3})).json()["data"]["status"] == "succeeded"
    await c.control.close()


@run_async
async def test_presets_are_versioned_and_copies_remain_independent(composed):
    c = composed
    sid = await new_session(c)
    first = await rpc(c, "config_preset.create", {"name": "reviewer", "config": {"system_prompt": {"mode": "replace", "text": "version one"}}})
    preset = first.json()["data"]
    applied = await rpc(c, "config_preset.apply", {"id": preset["id"], "session_id": sid, "expected_revision": 0})
    assert applied.status_code == 200, applied.text
    changed = await rpc(c, "config_preset.update", {"id": preset["id"], "name": "reviewer", "expected_revision": 1,
        "config": {"system_prompt": {"mode": "replace", "text": "version two"}}})
    assert changed.status_code == 200, changed.text
    assert c.service.configs.get(sid)["config"]["system_prompt"]["text"] == "version one"
    old = await rpc(c, "config_preset.get", {"id": preset["id"], "revision": 1})
    assert old.json()["data"]["config"]["system_prompt"]["text"] == "version one"
    await c.control.close()


def test_cli_real_http_backend_unicode_auth_send_and_config(composed, tmp_path):
    import socket
    import uvicorn
    c = composed
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.listen()
    server = uvicorn.Server(uvicorn.Config(c.app, log_level="error", lifespan="off"))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(.02)
    assert server.started
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "MYAGENT_SESSION_CREDENTIAL_DIR": str(tmp_path / "cli-credentials"), "PYTHONUTF8": "1"}
    env.pop("MYAGENT_CONTROL_TOKEN", None)
    env.pop("MYAGENT_CONTROL_TASK", None)
    def cli(*args):
        result = subprocess.run([sys.executable, str(root / "agent-session-control.py"), "--base-url", f"http://127.0.0.1:{port}", *args],
                                cwd=tmp_path, env=env, text=True, encoding="utf-8", capture_output=True, timeout=20)
        assert result.returncode == 0, (result.stdout, result.stderr)
        return json.loads(result.stdout)
    archive = tmp_path / "backend.zip"
    archive.write_bytes(b"archive-transfer-test")
    c.service.callbacks["session.export"] = lambda p: {"session_id": p["session_id"], "archive_path": str(archive), "filename": "session.zip"}
    def import_file(p):
        assert Path(p["source"]).read_bytes() == b"archive-transfer-test"
        return {"imported": True}
    c.service.callbacks["session.import"] = import_file
    try:
        login = tmp_path / "login.json"
        login.write_text(json.dumps({"bootstrap_token": c.control._bootstrap(), "name": "test CLI"}), encoding="utf-8")
        authenticated = cli("auth", "login", "--file", str(login))
        assert "token" not in authenticated["data"]
        created = cli("session", "create", "--work-dir", str(tmp_path), "--name", "会话中文")
        sid = created["data"]["session_id"]
        assert cli("session", "get", "--id", sid)["data"]["session"]["name"] == "会话中文"
        config_file = tmp_path / "runtime.json"
        config_file.write_text(json.dumps({"system_prompt": {"mode": "replace", "text": "你是研究员"},
                                          "tools": {"mode": "custom", "allow": []}}, ensure_ascii=False), encoding="utf-8")
        cli("config", "set", "--id", sid, "--file", str(config_file), "--expected-revision", "0")
        result = cli("session", "send", "--id", sid, "--message", "处理中文请求", "--wait", "--timeout", "5")
        assert result["data"]["status"] == "succeeded"
        assert c.calls[-1][2]["system_prompt"]["text"] == "你是研究员"
        exported = tmp_path / "client.zip"
        cli("session", "export", "--id", sid, "--output", str(exported))
        assert exported.read_bytes() == archive.read_bytes()
        assert cli("session", "import", "--archive", str(exported), "--idempotency-key", "upload-test")["data"]["imported"]
        assert cli("session", "import", "--archive", str(exported), "--idempotency-key", "upload-test")["data"]["imported"]
        cli("auth", "logout")
    finally:
        if c.service.loop and c.service.loop.is_running():
            asyncio.run_coroutine_threadsafe(c.control.close(), c.service.loop).result(10)
        server.should_exit = True
        thread.join(10)
        listener.close()


@run_async
async def test_event_cycles_and_new_session_occurrences_are_idempotent(composed):
    c = composed
    definition = {"name": "isolated", "workspace": str(c.root), "trigger": {"kind": "interval", "seconds": 60},
                  "target": {"mode": "new"}, "action": {"kind": "prompt", "text": "work"}}
    created = await rpc(c, "automation.create", definition)
    task = c.store.get("automations", created.json()["data"]["id"])
    first = await c.service.engine.fire(task, "occurrence", time.time())
    second = await c.service.engine.fire(task, "occurrence", time.time())
    assert first["session_id"] == second["session_id"] and first["operation_id"] == second["operation_id"]
    suppressed = await c.service.engine.fire(task, "cycle", time.time(), event={"automationchain": [task["id"]]})
    assert suppressed["suppressed"]
    assert len(c.manager.list_sessions()) == 1
    await c.control.close()


@run_async
async def test_attach_snapshot_cursor_generation_gap_and_live_revocation(composed):
    from runtime_v2 import RuntimeHistoryOps
    c = composed
    sid = await new_session(c)
    ops = RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
    first = ops.commit_user_turn(sid, "hello", operation_id="input", run_id="r")
    async def connected():
        return False
    request = SimpleNamespace(headers={"authorization": "Bearer " + c.token},
                              query_params={"session_id": sid}, is_disconnected=connected)
    response = await c.control.events(request)
    stream = response.body_iterator
    snapshot = json.loads(await anext(stream))
    assert snapshot["type"] == "snapshot" and snapshot["cursor"] >= first.seq
    assert not c.calls
    final = ops.commit_assistant_final(sid, "answer", operation_id="final:input", run_id="r")
    event = json.loads(await anext(stream))
    assert event["type"] == "event" and event["cursor"] == final.seq
    c.control.identities.revoke(c.token)
    denied = json.loads(await anext(stream))
    assert denied["type"] == "error" and denied["error"]["code"] == "unauthorized"
    await stream.aclose()
    fresh = c.control.identities.issue(c.admin)
    request.headers = {"authorization": "Bearer " + fresh}
    request.query_params.update(cursor="999999", generation="old")
    stream = (await c.control.events(request)).body_iterator
    gap = json.loads(await anext(stream))
    assert gap["type"] == "gap" and gap["cursor"] < 999999
    assert json.loads(await anext(stream))["type"] == "snapshot"
    await stream.aclose()


@run_async
async def test_unrelated_final_cannot_complete_an_operation(composed):
    from runtime_v2 import RuntimeHistoryOps
    c = composed
    sid = await new_session(c)
    async def wrong_final(message, *, session_id, run_id, user_operation_id, **kwargs):
        ops = RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
        ops.commit_user_turn(sid, message, operation_id=user_operation_id, run_id=run_id)
        ops.commit_assistant_final(sid, "another turn", operation_id="final:unrelated", run_id=run_id)
        yield {"type": "final", "content": "another turn"}
    c.service.deps.astream_events = wrong_final
    result = await rpc(c, "session.send", {"session_id": sid, "message": "my input"})
    waited = await rpc(c, "operation.wait", {"id": result.json()["operation_id"], "timeout": 4})
    assert waited.json()["data"]["status"] == "unknown"
    await c.control.close()


@run_async
async def test_revoked_origin_blocks_automation_and_configuration_cannot_self_grant(composed):
    c = composed
    sid = await new_session(c)
    restricted = Principal("task", policy=validate_policy({}, workspace=str(c.root)))
    task_token = c.control.identities.issue(restricted)
    denied = await rpc(c, "session.config.update", {"session_id": sid, "config": {}, "expected_revision": 0}, token=task_token)
    assert denied.status_code == 403
    created = await rpc(c, "automation.create", {"name": "revocable", "target": {"mode": "existing", "session_id": sid},
        "trigger": {"kind": "interval", "seconds": 60}, "action": {"kind": "prompt", "text": "work"}})
    task = c.store.get("automations", created.json()["data"]["id"])
    c.control.identities.revoke(c.token)
    with pytest.raises(ControlError, match="revoked"):
        await c.service.engine.fire(task, "after-revoke", time.time())
    await c.control.close()


def test_constraint_intersections_schema_change_and_source_aliases(tmp_path):
    from session_control.configuration import filter_registry
    read = descriptor()
    ref = tool_ref(read)
    base = {"tools": {"bindings": [{"tool_ref": ref, "fixed": {"limit": 5}}]}}
    with pytest.raises(ControlError, match="Conflicting fixed"):
        resolve_config(base, {"tools": {"bindings": [{"tool_ref": ref, "fixed": {"limit": 6}}]}})
    ranges = lambda low, high: {"tools": {"bindings": [{"tool_ref": ref, "constraints": [{"pointer": "/limit", "kind": "number", "min": low, "max": high}]}]}}
    with pytest.raises(ControlError, match="do not intersect"):
        resolve_config(ranges(1, 3), ranges(5, 8))
    registry = ToolRegistry()
    registry.register(read)
    registry.rename_tools({read.name: "friendly"})
    allowed = validate_config({"tools": {"mode": "custom", "allow": [ref]}})
    assert filter_registry(registry, allowed).resolve("friendly")
    changed = validate_config({"tools": {"bindings": [{"tool_ref": ref, "schema_digest": "old", "required": False}]}})
    assert not filter_registry(registry, changed).descriptors()
    changed["tools"]["bindings"][0]["required"] = True
    with pytest.raises(ControlError, match="Required tool"):
        filter_registry(registry, changed)


@run_async
async def test_archived_target_keeps_durable_automation_and_scheduler_is_fair(composed):
    c = composed
    sid = await new_session(c)
    await rpc(c, "session.archive", {"session_id": sid})
    created = await rpc(c, "automation.create", {"name": "archived", "target": {"mode": "existing", "session_id": sid},
        "trigger": {"kind": "interval", "seconds": 60}, "action": {"kind": "prompt", "text": "pending"}})
    task = c.store.get("automations", created.json()["data"]["id"])
    first = await c.service.engine.fire(task, "one", time.time())
    assert c.store.get_operation(first["operation_id"])["status"] == "queued"
    for i in range(210):
        c.store.admit(c.admin.id, "queue-" + str(i), "session.send", {"session_id": sid, "message": "blocked", "_principal": __import__("dataclasses").asdict(c.admin)})
    other = await new_session(c)
    sent = await rpc(c, "session.send", {"session_id": other, "message": "unblocked"})
    waited = await rpc(c, "operation.wait", {"id": sent.json()["operation_id"], "timeout": 5})
    assert waited.json()["data"]["status"] == "succeeded"
    assert c.store.get_operation(first["operation_id"])["status"] == "queued"
    await c.control.close()


@run_async
async def test_each_turn_freezes_config_and_recovery_reuses_it(composed, monkeypatch):
    import session_control.integration as integration
    from session_control.configuration import active_config
    c = composed
    sid = await new_session(c)
    monkeypatch.setattr(integration, "_application", c.control)
    captured = []
    async def react(state):
        captured.append(active_config(sid)["system_prompt"]["text"])
        return state
    monkeypatch.setitem(react.__globals__, "session_manager", c.manager)
    wrapped = integration.managed_turn(react)
    state = {"session_id": sid, "_runtime_v2_turn_id": "turn-one", "_runtime_v2_run_id": "run-one"}
    await wrapped(state)
    c.service.configs.update(sid, {"system_prompt": {"mode": "replace", "text": "new prompt"}}, 0)
    await wrapped(state)
    state["_runtime_v2_turn_id"] = "turn-two"
    await wrapped(state)
    await wrapped({"session_id": sid, "_runtime_v2_turn_id": "turn-one", "_runtime_v2_run_id": "recovered"})
    assert captured == ["", "", "new prompt", ""]


@run_async
async def test_preset_apply_and_model_update_require_configuration_permission(composed):
    c = composed
    sid = await new_session(c)
    restricted = Principal("limited", policy=validate_policy({"capabilities": ["read", "config_preset.apply", "session.update"]}, workspace=str(c.root)))
    token = c.control.identities.issue(restricted)
    for method, params in (("config_preset.apply", {"id": "any", "session_id": sid, "expected_revision": 0}),
                           ("session.update", {"session_id": sid, "model_profile_id": "any"})):
        denied = await rpc(c, method, params, token=token)
        assert denied.status_code == 403, denied.text
    assert c.service.configs.get(sid)["revision"] == 0


@run_async
async def test_event_inputs_do_not_coalesce_and_tool_overrides_can_narrow(composed):
    c = composed
    sid = await new_session(c)
    c.active[sid] = "busy"
    ref = tool_ref(descriptor())
    other = tool_ref(descriptor("write_file"))
    base = validate_config({"tools": {"mode": "custom", "allow": [ref, other], "bindings": [
        {"tool_ref": ref, "required": True}, {"tool_ref": other, "required": True}]}})
    narrowed = resolve_config(base, {"tools": {"mode": "custom", "allow": [ref]}})
    registry = await c.service.catalog(sid, narrowed)
    assert registry.resolve("read_file") and not registry.resolve("write_file")
    created = await rpc(c, "automation.create", {"name": "every event", "trigger": {"kind": "event", "types": ["job.completed"]},
        "target": {"mode": "existing", "session_id": sid}, "action": {"kind": "prompt", "text": "analyze"}})
    task = c.store.get("automations", created.json()["data"]["id"])
    one = await c.service.engine.fire(task, "event-one", time.time())
    two = await c.service.engine.fire(task, "event-two", time.time())
    assert c.store.get_operation(one["operation_id"])["status"] == "queued"
    assert c.store.get_operation(two["operation_id"])["status"] == "queued"
    c.active.clear()
    await c.control.close()


@run_async
async def test_shell_background_prohibition_prevents_timeout_promotion(tmp_path, monkeypatch):
    import agent_tools
    import execution_services.jobs as jobs
    from execution_services.shell import execute_prepared
    service = jobs.ExecutionService()
    monkeypatch.setattr(jobs, "execution_service", lambda: service)
    monkeypatch.setattr(agent_tools, "WORK_DIR", tmp_path)
    shell = ToolDescriptor.from_openai_definition({"type": "function", "function": {"name": "run_shell",
        "parameters": {"type": "object", "properties": {"run_in_background": {"type": "boolean"}}}}},
        invocation_kind="host", owner="test", effect="write")
    config = validate_config({"tools": {"bindings": [{"tool_ref": tool_ref(shell), "fixed": {"run_in_background": False}}]}})
    prepared = SimpleNamespace(argv=[sys.executable, "-c", "import time;time.sleep(20)"], env=dict(os.environ))
    try:
        with runtime_scope("owner", config):
            constrain_call("owner", shell, {}, tmp_path)
            text = await execute_prepared(prepared, tmp_path, {}, "sleeper", .05, False, [],
                {"session_id": "owner", "context": SimpleNamespace(mode="full_access")})
        assert "background execution is disabled" in text
        await asyncio.sleep(.3)
        assert all(not job.visible and job.status in {"killed", "stopping"} for job in service.jobs.values())
        assert not await service.call(service.notices, "owner")
    finally:
        await service.shutdown()


@run_async
async def test_message_control_permissions_are_independent_even_while_idle(composed):
    c = composed
    sid = await new_session(c)
    identity = Principal("limited", policy=validate_policy({}, workspace=str(c.root)))
    token = c.control.identities.issue(identity)
    for mode in ("append", "interrupt"):
        denied = await rpc(c, "session.send", {"session_id": sid, "message": "control", "mode": mode}, token=token)
        assert denied.status_code == 403
    assert not any(row["method"] == "session.send" for row in c.store.operations(session_id=sid))


@run_async
async def test_cancel_survives_runtime_clearing_its_interrupt_marker(composed):
    c = composed
    sid = await new_session(c)
    started, release = threading.Event(), threading.Event()
    async def stream(message, *, session_id, run_id, should_stop, **kwargs):
        started.set()
        while not release.is_set():
            await asyncio.sleep(.01)
        c.manager.clear_interrupt(session_id, run_id)
        assert should_stop(session_id)
        yield {"type": "user", "content": message}
    c.service.deps.astream_events = stream
    sent = await rpc(c, "session.send", {"session_id": sid, "message": "cancel me"})
    oid = sent.json()["operation_id"]
    try:
        assert await asyncio.to_thread(started.wait, 3)
        assert (await rpc(c, "operation.cancel", {"id": oid})).status_code == 200
        release.set()
        waited = await rpc(c, "operation.wait", {"id": oid, "timeout": 3})
        assert waited.json()["data"]["status"] == "stopped"
    finally:
        release.set()
        await c.control.close()


@run_async
async def test_scheduler_misfire_clock_rewind_and_latest_pending_are_durable(composed, monkeypatch):
    import session_control.automation as automation
    c = composed
    sid = await new_session(c)
    c.active[sid] = "busy"
    created = await rpc(c, "automation.create", {"name": "clock", "trigger": {"kind": "interval", "seconds": 60},
        "target": {"mode": "existing", "session_id": sid}, "action": {"kind": "prompt", "text": "work"}})
    task = c.store.get("automations", created.json()["data"]["id"])
    await c.control.close()
    async def no_start():
        pass
    monkeypatch.setattr(c.service, "start", no_start)
    now = [task["trigger"]["anchor"] + 185]
    monkeypatch.setattr(automation.time, "time", lambda: now[0])
    await c.service.engine.tick()
    first = [op for op in c.store.operations() if op["request"].get("_automation_id") == task["id"]]
    assert len(first) == 1
    assert first[0]["request"]["_scheduled_at"] == task["trigger"]["anchor"] + 180
    now[0] -= 100
    await c.service.engine.tick()
    assert len([op for op in c.store.operations() if op["request"].get("_automation_id") == task["id"]]) == 1
    now[0] = task["trigger"]["anchor"] + 365
    await c.service.engine.tick()
    operations = [op for op in c.store.operations() if op["request"].get("_automation_id") == task["id"]]
    assert len(operations) == 2
    assert sorted(op["status"] for op in operations) == ["coalesced", "queued"]
    assert c.store.get("automations", task["id"])["revision"] == 1
    c.active.clear()


@run_async
async def test_temporary_model_override_reaches_actual_client_builder(composed, monkeypatch):
    import agent_harness as harness
    c = composed
    sid = await new_session(c)
    monkeypatch.setattr(harness, "session_manager", c.manager)
    monkeypatch.setattr(harness, "_executor_config_cache", {sid: (time.monotonic(), (None, "cached-old", 10, 100))})
    requested = []
    def candidates(sid, **kwargs):
        requested.append(kwargs)
        return [{"profile_id": kwargs["profile_id_override"], "model": "temporary-model", "provider": "openai",
                 "transport": SimpleNamespace(), "max_output_tokens": 40, "context_window": 1000}]
    monkeypatch.setattr(harness, "resolve_executor_candidates_for_session", candidates)
    with runtime_scope(sid, validate_config({"model_profile_id": "temporary-profile", "reasoning_effort": "high"})):
        assert harness.resolve_executor_config_for_session(sid)[1] == "temporary-model"
    assert requested[0]["profile_id_override"] == "temporary-profile"
    assert requested[0]["reasoning_effort_override"] == "high"
    assert harness.resolve_executor_config_for_session(sid)[1] == "cached-old"
