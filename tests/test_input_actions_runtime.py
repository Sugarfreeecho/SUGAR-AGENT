import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_input_action_runtime_shortcuts_and_normalization():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests/js/input_actions_runtime.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "input action runtime checks passed" in result.stdout


def test_frontend_inputs_share_submission_helpers():
    app_index = (ROOT / "frontend/src/app/index.js").read_text(encoding="utf-8")
    shared = (ROOT / "frontend/src/app/modules/shared-state-and-dialogs.js").read_text(encoding="utf-8")
    sse = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    message = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    human = (ROOT / "frontend/src/app/modules/human-interactions.js").read_text(encoding="utf-8")
    goal = (ROOT / "frontend/src/app/modules/toc-todo.js").read_text(encoding="utf-8")
    team = (ROOT / "frontend/src/app/modules/agent-team.js").read_text(encoding="utf-8")

    assert "inputActionsSource" in app_index
    assert "isInputSubmitShortcut(e, 'single-line')" in shared
    assert sse.count("messageInput.addEventListener('keydown'") == 1
    assert sse.count("sendBtn.addEventListener('click'") == 1
    assert "const state = readComposerActionState();" in sse
    assert "dispatchComposerAction(false)" in sse
    assert "dispatchComposerAction(true)" in sse
    assert "isInputSubmitShortcut(e, 'editor')" in message
    assert "isInputSubmitShortcut(event, 'editor')" in human
    assert "isInputSubmitShortcut(event, 'editor')" in goal
    assert team.count("bindInputSubmit(") == 2


def test_send_preflight_does_not_consume_state_before_lock():
    source = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    send = source.split("async function sendMessage(options)", 1)[1].split(
        "function queueComposerBehindPendingQuestion", 1
    )[0]
    lock_index = send.index("const sendPipelineLock = acquireSendPipelineLock")
    epoch_index = send.index("messageLoadEpoch += 1")
    consume_index = send.index("window.consumeSelectedSkillsForSend()")
    assert lock_index < epoch_index < consume_index
    assert "if (!hasSendableText(rawMessage)) return;" in send


def test_agent_team_controls_are_present_in_both_html_sources():
    for relative in ("frontend/index.html", "frontend/src/shell-body.html"):
        html = (ROOT / relative).read_text(encoding="utf-8")
        assert 'id="agent-team-modal-root"' in html
        assert 'id="agent-team-title-input"' in html
        assert 'id="agent-team-task-title"' in html
