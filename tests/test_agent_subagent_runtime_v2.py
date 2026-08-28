import asyncio
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_task_action_status_routes_without_starting_subagent(monkeypatch):
    import agent_subagent

    monkeypatch.setattr(
        agent_subagent,
        "_format_subagent_status_report",
        lambda parent, resume: f"status:{parent}:{resume}",
    )

    result = asyncio.run(
        agent_subagent._run_single_subagent(
            tool_args={"action": "status", "resume": "child-1"},
            parent_session_id="parent-1",
        )
    )

    assert result == "status:parent-1:child-1"


def test_task_action_resume_requires_a_real_followup_prompt():
    import agent_subagent

    result = asyncio.run(
        agent_subagent._run_single_subagent(
            tool_args={"action": "resume", "resume": "child-1", "prompt": ""},
            parent_session_id="parent-1",
        )
    )

    assert "requires a non-empty follow-up prompt" in result
    assert "action=collect" in result


def test_task_action_switch_model_routes_to_existing_subagent(monkeypatch):
    import agent_subagent

    captured = {}

    async def fake_switch(parent, child, profile_id, **kwargs):
        captured.update({
            "parent": parent,
            "child": child,
            "profile_id": profile_id,
            **kwargs,
        })
        return {
            "ok": True,
            "agent_id": child,
            "previous_profile_id": "profile-fast",
            "continuation_queued": True,
        }

    monkeypatch.setattr(agent_subagent, "switch_subagent_model_profile", fake_switch)
    result = asyncio.run(
        agent_subagent._run_single_subagent(
            tool_args={
                "action": "switch_model",
                "resume": "child-1",
                "model_profile_id": "profile-deep",
                "prompt": "Keep the completed audit evidence.",
            },
            parent_session_id="parent-1",
            parent_run_id="run-parent",
        )
    )

    assert "Switched subagent child-1" in result
    assert "same task was queued to continue" in result
    assert captured == {
        "parent": "parent-1",
        "child": "child-1",
        "profile_id": "profile-deep",
        "instruction": "Keep the completed audit evidence.",
        "source_run_id": "run-parent",
        "requested_by": "parent_agent",
    }


def test_running_subagent_model_switch_interrupts_at_safe_boundary(monkeypatch):
    import agent_loop
    import agent_subagent

    captured = {"task_patches": [], "events": []}

    class _SessionManager:
        def validate_subagent_resume(self, parent, child):
            return child if parent == "parent" and child == "child" else None

        def _load_metadata(self, child):
            assert child == "child"
            return {"model_profile_id": "profile-fast", "is_subagent": True}

        def switch_subagent_model_profile(self, child, profile_id, **kwargs):
            captured["metadata_switch"] = (child, profile_id, kwargs)
            return {
                "switch_id": kwargs["switch_id"],
                "from_profile_id": "profile-fast",
                "to_profile_id": profile_id,
            }

        def upsert_subagent_task(self, parent, child, patch):
            captured["task_patches"].append((parent, child, dict(patch)))

        def append_ui_event(self, child, event):
            captured["events"].append((child, dict(event)))

    class _Registry:
        @staticmethod
        def is_running(child):
            return child == "child"

    def fake_enqueue(session_id, message, **kwargs):
        captured["steer"] = (session_id, message, kwargs)
        return {"ok": True, "item": {"id": "steer-1"}}

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent, "subagent_registry", _Registry())
    monkeypatch.setattr(
        agent_subagent,
        "list_executor_model_profile_choices",
        lambda: [
            {"id": "profile-fast", "model": "fast-model"},
            {"id": "profile-deep", "model": "deep-model"},
        ],
    )
    monkeypatch.setattr(agent_loop, "enqueue_session_steer", fake_enqueue)
    monkeypatch.setattr(
        agent_loop,
        "abort_session_steer_run",
        lambda session_id, reason="": captured.setdefault("abort", (session_id, reason)) is not None,
    )

    result = asyncio.run(
        agent_subagent.switch_subagent_model_profile(
            "parent",
            "child",
            "profile-deep",
            instruction="Continue with the existing findings.",
            requested_by="user",
        )
    )

    assert result["ok"] is True
    assert result["agent_id"] == "child"
    assert result["previous_profile_id"] == "profile-fast"
    assert result["continuation_queued"] is True
    assert result["interrupted_current_step"] is True
    assert captured["metadata_switch"][0:2] == ("child", "profile-deep")
    assert captured["metadata_switch"][2]["executor_model"] == "deep-model"
    assert captured["steer"][0] == "child"
    assert captured["steer"][2]["mode"] == "interrupt"
    assert "same assigned task" in captured["steer"][1]
    assert "Continue with the existing findings." in captured["steer"][1]
    assert captured["abort"] == ("child", "model_switch")
    assert captured["task_patches"][-1][2]["model_switch_status"] == "continuation_queued"
    assert captured["events"][0][1]["model_switch"] is True


