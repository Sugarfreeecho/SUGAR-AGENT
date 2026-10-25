import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture
def background_session(tmp_path, monkeypatch):
    import agent_subagent
    import webui
    from agent_harness import SessionManager
    from execution_services import jobs

    sid = "19191919-1919-4191-8191-191919191919"
    directory = tmp_path / "sessions" / sid
    directory.mkdir(parents=True)
    metadata = {"id": sid, "name": "background", "created_at": "2099-01-01T00:00:00Z"}
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    index = tmp_path / "sessions.json"
    index.write_text(json.dumps({"sessions": [metadata]}), encoding="utf-8")
    manager = SessionManager(directory.parent, index)
    manager.add_session_state_listener(webui._on_session_manager_state_changed)
    service = jobs.ExecutionService(manager)
    registry = agent_subagent.SubagentTaskRegistry()
    monkeypatch.setattr(jobs, "_SERVICE", service)
    monkeypatch.setattr(agent_subagent, "subagent_registry", registry)
    monkeypatch.setattr(agent_subagent, "session_manager", manager)
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    state = {"stream_active": False, "run_active": False, "run_started_at": None, "active_run": None}
    monkeypatch.setattr(webui, "_session_run_state_fields_light", lambda _: dict(state))
    monkeypatch.setattr(webui, "_session_run_state_fields", lambda _: dict(state))
    webui._invalidate_sessions_state_cache()
    yield manager, sid, service, registry
    webui._invalidate_sessions_state_cache()


def test_background_work_includes_descendants_but_not_hidden_or_finished_jobs(monkeypatch):
    import agent_subagent
    import session_lifecycle
    from execution_services import jobs
    from session_activity import background_work_snapshot

    manager = SimpleNamespace(_load_subagent_index=lambda: {
        "child": "root", "grandchild": "child", "manual": "root", "other-child": "other",
    })
    service = jobs.ExecutionService(manager)
    service.jobs = {str(i): jobs.Job(str(i), owner, "process", "test", visible=visible, status=status)
        for i, (owner, visible, status) in enumerate([
            ("root", True, "running"), ("grandchild", True, "stopping"),
            ("root", False, "running"), ("root", True, "completed"),
            ("root", True, "failed"), ("root", True, "killed"), ("other", True, "running"),
        ])}
    service.terminals = SimpleNamespace(sessions={"user": SimpleNamespace(actor="user", status="running")})
    monkeypatch.setattr(jobs, "_SERVICE", service)
    monkeypatch.setattr(agent_subagent, "subagent_registry", SimpleNamespace(running_runs=lambda: {
        "child": "r1", "grandchild": "r2", "other-child": "r3",
    }))
    monkeypatch.setattr(session_lifecycle, "is_run_active", lambda child: child == "manual")
    snapshot = background_work_snapshot(manager)
    assert snapshot["root"] == {"background_jobs_running": 2, "subagent_running": 3}
    assert snapshot["child"] == {"background_jobs_running": 1, "subagent_running": 1}
    assert snapshot["grandchild"] == {"background_jobs_running": 1, "subagent_running": 0}
    assert snapshot["other"] == {"background_jobs_running": 1, "subagent_running": 1}
    # The finished child's continuing job still belongs to every ancestor.
    monkeypatch.setattr(agent_subagent, "subagent_registry", SimpleNamespace(running_runs=lambda: {}))
    monkeypatch.setattr(session_lifecycle, "is_run_active", lambda _: False)
    assert background_work_snapshot(manager)["root"] == {"background_jobs_running": 2, "subagent_running": 0}


@pytest.mark.parametrize("work", ["job", "subagent"])
def test_main_run_is_not_complete_until_background_work_finishes(background_session, monkeypatch, work):
    import agent_loop

    manager, sid, service, registry = background_session
    monkeypatch.setattr(agent_loop, "session_manager", manager)
    child = "29292929-2929-4292-8292-292929292929"
    if work == "job":
        job = asyncio.run(service.admit(sid, "process", "background"))
    else:
        monkeypatch.setattr(manager, "_load_subagent_index", lambda: {child: sid})
        asyncio.run(registry.reserve(child, "child-run", parent_session_id=sid))
    manager.mark_session_unread_result(sid, run_id="old-run")
    agent_loop._mark_run_terminal_unread(sid, "run_finished", "main-run")
    assert manager.get_session_summary(sid)["unread_result"] is False
    # Failures remain recorded even while their indicator is covered by work.
    agent_loop._mark_run_terminal_unread(sid, "run_failed", "failed-run")
    assert manager.get_session_summary(sid)["unread_result_status"] == "failed"
    if work == "job":
        asyncio.run(service.settle(job))
    else:
        asyncio.run(registry.unregister(child, "child-run"))
    agent_loop._mark_run_terminal_unread(sid, "run_finished", "continuation-run")
    assert manager.get_session_summary(sid)["unread_result_status"] == "success"


