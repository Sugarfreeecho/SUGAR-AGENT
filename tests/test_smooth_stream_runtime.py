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


def test_text_reveal_and_unified_follow_contract():
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
    assert "followStiffness: 180" in smooth
    assert "Math.sqrt(SMOOTH_STREAM_CONFIG.followStiffness)" in smooth
    assert "maxFollowStepPx: 20" in smooth
    assert "maxFollowAccelPxPerFrame2" in smooth
    assert "stepCeiling" in smooth
    # 行高变化必须先钉住旧高度再改内容：否则「内容瞬时变矮」的那次布局会把贴底容器的
    # scrollTop 硬钳下去（矮窗口下整个执行过程框单帧闪跳），且钳下去后不会自动恢复。
    assert "function measureSmoothTraceRowNaturalHeight" in smooth
    assert "row.style.height = fromHeight + 'px';" in smooth
    assert "if (pinned) row.style.removeProperty('height');" in smooth
    assert "function computeSmoothFollowSpringStep" in smooth
    assert "followDeadlineMs" not in smooth
    assert "SMOOTH_STREAM_FOLLOW_PROFILES" not in smooth
    assert "minFollowSpeedPxPerSec" not in smooth
    assert "traceHeightStableSince" not in smooth
    assert "measureSmoothTraceItemsHeight" not in smooth
    assert "llmRevealCpsEma" not in scrolling
    assert "followStreamProcessScroll(ctx, runSessionId, 'text');" in scrolling
    assert "followStreamProcessScroll(ctx, runSessionId, channel || 'row');" in scrolling
    # 流式文字写入行时，行上还挂着的插入/高度动画必须释放（否则动画的裁切快照
    # 会把新文字切掉，并在动画结束时整行跳高）。
    assert "data-smooth-trace-layout-owned" in scrolling
    assert "cancelSmoothTraceLayoutAnimation(row);" in scrolling
    rendering = (
        ROOT / "frontend/src/app/modules/message-rendering.js"
    ).read_text(encoding="utf-8")
    # 流式行不做插入高度动画（空行快照 + overflow:clip 会裁掉流入的文字）。
    assert "var isLiveStreamRow = !!(streamOpts.streaming" in rendering
    assert "if (!isHistoryHydrate && !isInitialLiveStatusRow && !isLiveStreamRow) {" in rendering
    assert "if (isInitialLiveStatusRow) finishStreamScrollIfFollow(ctx, runSessionId);" in rendering
    assert "mutateSmoothTraceRowHeight(row, collapse);" in rendering
