import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from runtime_lifecycle import (LifecycleConflict, LifecycleStore, RuntimeLifecycle,
                               invoke_restart, supervisor_environment)
from lifecycle_supervisor import RestartMailbox, backend_ready


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    store = LifecycleStore(tmp_path / "state.sqlite3")
    mailbox = RestartMailbox("controller", "secret", store=store)
    interrupts = []
    manager = SimpleNamespace(sessions_dir=tmp_path / "sessions",
                              request_interrupt=lambda *a, **k: interrupts.append((a, k)))
    env = supervisor_environment("controller", "secret", "old-instance")
    service = RuntimeLifecycle(manager, store=store, environment=env)
    monkeypatch.setattr(service, "impact", lambda: {"running_tasks": 1, "background_jobs": 0, "terminals": 0})
    service.mark_ready()
    return service, mailbox, interrupts


def request(service, **kwargs):
    return service.request(session_id="session", run_id="run", tool_call_id="tool",
                           reason="修改后端后加载新代码", **kwargs)


def approve(service, record, **kwargs):
    return service.store.decide(record["restart_id"], instance_id=service.instance_id,
        digest=record["request_digest"], allow=True, impact=service.impact(), **kwargs)


def test_no_supervisor_means_no_request(tmp_path):
    service = RuntimeLifecycle(SimpleNamespace(sessions_dir=tmp_path), store=LifecycleStore(tmp_path / "state"), environment={})
    with pytest.raises(LifecycleConflict, match="restart_unavailable"):
        request(service)


def test_human_decision_and_checkpoint_are_both_required(lifecycle):
    service, mailbox, _ = lifecycle
    record = request(service)
    assert mailbox.tick() is None
    assert approve(service, record)["phase"] == "authorized"
    assert mailbox.tick() is None
    service.checkpoint(record["restart_id"], "session", "run")
    claimed = mailbox.tick()
    assert claimed["phase"] == "draining"
    assert claimed["expected_new_instance_id"] != service.instance_id
    assert mailbox.tick() is None


def test_duplicate_requests_and_concurrent_confirmations_claim_once(lifecycle):
    service, mailbox, _ = lifecycle
    record = request(service)
    assert request(service)["restart_id"] == record["restart_id"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(lambda _: approve(service, record), range(12)))
    assert all(row["phase"] == "authorized" for row in records)
    service.checkpoint(record["restart_id"], "session", "run")
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = list(pool.map(lambda _: mailbox.tick(), range(12)))
    assert sum(item is not None for item in claims) == 1


def test_denial_and_wrong_identity_cannot_restart(lifecycle):
    service, mailbox, _ = lifecycle
    record = request(service)
    with pytest.raises(LifecycleConflict):
        service.store.decide(record["restart_id"], instance_id="other", digest=record["request_digest"], allow=True)
    with pytest.raises(LifecycleConflict):
        service.store.decide(record["restart_id"], instance_id=service.instance_id, digest="changed", allow=True)
    result = service.store.decide(record["restart_id"], instance_id=service.instance_id, digest=record["request_digest"], allow=False)
    assert result["phase"] == "denied"
    assert approve(service, record)["phase"] == "denied"
    assert mailbox.tick() is None


def test_impact_change_requires_a_new_confirmation(lifecycle, monkeypatch):
    service, mailbox, _ = lifecycle
    record = request(service)
    monkeypatch.setattr(service, "impact", lambda: {"running_tasks": 4, "background_jobs": 0, "terminals": 0})
    changed = approve(service, record)
    assert changed["confirmation_changed"] and changed["phase"] == "awaiting_confirmation"
    assert mailbox.tick() is None
    with pytest.raises(LifecycleConflict):
        approve(service, record)
    assert approve(service, changed)["phase"] == "authorized"


def test_foreign_checkpoint_and_wrong_supervisor_secret_rejected(lifecycle):
    service, mailbox, _ = lifecycle
    record = request(service)
    approve(service, record)
    with pytest.raises(LifecycleConflict):
        service.checkpoint(record["restart_id"], "session", "wrong-run")
    service.checkpoint(record["restart_id"], "session", "run")
    assert service.store.claim(mailbox.supervisor_id, "not-the-secret") is None
    assert mailbox.tick() is not None


def test_new_instance_restores_result_and_resume_choice_before_recovery(lifecycle):
    service, mailbox, interrupts = lifecycle
    record = request(service, resume_hint="检查新功能")
    approve(service, record, resume=False)
    service.checkpoint(record["restart_id"], "session", "run")
    operation = mailbox.tick()
    service.store.transition(record["restart_id"], "stopping")
    mailbox.starting(operation)
    restored = RuntimeLifecycle(service.manager, store=service.store, environment=mailbox.environment(operation=operation))
    assert interrupts[-1] == (("session",), {"reason": "manual_stop"})
    restored.mark_ready()
    result = restored.status(record["restart_id"])["operations"][0]
    assert result["phase"] == "completed"
    assert result["new_instance_id"] == restored.instance_id
    assert result["resume_hint"] == "检查新功能"
    assert mailbox.tick() is None


