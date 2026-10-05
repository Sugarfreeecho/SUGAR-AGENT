import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture
def queued_runtime(monkeypatch, tmp_path):
    import agent_loop

    class Manager:
        sessions_dir = tmp_path
        repository = SimpleNamespace(sessions_dir=tmp_path)

        def _resolve_session_path(self, sid):
            return tmp_path / sid

        def clear_interrupt(self, *args):
            pass

        def is_interrupt_requested(self, *args):
            return False

        def append_ui_event(self, *args):
            pass

        def _load_metadata(self, *args):
            return {"name": "Queue test"}

        def clear_session_unread_result(self, *args, **kwargs):
            pass

        def mark_session_unread_result(self, *args, **kwargs):
            pass

    monkeypatch.setenv("RUNTIME_VERSION", "2")
    monkeypatch.setattr(agent_loop, "session_manager", Manager())
    monkeypatch.setattr(agent_loop, "_load_key_context_for_run", lambda *args: "")
    monkeypatch.setattr(agent_loop, "_load_model_history_dicts_v2_primary", lambda *args, **kwargs: [])
    monkeypatch.setattr(agent_loop, "_load_work_history_dicts_for_run", lambda *args: [])
    monkeypatch.setattr(agent_loop.session_plan_store, "sync_session_from_key_context", lambda *args: None)
    for name in ("setup_logging", "_runtime_v2_append_model_message", "_persist_state",
                 "_persist_session_messages_with_model_replace", "schedule_session_title_generation"):
        monkeypatch.setattr(agent_loop, name, lambda *args, **kwargs: None)
    agent_loop._STEER_QUEUES.clear()
    agent_loop._STEER_QUEUE_SIGNATURES.clear()
    return agent_loop, tmp_path


def publish(agent, sid, *texts):
    return agent.sync_session_followup_queue(sid, [
        {"client_id": text, "content": text, "ui_content": text, "mode": "append"}
        for text in texts
    ])


def test_queue_is_durable_ordered_and_only_claimed_after_a_complete_answer(queued_runtime):
    agent, _ = queued_runtime
    publish(agent, "queue", "second", "third")
    publish(agent, "queue", "third", "second")
    agent._STEER_QUEUES.clear()
    assert [x["content"] for x in agent.list_session_steers("queue")["items"]] == ["third", "second"]
    assert not agent._has_session_steers("queue")
    assert agent._claim_session_steers("queue", "run") == []
    first = agent._claim_session_steers("queue", "run", after_turn=True)
    assert [x["content"] for x in first] == ["third"]
    assert agent.remove_session_steer("queue", client_id="second")["ok"]
    assert not agent.remove_session_steer("queue", client_id="third")["ok"]
    publish(agent, "queue", "second", "third")
    assert agent.get_session_steer("queue", client_id="second")["item"]["state"] == "cancelled"
    assert not agent.transition_session_steer(
        "queue", first[0]["id"], {"queued"}, "claimed", claimed_by="competing-run"
    )["ok"]
    assert not agent.transition_session_steer(
        "queue", first[0]["id"], {"queued"}, "claimed", claimed_by="run"
    )["ok"], "even a repeated start for the same run must not claim twice"


@pytest.mark.parametrize("continuation", [False, True])
def test_three_answers_keep_one_run_and_distinct_durable_turns(queued_runtime, monkeypatch, continuation):
    agent, directory = queued_runtime
    from runtime_v2.event_log import SessionEventLog
    from runtime_v2.projector import RuntimeProjector
    from runtime_v2.ui_projection import RuntimeUiProjection

    sid = "continuous"
    if continuation:
        agent._runtime_v2_react_history_ops().commit_user_turn(sid, "first", run_id="previous")
    publish(agent, sid, "second", "third")
    prompts = []

    async def react(state, emit):
        from session_lifecycle import get_active_run_info
        assert get_active_run_info(sid)["phase"] == "running"
        snapshot = RuntimeProjector().project(SessionEventLog(directory).read_all(sid))
        assert snapshot["runs"]["same-run"]["phase"] == "running"
        assert not agent._has_session_steers(sid), "ordinary queued inputs must not steer the current answer"
        prompts.append(state["user_input"])
        state["_current_react_iter"] = state.get("_queued_react_iter_offset", 0) + 1
        state["final_response"] = "answer " + str(len(prompts))
        state["_queue_can_continue"] = True
        return state

    monkeypatch.setattr(agent, "_run_react_node_off_loop", react)
    seen = []

    async def collect():
        stream = (agent.astream_events_continuation(sid, require_pending_subagents=False, run_id="same-run")
                  if continuation else agent.astream_events("first", session_id=sid, run_id="same-run"))
        async for event in stream:
            if event.get("type") == "final":
                snapshot = RuntimeProjector().project(SessionEventLog(directory).read_all(sid))
                assert snapshot["active_runs"], "a complete answer must not terminate a run that has queued inputs"
            seen.append(event)

    asyncio.run(collect())
    assert len(prompts) == 3
    assert prompts[-2:] == ["second", "third"]
    assert [x["content"] for x in seen if x.get("type") == "final"] == ["answer 1", "answer 2", "answer 3"]
    assert sum(x.get("type") == "run_started" for x in seen) == 1
    assert sum(x.get("type") == "run_finished" for x in seen) == 1
    assert not any(x.get("type") in {"run_failed", "run_interrupted"} for x in seen)
    assert {x.get("run_id") for x in seen if x.get("run_id")} == {"same-run"}
    durable = SessionEventLog(directory).read_all(sid)
    finals = [x for x in durable if x.type == "assistant_final_committed"]
    assert len(finals) == 3, "final deduplication must use a turn id, not just the shared run id"
    assert len({x.payload["operation_id"] for x in finals}) == 3
    projection = RuntimeUiProjection(directory).read_ui_events(sid)
    users = [x for x in projection if x["type"] == "user"]
    assert len({x["turn_id"] for x in users}) == 3
    assert agent._latest_official_user_turn_id(sid) == users[-1]["turn_id"]
    assert agent.list_session_steers(sid)["items"] == []