@pytest.mark.parametrize("work", ["job", "subagent"])
def test_all_summary_endpoints_refresh_on_background_transitions(background_session, monkeypatch, work):
    import webui
    from starlette.testclient import TestClient

    manager, sid, service, registry = background_session
    client = TestClient(webui.fastapi_app)
    child = "29292929-2929-4292-8292-292929292929"
    monkeypatch.setattr(manager, "_load_subagent_index", lambda: {child: sid})
    manager.mark_session_unread_result(sid, run_id="old-run")
    before = client.get("/sessions/state").json()
    if work == "job":
        job = asyncio.run(service.admit(sid, "process", "background"))
        field = "background_jobs_running"
    else:
        asyncio.run(registry.reserve(child, "child-run", parent_session_id=sid))
        field = "subagent_running"
    during = client.get("/sessions/state").json()
    assert during["state_revision"] > before["state_revision"]
    summaries = [during["sessions"][0], client.get("/sessions").json()[0],
                 client.get(f"/sessions/{sid}").json(), client.get(f"/sessions/{sid}?include_subagents=true").json()]
    for summary in summaries:
        assert summary[field] == 1
        assert summary["run_active"] is False
        assert summary["unread_result"] is False
    assert webui._ui_attention_terminal_is_obsolete(sid, "completed") is True
    if work == "job":
        asyncio.run(service.settle(job))
    else:
        asyncio.run(registry.unregister(child, "child-run"))
    after = client.get("/sessions/state").json()
    assert after["state_revision"] > during["state_revision"]
    assert after["sessions"][0][field] == 0
    assert webui._ui_attention_terminal_is_obsolete(sid, "completed") is False


def test_output_persistence_does_not_republish_unchanged_activity(background_session):
    manager, sid, service, _ = background_session
    changes = []
    manager.add_session_state_listener(lambda owner, fields: changes.append((owner, fields)))
    job = asyncio.run(service.admit(sid, "process", "background"))
    asyncio.run(service._persist_job(job))
    job.status = "stopping"
    asyncio.run(service._persist_job(job))
    asyncio.run(service.settle(job))
    assert changes == [(sid, frozenset({"background_jobs_running"}))] * 2


def test_durable_and_live_run_terminals_keep_background_work_pending(background_session, monkeypatch):
    import agent_loop
    import agent_subagent_sync

    manager, sid, service, _ = background_session
    asyncio.run(service.admit(sid, "process", "background"))
    monkeypatch.setattr(agent_loop, "session_manager", manager)
    monkeypatch.setattr(agent_loop, "_workflow_callbacks", lambda: SimpleNamespace(call=lambda *a, **k: None))
    for name in ("_clear_steer_run_control", "_release_pending_queued_turn"):
        monkeypatch.setattr(agent_loop, name, lambda *a, **k: None)
    monkeypatch.setattr(agent_loop.execution_metrics, "finish_run", lambda *a, **k: None)
    emitted, committed = [], []

    async def ignore(*a, **k):
        pass

    async def emit(event):
        emitted.append(event)

    async def commit(kind, payload):
        committed.append((kind, payload))

    monkeypatch.setattr(agent_loop, "close_session_stream", ignore)
    monkeypatch.setattr(agent_subagent_sync, "finish_manual_subagent_run", ignore)

    async def scenario():
        await agent_loop._finalize_agent_run_lifecycle(
            state={}, session_id=sid, run_id="parent-run", mode="chat", continuation=False,
            completed=True, terminal_event={}, runtime_lifecycle=SimpleNamespace(commit=commit),
            power_guard=SimpleNamespace(close=ignore), steer_control=None, emit=emit,
            queue=asyncio.Queue(), consumer_attached=False,
        )

    asyncio.run(scenario())
    assert committed[0][0] == "run_finished"
    assert committed[0][1]["result_status"] == "pending"
    assert emitted[0]["result_status"] == "pending"
    assert emitted[0]["background_jobs_running"] == 1
    assert emitted[0]["subagent_running"] == 0
    assert not manager.get_session_summary(sid).get("unread_result")