def test_task_schema_injects_registered_profiles_without_mutating_static_schema(monkeypatch):
    import agent_subagent
    import agent_tools

    monkeypatch.setattr(
        agent_subagent,
        "list_executor_model_profile_choices",
        lambda: [
            {
                "id": "profile-fast",
                "name": "Fast profile",
                "model": "fast-model",
                "capability_description": "低成本/多并发：批量总结和并行探索",
                "input_modalities": ["text"],
                "multimodal_mode": "disabled",
            },
            {
                "id": "profile-deep",
                "name": "Deep profile",
                "model": "deep-model",
                "input_modalities": ["text", "image"],
                "multimodal_mode": "enabled",
            },
        ],
    )

    injected = agent_subagent.inject_task_model_profiles(agent_tools.OPENAI_TOOL_DEFINITIONS)
    injected_task = next(
        row["function"] for row in injected if row["function"]["name"] == "task"
    )
    static_task = next(
        row["function"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
        if row["function"]["name"] == "task"
    )
    injected_profile = injected_task["parameters"]["properties"]["model_profile_id"]
    static_profile = static_task["parameters"]["properties"]["model_profile_id"]

    assert injected_profile["enum"] == ["profile-fast", "profile-deep"]
    assert "profile-fast: Fast profile (model=fast-model)" in injected_profile["description"]
    assert "低成本/多并发：批量总结和并行探索" in injected_profile["description"]
    assert "Inputs: text only; multimodal: manually disabled" in injected_profile["description"]
    assert "profile-deep: Deep profile (model=deep-model) — Inputs: text, image" in injected_profile["description"]
    assert "omit by default" in injected_profile["description"]
    assert "enum" not in static_profile
    assert "switch_model" in injected_task["parameters"]["properties"]["action"]["enum"]


def test_task_selected_profile_is_bound_to_created_subagent(monkeypatch):
    import agent_subagent

    captured = {}

    class _SessionManager:
        def get_session_subagent_depth(self, _session_id):
            return 0

        def create_subagent_session(self, *args, **kwargs):
            captured.update(kwargs)
            return "child-profile"

    async def fake_execute(**kwargs):
        captured["executed_child_id"] = kwargs["child_id"]
        return "done"

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent, "_save_initial_subagent_key_context", lambda *args: None)
    monkeypatch.setattr(agent_subagent, "_execute_subagent_run", fake_execute)
    monkeypatch.setattr(
        agent_subagent,
        "list_executor_model_profile_choices",
        lambda: [{"id": "profile-deep", "name": "Deep", "model": "deep-model"}],
    )

    result = asyncio.run(
        agent_subagent._run_single_subagent(
            tool_args={
                "action": "start",
                "description": "Use selected model",
                "prompt": "Complete the delegated task.",
                "model_profile_id": "profile-deep",
            },
            parent_session_id="parent",
        )
    )

    assert result == "done"
    assert captured["model_profile_id"] == "profile-deep"
    assert captured["executor_model"] == ""
    assert captured["executed_child_id"] == "child-profile"


def test_task_rejects_unknown_profile_or_removed_raw_model(monkeypatch):
    import agent_subagent

    monkeypatch.setattr(
        agent_subagent,
        "list_executor_model_profile_choices",
        lambda: [{"id": "profile-valid", "name": "Valid", "model": "valid-model"}],
    )

    unknown = asyncio.run(
        agent_subagent._run_single_subagent(
            tool_args={
                "action": "start",
                "prompt": "Do work.",
                "model_profile_id": "profile-missing",
            },
            parent_session_id="parent",
        )
    )
    removed_raw_model = asyncio.run(
        agent_subagent._run_single_subagent(
            tool_args={
                "action": "start",
                "prompt": "Do work.",
                "model": "raw-model",
            },
            parent_session_id="parent",
        )
    )

    assert "unknown model_profile_id='profile-missing'" in unknown
    assert "task.model has been removed" in removed_raw_model
    assert "model_profile_id instead" in removed_raw_model


