import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent_team import (
    AgentTeamConflictError,
    AgentTeamDisabledError,
    AgentTeamService,
    TeamLimits,
)
from app.agent_team.api import create_agent_team_router
from app.runtime_v2.event_schema import CORE_EVENT_TYPES, RuntimeEvent
from app.runtime_v2.projector import RuntimeProjector


def test_team_event_types_are_registered_and_projected():
    required = {
        "team_created",
        "team_member_added",
        "team_task_created",
        "team_task_claimed",
        "team_message_enqueued",
        "team_shutdown_requested",
        "team_archived",
    }
    assert required.isdisjoint(CORE_EVENT_TYPES)

    snapshot = RuntimeProjector().project(
        [
            RuntimeEvent(
                seq=1,
                type="team_created",
                session_id="root",
                payload={"team_id": "team_1", "title": "Build", "max_members": 4},
            ),
            RuntimeEvent(
                seq=2,
                type="team_member_added",
                session_id="root",
                payload={"member_id": "member_1", "name": "Coder", "role": "implementation"},
            ),
            RuntimeEvent(
                seq=3,
                type="team_task_created",
                session_id="root",
                payload={"task_id": "task_1", "title": "Implement", "status": "pending"},
            ),
            RuntimeEvent(
                seq=4,
                type="team_task_claimed",
                session_id="root",
                payload={"task_id": "task_1", "member_id": "member_1"},
            ),
        ]
    )

    team = snapshot["extensions"]["agent-team"]["team"]["value"]
    assert team["team_id"] == "team_1"
    assert team["members"]["member_1"]["state"] == "starting"
    task = team["tasks"]["task_1"]
    assert task["status"] == "in_progress"
    assert task["assignee_id"] == "member_1"


def test_team_service_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENT_TEAM_ENABLED", raising=False)
    service = AgentTeamService(tmp_path)

    with pytest.raises(AgentTeamDisabledError):
        service.create_team("root")
    assert not (tmp_path / "root" / "events.jsonl").exists()


def test_team_service_persists_tasks_messages_and_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path, limits=TeamLimits(max_members=2))
    team = service.create_team("root", "Release team")
    assert team["status"] == "active"

    coder = service.add_member("root", name="Coder", role="implementation")
    reviewer = service.add_member("root", name="Reviewer", role="review")
    service.set_member_state("root", coder["member_id"], "idle")
    task = service.create_task("root", title="Implement switch")
    claimed = service.claim_task("root", task["task_id"], coder["member_id"])
    assert claimed["assignee_id"] == coder["member_id"]
    done = service.update_task("root", task["task_id"], status="completed", result="done")
    assert done["result"] == "done"

    message = service.send_message(
        "root",
        sender_id=coder["member_id"],
        recipient_ids=[reviewer["member_id"], "lead"],
        content="Ready for review",
    )
    service.update_message_delivery(
        "root", message["message_id"], reviewer["member_id"], "delivered"
    )
    inbox = service.list_inbox("root", reviewer["member_id"])
    assert [row["message_id"] for row in inbox] == [message["message_id"]]

    service.request_shutdown("root", "complete")
    stopped = service.complete_shutdown("root")
    assert stopped["status"] == "stopped"
    assert all(member["state"] == "stopped" for member in stopped["members"].values())
    assert service.archive_team("root")["status"] == "archived"

    restored = AgentTeamService(tmp_path).read_team("root")
    assert restored["tasks"][task["task_id"]]["status"] == "completed"
    assert restored["messages"][message["message_id"]]["content"] == "Ready for review"


def test_task_claim_is_atomic_under_concurrency(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path, limits=TeamLimits(max_members=2))
    service.create_team("root")
    one = service.add_member("root", name="One", role="worker")
    two = service.add_member("root", name="Two", role="worker")
    task = service.create_task("root", title="One owner")

    def claim(member_id):
        try:
            return service.claim_task("root", task["task_id"], member_id)["assignee_id"]
        except AgentTeamConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, [one["member_id"], two["member_id"]]))

    winners = [value for value in outcomes if value]
    assert len(winners) == 1
    assert service.read_team("root")["tasks"][task["task_id"]]["assignee_id"] == winners[0]


