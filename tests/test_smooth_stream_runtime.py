import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_smooth_stream_frontend_runtime():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests/js/smooth_stream_runtime.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "smooth stream runtime checks passed" in result.stdout


def test_smooth_stream_legacy_path_remains_available_when_disabled():
    scrolling = (
        ROOT / "frontend/src/app/modules/session-scroll-history.js"
    ).read_text(encoding="utf-8")
    assert "if (!isSmoothStreamActive())" in scrolling
    assert "flushLlmDeltaText(ctx);" in scrolling
    assert "scrollProcessBodyToBottom(ctx, runSessionId);" in scrolling
    assert "scrollChatToBottomIfFollow(runSessionId, {});" in scrolling
    assert "followStreamProcessScroll(ctx, runSessionId, 'text');" in scrolling


def test_final_answer_card_keeps_legacy_immediate_scroll_path():
    rendering = (
        ROOT / "frontend/src/app/modules/message-rendering.js"
    ).read_text(encoding="utf-8")
    assert "cancelSmoothStreamFollowForFinal(ctx);" in rendering
    assert "scrollChatToBottomIfFollow(runSessionId, {});" in rendering
    assert "else if (isSmoothStreamActive()) finishStreamScrollIfFollow" not in rendering


def test_history_scroll_is_isolated_and_stream_end_has_no_easing_tail():
    scrolling = (
        ROOT / "frontend/src/app/modules/session-scroll-history.js"
    ).read_text(encoding="utf-8")
    sessions = (
        ROOT / "frontend/src/app/modules/session-management.js"
    ).read_text(encoding="utf-8")
    assert "smoothFollowController.snapToBottom(processBody);" in scrolling
    assert "smoothFollowController.snapToBottom(chatContainer);" in scrolling
    assert "function cancelSmoothStreamFollowForHistoryLoad()" in scrolling
    assert "cancelSmoothStreamFollowForHistoryLoad();" in sessions


def test_stream_end_pins_trace_before_active_run_context_is_cleared():
    handling = (
        ROOT / "frontend/src/app/modules/sse-handling.js"
    ).read_text(encoding="utf-8")
    start = handling.index("function endRunForClient(")
    end = handling.index("async function readSseChunkWithIdleTimeout", start)
    end_run = handling[start:end]
    assert end_run.index("finishStreamScrollIfFollow(ctx, sid);") < end_run.index(
        "clearSessionRunStateIfMatch"
    )


def test_first_version_text_and_follow_cadence_are_preserved():
    smooth = (
        ROOT / "frontend/src/app/modules/smooth-stream.js"
    ).read_text(encoding="utf-8")
    scrolling = (
        ROOT / "frontend/src/app/modules/session-scroll-history.js"
    ).read_text(encoding="utf-8")
    assert "computeSmoothRevealCount(reasoningPending.length" in scrolling
    assert "computeSmoothRevealCount(responsePending.length" in scrolling
    assert "llmArrivalCpsEma" not in scrolling
    assert "textWarmupMs" not in smooth
    assert "function mutateSmoothTraceTextHeight" not in smooth
    assert "followDtMs: 18" in smooth
    assert "followMinLerp: 0.05" in smooth
    assert "followMaxLerp: 0.25" in smooth
    assert "maxFollowSpeedPxPerSec: 1200" in smooth
    assert "const SMOOTH_STREAM_FOLLOW_PROFILES" in smooth
    text_profile = smooth.index("text: Object.freeze({")
    row_profile = smooth.index("row: Object.freeze({")
    assert smooth.index("minFollowSpeedPxPerSec: 0", text_profile, row_profile) > text_profile
    assert smooth.index("minFollowSpeedPxPerSec: 60", row_profile) > row_profile
    assert "state.requestedChannel = requestedChannel;" in smooth
    assert "state.activeChannel" in smooth
    assert "followStreamProcessScroll(ctx, runSessionId, 'text');" in scrolling
    assert "followStreamProcessScroll(ctx, runSessionId, channel || 'row');" in scrolling
    rendering = (
        ROOT / "frontend/src/app/modules/message-rendering.js"
    ).read_text(encoding="utf-8")
    assert "if (!isHistoryHydrate && !isInitialLiveStatusRow) animateSmoothTraceRowInsertion(row);" in rendering
    assert "if (isInitialLiveStatusRow) finishStreamScrollIfFollow(ctx, runSessionId);" in rendering
    assert "mutateSmoothTraceRowHeight(row, collapse);" in rendering
