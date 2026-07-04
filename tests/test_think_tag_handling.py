import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_api_param_conversion_strips_think_from_assistant_content():
    from agent_messages import AssistantMessage
    from agent_openai import messages_to_openai_params

    params = messages_to_openai_params([
        AssistantMessage(content="<think>hidden reasoning</think>\nvisible answer")
    ])

    assert params[0]["content"] == "visible answer"
    assert "hidden reasoning" not in params[0]["content"]


def test_strip_reasoning_for_api_request_strips_think_for_token_estimate():
    import agent_harness
    from agent_messages import AssistantMessage

    stripped = agent_harness.strip_reasoning_for_api_request([
        AssistantMessage(content="<think>hidden reasoning</think>\nvisible answer")
    ])

    assert stripped[0].content == "visible answer"


def test_compress_phase_strips_think_blocks_from_assistant_content():
    import agent_memory

    msg = agent_memory.AssistantMessage(
        content="<think>" + ("hidden " * 50) + "</think>\nvisible"
    )

    assert agent_memory._strip_reasoning_inplace(msg) is True
    assert msg.content == "visible"


def test_compress_executor_keeps_think_as_short_reasoning_excerpt():
    import agent_memory

    msg = agent_memory.AssistantMessage(
        content="<think>important internal conclusion</think>\nvisible"
    )

    out = agent_memory._dialogue_work_to_chat_messages(
        [msg],
        tool_line_max=1000,
        reasoning_max=1000,
    )

    assert len(out) == 1
    assert "[思考/推理摘录]" in out[0].content
    assert "important internal conclusion" in out[0].content
    assert "<think>" not in out[0].content
