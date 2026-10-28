"""Recoverability and concurrency regressions found while completing consoles."""
import asyncio
import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def team_store(tmp_path, monkeypatch):
    from agent_team.service import AgentTeamService
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    monkeypatch.setenv("AGENT_TEAM_AUTO_SCHEDULE", "0")
    service = AgentTeamService(tmp_path)
    service.create_team("root")
    member = service.add_member("root", name="Coder", role="implementation", child_session_id="child")
    service.set_member_state("root", member["member_id"], "idle")
    return service, member


def test_cancelled_writer_waiter_settles_while_owner_still_holds_lock():
    from agent_team.policy import acquire_workspace_write_lock

    async def scenario():
        lock = threading.Lock()
        lock.acquire()
        try:
            waiter = asyncio.create_task(acquire_workspace_write_lock(lock))
            await asyncio.sleep(0.03)
            waiter.cancel()
            done, _ = await asyncio.wait({waiter}, timeout=0.2)
            assert waiter in done, "cancellation waited for the unrelated lock owner"
            assert waiter.cancelled()
            assert lock.locked()
        finally:
            lock.release()

    asyncio.run(scenario())


def test_member_reservation_rejects_second_dispatch_and_shutdown(team_store):
    from agent_team.models import AgentTeamConflictError
    service, member = team_store
    mid = member["member_id"]
    service.set_member_state("root", mid, "working", expected_states={"idle"})
    with pytest.raises(AgentTeamConflictError):
        service.set_member_state("root", mid, "working", expected_states={"idle"})
    with pytest.raises(AgentTeamConflictError):
        service.remove_member("root", mid)
    service.request_shutdown("root")
    with pytest.raises(AgentTeamConflictError):
        service.complete_shutdown("root")
    service.set_member_state("root", mid, "idle")
    assert service.complete_shutdown("root")["status"] == "stopped"


def test_task_reset_clears_owner_and_blocked_task_can_be_released(team_store):
    service, member = team_store
    tid = service.create_task("root", title="Recover work")["task_id"]
    mid = member["member_id"]
    service.claim_task("root", tid, mid)
    service.update_task("root", tid, status="blocked")
    assert service.release_task("root", tid, mid)["assignee_id"] is None
    service.claim_task("root", tid, mid)
    assert service.update_task("root", tid, status="pending")["assignee_id"] is None
    assert service.claim_next_task("root", mid)["task_id"] == tid


def test_recipient_can_consume_queued_mail_without_a_delivery_worker(team_store):
    service, member = team_store
    message = service.send_message("root", sender_id="lead", recipient_ids=[member["member_id"]], content="Review")
    result = service.update_message_delivery("root", message["message_id"], member["member_id"], "consumed")
    assert result["status"] == "consumed"
    assert service.list_inbox("root", member["member_id"]) == []


def test_team_reads_do_not_copy_the_conversation(team_store, monkeypatch):
    service, _ = team_store
    team = service.read_team("root")
    class Unrelated:
        def __deepcopy__(self, memo): raise AssertionError("copied the transcript")
    monkeypatch.setattr(service.store.snapshots, "read_consistent_view", lambda *args: {
        "raw_model_messages": Unrelated(), "extensions": {"agent-team": {"team": {"value": team}}}})
    value = service.read_team("root")
    value["members"].clear()
    assert team["members"]


def test_team_runtime_api_validates_session_and_action(team_store):
    from agent_team.api import create_agent_team_router
    service, _ = team_store
    received = []
    async def runtime(sid, data):
        received.append((sid, data))
        return {"accepted": True}
    app = FastAPI()
    app.include_router(create_agent_team_router(lambda: service, session_exists=lambda sid: sid == "root", runtime_action=runtime))
    with TestClient(app) as client:
        assert client.post("/api/agent-team/missing/control", json={"action": "auto_schedule"}).status_code == 404
        assert client.post("/api/agent-team/root/control", json={"action": "unknown"}).status_code == 400
        assert client.post("/api/agent-team/root/control", json={"action": "auto_schedule"}).json()["data"]["accepted"]
    assert received == [("root", {"action": "auto_schedule"})]