def test_subagent_prompt_is_self_contained_and_has_a_completion_contract():
    import agent_subagent

    message = agent_subagent.build_subagent_user_message(
        prompt="Inspect app/example.py, explain the defect, implement the fix, and run the focused test.",
        description="Fix parser defect",
        subagent_type="generalPurpose",
        is_resume=True,
        readonly=False,
        best_of_attempt=2,
        best_of_total=3,
    )

    assert "## Subagent 任务：Fix parser defect" in message
    assert "权限模式：通用" in message
    assert "会话模式：续接已有 subagent" in message
    assert "沿用已验证的状态" in message
    assert "### 父 Agent 指令" in message
    assert "Inspect app/example.py" in message
    assert "### 返回父 Agent" in message
    assert "先给结果，再给关键证据" in message
    assert "尝试 **2/3**" in message

    instruction = agent_subagent.SUBAGENT_RUN_INSTRUCTION
    assert "不要假设能看到父会话" in instruction
    assert "只有任务明确要求实施时才修改" in instruction
    assert "最终输出必须自包含" in instruction


def test_subagent_prompt_and_file_attachment_share_image_modality_routing(tmp_path):
    import agent_openai
    import agent_subagent
    from agent_messages import UserMessage

    image_path = tmp_path / "screen shot.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    quoted_path = f'"{image_path}"'
    prompt_text = agent_subagent.build_subagent_user_message(
        prompt=f"请识别图片 {quoted_path}",
        description="Inspect prompt image",
        subagent_type="generalPurpose",
    )
    attachment_text = agent_subagent.build_subagent_user_message(
        prompt="请识别附件图片",
        description="Inspect attached image",
        subagent_type="generalPurpose",
        file_attachments=[str(image_path)],
    )
    remote_url = "https://cdn.example.com/signed-image?id=123"
    remote_attachment_text = agent_subagent.build_subagent_user_message(
        prompt="请识别远程附件图片",
        description="Inspect remote attached image",
        subagent_type="generalPurpose",
        file_attachments=[remote_url],
    )
    image_client = type(
        "ImageClient",
        (),
        {"_myagent_input_modalities": ["text", "image"]},
    )()
    text_client = type(
        "TextClient",
        (),
        {"_myagent_input_modalities": ["text"]},
    )()

    for user_text, expected_reference in (
        (prompt_text, str(image_path)),
        (attachment_text, str(image_path)),
        (remote_attachment_text, remote_url),
    ):
        messages = [UserMessage(content=user_text)]
        image_params = agent_openai._messages_to_params_for_client(
            image_client,
            messages,
        )
        text_params = agent_openai._messages_to_params_for_client(
            text_client,
            messages,
        )

        assert agent_openai._api_messages_required_modalities(image_params) == {
            "image"
        }
        assert not agent_openai._api_messages_have_media(text_params)
        fallback_user = next(
            message for message in text_params if message.get("role") == "user"
        )
        fallback_system = next(
            message for message in text_params if message.get("role") == "system"
        )
        assert expected_reference in fallback_user["content"]
        assert "task 工具" in fallback_system["content"]


def test_task_tool_description_explains_uniform_multimodal_routing():
    from agent_tools import OPENAI_TOOL_DEFINITIONS

    task_tool = next(
        item
        for item in OPENAI_TOOL_DEFINITIONS
        if item.get("function", {}).get("name") == "task"
    )["function"]
    properties = task_tool["parameters"]["properties"]

    assert "In prompt" in task_tool["description"]
    assert "file_attachments" in task_tool["description"]
    assert "image_url content" in task_tool["description"]
    assert "text-only profile" in task_tool["description"]
    assert "always wrap each exact local image path in double quotes" in task_tool[
        "description"
    ]
    assert "Always wrap every exact local image path in double quotes" in properties[
        "prompt"
    ]["description"]
    assert "effective input_modalities are authoritative" in properties[
        "model_profile_id"
    ]["description"]
    assert "same modality routing" in properties["file_attachments"]["description"]
    assert "automatically wrapped in double quotes" in properties[
        "file_attachments"
    ]["description"]


