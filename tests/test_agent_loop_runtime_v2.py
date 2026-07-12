import sys
import asyncio
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _NoLegacySessionManager:
    def reconcile_llm_work_to_ui_user_count(self, *args, **kwargs):
        raise AssertionError("Runtime V2 projection reads must not reconcile legacy history")

    def _load_llm_history(self, session_id):
        raise AssertionError("Runtime V2 projection reads must not load legacy llm_history")

    def can_continue_after_subagents(self, session_id):
        return True

    def _load_key_context(self, session_id):
        raise AssertionError("Runtime V2 run setup must not load legacy key_context")

    def migrate_todo_plan_off_key_context(self, session_id, key_context):
        raise AssertionError("Runtime V2 run setup must not migrate legacy key_context")


def test_steer_inbox_is_persistent_and_client_idempotent(monkeypatch, tmp_path):
    import agent_loop

    class _SessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    agent_loop._STEER_QUEUES.clear()

    first = agent_loop.enqueue_session_steer("s1", "follow up", client_id="client-1")
    second = agent_loop.enqueue_session_steer("s1", "follow up", client_id="client-1")
    agent_loop._STEER_QUEUES.clear()  # simulate a process-local cache loss
    recovered = agent_loop._pop_session_steers("s1")

    assert first["item"]["id"] == second["item"]["id"]
    assert second["deduplicated"] is True
    assert [row["content"] for row in recovered] == ["follow up"]
    assert (tmp_path / "s1" / "steer_inbox.json").is_file()
    agent_loop.remove_session_steer("s1", client_id="client-1")
    cancelled = agent_loop.get_session_steer("s1", client_id="client-1")
    assert cancelled["item"]["state"] == "cancelled"


def test_runtime_v1_steer_transaction_uses_neutral_lock_not_v2_event_lock(monkeypatch, tmp_path):
    import agent_loop

    class _SessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setenv("RUNTIME_VERSION", "1")

    with agent_loop._steer_transaction("legacy-session"):
        assert (tmp_path / "legacy-session" / ".steer.lock").is_file()

    assert not (tmp_path / "legacy-session" / ".events.lock").exists()


def test_steer_state_machine_claim_ack_and_cancel_fencing(monkeypatch, tmp_path):
    import agent_loop

    class _SessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    agent_loop._STEER_QUEUES.clear()
    agent_loop._STEER_QUEUE_SIGNATURES.clear()

    queued = agent_loop.enqueue_session_steer(
        "s-state", "follow up", client_id="client-state", source_run_id="run-old"
    )["item"]
    steer_id = queued["id"]
    claimed = agent_loop._claim_session_steers("s-state", "run-old")
    assert [row["id"] for row in claimed] == [steer_id]
    assert agent_loop.get_session_steer("s-state", steer_id=steer_id)["item"]["state"] == "claimed"

    cancelled = agent_loop.remove_session_steer("s-state", steer_id=steer_id)
    assert cancelled == {"ok": False, "error": "steer already claimed or not pending"}

    consumed = agent_loop.transition_session_steer(
        "s-state", steer_id, {"claimed"}, "consumed", consumed_by="run-old"
    )
    assert consumed["ok"] is True
    assert consumed["item"]["state"] == "consumed"
    assert agent_loop._pop_session_steers("s-state") == []

    duplicate = agent_loop.enqueue_session_steer(
        "s-state", "follow up", client_id="client-state", source_run_id="run-old"
    )
    assert duplicate["deduplicated"] is True
    assert duplicate["item"]["id"] == steer_id
    assert duplicate["item"]["state"] == "consumed"


def test_replacement_run_fences_late_old_run_events():
    import agent_loop

    old = agent_loop._register_steer_run_control("s-fence", "run-old")
    state = {
        "session_id": "s-fence",
        "_runtime_v2_run_id": "run-old",
        "_steer_control": old,
        "stream_events": [],
    }
    new = agent_loop._register_steer_run_control("s-fence", "run-new")
    emitted = []

    async def emit(event):
        emitted.append(event)

    asyncio.run(agent_loop._push_stream_event(state, {"type": "final", "content": "late"}, emit=emit))
    assert state["stream_events"] == []
    assert emitted == []
    agent_loop._clear_steer_run_control("s-fence", new)


