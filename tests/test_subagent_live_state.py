import asyncio
import json
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_subagent_registry_exposes_only_live_run_id():
    from agent_subagent import SubagentTaskRegistry

    registry = SubagentTaskRegistry()
    assert asyncio.run(registry.reserve("child", "run-child"))
    assert registry.running_runs() == {"child": "run-child"}
    assert asyncio.run(registry.unregister("child", "run-child"))
    assert registry.running_runs() == {}


def test_root_state_snapshot_includes_active_nested_child_identity(monkeypatch):
    import agent_subagent
    import webui

    class Manager:
        def list_sessions(self, include_archived=False):
            return [{"id": "parent", "name": "Parent"}]

        def archived_session_count(self):
            return 0

        def _load_metadata(self, sid):
            assert sid == "child"
            return {"subagent_run_started_at": "2026-09-29T08:14:36Z"}

    class HumanService:
        def pending_counts_many(self, _ids):
            return {}

        def pending_counts(self, _sid):
            return {"questions": 0, "approvals": 0, "total": 0}

    import human_interaction

    monkeypatch.setattr(webui, "session_manager", Manager())
    monkeypatch.setattr(webui, "_is_subagent_execution_active", lambda sid: sid == "child")
    monkeypatch.setattr(webui, "get_active_run_info", lambda _sid: None)
    monkeypatch.setattr(webui, "is_run_active", lambda _sid: False)
    monkeypatch.setattr(webui, "_active_chat_by_session", {})
    monkeypatch.setattr(webui, "_chat_starting_by_session", {})
    monkeypatch.setattr(webui, "is_session_title_generation_pending", lambda _sid: False)
    monkeypatch.setattr(agent_subagent.subagent_registry, "running_runs", lambda: {"child": "run-child"})
    monkeypatch.setattr(human_interaction, "get_human_interaction_service", lambda: HumanService())

    state = webui._session_run_state_fields_light("child")
    assert state["active_run"]["run_id"] == "run-child"
    assert state["active_run"]["started_at"] == "2026-09-29T08:14:36Z"

    snapshot = webui._build_sessions_state_snapshot()
    assert [row["id"] for row in snapshot["sessions"]] == ["parent"]
    assert [run["session_id"] for run in snapshot["active_runs"]] == ["child"]
    assert snapshot["active_runs"][0]["run_id"] == "run-child"


def test_recover_append_steer_requeues_when_child_still_running(monkeypatch):
    import webui

    monkeypatch.setattr(webui, "_is_subagent_execution_active", lambda sid: sid == "child")
    monkeypatch.setattr(webui, "get_session_steer", lambda *_args, **_kwargs: {
        "ok": True,
        "item": {"id": "steer", "state": "restarting", "mode": "append",
                 "replacement_run_id": "wrong-replacement"},
    })
    calls = []

    def transition(*args, **kwargs):
        calls.append((args, kwargs))
        return {"ok": True, "item": {"id": "steer", "state": "queued"}}

    monkeypatch.setattr(webui, "transition_session_steer", transition)
    response = asyncio.run(webui.recover_session_steer("child", "steer"))
    assert json.loads(response.body)["item"]["state"] == "queued"
    assert calls == [(('child', 'steer', {'restarting'}, 'queued'), {
        "replacement_run_id": "", "claimed_by": "", "claimed_at": 0,
    })]


def test_child_detail_is_addressable_without_root_index_entry(monkeypatch):
    import webui
    from workflow_extensions import session_workflows

    class Manager:
        def get_session_summary(self, _sid):
            return None

        def _load_metadata(self, _sid):
            return {"is_subagent": True, "parent_session_id": "parent", "name": "Child"}

        def can_continue_react_session(self, _sid):
            return False

    monkeypatch.setattr(webui, "session_manager", Manager())
    monkeypatch.setattr(webui, "_cleanup_stale_active_chat", lambda: None)
    monkeypatch.setattr(webui, "_session_run_state_fields_light", lambda _sid: {
        "stream_active": True, "run_active": True,
        "run_started_at": "2026-09-29T08:14:36Z",
        "active_run": {"session_id": "child", "run_id": "run-child", "run_active": True},
    })
    monkeypatch.setattr(webui, "is_session_title_generation_pending", lambda _sid: False)
    monkeypatch.setattr(webui, "_session_pending_human_counts", lambda _sid: {
        "questions": 0, "approvals": 0, "total": 0,
    })
    monkeypatch.setattr(session_workflows, "continuation_source", lambda _sid: "")
    response = asyncio.run(webui.get_session_detail("child"))
    detail = json.loads(response.body)
    assert response.status_code == 200
    assert detail["id"] == "child"
    assert detail["parent_session_id"] == "parent"
    assert detail["active_run"]["run_id"] == "run-child"


def test_followup_takeover_cannot_start_chat_over_running_child(monkeypatch):
    import webui

    monkeypatch.setattr(webui, "_is_subagent_execution_active", lambda _sid: True)
    monkeypatch.setattr(webui.session_manager, "get_interrupt_reason", lambda _sid: "followup")
    assert webui._reserve_session_chat_start("child", "replacement") is None