def test_runtime_v2_subagent_run_uses_projection_not_legacy(monkeypatch, tmp_path):
    import agent_loop
    import agent_subagent
    from agent_harness import AssistantMessage
    from runtime_v2 import RuntimeMirror, RuntimeModelProjection

    monkeypatch.setenv("RUNTIME_VERSION", "2")

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, session_id):
            pass

        def get_or_create_session(self, session_id):
            raise AssertionError("Runtime V2 subagent run must not load legacy session histories")

        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 subagent run must not save legacy session histories")

        def _load_ui_events(self, session_id):
            raise AssertionError("Runtime V2 subagent final reads must not load legacy ui_events")

        def append_ui_event(self, session_id, event):
            RuntimeMirror(tmp_path).mirror_ui_event(session_id, event)

        def upsert_subagent_task(self, *args, **kwargs):
            pass

        def append_pending_subagent_result(self, *args, **kwargs):
            pass

        def patch_subagent_metadata(self, *args, **kwargs):
            pass

        def write_subagent_output(self, child_session_id, text):
            return str(tmp_path / child_session_id / "output.md")

    async def fake_react_node(state, emit=None):
        final = AssistantMessage(content="done")
        final.metadata = {"is_final": True}
        out = dict(state)
        out["llm_history"] = list(state.get("llm_history") or []) + [final]
        out["work_messages"] = list(state.get("work_messages") or []) + [final]
        out["final_response"] = "done"
        out["key_context"] = "subagent context"
        return out

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent, "cleanup_git_worktree_for_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "react_node", fake_react_node)

    result = asyncio.run(
        agent_subagent._execute_subagent_run(
            child_id="child",
            parent_session_id="parent",
            user_text="task",
            description="desc",
            subagent_type="generalPurpose",
            resumed=False,
        )
    )

    messages = RuntimeModelProjection(tmp_path).read_message_dicts("child")
    assert any(item.get("type") == "user" and "task" in item.get("content", "") for item in messages)
    assert any(item.get("type") == "assistant" and item.get("content") == "done" for item in messages)
    assert agent_subagent._get_subagent_final_result("child") == "done"
    assert "done" in result


def test_subagent_child_session_state_is_not_forwarded_to_parent(monkeypatch, tmp_path):
    import agent_loop
    import agent_subagent
    from agent_harness import AssistantMessage
    from runtime_v2 import RuntimeMirror

    monkeypatch.setenv("RUNTIME_VERSION", "2")
    persisted_events = []
    parent_events = []

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, session_id):
            pass

        def get_or_create_session(self, session_id):
            raise AssertionError("Runtime V2 subagent run must not load legacy session histories")

        def update_session(self, *args, **kwargs):
            raise AssertionError("Runtime V2 subagent run must not save legacy session histories")

        def append_ui_event(self, session_id, event):
            persisted_events.append((session_id, dict(event)))
            RuntimeMirror(tmp_path).mirror_ui_event(session_id, event)

        def upsert_subagent_task(self, *args, **kwargs):
            pass

        def append_pending_subagent_result(self, *args, **kwargs):
            pass

        def patch_subagent_metadata(self, *args, **kwargs):
            pass

        def write_subagent_output(self, child_session_id, text):
            return str(tmp_path / child_session_id / "output.md")

    async def fake_react_node(state, emit=None):
        if emit:
            await emit({"type": "todo_plan", "items": [{"id": "1", "text": "child todo"}]})
            await emit({"type": "context_tokens", "estimated": 123, "threshold": 1000})
            await emit({"type": "status", "content": "child working"})
        final = AssistantMessage(content="done")
        final.metadata = {"is_final": True}
        out = dict(state)
        out["llm_history"] = list(state.get("llm_history") or []) + [final]
        out["work_messages"] = list(state.get("work_messages") or []) + [final]
        out["final_response"] = "done"
        return out

    async def parent_emit(ev):
        parent_events.append(dict(ev))

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent, "cleanup_git_worktree_for_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "react_node", fake_react_node)

    result = asyncio.run(
        agent_subagent._execute_subagent_run(
            child_id="child",
            parent_session_id="parent",
            user_text="task",
            description="desc",
            subagent_type="generalPurpose",
            resumed=False,
            parent_emit=parent_emit,
        )
    )

    persisted_types = [event.get("type") for sid, event in persisted_events if sid == "child"]
    parent_types = [event.get("type") for event in parent_events]

    assert "todo_plan" in persisted_types
    assert "context_tokens" in persisted_types
    assert "todo_plan" not in parent_types
    assert "context_tokens" not in parent_types
    assert any(event.get("type") == "status" and event.get("agent_id") == "child" for event in parent_events)
    assert any(event.get("type") == "subagent_finish" and event.get("agent_id") == "child" for event in parent_events)
    assert "done" in result