def test_cross_process_fence_file_blocks_local_late_writer(monkeypatch, tmp_path):
    import json
    import agent_loop

    class _SessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    control = agent_loop._register_steer_run_control("s-cross", "run-local")
    state = {"session_id": "s-cross", "_runtime_v2_run_id": "run-local", "_steer_control": control}
    fence_path = tmp_path / "s-cross" / "active_run_fence.json"
    fence_path.write_text(json.dumps({"run_id": "run-remote", "token": "remote-token"}), encoding="utf-8")

    assert agent_loop._state_run_has_write_fence(state) is False
    agent_loop._clear_steer_run_control("s-cross", control)


def test_twenty_consecutive_steers_replan_without_recursive_react(monkeypatch):
    import agent_loop

    calls = 0

    async def run_once(state, emit=None):
        nonlocal calls
        calls += 1
        if calls <= 20:
            raise agent_loop._SteerRestartRequested()
        state["done"] = True
        return state

    async def consume(state, emit=None):
        return True

    monkeypatch.setattr(agent_loop, "_react_node_once", run_once)
    monkeypatch.setattr(agent_loop, "_consume_steer_messages", consume)
    monkeypatch.setattr(agent_loop, "_rollback_steer_partial_turn", lambda state: None)
    monkeypatch.setattr(agent_loop, "_reset_steer_control", lambda state: None)
    state = {"session_id": "s-many", "stream_events": []}

    result = asyncio.run(agent_loop.react_node(state))
    assert result["done"] is True
    assert calls == 21


def test_crash_after_user_turn_commit_replay_is_idempotent(monkeypatch, tmp_path):
    import agent_loop
    from langchain_core.messages import HumanMessage
    from runtime_v2 import RuntimeModelProjection

    class _SessionManager:
        sessions_dir = tmp_path

        def _apply_appended_ui_event_side_effects(self, session_id, event):
            pass

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    state = {"session_id": "s-crash", "_runtime_v2_run_id": "run-1"}
    message = HumanMessage(content="durable followup")

    assert agent_loop._runtime_v2_commit_user_turn(
        state, message, ui_content="durable followup", ui_type="user_steer", operation_id="steer-op"
    ) is True
    assert state["_last_user_turn_was_deduplicated"] is False

    # Simulate process loss after the atomic commit but before inbox ack.
    replay_state = {"session_id": "s-crash", "_runtime_v2_run_id": "run-2"}
    assert agent_loop._runtime_v2_commit_user_turn(
        replay_state, message, ui_content="durable followup", ui_type="user_steer", operation_id="steer-op"
    ) is True
    assert replay_state["_last_user_turn_was_deduplicated"] is True
    projected = RuntimeModelProjection(tmp_path).read_message_dicts("s-crash")
    assert [row["content"] for row in projected if row.get("type") in {"human", "user"}] == ["durable followup"]


