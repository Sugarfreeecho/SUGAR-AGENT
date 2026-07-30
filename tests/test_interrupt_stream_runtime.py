import inspect
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_interrupt_checkpoint_precedes_abort_and_tool_visibility():
    import agent_loop
    import webui

    react_source = inspect.getsource(agent_loop._react_node_once)
    stream_detection = react_source.split("if _steer_requested(state):", 1)[1].split(
        "try:", 1
    )[0]
    assert "_emit_steer_abort_event" not in stream_detection

    interrupted = react_source.split("if steer_interrupted_this_call:", 1)[1].split(
        "if stream_error is not None:", 1
    )[0]
    assert interrupted.index("_persist_state_with_model_append") < interrupted.index(
        "_emit_steer_abort_event"
    )
    assert interrupted.index("_emit_tool_call_sse") < interrupted.index(
        "_emit_steer_abort_event"
    )

    stream_source = inspect.getsource(agent_loop.astream_events)
    tool_branch = stream_source.split(
        'if persist and ev.get("type") == "tool_call":', 1
    )[1].split("return", 1)[0]
    assert tool_branch.index("append_ui_event") < tool_branch.index("queue.put")

    steer_endpoint = inspect.getsource(webui.post_session_steer)
    assert '"cleanup_scope": "none"' in steer_endpoint
    assert '"checkpoint_ok": False' in steer_endpoint


def test_interrupt_stream_frontend_runtime():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests" / "js" / "interrupt_stream_runtime.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "interrupt stream runtime checks passed" in result.stdout
