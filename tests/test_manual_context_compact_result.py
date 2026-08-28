import asyncio
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _invoke_context_manage(*, changed: bool):
    from builtin_host_tools import _invoke_context_manage
    from host_tool_registry import HostToolInvocationContext

    original_history = [object()]
    compacted_history = [object()]
    state = {"llm_history": original_history, "key_context": "before"}

    async def await_thread_keepalive(work, _hints, _keepalive):
        return work()

    async def publish(_event):
        return None

    context = HostToolInvocationContext(
        session_id="manual-compact-test",
        tool_call_id="call-1",
        state=state,
        emit_event=publish,
        services={
            "await_thread_keepalive": await_thread_keepalive,
            "progress_hint_event": lambda item: item,
            "llm_history": original_history,
            "run_context_policy": lambda *_args, **_kwargs: (
                compacted_history if changed else original_history,
                "after" if changed else "before",
                changed,
                [],
                changed,
                "recap" if changed else None,
            ),
            "context_window": 32_000,
            "run_interrupt_check": lambda: False,
            "derive_dialogue": lambda history: list(history),
        },
    )
    return asyncio.run(_invoke_context_manage(context, {"mode": "compact"}))


def test_manual_compact_returns_explicit_completed_tool_content():
    outcome = _invoke_context_manage(changed=True)

    assert outcome.content == "手动压缩已完成"
    assert outcome.metadata["control_result"]["type"] == "compact"


def test_manual_compact_noop_still_tells_model_operation_completed():
    outcome = _invoke_context_manage(changed=False)

    assert outcome.content.startswith("手动压缩已完成")
    assert outcome.metadata["control_result"]["type"] == "compact_noop"


def test_manual_compact_control_result_uses_normal_tool_checkpoint_path():
    import agent_loop

    source = inspect.getsource(agent_loop._react_node_once)
    outcome_adapter = source.split("def _response_from_outcome", 1)[1].split(
        "if tool_descriptor is not None and tool_descriptor.invoker_id", 1
    )[0]
    checkpoint = source.split("async def checkpoint_completed_tool_result", 1)[1].split(
        "# 记录 LLM 调用详情", 1
    )[0]

    assert 'response["_control_result"] = dict(control_result)' in outcome_adapter
    assert 'control_result.get("type") == "compact"' in checkpoint
    assert checkpoint.index("llm_history.append(tool_msg_llm)") < checkpoint.index(
        '"manual_context_manage"'
    )
    assert "_persist_state_with_model_replace(" in checkpoint
