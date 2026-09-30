import json
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


def test_execution_metrics_list_sessions_is_lightweight(tmp_path, monkeypatch):
    import execution_metrics

    old_root = execution_metrics._root
    # Windows can return the same wall-clock timestamp for consecutive starts.
    # The persisted ordering key must still keep the later run first.
    monkeypatch.setattr(execution_metrics, "_now", lambda: "2026-08-21T00:00:00.000000Z")
    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    execution_metrics.start_run("s4", "r1", "chat", "会话甲")
    execution_metrics.record_request("s4", "r1", 1, duration_ms=1000)
    execution_metrics.finish_run("s4", "r1", "finished")
    execution_metrics.start_run("s5", "r2", "chat", "会话乙")
    execution_metrics.record_request("s5", "r2", 1, duration_ms=500)
    execution_metrics.finish_run("s5", "r2", "finished")

    index = execution_metrics.list_sessions({"s4": "会话甲", "s5": "会话乙"})
    sessions = index["sessions"]
    assert {row["session_id"] for row in sessions} == {"s4", "s5"}
    assert {row["session_name"] for row in sessions} == {"会话甲", "会话乙"}
    assert all(row["run_count"] == 1 for row in sessions)
    assert all("requests" not in row for row in sessions)
    # 最新 run 排最前（s5 后写，last_started_at 更晚）。
    assert sessions[0]["session_id"] == "s5"
    execution_metrics._root = old_root
    execution_metrics._sessions.clear()


def test_execution_metrics_uses_one_shared_heartbeat_thread(monkeypatch):
    import execution_metrics

    starts = []

    class FakeThread:
        def __init__(self, *args, **kwargs):
            self.alive = False

        def start(self):
            self.alive = True
            starts.append(1)

        def is_alive(self):
            return self.alive

    monkeypatch.setattr(execution_metrics, "_heartbeat_thread", None)
    monkeypatch.setattr(execution_metrics.threading, "Thread", FakeThread)

    assert execution_metrics._ensure_heartbeat_thread() is True
    assert execution_metrics._ensure_heartbeat_thread() is True
    assert len(starts) == 1


def test_execution_metrics_heartbeat_thread_exhaustion_is_nonfatal(monkeypatch):
    import execution_metrics

    class FailingThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

        @staticmethod
        def is_alive():
            return False

    monkeypatch.setattr(execution_metrics, "_heartbeat_thread", None)
    monkeypatch.setattr(execution_metrics.threading, "Thread", FailingThread)
    assert execution_metrics._ensure_heartbeat_thread() is False


def test_slow_metrics_flush_does_not_block_other_sessions_or_lose_newer_data(tmp_path, monkeypatch):
    import threading
    import execution_metrics

    old_root = execution_metrics._root
    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    execution_metrics.flush()
    monkeypatch.setattr(execution_metrics, "_FLUSH_DELAY_SEC", 10.0)
    original_write = execution_metrics._write_now
    write_started = threading.Event()
    release_write = threading.Event()
    first_write = True

    def delayed_write(session_id, data):
        nonlocal first_write
        if session_id == "slow" and first_write:
            first_write = False
            write_started.set()
            assert release_write.wait(3)
        original_write(session_id, data)

    monkeypatch.setattr(execution_metrics, "_write_now", delayed_write)
    execution_metrics.start_run("slow", "r1")
    first_flush = threading.Thread(target=execution_metrics.flush, args=("slow",))
    second_flush = None
    first_flush.start()
    try:
        assert write_started.wait(3)
        other_done = threading.Event()
        other = threading.Thread(
            target=lambda: (execution_metrics.record_request("other", "r2", 1), other_done.set())
        )
        other.start()
        assert other_done.wait(1), "another session waited for slow disk I/O"
        other.join(3)

        execution_metrics.record_request("slow", "r1", 1, latest=2)
        second_flush = threading.Thread(target=execution_metrics.flush, args=("slow",))
        second_flush.start()
    finally:
        release_write.set()
        first_flush.join(3)
    assert second_flush is not None
    second_flush.join(3)
    assert not first_flush.is_alive()
    assert not second_flush.is_alive()
    execution_metrics.flush("other")
    data = json.loads(
        (tmp_path / "sessions" / "slow" / "execution_metrics.json").read_text(encoding="utf-8")
    )
    assert data["runs"][0]["requests"][0]["latest"] == 2
    assert (tmp_path / "sessions" / "other" / "execution_metrics.json").exists()
    execution_metrics._root = old_root
    execution_metrics._sessions.clear()


def test_dashboard_disk_scan_does_not_hold_metrics_lock(tmp_path, monkeypatch):
    import threading
    import execution_metrics

    old_root = execution_metrics._root
    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    scan_started = threading.Event()
    release_scan = threading.Event()

    def slow_scan(_root):
        scan_started.set()
        assert release_scan.wait(3)
        return {}

    monkeypatch.setattr(execution_metrics, "_scan_persisted_metrics", slow_scan)
    listing = threading.Thread(target=execution_metrics.list_sessions)
    listing.start()
    try:
        assert scan_started.wait(3)
        recorded = threading.Event()
        writer = threading.Thread(
            target=lambda: (execution_metrics.record_request("live", "r1", 1), recorded.set())
        )
        writer.start()
        assert recorded.wait(1), "dashboard scan blocked a live request"
        writer.join(3)
    finally:
        release_scan.set()
        listing.join(3)
    assert not listing.is_alive()
    execution_metrics.flush("live")
    execution_metrics._root = old_root
    execution_metrics._sessions.clear()


def test_timer_flush_allows_live_updates_and_flushes_following_changes(tmp_path, monkeypatch):
    import threading
    import execution_metrics

    old_root = execution_metrics._root
    execution_metrics.configure(tmp_path / "sessions")
    execution_metrics._sessions.clear()
    monkeypatch.setattr(execution_metrics, "_FLUSH_DELAY_SEC", 0.01)
    original_write = execution_metrics._write_now
    write_started = threading.Event()
    release_write = threading.Event()
    first_write = True

    def delayed_write(session_id, data):
        nonlocal first_write
        if session_id == "timer" and first_write:
            first_write = False
            write_started.set()
            assert release_write.wait(3)
        original_write(session_id, data)

    monkeypatch.setattr(execution_metrics, "_write_now", delayed_write)
    execution_metrics.start_run("timer", "r1")
    try:
        assert write_started.wait(3)
        updated = threading.Event()
        writer = threading.Thread(
            target=lambda: (execution_metrics.record_request("timer", "r1", 1, latest=3), updated.set())
        )
        writer.start()
        assert updated.wait(1), "timer held the metrics lock during disk I/O"
        writer.join(3)
    finally:
        release_write.set()
    execution_metrics.flush("timer")
    data = json.loads(
        (tmp_path / "sessions" / "timer" / "execution_metrics.json").read_text(encoding="utf-8")
    )
    assert data["runs"][0]["requests"][0]["latest"] == 3
    execution_metrics._root = old_root
    execution_metrics._sessions.clear()
