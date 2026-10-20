import asyncio
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture
def family(monkeypatch):
    import agent_harness
    import human_interaction
    import session_event_bus
    import webui
    from human_interaction.service import HumanInteractionService

    monkeypatch.setenv("RUNTIME_VERSION", "2")
    monkeypatch.setenv("ASK_USER_ENABLED", "1")
    # Keep nested UUID session paths below Windows' legacy path limit.
    temporary = tempfile.TemporaryDirectory(prefix=".sync-", dir=Path(__file__).resolve().parents[1])
    tmp_path = Path(temporary.name)
    manager = agent_harness.SessionManager(tmp_path, tmp_path / "sessions.json")
    parent = manager.get_or_create_session()[0]
    child = manager.create_subagent_session(parent, "child task", "generalPurpose", 1)
    nested = manager.create_subagent_session(child, "nested task", "generalPurpose", 2)
    unrelated = manager.get_or_create_session()[0]
    service = HumanInteractionService(tmp_path, path_resolver=manager._resolve_session_path)
    monkeypatch.setattr(agent_harness, "session_manager", manager)
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(human_interaction, "get_human_interaction_service", lambda: service)
    monkeypatch.setattr(session_event_bus, "_event_listeners", [])
    yield manager, service, parent, child, nested, unrelated
    temporary.cleanup()


@pytest.mark.parametrize("kind", ["question", "approval"])
def test_child_human_request_reaches_parent_without_child_page_or_parent_emitter(family, kind):
    import session_event_bus as bus
    import webui

    manager, service, parent, child, nested, unrelated = family
    if kind == "question":
        record = service.create_question(nested, {
            "questions": [{"header": "范围", "question": "选哪个？", "options": [
                {"label": "完整", "description": "全部实现"},
                {"label": "最小", "description": "仅修复"},
            ]}],
        })
        event_type, id_key = "interaction_requested", "interaction_id"
    else:
        record = service.create_approval(nested, approval_id="approval-child")
        event_type, id_key = "approval_requested", "approval_id"

    async def scenario():
        subscription = bus.subscribe_session_events(parent, replay_recent=False)
        waiting = asyncio.create_task(subscription.__anext__())
        await asyncio.sleep(0)
        await bus.publish_session_event(nested, {"type": event_type, **record})
        forwarded = await asyncio.wait_for(waiting, timeout=1)
        await subscription.aclose()
        assert forwarded["session_id"] == nested
        assert forwarded["agent_id"] == nested
        assert forwarded[id_key] == record[id_key]
        assert forwarded["request_digest"] == record["request_digest"]
        assert forwarded["_subagent_forward"] and forwarded["ephemeral"]

    asyncio.run(scenario())
    rows = webui._list_session_human_interactions(parent, kind, "pending", True)
    assert [row["session_id"] for row in rows] == [nested]
    assert webui._list_session_human_interactions(parent, kind, "pending", False) == []
    assert webui._list_session_human_interactions(unrelated, kind, "pending", True) == []
    summary = webui._build_sessions_state_snapshot()
    parent_summary = next(row for row in summary["sessions"] if row["id"] == parent)
    assert parent_summary["pending_human_interactions"]["total"] == 1
    if kind == "approval":
        service.resolve_approval(nested, record[id_key], "allow_once")
    else:
        service.resolve_question(nested, record[id_key], [{
            "question_id": record["questions"][0]["question_id"],
            "selected_option_ids": [record["questions"][0]["options"][0]["option_id"]],
        }])
    assert webui._list_session_human_interactions(parent, kind, "pending", True) == []
    assert service.pending_counts(nested)["total"] == 0


@pytest.mark.parametrize("terminal,status", [("run_finished", "completed"), ("run_failed", "failed"), ("run_interrupted", "interrupted")])
def test_manual_child_run_updates_catalog_and_delivers_result_once(family, terminal, status):
    from agent_subagent_sync import start_manual_subagent_run, finish_manual_subagent_run
    import webui

    manager, service, parent, child, nested, unrelated = family
    manager.append_ui_event(parent, {"type": "user", "content": "start task"})
    manager.append_ui_event(parent, {"type": "final", "content": "waiting for child"})
    manager.patch_subagent_metadata(child, {"subagent_ok": False, "subagent_error": "interrupted"})
    state = {"session_id": child, "_runtime_v2_run_id": "manual-run", "final_response": "manual result"}

    async def scenario():
        await start_manual_subagent_run(manager, state)
        running = json.loads(webui._build_session_subagents_response(parent, True).body)
        row = next(row for row in running["subagents"] if row["id"] == child)
        assert row["running"] and row["status"] == "running" and row["ok"] is None
        await finish_manual_subagent_run(manager, state, {"type": terminal, "error": "failure" if terminal == "run_failed" else ""})
        await finish_manual_subagent_run(manager, state, {"type": terminal})

    asyncio.run(scenario())
    finished = json.loads(webui._build_session_subagents_response(parent, True).body)
    row = next(row for row in finished["subagents"] if row["id"] == child)
    assert not row["running"] and row["status"] == status
    assert Path(row["output_file"]).read_text(encoding="utf-8") == "manual result"
    notifications = manager.consume_pending_subagent_notifications(parent)
    assert len(notifications) == 1 and "manual result" in notifications[0]
    assert manager.consume_pending_subagent_notifications(parent) == []
    assert not manager.has_pending_subagent_notifications(unrelated)


def test_superseded_manual_child_cannot_overwrite_new_run_or_deliver_stale_result(family):
    from agent_subagent_sync import start_manual_subagent_run, finish_manual_subagent_run

    manager, _, parent, child, *_ = family
    old = {"session_id": child, "_runtime_v2_run_id": "old", "final_response": "stale"}
    new = {"session_id": child, "_runtime_v2_run_id": "new", "final_response": "fresh"}

    async def scenario():
        await start_manual_subagent_run(manager, old)
        await start_manual_subagent_run(manager, new)
        await finish_manual_subagent_run(manager, old, {"type": "run_interrupted"})

    asyncio.run(scenario())
    assert manager._load_metadata(child)["subagent_run_id"] == "new"
    assert manager._load_metadata(child)["subagent_run_status"] == "running"
    assert not manager.has_pending_subagent_notifications(parent)