def test_restart_receipt_is_written_once_without_finishing_the_user_turn(lifecycle):
    from runtime_v2 import RuntimeHistoryOps, RuntimeModelProjection, RuntimeMirror, RuntimeUiProjection
    service, mailbox, _ = lifecycle
    root = service.manager.sessions_dir
    service.manager.repository = SimpleNamespace(sessions_dir=root)
    service.manager.get_session_summary = lambda _: {"id": "session"}
    ops = RuntimeHistoryOps(root)
    ops.append_model_message("session", "user", "请修改后端并验证")
    mirror = RuntimeMirror(root)
    mirror.mirror_ui_event("session", {"type": "user", "content": "请修改后端并验证"})
    record = request(service, resume_hint="验证修改生效")
    approve(service, record)
    service.checkpoint(record["restart_id"], "session", "run")
    operation = mailbox.tick()
    service.store.transition(record["restart_id"], "stopping")
    mailbox.starting(operation)
    environment = mailbox.environment(operation=operation)
    RuntimeLifecycle(service.manager, store=service.store, environment=environment)
    RuntimeLifecycle(service.manager, store=service.store, environment=environment)
    messages = RuntimeModelProjection(root).read_message_dicts("session")
    receipts = [row for row in messages if "服务重启回执" in str(row.get("content") or "")]
    assert len(receipts) == 1 and "验证修改生效" in receipts[0]["content"]
    assert RuntimeUiProjection(root).has_unanswered_user("session")


def test_manual_confirmation_has_no_tool_waiter(lifecycle):
    service, mailbox, _ = lifecycle
    record = service.request(reason="用户重启")
    assert approve(service, record)["phase"] == "checkpointed"
    assert mailbox.tick() is not None


def test_denied_request_cannot_be_repeated_in_the_same_run(lifecycle):
    service, mailbox, _ = lifecycle
    record = request(service)
    service.store.decide(record["restart_id"], instance_id=service.instance_id, digest=record["request_digest"], allow=False)
    repeated = service.request(session_id="session", run_id="run", tool_call_id="another-tool", reason="再问一次")
    assert repeated["restart_id"] == record["restart_id"] and repeated["phase"] == "denied"
    assert mailbox.tick() is None


def test_failed_drain_can_only_retry_through_new_human_confirmation(lifecycle):
    service, mailbox, _ = lifecycle
    record = service.request(reason="manual")
    approve(service, record)
    claimed = mailbox.tick()
    service.draining = True
    mailbox.fail(claimed, "stop failed")
    with pytest.raises(LifecycleConflict):
        request(service)
    retry = service.request_manual("用户重新申请")
    assert retry["phase"] == "awaiting_confirmation" and retry["restart_id"] != record["restart_id"]
    assert service.draining and mailbox.tick() is None


def test_launch_credentials_are_not_settings_or_extension_environment(tmp_path, monkeypatch):
    import agent_harness
    from security.extensions import minimal_extension_environment
    path = tmp_path / ".env"
    path.write_text("MYAGENT_LIFECYCLE_TOKEN=forged\nMYAGENT_LIFECYCLE_SUPERVISOR_ID=forged\n", encoding="utf-8")
    monkeypatch.setattr(agent_harness, "dotenv_file_path", lambda: path)
    monkeypatch.setenv("MYAGENT_LIFECYCLE_TOKEN", "supervisor-secret")
    monkeypatch.setenv("MYAGENT_LIFECYCLE_SUPERVISOR_ID", "supervisor")
    agent_harness.load_app_dotenv()
    assert __import__("os").environ["MYAGENT_LIFECYCLE_TOKEN"] == "supervisor-secret"
    assert "MYAGENT_LIFECYCLE_TOKEN" not in minimal_extension_environment(
        allow_names=["MYAGENT_LIFECYCLE_TOKEN"], explicit={"MYAGENT_LIFECYCLE_TOKEN": "secret"})


def test_full_access_shell_does_not_inherit_lifecycle_credentials(tmp_path, monkeypatch):
    import agent_tools
    from security.models import PermissionMode
    monkeypatch.setattr(agent_tools, "active_security_context", lambda: {"context": SimpleNamespace(mode=PermissionMode.FULL_ACCESS)})
    monkeypatch.setattr(agent_tools, "WORK_DIR", tmp_path)
    monkeypatch.setenv("MYAGENT_LIFECYCLE_TOKEN", "secret")
    monkeypatch.setenv("MYAGENT_LIFECYCLE_SUPERVISOR_ID", "controller")
    assert not any(name.startswith("MYAGENT_LIFECYCLE_") for name in agent_tools._subprocess_env_for_shell())