@pytest.mark.parametrize("continuation", [False, True])
def test_displayed_llm_error_is_a_failed_run_and_pauses_goal(queued_runtime, monkeypatch, continuation):
    agent, directory = queued_runtime
    from agent_goal import GoalManager
    from runtime_v2.event_log import SessionEventLog
    from runtime_v2.projector import RuntimeProjector

    sid = "goal-api-error"
    monkeypatch.setenv("GOAL_ENABLED", "1")
    manager = GoalManager(directory)
    manager.create(sid, "Finish the task")
    if continuation:
        agent._runtime_v2_react_history_ops().commit_user_turn(sid, "first", run_id="previous")
        manager.mark_continuation_started(sid, run_id="failed-run")
    publish(agent, sid, "later")

    class Callbacks:
        @staticmethod
        async def call_async(*_args, **_kwargs):
            return None

        @staticmethod
        def call(name, *args, **kwargs):
            if name == "record_run_usage":
                return manager.record_run(sid, 0, run_id="failed-run", **kwargs)
            return None

    async def failed_react(state, emit):
        state["final_response"] = "LLM 调用失败 [403] 访问被拒绝"
        state["_run_error"] = "PermissionDeniedError: provider returned 403"
        return state

    monkeypatch.setattr(agent, "_workflow_callbacks", lambda: Callbacks())
    monkeypatch.setattr(agent, "_run_react_node_off_loop", failed_react)

    async def collect():
        stream = (agent.astream_events_continuation(sid, require_pending_subagents=False, run_id="failed-run")
                  if continuation else agent.astream_events("first", session_id=sid, run_id="failed-run"))
        return [event async for event in stream]

    seen = asyncio.run(collect())
    assert any(event.get("type") == "final" and "403" in event.get("content", "") for event in seen)
    assert seen[-1]["type"] == "run_failed"
    assert not any(event.get("type") == "run_finished" for event in seen)
    goal = manager.get(sid)
    assert goal["status"] == "paused"
    assert goal["last_error"] == "PermissionDeniedError: provider returned 403"
    assert not manager.should_continue(sid)
    assert agent.list_session_steers(sid)["items"][0]["state"] == "queued"
    snapshot = RuntimeProjector().project(SessionEventLog(directory).read_all(sid))
    assert snapshot["runs"]["failed-run"]["status"] == "failed"


@pytest.mark.parametrize("blocked", ["stop", "limit", "hook", "failure", "api_error"])
def test_stop_and_failure_boundaries_preserve_the_pending_queue(queued_runtime, monkeypatch, blocked):
    agent, _ = queued_runtime
    publish(agent, "stop", "later")
    state = {"session_id": "stop", "_runtime_v2_run_id": "run"}
    if blocked == "limit":
        state["react_limit_reached"] = True
    elif blocked == "hook":
        state["_queue_continuation_blocked"] = True
    elif blocked == "failure":
        state["_queue_can_continue"] = False
    elif blocked == "api_error":
        state["_run_error"] = "provider rejected the request"
    assert not asyncio.run(agent._continue_with_queued_turn(state, None, lambda sid: blocked == "stop"))
    assert agent.list_session_steers("stop")["items"][0]["state"] == "queued"


def test_queue_api_preserves_skills_and_does_not_abort(queued_runtime, monkeypatch):
    agent, directory = queued_runtime
    import webui

    monkeypatch.setattr(webui, "WORK_DIR", directory)
    monkeypatch.setattr(webui, "sync_session_followup_queue", agent.sync_session_followup_queue)
    monkeypatch.setattr(webui, "_valid_selected_skill_names", lambda names: names)
    monkeypatch.setattr(webui, "abort_session_steer_run", lambda *args, **kwargs: pytest.fail("queue must not abort"))

    class Request:
        async def json(self):
            return {"items": [{"client_id": "skill", "message": "next", "selected_skills": ["read"]}]}

    response = asyncio.run(webui.post_session_followup_queue("api", Request()))
    assert response.status_code == 200
    item = json.loads(response.body)["items"][0]
    assert item["after_turn"] and item["selected_skills"] == ["read"]
    assert "read" in item["user_content"]