def test_dispatch_rejects_foreign_owner_without_running_child(team_store, monkeypatch):
    import agent_subagent  # Load host configuration before setting the test toggle.
    from agent_team import tools
    from agent_team.models import AgentTeamError
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service, member = team_store
    other = service.add_member("root", name="Reviewer", role="review", child_session_id="reviewer")
    tid = service.create_task("root", title="Exclusive ownership")["task_id"]
    service.claim_task("root", tid, other["member_id"])
    with pytest.raises(AgentTeamError, match="another member"):
        asyncio.run(tools._dispatch_member(service, "root", member_id=member["member_id"], prompt="", task_id=tid,
            run_in_background=False, parent_key_context="", emit=None, parent_run_id="run"))
    assert service.read_team("root")["members"][member["member_id"]]["state"] == "idle"


def test_goal_resume_from_blocked_and_reject_stale_identity(tmp_path, monkeypatch):
    from agent_goal import GoalManager, GoalError
    monkeypatch.setenv("GOAL_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    manager = GoalManager(tmp_path)
    old = manager.create("s1", "Finish migration")
    for i in range(3):
        manager.update_status("s1", "blocked", "Missing credential", report_id=f"run-{i}", blocker_key="credential")
    assert manager.get("s1")["status"] == "blocked"
    resumed = manager.user_action("s1", "resume")
    assert resumed["status"] == "active" and resumed["blocked_streak"] == 0
    manager.user_action("s1", "delete")
    manager.create("s1", "New objective")
    with pytest.raises(GoalError, match="Goal changed"):
        manager.user_action("s1", "edit", objective="stale edit", expected_goal_id=old["id"])
    assert manager.get("s1")["objective"] == "New objective"


def test_host_team_tool_accepts_parent_runtime_config(team_store, monkeypatch):
    from agent_team import tools
    service, _ = team_store
    monkeypatch.setattr(tools, "_service", lambda: service)
    result = asyncio.run(tools.execute_team_tool({"action": "status"}, session_id="root", parent_runtime_config={"read_only": True}))
    assert json.loads(result)["data"]["status"] == "active"


def test_task_dependency_edits_reject_cycles_and_stale_updates(team_store):
    from agent_team.models import AgentTeamConflictError, AgentTeamValidationError
    service, _ = team_store
    first = service.create_task("root", title="First")
    second = service.create_task("root", title="Second", depends_on=[first["task_id"]])
    with pytest.raises(AgentTeamValidationError, match="cycle"):
        service.update_task("root", first["task_id"], status="pending", depends_on=[second["task_id"]])
    changed = service.update_task("root", first["task_id"], status="pending", title="New title", expected_seq=first["seq"])
    assert changed["title"] == "New title"
    with pytest.raises(AgentTeamConflictError, match="task changed"):
        service.update_task("root", first["task_id"], status="pending", title="Stale title", expected_seq=first["seq"])


def test_background_child_cancellation_settles_member(team_store, monkeypatch):
    import agent_harness
    import agent_subagent
    from agent_team import tools
    from types import SimpleNamespace
    service, member = team_store
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    monkeypatch.setenv("AGENT_TEAM_AUTO_SCHEDULE", "0")
    monkeypatch.setattr(agent_harness, "session_manager", SimpleNamespace(_load_metadata=lambda _: {"subagent_run_status": "interrupted"}))
    async def run(**kwargs): return "accepted"
    async def cancelled_child(_): raise asyncio.CancelledError()
    monkeypatch.setattr(agent_subagent, "run_subagent_task", run)
    monkeypatch.setattr(agent_subagent.subagent_registry, "wait", cancelled_child)
    async def scenario():
        await tools._dispatch_member(service, "root", member_id=member["member_id"], prompt="work", task_id="",
            run_in_background=True, parent_key_context="", emit=None, parent_run_id="run")
        for _ in range(100):
            await asyncio.sleep(0.01)
            if service.read_team("root")["members"][member["member_id"]]["state"] != "working": break
        assert service.read_team("root")["members"][member["member_id"]]["state"] == "idle"
    asyncio.run(scenario())