def test_hooks_cannot_allowlist_supervisor_credentials(tmp_path):
    from hooks.executor import build_hook_environment
    definition = SimpleNamespace(command=SimpleNamespace(env_allowlist=["MYAGENT_LIFECYCLE_TOKEN"], env={}),
                                 event="PreToolUse", execution_id="hook", source_id="source", source_root=tmp_path, plugin_id="")
    env = build_hook_environment(definition, tmp_path, source_environment={"MYAGENT_LIFECYCLE_TOKEN": "secret"})
    assert "MYAGENT_LIFECYCLE_TOKEN" not in env


def test_mcp_headers_cannot_expand_supervisor_credentials(monkeypatch):
    import agent_mcp
    monkeypatch.setenv("MYAGENT_LIFECYCLE_TOKEN", "secret")
    with pytest.raises(ValueError, match="protected supervisor"):
        agent_mcp._headers_from_config({"headers": {"Authorization": "${MYAGENT_LIFECYCLE_TOKEN}"}})


def test_impact_counts_owned_runs_and_only_visible_background_jobs(lifecycle, monkeypatch):
    import agent_subagent
    import execution_services.jobs
    import session_lifecycle
    service, _, _ = lifecycle
    monkeypatch.setattr(session_lifecycle, "active_run_rows", lambda: [{"session_id": "main", "run_id": "r"}])
    monkeypatch.setattr(agent_subagent.subagent_registry, "running_runs", lambda: {"child": "c", "main": "r"})
    active = SimpleNamespace(is_set=lambda: False)
    fake = SimpleNamespace(jobs={"background": SimpleNamespace(visible=True, done=active),
                                 "foreground": SimpleNamespace(visible=False, done=active)},
                           terminals=SimpleNamespace(sessions={"pty": SimpleNamespace(status="running")}))
    monkeypatch.setattr(execution_services.jobs, "_SERVICE", fake)
    assert RuntimeLifecycle.impact(service) == {"running_tasks": 2, "background_jobs": 1, "terminals": 1}


def test_requests_survive_store_recreation(lifecycle):
    service, _, _ = lifecycle
    record = request(service)
    assert LifecycleStore(service.store.path).read(record["restart_id"]) == record


@pytest.mark.parametrize("owner", ["live", "dead", "unknown"])
def test_supervisor_relaunch_only_settles_verified_dead_old_requests(lifecycle, monkeypatch, owner):
    service, _, _ = lifecycle
    record = request(service)
    monkeypatch.setattr("run_ownership._process_start_time", lambda _: (owner, None))
    replacement = RuntimeLifecycle(service.manager, store=service.store,
        environment=supervisor_environment("new-supervisor", "new-secret", "replacement"))
    operation = replacement.status(record["restart_id"])["operations"][0]
    assert operation["phase"] == ("failed" if owner == "dead" else "awaiting_confirmation")


@pytest.mark.parametrize("commit_fails", [False, True])
def test_run_terminal_commit_precedes_supervisor_handoff(lifecycle, monkeypatch, commit_fails):
    import agent_loop
    import agent_subagent_sync
    service, mailbox, _ = lifecycle
    record = request(service)
    approve(service, record)
    monkeypatch.setattr("runtime_lifecycle._service", service)
    monkeypatch.setattr(agent_loop, "_workflow_callbacks", lambda: SimpleNamespace(call=lambda *a, **k: None))
    for name in ("_clear_steer_run_control", "_release_pending_queued_turn", "_mark_run_terminal_unread"):
        monkeypatch.setattr(agent_loop, name, lambda *a, **k: None)
    monkeypatch.setattr(agent_loop.execution_metrics, "finish_run", lambda *a, **k: None)
    async def ignore(*a, **k): pass
    monkeypatch.setattr(agent_loop, "close_session_stream", ignore)
    monkeypatch.setattr(agent_subagent_sync, "finish_manual_subagent_run", ignore)
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def commit(*a):
            entered.set()
            await release.wait()
            if commit_fails:
                raise OSError("disk write failed")
        task = asyncio.create_task(agent_loop._finalize_agent_run_lifecycle(
            state={"_lifecycle_restart_id": record["restart_id"], "_lifecycle_tool_checkpointed": True},
            session_id="session", run_id="run", mode="chat", continuation=False, completed=False,
            terminal_event={"type": "run_interrupted", "reason": "process_restart"},
            runtime_lifecycle=SimpleNamespace(commit=commit), power_guard=SimpleNamespace(close=ignore),
            steer_control=None, emit=ignore, queue=asyncio.Queue(), consumer_attached=False))
        await entered.wait()
        assert mailbox.tick() is None
        release.set()
        if commit_fails:
            with pytest.raises(OSError):
                await task
            assert mailbox.tick() is None
            assert service.store.read(record["restart_id"])["phase"] == "failed"
        else:
            await task
            assert mailbox.tick()["phase"] == "draining"
    asyncio.run(scenario())