def test_cancel_during_prompt_hooks_releases_the_unstarted_turn(queued_runtime, monkeypatch):
    agent, _ = queued_runtime
    operation = publish(agent, "cancel-hook", "later")["items"][0]
    state = {"session_id": "cancel-hook", "_runtime_v2_run_id": "owner", "llm_history": [], "work_messages": []}

    async def run():
        entered = asyncio.Event()

        async def hook(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(agent, "_dispatch_state_hook", hook)
        task = asyncio.create_task(agent._continue_with_queued_turn(state, None))
        await entered.wait()
        agent.release_session_followup_claim("cancel-hook", operation["id"], "other-owner")
        assert agent.get_session_steer("cancel-hook", steer_id=operation["id"])["item"]["state"] == "claimed"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        agent._release_pending_queued_turn(state)

    asyncio.run(run())
    assert agent.get_session_steer("cancel-hook", steer_id=operation["id"])["item"]["state"] == "queued"


def test_idle_fallback_claims_the_same_operation_only_once(queued_runtime, monkeypatch):
    agent, directory = queued_runtime
    import webui

    operation = publish(agent, "idle", "next")["items"][0]
    for name in ("get_session_steer", "transition_session_steer", "release_session_followup_claim"):
        monkeypatch.setattr(webui, name, getattr(agent, name))
    monkeypatch.setattr(webui, "session_manager", agent.session_manager)
    monkeypatch.setattr(webui, "WORK_DIR", directory)
    monkeypatch.setattr(webui, "astream_events", agent.astream_events)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda *args: "reserved")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda *args: None)
    monkeypatch.setattr(webui, "_runtime_v2_legacy_only_migration_pending", lambda *args: {"pending": False})
    monkeypatch.setattr(webui, "_runtime_v2_chat_protocol_enabled", lambda *args: False)

    async def react(state, emit):
        state["final_response"] = "done"
        return state

    monkeypatch.setattr(agent, "_run_react_node_off_loop", react)

    class Request:
        async def is_disconnected(self):
            return False

    async def run():
        kwargs = dict(request=Request(), message="next", session_id="idle", client_run_id="fallback",
                      stream_protocol="runtime_v2", followup_steer=False, queued_followup=True,
                      steer_id=operation["id"], selected_skills="[]", ui_message="next",
                      ui_language="zh-CN", attachments="[]", preserve_unread_result=True)
        response = await webui.chat(**kwargs)
        duplicate = await webui.chat(**kwargs)
        assert duplicate.status_code == 409
        chunks = [chunk async for chunk in response.body_iterator]
        assert any('"type": "final"' in chunk for chunk in chunks)
        assert agent.get_session_steer("idle", steer_id=operation["id"])["item"]["state"] == "consumed"

    asyncio.run(run())


def test_queued_user_turn_is_projected_live_without_optimistic_skip(queued_runtime, monkeypatch):
    agent, _ = queued_runtime
    import webui

    monkeypatch.setattr(webui, "session_manager", agent.session_manager)
    event = agent._runtime_v2_react_history_ops().commit_user_turn(
        "live", "next", run_id="shared", operation_id="queued-id",
        model_payload={"queued_followup": True, "client_id": "client", "turn_id": "queued-id"},
    )
    payload = webui._runtime_v2_chat_sse_payload("live", event.to_dict())
    assert not payload.get("skip_ui")
    assert payload["ui_event"]["type"] == "user"
    assert payload["ui_event"]["queued_followup"] is True
    assert payload["ui_event"]["turn_id"] == "queued-id"


def test_queued_image_survives_registration_and_turn_commit(queued_runtime, monkeypatch):
    agent, directory = queued_runtime
    import webui
    from PIL import Image
    from attachments.request_budget import walk_images

    image_path = directory / "queued.png"
    Image.new("RGB", (8, 8), "blue").save(image_path)
    monkeypatch.setattr(webui, "WORK_DIR", directory)
    monkeypatch.setattr(webui, "sync_session_followup_queue", agent.sync_session_followup_queue)

    class Request:
        async def json(self):
            return {"items": [{"client_id": "image", "message": "look at this", "attachments": [{"path": str(image_path)}]}]}

    response = asyncio.run(webui.post_session_followup_queue("image", Request()))
    assert response.status_code == 200
    operation = json.loads(response.body)["items"][0]
    state = {"session_id": "image", "_runtime_v2_run_id": "owner", "stream_events": [],
             "llm_history": [], "work_messages": []}
    assert asyncio.run(agent._consume_steer_messages(state, after_turn=True))
    images = list(walk_images(state["llm_history"][-1].content))
    assert images[0]["attachment"]["attachmentId"] == operation["ui_attachments"][0]["attachmentId"]