def test_team_projection_does_not_synthesize_team_from_orphan_event():
    snapshot = RuntimeProjector().project(
        [RuntimeEvent(seq=1, type="team_task_created", session_id="root", payload={"task_id": "x"})]
    )
    assert "team" not in snapshot


def test_agent_team_api_is_guarded_and_supports_control_plane(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(
        create_agent_team_router(
            lambda: AgentTeamService(tmp_path, limits=TeamLimits(max_members=2))
        )
    )

    monkeypatch.delenv("AGENT_TEAM_ENABLED", raising=False)
    with TestClient(app) as client:
        disabled = client.post("/api/agent-team/root", json={"title": "No"})
        assert disabled.status_code == 403
        assert disabled.json()["code"] == "feature_disabled"

        monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
        created = client.post("/api/agent-team/root", json={"title": "API team"})
        assert created.status_code == 200
        member = client.post(
            "/api/agent-team/root/members",
            json={"name": "Coder", "role": "implementation"},
        ).json()["data"]
        task = client.post(
            "/api/agent-team/root/tasks", json={"title": "Build API"}
        ).json()["data"]
        claimed = client.post(
            f"/api/agent-team/root/tasks/{task['task_id']}/claim",
            json={"member_id": member["member_id"]},
        )
        assert claimed.status_code == 200
        assert claimed.json()["data"]["assignee_id"] == member["member_id"]

        state = client.get("/api/agent-team/root")
        assert state.status_code == 200
        assert state.json()["data"]["title"] == "API team"


def test_agent_team_api_rejects_unknown_root_session(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    app = FastAPI()
    app.include_router(
        create_agent_team_router(
            lambda: AgentTeamService(tmp_path),
            session_exists=lambda session_id: False,
        )
    )

    with TestClient(app) as client:
        response = client.post("/api/agent-team/missing", json={})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert not (tmp_path / "missing").exists()


def test_incremental_team_projection_preserves_published_snapshot():
    projector = RuntimeProjector()
    original = projector.project(
        [
            RuntimeEvent(seq=1, type="team_created", session_id="root", payload={"team_id": "t"}),
            RuntimeEvent(
                seq=2,
                type="team_message_enqueued",
                session_id="root",
                payload={
                    "message_id": "m",
                    "sender_id": "lead",
                    "recipient_ids": ["member"],
                    "content": "hello",
                },
            ),
        ]
    )
    updated = projector.project_incremental(
        original,
        RuntimeEvent(
            seq=3,
            type="team_message_delivered",
            session_id="root",
            payload={"message_id": "m", "recipient_id": "member"},
        ),
    )

    original_message = original["extensions"]["agent-team"]["team"]["value"]["messages"]["m"]
    updated_message = updated["extensions"]["agent-team"]["team"]["value"]["messages"]["m"]
    assert original_message["status"] == "queued"
    assert original_message["deliveries"]["member"]["status"] == "queued"
    assert updated_message["status"] == "delivered"


def test_invalid_limit_environment_falls_back_safely(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TEAM_MAX_MEMBERS", "not-an-int")
    monkeypatch.setenv("AGENT_TEAM_MAX_MESSAGES", "")
    service = AgentTeamService(tmp_path)
    assert service.limits.max_members == 4
    assert service.limits.max_messages == 2000


def test_terminal_transitions_and_shutdown_order_are_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path)
    service.create_team("root")
    member = service.add_member("root", name="Worker", role="implementation")
    task = service.create_task("root", title="Finish once")
    service.claim_task("root", task["task_id"], member["member_id"])
    service.update_task("root", task["task_id"], status="completed")
    with pytest.raises(AgentTeamConflictError):
        service.update_task("root", task["task_id"], status="in_progress")

    message = service.send_message(
        "root", sender_id="lead", recipient_ids=[member["member_id"]], content="done"
    )
    service.update_message_delivery(
        "root", message["message_id"], member["member_id"], "delivered"
    )
    service.update_message_delivery(
        "root", message["message_id"], member["member_id"], "consumed"
    )
    with pytest.raises(AgentTeamConflictError):
        service.update_message_delivery(
            "root", message["message_id"], member["member_id"], "delivered"
        )

    service.request_shutdown("root")
    with pytest.raises(AgentTeamConflictError):
        service.archive_team("root")
    service.complete_shutdown("root")
    assert service.archive_team("root")["status"] == "archived"
