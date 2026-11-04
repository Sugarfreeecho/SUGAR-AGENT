import logging


def test_default_summary_kinds_include_event_delivery():
    import agent_local_timing as lt

    assert "event_delivery" in lt.SUMMARY_KINDS
    assert lt.TIMING_MODE in {"summary", "detail", "off"}


def test_summary_mode_aggregates_and_flushes(caplog):
    import agent_local_timing as lt

    saved = (lt.TIMING_MODE, lt.SUMMARY_KINDS, lt.SUMMARY_SLOW_MS)
    try:
        lt.TIMING_MODE = "summary"
        lt.SUMMARY_KINDS = frozenset({"event_delivery"})
        lt.SUMMARY_SLOW_MS = 10_000
        lt._agg_rows.clear()
        lt._agg_total = 0

        for _ in range(4):
            lt.LocalOperationTrace("event_delivery", session_id="s1", run_id="r1").finish()

        row = lt._agg_rows[("event_delivery", "s1", "r1")]
        assert row["count"] == 4
        assert row["total_ms"] >= 0

        with caplog.at_level(logging.INFO, logger="agent_harness"):
            lt.flush_local_operation_summary()

        messages = [record.getMessage() for record in caplog.records]
        assert any("local_operation_summary kind=event_delivery" in m and "count=4" in m
                   for m in messages), messages
        assert lt._agg_rows == {}
        assert lt._agg_total == 0
    finally:
        lt.TIMING_MODE, lt.SUMMARY_KINDS, lt.SUMMARY_SLOW_MS = saved
        lt._agg_rows.clear()
        lt._agg_total = 0


def test_slow_trace_still_logs_individually(caplog):
    import agent_local_timing as lt

    saved = (lt.TIMING_MODE, lt.SUMMARY_KINDS, lt.SUMMARY_SLOW_MS)
    try:
        lt.TIMING_MODE = "summary"
        lt.SUMMARY_KINDS = frozenset({"event_delivery"})
        lt.SUMMARY_SLOW_MS = 0  # 0 表示全部单独留痕
        lt._agg_rows.clear()
        lt._agg_total = 0
        with caplog.at_level(logging.INFO, logger="agent_harness"):
            lt.LocalOperationTrace("event_delivery", session_id="s2", run_id="r2").finish()
        assert any("local_operation_timing" in r.getMessage() for r in caplog.records)
    finally:
        lt.TIMING_MODE, lt.SUMMARY_KINDS, lt.SUMMARY_SLOW_MS = saved
        lt._agg_rows.clear()
        lt._agg_total = 0