def test_claim_cancel_race_has_single_winner(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import agent_loop

    class _SessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    agent_loop._STEER_QUEUES.clear()
    agent_loop._STEER_QUEUE_SIGNATURES.clear()
    steer_id = agent_loop.enqueue_session_steer("s-race", "race", client_id="race-client")["item"]["id"]
    barrier = threading.Barrier(2)

    def claim():
        barrier.wait()
        return agent_loop._claim_session_steers("s-race", "run-race")

    def cancel():
        barrier.wait()
        return agent_loop.remove_session_steer("s-race", steer_id=steer_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed_future = pool.submit(claim)
        cancelled_future = pool.submit(cancel)
        claimed = claimed_future.result()
        cancelled = cancelled_future.result()

    final_state = agent_loop.get_session_steer("s-race", steer_id=steer_id)["item"]["state"]
    assert (bool(claimed), bool(cancelled.get("ok"))) in {(True, False), (False, True)}
    assert final_state in {"claimed", "cancelled"}


def test_deferred_write_tool_wait_preserves_result_before_steer(monkeypatch):
    import agent_loop

    checks = 0

    async def check(state, emit, stage):
        nonlocal checks
        checks += 1

    async def irreversible_write():
        await asyncio.sleep(0)
        return {"type": "tool", "result": "written"}

    monkeypatch.setattr(agent_loop, "_raise_if_steer_requested", check)
    result = asyncio.run(agent_loop._await_steerable(
        {"session_id": "s-write"}, irreversible_write(), None, "tool", defer_steer=True
    ))
    assert result["result"] == "written"
    assert checks == 1


def test_tool_steer_policy_does_not_claim_irreversible_rollback():
    import agent_loop

    assert agent_loop._tool_steer_policy("read_file") == {
        "interruptibility": "safe", "side_effect": "none"
    }
    assert agent_loop._tool_steer_policy("task")["interruptibility"] == "cooperative"
    assert agent_loop._tool_steer_policy("write_file") == {
        "interruptibility": "non_interruptible", "side_effect": "irreversible"
    }


def test_non_interruptible_tool_exposes_deferred_state_until_safe_point(monkeypatch, tmp_path):
    import agent_loop

    class _SessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    agent_loop._STEER_QUEUES.clear()
    agent_loop._STEER_QUEUE_SIGNATURES.clear()
    async def slow_write():
        await asyncio.sleep(0.16)
        return "done"

    async def scenario():
        waiting = asyncio.create_task(agent_loop._await_steerable(
            {"session_id": "s-deferred", "stream_events": []}, slow_write(), None, "tool", poll_sec=0.02, defer_steer=True
        ))
        await asyncio.sleep(0.03)
        item = agent_loop.enqueue_session_steer("s-deferred", "change direction", client_id="defer-client")["item"]
        await asyncio.sleep(0.07)
        during = agent_loop.get_session_steer("s-deferred", steer_id=item["id"])["item"]["state"]
        result = await waiting
        after = agent_loop.get_session_steer("s-deferred", steer_id=item["id"])["item"]["state"]
        return during, result, after

    during, result, after = asyncio.run(scenario())
    assert (during, result, after) == ("deferred", "done", "interrupting")


def test_user_turn_commit_failure_never_acknowledges_steer(monkeypatch, tmp_path):
    import pytest
    import agent_loop

    class _SessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    agent_loop._STEER_QUEUES.clear()
    agent_loop._STEER_QUEUE_SIGNATURES.clear()
    item = agent_loop.enqueue_session_steer("s-fail", "must survive", client_id="fail-client")["item"]

    def fail_commit(*args, **kwargs):
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(agent_loop, "_runtime_v2_commit_user_turn", fail_commit)
    state = {
        "session_id": "s-fail",
        "_runtime_v2_run_id": "run-fail",
        "work_messages": [],
        "llm_history": [],
        "dialogue": [],
        "stream_events": [],
    }
    with pytest.raises(RuntimeError, match="injected commit failure"):
        asyncio.run(agent_loop._consume_steer_messages(state))

    failed = agent_loop.get_session_steer("s-fail", steer_id=item["id"])["item"]
    assert failed["state"] == "failed"
    assert failed.get("consumed_at") is None


def test_steer_trim_keeps_completed_prefix_and_assistant_text():
    import agent_loop

    assistant = agent_loop.AssistantMessage(
        content="already streamed response",
        tool_calls=[
            {"name": "read_file", "args": {"path": "a"}, "id": "done"},
            {"name": "run_shell", "args": {"command": "sleep"}, "id": "running"},
        ],
        additional_kwargs={"reasoning_content": "already streamed reasoning"},
    )
    completed = agent_loop.ToolMessage(content="file contents", tool_call_id="done")

    trimmed, changed_at = agent_loop._trim_unclosed_tool_call_tail_preserve_completed(
        [assistant, completed]
    )

    assert changed_at == 0
    assert len(trimmed) == 2
    assert trimmed[0].content == "already streamed response"
    assert [call["id"] for call in trimmed[0].tool_calls] == ["done"]
    assert trimmed[1].tool_call_id == "done"

def test_runtime_v2_model_history_prefers_projection(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [
        {"type": "user", "content": "hello"},
    ])

    messages = agent_loop._load_model_history_dicts_v2_primary("s1", reconcile_legacy=True)

    assert messages == [{"type": "user", "content": "hello"}]


def test_runtime_v2_model_history_empty_projection_does_not_fallback_legacy(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [])

    messages = agent_loop._load_model_history_dicts_v2_primary("s1", reconcile_legacy=True)

    assert messages == []


def test_runtime_v1_model_history_keeps_legacy_fallback(monkeypatch):
    import agent_loop

    calls = []

    class _SessionManager:
        def reconcile_llm_work_to_ui_user_count(self, session_id, include_work=False):
            calls.append(("reconcile", session_id, include_work))

        def _load_llm_history(self, session_id):
            calls.append(("load", session_id))
            return [{"type": "user", "content": "legacy"}]

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: False)

    messages = agent_loop._load_model_history_dicts_v2_primary("s1", reconcile_legacy=True)

    assert messages == [{"type": "user", "content": "legacy"}]
    assert calls == [("reconcile", "s1", False), ("load", "s1")]


def test_runtime_v2_context_token_compute_uses_projection_not_legacy(monkeypatch):
    import agent_loop

    captured = {}

    class _SessionManager:
        sessions_dir = Path("unused")

        def get_or_create_session(self, session_id):
            raise AssertionError("Runtime V2 context token compute must not read legacy session history")

    def fake_estimate(session_id, messages, key_context):
        captured["session_id"] = session_id
        captured["messages"] = messages
        captured["key_context"] = key_context
        return 123, "provider_calibrated"

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [
        {"type": "user", "content": "hello"},
    ])
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_context_summary", lambda _sid: "summary")
    monkeypatch.setattr(agent_loop, "get_context_token_mode", lambda: "hybrid")
    monkeypatch.setattr(agent_loop, "estimate_hybrid_input_tokens_for_llm_history", fake_estimate)
    monkeypatch.setattr(agent_loop, "resolve_executor_config_for_session", lambda _sid: (None, "m", 1024, 4096))

    result = agent_loop.compute_context_tokens_for_session("s1")

    assert result == {
        "ok": True,
        "estimated": 123,
        "threshold": 4096,
        "model": "m",
        "source": "runtime_v2_projection",
        "token_source": "provider_calibrated",
        "token_mode": "hybrid",
    }
    assert captured["session_id"] == "s1"
    assert captured["messages"][0].content == "hello"
    assert captured["key_context"] == "summary"


