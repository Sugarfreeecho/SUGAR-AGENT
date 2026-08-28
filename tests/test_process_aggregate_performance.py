from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/src/app/modules/message-rendering.js"


def _section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_process_stats_use_incremental_state_instead_of_dom_rescan():
    source = SOURCE.read_text(encoding="utf-8")
    stats = _section(source, "function refreshProcessAggregateStats", "function ensureProcessGroup")
    assert "processAggregateStateByElement.get(agg)" in stats
    assert "body.querySelectorAll" not in stats


def test_history_replay_defers_per_row_summary_stats_and_overflow_work():
    source = SOURCE.read_text(encoding="utf-8")
    create = _section(source, "function createProcessFeedRow", "function appendLlmStreamDelta")
    assert "if (!replayingMessages && agg && agg.classList.contains('is-collapsed'))" in create
    assert "if (!replayingMessages) refreshAggregateStatsSmart(agg);" in create


def test_react_ordering_has_monotonic_append_fast_path():
    source = SOURCE.read_text(encoding="utf-8")
    insert = _section(source, "function insertReactOrderedFeedRow", "function feedRowCollapseAriaLabel")
    assert "body._reactOrderTailKey" in insert
    assert insert.index("appendProcessRowBeforePendingAppendSteer") < insert.index("body.querySelectorAll")


def test_trace_measurements_are_coalesced_and_ignore_character_deltas():
    source = SOURCE.read_text(encoding="utf-8")
    assert "var feedChunkOverflowQueue = new Set();" in source
    observer = _section(source, "agg._processHeightMutationObserver.observe", "if (!agg._processHeightResizeObserver")
    assert "characterData" not in observer