def test_registry_reservation_is_visible_and_release_is_run_identity_safe():
    import agent_subagent

    async def scenario():
        registry = agent_subagent.SubagentTaskRegistry()
        assert await registry.reserve("child", "run-a", parent_session_id="parent") is True
        assert registry.is_running("child") is True
        assert await registry.reserve("child", "run-b", parent_session_id="parent") is False
        assert await registry.unregister("child", "run-b") is False
        assert registry.is_running("child") is True
        assert await registry.unregister("child", "run-a") is True
        assert registry.is_running("child") is False

    asyncio.run(scenario())


def test_registry_cancels_task_on_foreign_worker_loop(monkeypatch):
    import agent_subagent

    registry = agent_subagent.SubagentTaskRegistry()
    ready = threading.Event()
    cancelled = threading.Event()
    worker_done = threading.Event()
    requested = []

    monkeypatch.setattr(
        agent_subagent.session_manager,
        "request_interrupt",
        lambda child_id, *args, **kwargs: requested.append(child_id),
    )

    def worker():
        async def run():
            async def wait_forever():
                try:
                    ready.set()
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

            task = asyncio.create_task(wait_forever())
            assert await registry.attach("child", "run-a", task) is True
            try:
                await task
            except asyncio.CancelledError:
                pass
            finally:
                worker_done.set()

        asyncio.run(run())

    async def scenario():
        assert await registry.reserve("child", "run-a", parent_session_id="parent") is True
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        assert await asyncio.to_thread(ready.wait, 1.0) is True
        assert await registry.cancel("child") is True
        await asyncio.to_thread(thread.join, 1.0)
        assert thread.is_alive() is False

    asyncio.run(scenario())

    assert cancelled.is_set()
    assert worker_done.is_set()
    assert requested == ["child"]


def test_subagent_tool_filter_reuses_bounded_identity_cache(monkeypatch):
    import agent_subagent

    definitions = [
        {"type": "function", "function": {"name": "read_file"}},
        {"type": "function", "function": {"name": "write_file"}},
        {"type": "function", "function": {"name": "mcp_remote"}},
    ]
    meta = {"is_subagent": True, "subagent_type": "explore", "subagent_depth": 1}
    calls = 0
    original = agent_subagent._tool_name

    def counted(definition):
        nonlocal calls
        calls += 1
        return original(definition)

    with agent_subagent._tool_filter_cache_lock:
        agent_subagent._tool_filter_cache.clear()
    monkeypatch.setattr(agent_subagent, "_tool_name", counted)

    first = agent_subagent.filter_tools_for_session(definitions, meta)
    second = agent_subagent.filter_tools_for_session(definitions, dict(meta))

    assert [item["function"]["name"] for item in first] == ["read_file"]
    assert second == first
    assert second is not first
    assert calls == len(definitions)


def test_same_subagent_cannot_enter_two_foreground_model_runs(monkeypatch, tmp_path):
    import agent_loop
    import agent_subagent
    from agent_harness import AssistantMessage

    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, session_id):
            pass

        def append_ui_event(self, *args, **kwargs):
            pass

        def upsert_subagent_task(self, *args, **kwargs):
            pass

        def append_pending_subagent_result(self, *args, **kwargs):
            pass

        def patch_subagent_metadata(self, *args, **kwargs):
            pass

        def write_subagent_output(self, child_session_id, text):
            return str(tmp_path / child_session_id / "output.md")

    async def fake_react_node(state, emit=None):
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        final = AssistantMessage(content="done")
        final.metadata = {"is_final": True}
        out = dict(state)
        out["llm_history"] = list(state.get("llm_history") or []) + [final]
        out["work_messages"] = list(state.get("work_messages") or []) + [final]
        out["final_response"] = "done"
        return out

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent, "subagent_registry", agent_subagent.SubagentTaskRegistry())
    monkeypatch.setattr(agent_subagent, "_load_subagent_run_histories", lambda child_id: ([], [], ""))
    monkeypatch.setattr(agent_subagent, "_persist_subagent_run_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent, "cleanup_git_worktree_for_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "react_node", fake_react_node)

    async def scenario():
        kwargs = dict(
            child_id="child",
            parent_session_id="parent",
            user_text="task",
            description="desc",
            subagent_type="generalPurpose",
            resumed=True,
        )
        first = asyncio.create_task(agent_subagent._execute_subagent_run(**kwargs))
        await entered.wait()
        second_result = await agent_subagent._execute_subagent_run(**kwargs)
        assert "already running" in second_result
        assert calls == 1
        release.set()
        assert "done" in await first
        assert agent_subagent.subagent_registry.is_running("child") is False

    asyncio.run(scenario())