def test_react_resolves_model_config_at_each_llm_boundary():
    source = (APP_DIR / "agent_loop.py").read_text(encoding="utf-8")
    react_source = source.split("async def _react_node_once", 1)[1].split(
        "async def react_node", 1
    )[0]
    loop_source = react_source.split("while iter_count < max_react_iter:", 1)[1]

    assert 'resolve_executor_config_for_session(state["session_id"])' in loop_source
    assert "run_executor_config" not in react_source
    assert "resolve_model_config_reuse" not in react_source
    assert '_pre_api_timing_mark(pre_api_timings, "resolve_model_config"' in loop_source


def test_runtime_v2_run_key_context_uses_snapshot_not_legacy(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_context_summary", lambda _sid: "summary")

    assert agent_loop._load_key_context_for_run("s1") == "summary"


def test_runtime_v1_run_key_context_keeps_legacy_migration(monkeypatch):
    import agent_loop

    calls = []

    class _SessionManager:
        def _load_key_context(self, session_id):
            calls.append(("load", session_id))
            return "legacy"

        def migrate_todo_plan_off_key_context(self, session_id, key_context):
            calls.append(("migrate", session_id, key_context))
            return "migrated"

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: False)

    assert agent_loop._load_key_context_for_run("s1") == "migrated"
    assert calls == [("load", "s1"), ("migrate", "s1", "legacy")]


def test_agent_loop_does_not_auto_backfill_v2_model_history_from_legacy():
    source = (APP_DIR / "agent_loop.py").read_text(encoding="utf-8")

    assert "legacy_model_sync_on_read" not in source
    assert "legacy_model_sync_on_continuation" not in source
    assert ".ensure_backfilled_from_legacy(" not in source
    assert ".sync_from_legacy_if_needed(" not in source


