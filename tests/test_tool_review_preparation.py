"""Exercise the real execution closure without model/network or user cards."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent_loop
import agent_mcp
from security.models import DecisionOutcome, PermissionMode, SecurityDecision, PERMISSION_PRESETS
from tool_registry import ToolRegistry


@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize("outcome,mode,hook,needs_context", [
    ("allow", "full_access", False, False),
    ("allow", "full_access", True, False),
    ("allow", "ask_for_approval", False, False),
    ("allow", "approve_for_me", False, False),
    ("deny", "ask_for_approval", False, False),
    ("ask", "ask_for_approval", False, True),
    ("ask", "approve_for_me", False, True),
    ("allow", "ask_for_approval", True, True),
])
def test_context_built_only_for_approval_preserving_auth_and_snapshot(
    monkeypatch, tmp_path, child, outcome, mode, hook, needs_context
):
    registry = ToolRegistry()
    registry.register_definition({"type": "function", "function": {"name": "mcp_fixture",
        "parameters": {"type": "object", "properties": {}}}},
        invocation_kind="mcp", owner="fixture", effect="read")
    state = {"session_id": "child" if child else "parent", "_submitted_user_input": "question"}
    args = {"items": ["original"]}
    observations, delivered_contexts = [], []
    granted = False
    context = {"initial_user_question": "original question", "user_followups": [],
               "assistant_context": []}

    def read_context(sid):
        assert needs_context, "allowed/denied tools must not read approval history"
        assert sid == state["session_id"]
        observations.append("context")
        return context

    monkeypatch.setattr(agent_loop, "_tool_review_conversation_from_events", read_context)

    def authorize(**kwargs):
        observations.append("authorize")
        assert kwargs["arguments"] is args
        return (SimpleNamespace(), SecurityDecision(
            DecisionOutcome.ALLOW if granted else DecisionOutcome(outcome), "fixture", "fixture", "digest"),
            PERMISSION_PRESETS[PermissionMode(mode)])

    async def noop(*args, **kwargs):
        pass

    async def pending(*unused):
        observations.append("pending")

    async def wait_approval(sid, aid, publish, **kwargs):
        nonlocal granted
        await publish()
        observations.append("manual_review")
        delivered_contexts.append(kwargs["review_context"]["review_context"])
        granted = True
        return {"approved": True, "decision": "allow_once"}

    async def review(*unused, **kwargs):
        observations.append("auto_review")
        delivered_contexts.append(kwargs["review_context"])
        return SimpleNamespace(approved=True, available=True, risk="low", reason="fixture",
                               intercept_reason="", risk_analysis="", command_purpose="")

    def grant(*unused):
        nonlocal granted
        granted = True

    async def invoke(*unused, **kwargs):
        observations.append("invoke")
        return "fixture result"

    async def awaiter(state, value, *unused, **kwargs):
        return await value

    monkeypatch.setattr(agent_mcp, "invoke_tool_by_fname", invoke)
    namespace = dict(vars(agent_loop)) | dict(
        tool_registry=registry, llm_stream_seq=1, state=state,
        session_meta={"is_subagent": child}, iter_count=1, iter_model="fixture",
        iter_client=SimpleNamespace(current_candidate=lambda: {"input_modalities": ["text"]}),
        emit=noop, _runtime_v2_is_primary=lambda: False, session_work_root=lambda _: tmp_path,
        authorize_tool=authorize, _raise_if_steer_requested=noop, _await_steerable=awaiter,
        _push_stream_event=noop, _emit_tool_pending_sse=pending,
        _emit_tool_approval_required_sse=noop, wait_tool_ui_approval_after_emit=wait_approval,
        _tool_ui_approval_spec=lambda *_: None,
        _security_approval_spec=lambda *_: {"title": "fixture", "message": "fixture"},
        always_ask_for=lambda _: False, review_request=review, add_approval_grant=grant,
        _workflow_callbacks=lambda: SimpleNamespace(call=lambda *_: None),
        _tool_result_details_for_views=lambda result, *_: (result, result, result))
    source = Path(agent_loop.__file__).read_text(encoding="utf-8")
    core = next(node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "_execute_one_core")
    exec(compile(ast.Module(body=[core], type_ignores=[]), agent_loop.__file__, "exec"), namespace)
    call = {"id": "fixture", "name": "mcp_fixture", "args": args}
    if hook:
        call["_hook_approval_spec"] = {"title": "hook", "message": "hook permission"}
    result = asyncio.run(namespace["_execute_one_core"](call))
    assert observations[0] == "authorize"
    assert observations.count("context") == int(needs_context)
    assert observations.count("authorize") == (2 if needs_context else 1)
    assert observations.count("invoke") == int(outcome != "deny")
    assert result["tool_failed"] is (outcome == "deny")
    if needs_context:
        assert observations.index("context") < observations.index("pending")
        assert delivered_contexts == [{**context, "tool_arguments": args}]
        args["items"].append("later")
        assert delivered_contexts[0]["tool_arguments"]["items"] == ["original"]
        assert ("auto_review" in observations) is (mode == "approve_for_me" and not hook)