def test_tool_waits_for_user_and_only_sets_checkpoint_intent(lifecycle, monkeypatch):
    service, mailbox, _ = lifecycle
    monkeypatch.setattr("runtime_lifecycle._service", service)
    async def scenario():
        async def ignore(*_): return []
        monkeypatch.setattr("notification_providers.notify_user", ignore)
        context = SimpleNamespace(session_id="session", run_id="run", tool_call_id="tool",
                                  state={}, services={}, publish=ignore)
        task = asyncio.create_task(invoke_restart(context, {"reason": "加载修改"}))
        for _ in range(100):
            records = service.store.recent(service.supervisor_id)
            if records: break
            await asyncio.sleep(.01)
        assert not task.done() and mailbox.tick() is None
        approve(service, records[0])
        outcome = await asyncio.wait_for(task, 2)
        assert json.loads(outcome.content)["status"] == "restart_authorized"
        assert context.state["_lifecycle_restart_id"] == records[0]["restart_id"]
        assert mailbox.tick() is None  # Only persisted finalization may release it.
    asyncio.run(scenario())


def test_decision_api_requires_ui_token_and_rejects_automatic_grants(lifecycle, monkeypatch):
    from fastapi import FastAPI
    import runtime_lifecycle
    service, mailbox, _ = lifecycle
    monkeypatch.setattr(runtime_lifecycle, "_service", service)
    app = FastAPI()
    runtime_lifecycle.register_routes(app, service.manager)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            status = (await client.get("/api/lifecycle/status")).json()
            headers = {"X-MyAgent-Lifecycle-UI": status["ui_token"], "Origin": "http://test"}
            record = request(service)
            endpoint = f'/api/lifecycle/restarts/{record["restart_id"]}/decision'
            payload = {"decision": "allow_once", "request_digest": record["request_digest"]}
            assert (await client.post(endpoint, json=payload)).status_code == 409
            assert (await client.post(endpoint, json={**payload, "decision": "allow_always"}, headers=headers)).status_code == 409
            assert (await client.post(endpoint, json=payload, headers={**headers, "Origin": "https://evil.test"})).status_code == 409
            assert mailbox.tick() is None
            response = await client.post(endpoint, json=payload, headers=headers)
            assert response.status_code == 202 and response.json()["operation"]["phase"] == "authorized"
            ready = (await client.get("/api/ready")).json()
            assert ready == {"ok": True, "protocol": "myagent-lifecycle-v1", "instance_id": service.instance_id}
    asyncio.run(scenario())


def test_prepare_ack_commits_state_before_requesting_server_exit(lifecycle, monkeypatch):
    from fastapi import FastAPI
    import runtime_lifecycle
    service, mailbox, _ = lifecycle
    monkeypatch.setattr(runtime_lifecycle, "_service", service)
    order = []
    async def save(_):
        order.append("saved")
        return []
    monkeypatch.setattr(runtime_lifecycle, "prepare_runtime", save)
    monkeypatch.setattr(runtime_lifecycle, "_exit_callback", lambda: order.append("exit"))
    record = service.request(reason="manual")
    approve(service, record)
    claimed = mailbox.tick()
    app = FastAPI()
    runtime_lifecycle.register_routes(app, service.manager)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            body = {"restart_id": claimed["restart_id"]}
            assert (await client.post("/api/lifecycle/prepare", json=body)).status_code == 403
            result = await client.post("/api/lifecycle/prepare", json=body, headers={"X-MyAgent-Supervisor": mailbox.token})
            assert result.status_code == 200 and result.json()["exiting"] is True
    asyncio.run(scenario())
    assert order == ["saved", "exit"]


@pytest.mark.parametrize("payload", [{"ok": True, "instance_id": "x"},
    {"ok": True, "protocol": "myagent-lifecycle-v1", "instance_id": "wrong"}, {"ok": False}])
def test_ready_needs_protocol_and_expected_identity(monkeypatch, payload):
    monkeypatch.setattr("lifecycle_supervisor.request_json", lambda *a, **k: payload)
    assert not backend_ready("http://test", "x")