def test_runtime_v2_run_does_not_load_work_messages(monkeypatch):
    import agent_loop

    class _SessionManager:
        def _load_work_messages(self, session_id):
            raise AssertionError("Runtime V2 run setup must not load work_messages")

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)

    assert agent_loop._load_work_history_dicts_for_run("s1") == []


def test_runtime_v2_lazy_work_materialize_is_noop(monkeypatch):
    import agent_loop

    class _SessionManager:
        def _load_work_messages(self, session_id):
            raise AssertionError("Runtime V2 lazy materialize must not read work_messages")

    msg = agent_loop.UserMessage(content="current")
    state = {
        "session_id": "s1",
        "work_messages": [msg],
        "_lazy_prepend_work_messages": True,
    }

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)

    agent_loop._materialize_lazy_work_messages(state)

    assert state["work_messages"] == [msg]
    assert state["work_messages"][0].content == "current"
    assert "_lazy_prepend_work_messages" not in state


def test_runtime_v2_todo_sync_uses_snapshot_not_legacy(monkeypatch, tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeMirror

    monkeypatch.setenv("RUNTIME_VERSION", "2")
    RuntimeMirror(tmp_path).mirror_ui_event(
        "s1",
        {
            "type": "todo_plan",
            "items": [{"id": "1", "text": "from snapshot", "status": "in_progress"}],
            "has_plan": True,
            "done": 0,
            "total": 1,
        },
    )

    class _SessionManager:
        sessions_dir = tmp_path

        def load_todo_plan(self, session_id):
            raise AssertionError("Runtime V2 todo sync must not read legacy todo_plan.md")

    monkeypatch.setattr(agent_harness, "session_manager", _SessionManager())

    manager = agent_harness.TodoManager()
    manager.sync_session_from_key_context("s1", "")

    assert manager._by_session["s1"] == [
        {"id": "1", "text": "from snapshot", "status": "in_progress"}
    ]


def test_runtime_v2_todo_update_does_not_write_legacy_file(monkeypatch, tmp_path):
    import agent_harness

    monkeypatch.setenv("RUNTIME_VERSION", "2")

    class _SessionManager:
        sessions_dir = tmp_path

        def save_todo_plan(self, *args, **kwargs):
            raise AssertionError("Runtime V2 todo update must not write legacy todo_plan.md")

    monkeypatch.setattr(agent_harness, "session_manager", _SessionManager())

    manager = agent_harness.TodoManager()
    result = manager.update_for_session(
        "s1",
        [{"id": "1", "text": "keep in runtime snapshot", "status": "pending"}],
    )

    assert "keep in runtime snapshot" in result
    assert manager._by_session["s1"] == [
        {"id": "1", "text": "keep in runtime snapshot", "status": "pending"}
    ]


def test_runtime_v2_persist_does_not_save_legacy_histories(monkeypatch, tmp_path):
    import agent_loop
    from runtime_v2 import SnapshotStore

    class _SessionManager:
        sessions_dir = None

        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not write work_messages")

        def update_session_model_state(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not write legacy llm_history")

        def _save_llm_history(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy llm_history")

        def _save_work_messages(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy work_messages")

        def _save_key_context(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy key_context")

        def _save_dialogue_history(self, *args, **kwargs):
            raise AssertionError("Runtime V2 persist must not save legacy dialogue_history")

        def dialogue_dicts_from_ui_events_file(self, session_id):
            raise AssertionError("Runtime V2 persist must not read legacy ui_events for dialogue_history")

    manager = _SessionManager()
    manager.sessions_dir = tmp_path
    monkeypatch.setattr(agent_loop, "session_manager", manager)
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)

    agent_loop._persist_session_messages(
        {
            "session_id": "s1",
            "work_messages": [agent_loop.UserMessage(content="legacy")],
            "llm_history": [agent_loop.UserMessage(content="hello")],
            "key_context": "runtime v2 context",
        }
    )

    snapshot = SnapshotStore(tmp_path).read("s1")
    summary = snapshot.get("context", {}).get("summary", {})
    assert summary.get("summary") == "runtime v2 context"

    event_log_path = tmp_path / "s1" / "events.jsonl"
    before_events = event_log_path.read_text(encoding="utf-8")
    agent_loop._persist_session_messages(
        {
            "session_id": "s1",
            "work_messages": [agent_loop.UserMessage(content="legacy")],
            "llm_history": [agent_loop.UserMessage(content="hello")],
            "key_context": "runtime v2 context",
        }
    )
    after_events = event_log_path.read_text(encoding="utf-8")
    assert after_events == before_events


def test_runtime_v2_continuation_empty_projection_does_not_reconcile(monkeypatch):
    import agent_loop

    monkeypatch.setattr(agent_loop, "session_manager", _NoLegacySessionManager())
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_load_runtime_v2_model_history_dicts", lambda _sid: [])
    monkeypatch.setattr(agent_loop, "setup_logging", lambda *args, **kwargs: None)

    async def collect():
        out = []
        async for ev in agent_loop.astream_events_continuation(
            "s1",
            require_pending_subagents=False,
        ):
            out.append(ev)
        return out

    import asyncio

    assert asyncio.run(collect()) == []


def test_finish_uses_title_generator_for_new_session(monkeypatch):
    import agent_loop

    names = []
    calls = []

    class _SessionManager:
        def _load_metadata(self, session_id):
            return {"name": "新会话"}

        def set_session_name(self, session_id, title):
            names.append((session_id, title))

    def fake_generate_title(session_id, first_user, final_response):
        prompt = f"Q:{first_user}\nA:{final_response}"
        calls.append((prompt, list(state["stream_events"])))
        return "model title", {"prompt_tokens": 3, "completion_tokens": 2}

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "load_prompt_template", lambda name: "Q:{first_user}\nA:{final_response}")
    monkeypatch.setattr(agent_loop, "_generate_session_title_with_diagnostics", fake_generate_title)
    monkeypatch.setattr(agent_loop, "_persist_session_messages_with_model_replace", lambda *args, **kwargs: None)

    state = {
        "session_id": "s1",
        "dialogue": [agent_loop.UserMessage(content="hello world from user")],
        "work_messages": [],
        "llm_history": [],
        "stream_events": [],
        "final_response": "done",
        "final_printed": False,
        "llm_calls": [],
    }

    out = agent_loop.finish(state)

    assert out["final_printed"] is True
    assert out["stream_events"][-1] == {"type": "final", "content": "done"}
    assert calls == [("Q:hello world from user\nA:done", [{"type": "final", "content": "done"}])]
    assert names == [("s1", "model title")]


def test_generated_session_title_strips_leading_think_block():
    import agent_loop

    assert agent_loop._normalize_generated_session_title(
        "<think>The user wants a diagnostic title</think>\n修复会话标题"
    ) == "修复会话标题"
    assert agent_loop._normalize_generated_session_title(
        "<think>The user wants a diagnostic title"
    ) == ""


def test_reasoning_polluted_session_title_needs_regeneration():
    import agent_loop

    assert agent_loop._session_title_needs_generation("<think>The user want", "hello")
    assert agent_loop._session_title_needs_generation("is. The conversation", "hello")


def test_finish_does_not_duplicate_prepared_final_event(monkeypatch):
    import agent_loop

    names = []

    class _SessionManager:
        def _load_metadata(self, session_id):
            return {"name": "新会话"}

        def set_session_name(self, session_id, title):
            names.append((session_id, title))

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "load_prompt_template", lambda name: "{first_user} {final_response}")
    monkeypatch.setattr(agent_loop, "_generate_session_title_with_diagnostics", lambda *args: ("model title", None))
    monkeypatch.setattr(agent_loop, "_persist_session_messages_with_model_replace", lambda *args, **kwargs: None)

    state = {
        "session_id": "s1",
        "dialogue": [agent_loop.UserMessage(content="hello")],
        "work_messages": [],
        "llm_history": [],
        "stream_events": [],
        "final_response": "done",
        "final_printed": False,
        "llm_calls": [],
    }

    agent_loop.prepare_final_event(state)
    assert state["stream_events"] == [{"type": "final", "content": "done"}]

    out = agent_loop.finish(state)

    assert out["final_printed"] is True
    assert out["stream_events"] == [{"type": "final", "content": "done"}]
    assert names == [("s1", "model title")]


def test_astream_emits_final_before_title_generation(monkeypatch, tmp_path):
    import agent_loop

    seen = []
    title_call_seen = []

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, *args, **kwargs):
            pass

        def append_ui_event(self, *args, **kwargs):
            pass

        def _load_metadata(self, session_id):
            return {"name": "新会话"}

        def set_session_name(self, *args, **kwargs):
            pass

        def mark_session_unread_result(self, *args, **kwargs):
            pass

    async def fake_run_react(state, emit):
        out = dict(state)
        out["final_response"] = "done"
        return out

    def fake_generate_title(*args):
        title_call_seen.append(list(seen))
        return "model title", None

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_load_key_context_for_run", lambda session_id: "")
    monkeypatch.setattr(agent_loop, "_load_model_history_dicts_v2_primary", lambda session_id, reconcile_legacy=True: [])
    monkeypatch.setattr(agent_loop, "_load_work_history_dicts_for_run", lambda session_id: [])
    monkeypatch.setattr(agent_loop, "_sanitize_loaded_histories_for_new_run", lambda sid, work, llm, key, reason: (work, llm))
    monkeypatch.setattr(agent_loop.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "setup_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_runtime_v2_append_model_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_persist_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_persist_session_messages_with_model_replace", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_run_react_node_off_loop", fake_run_react)
    monkeypatch.setattr(agent_loop, "load_prompt_template", lambda name: "{first_user} {final_response}")
    monkeypatch.setattr(agent_loop, "_generate_session_title_with_diagnostics", fake_generate_title)

    async def collect():
        async for ev in agent_loop.astream_events("hello", session_id="s-final-first"):
            seen.append(ev)

    asyncio.run(collect())

    assert title_call_seen, "title generation should still run for new sessions"
    assert any(ev.get("type") == "final" and ev.get("content") == "done" for ev in title_call_seen[0])

    from runtime_v2.event_log import SessionEventLog
    from runtime_v2.projector import RuntimeProjector

    snapshot = RuntimeProjector().project(SessionEventLog(tmp_path).read_all("s-final-first"))
    assert snapshot["active_runs"] == []


def test_astream_can_record_initial_ui_message_as_user_steer(monkeypatch, tmp_path):
    import agent_loop

    ui_events = []

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, *args, **kwargs):
            pass

        def append_ui_event(self, session_id, event):
            ui_events.append((session_id, dict(event)))

        def _load_metadata(self, session_id):
            return {"name": "existing"}

        def set_session_name(self, *args, **kwargs):
            pass

        def mark_session_unread_result(self, *args, **kwargs):
            pass

    async def fake_run_react(state, emit):
        out = dict(state)
        out["final_response"] = "done"
        return out

    monkeypatch.setattr(agent_loop, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_loop, "_load_key_context_for_run", lambda session_id: "")
    monkeypatch.setattr(agent_loop, "_load_model_history_dicts_v2_primary", lambda session_id, reconcile_legacy=True: [])
    monkeypatch.setattr(agent_loop, "_load_work_history_dicts_for_run", lambda session_id: [])
    monkeypatch.setattr(agent_loop, "_sanitize_loaded_histories_for_new_run", lambda sid, work, llm, key, reason: (work, llm))
    monkeypatch.setattr(agent_loop.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "setup_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_runtime_v2_append_model_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_persist_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_persist_session_messages_with_model_replace", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "_run_react_node_off_loop", fake_run_react)

    async def collect():
        async for _ev in agent_loop.astream_events(
            "follow up",
            session_id="s-followup",
            ui_user_event_type="user_steer",
        ):
            pass

    asyncio.run(collect())

    assert ("s-followup", {"type": "user_steer", "content": "follow up", "steer": True}) in ui_events
    assert ("s-followup", {"type": "user", "content": "follow up"}) not in ui_events