def test_deleting_foreground_subagent_does_not_cancel_parent_task(monkeypatch, tmp_path):
    import agent_loop
    import agent_subagent

    entered = asyncio.Event()
    interrupted = []

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, session_id):
            pass

        def request_interrupt(self, session_id, *args, **kwargs):
            interrupted.append(session_id)

        def append_ui_event(self, *args, **kwargs):
            pass

        def upsert_subagent_task(self, *args, **kwargs):
            pass

        def append_pending_subagent_result(self, *args, **kwargs):
            pass

        def patch_subagent_metadata(self, *args, **kwargs):
            pass

        def write_subagent_output(self, child_session_id, text):
            return str(tmp_path / child_session_id / "output.md")

        def _load_metadata(self, child_session_id):
            return {}

    async def fake_react_node(state, emit=None):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent, "subagent_registry", agent_subagent.SubagentTaskRegistry())
    monkeypatch.setattr(agent_subagent, "_load_subagent_run_histories", lambda child_id: ([], [], ""))
    monkeypatch.setattr(agent_subagent.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent, "cleanup_git_worktree_for_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "react_node", fake_react_node)

    async def scenario():
        parent_task = asyncio.create_task(
            agent_subagent._execute_subagent_run(
                child_id="child",
                parent_session_id="parent",
                user_text="task",
                description="desc",
                subagent_type="generalPurpose",
                resumed=False,
            )
        )
        await entered.wait()

        registered_child_task = agent_subagent.subagent_registry._tasks["child"]
        assert registered_child_task is not parent_task

        assert await agent_subagent.subagent_registry.cancel("child") is True
        result = await parent_task

        assert parent_task.cancelled() is False
        assert "Subagent 已中断" in result
        assert "interrupted or deleted" in result
        assert interrupted == ["child"]

    asyncio.run(scenario())


def test_cancelling_parent_still_cancels_foreground_subagent(monkeypatch, tmp_path):
    import agent_loop
    import agent_subagent

    entered = asyncio.Event()
    child_cancelled = asyncio.Event()

    class _SessionManager:
        sessions_dir = tmp_path

        def clear_interrupt(self, session_id):
            pass

        def append_ui_event(self, *args, **kwargs):
            pass

        def upsert_subagent_task(self, *args, **kwargs):
            pass

        def append_pending_subagent_result(self, *args, **kwargs):
            pass

        def patch_subagent_metadata(self, *args, **kwargs):
            pass

        def write_subagent_output(self, child_session_id, text):
            return str(tmp_path / child_session_id / "output.md")

        def _load_metadata(self, child_session_id):
            return {}

    async def fake_react_node(state, emit=None):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            child_cancelled.set()

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent, "subagent_registry", agent_subagent.SubagentTaskRegistry())
    monkeypatch.setattr(agent_subagent, "_load_subagent_run_histories", lambda child_id: ([], [], ""))
    monkeypatch.setattr(agent_subagent.todo_manager, "sync_session_from_key_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_subagent, "cleanup_git_worktree_for_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_loop, "react_node", fake_react_node)

    async def scenario():
        parent_task = asyncio.create_task(
            agent_subagent._execute_subagent_run(
                child_id="child",
                parent_session_id="parent",
                user_text="task",
                description="desc",
                subagent_type="generalPurpose",
                resumed=False,
            )
        )
        await entered.wait()
        parent_task.cancel()
        try:
            await parent_task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("parent cancellation was swallowed")

        assert child_cancelled.is_set()
        assert agent_subagent.subagent_registry.is_running("child") is False

    asyncio.run(scenario())
