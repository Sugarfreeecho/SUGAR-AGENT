import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_execution_metrics_groups_requests_phases_usage_and_tools(tmp_path):
    import execution_metrics

    old_root = execution_metrics._root
    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    execution_metrics.start_run("s1", "r1", "chat", "这是用户消息")
    execution_metrics.record_request(
        "s1", "r1", 1,
        model="m1",
        context={"estimated_tokens": 120, "context_window": 1000},
    )
    execution_metrics.record_phase("s1", "r1", 1, "pre_api", {"build_messages": 3, "token_estimate": 4})
    execution_metrics.record_stream_event("s1", "r1", 1, {"step": "first_delta", "ms_since_api_start": 50})
    execution_metrics.record_usage("s1", "r1", 1, {"prompt_tokens": 121, "completion_tokens": 9})
    execution_metrics.record_tool("s1", "r1", 1, "read_file", 7, False)
    execution_metrics.finish_run("s1", "r1", "finished")

    data = execution_metrics.snapshot("s1")
    run = data["runs"][0]
    request = run["requests"][0]
    assert run["status"] == "finished"
    assert run["user_preview"] == "这是用户消息"
    assert request["model"] == "m1"
    assert request["first_token_ms"] == 50
    assert request["usage"]["completion_tokens"] == 9
    assert request["phases"]["pre_api"]["total_ms"] == 7
    assert request["tools"][0]["duration_ms"] == 7
    assert (tmp_path / "sessions" / "s1" / "execution_metrics.json").exists()
    all_data = execution_metrics.snapshot_all({"s1": "会话一"})
    assert all_data["sessions"][0]["session_name"] == "会话一"
    # A later run appends; it must not replace the previous persisted run.
    execution_metrics.start_run("s1", "r2", "chat")
    assert [row["run_id"] for row in execution_metrics.snapshot("s1")["runs"]] == ["r1", "r2"]
    execution_metrics._sessions.clear()
    assert [row["run_id"] for row in execution_metrics.snapshot("s1")["runs"]] == ["r1", "r2"]
    execution_metrics._root = old_root
    execution_metrics._sessions.clear()


def test_execution_metrics_run_wall_and_reconcile_fields(tmp_path):
    import execution_metrics

    old_root = execution_metrics._root
    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    execution_metrics.start_run("s2", "r1", "chat", "对账")
    execution_metrics.record_request(
        "s2", "r1", 1,
        startup_ms=3100,
        round_gap_ms=0,
        pre_api_tail_ms=42,
        wall_ms=9700,
    )
    execution_metrics.record_request(
        "s2", "r1", 2,
        round_gap_ms=5088,
        wall_ms=8550,
    )
    execution_metrics.record_run_fields(
        "s2", "r1",
        startup_ms=3100,
        round_gap_ms=5088,
    )
    execution_metrics.finish_run("s2", "r1", "finished")

    data = execution_metrics.snapshot("s2")
    run = data["runs"][0]
    assert run["status"] == "finished"
    assert isinstance(run["wall_ms"], int) and run["wall_ms"] >= 0
    assert run["startup_ms"] == 3100
    assert run["round_gap_ms"] == 5088
    assert data["runs"][0]["requests"][0]["pre_api_tail_ms"] == 42
    assert data["runs"][0]["requests"][1]["round_gap_ms"] == 5088
    execution_metrics._root = old_root
    execution_metrics._sessions.clear()


def test_execution_metrics_record_phase_explicit_total_overwrites(tmp_path):
    import execution_metrics

    old_root = execution_metrics._root
    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    execution_metrics.start_run("s3", "r1", "chat")
    execution_metrics.record_phase("s3", "r1", 1, "pre_api", {"build_messages": 3}, total_ms=3)
    execution_metrics.record_phase("s3", "r1", 1, "pre_api", {"pre_api_tail": 42}, total_ms=45)
    phase = execution_metrics.snapshot("s3")["runs"][0]["requests"][0]["phases"]["pre_api"]
    assert phase["total_ms"] == 45
    assert phase["events"] == {"build_messages": 3, "pre_api_tail": 42}
    execution_metrics._root = old_root
    execution_metrics._sessions.clear()
