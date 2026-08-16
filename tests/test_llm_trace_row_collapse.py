from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_reasoning_auto_collapses_before_the_turn_finishes() -> None:
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    scrolling = (ROOT / "frontend/src/app/modules/session-scroll-history.js").read_text(encoding="utf-8")

    assert "function finalizeActiveLlmReasoningRow(ctx)" in rendering
    assert "if (responseStarted) finalizeActiveLlmReasoningRow(ctx);" in rendering
    assert "if (logType === 'llm-reasoning') autoCollapseLlmReasoningRow(existing);" in rendering
    assert "row.dataset.manualToggle === '1'" in rendering
    assert "if (row && row.classList.contains('feed--llm')) autoCollapseLlmReasoningRow(row);" in scrolling


def test_reasoning_row_control_is_independent() -> None:
    rendering = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")

    creator = rendering.split("function createProcessFeedRow", 1)[1].split(
        "function appendLlmStreamDelta", 1
    )[0]
    assert "type === 'tool-call' || type === 'llm-reasoning'" in creator
    assert "chunk.classList.add('expanded')" in creator
    assert "type === 'llm-reasoning' && !streamOpts.streaming" in creator
    assert "function handleLlmRowChunkClick" in rendering
    assert "toggleCollapsibleFeedRow(row, true);" in rendering
    # The answer row stays on the pre-change behavior: no row-level fold
    # button, not forced expanded, content-height expand on click.
    assert "type === 'llm-response') chunk.classList.add('expanded')" not in rendering
    assert "llm-response') ch.classList.add('expanded')" not in rendering


def test_collapsed_trace_row_is_exactly_one_line() -> None:
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")

    collapsed = styles.split(".feed-item.is-collapsed .feed-chunk-scroller {", 1)[1].split("}", 1)[0]
    assert "white-space: nowrap;" in collapsed
    assert "text-overflow: ellipsis;" in collapsed
    assert "max-height: calc(var(--line) * 1 + var(--scroller-pad-y) * 2);" in collapsed
    assert "--line: calc(0.74rem * 1.6);" in styles
