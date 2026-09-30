import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_fence_identifies_live_owner_and_reused_pid(monkeypatch, tmp_path):
    import run_ownership

    pid, started_at = run_ownership.current_process_identity()
    assert pid == os.getpid()
    assert started_at is not None
    path = tmp_path / "active_run_fence.json"
    path.write_text(json.dumps({
        "run_id": "running", "owner_pid": pid, "owner_started_at": started_at,
    }), encoding="utf-8")

    assert run_ownership.inspect_run_fence(path).status == "live"
    monkeypatch.setattr(run_ownership, "_process_start_time", lambda _pid: ("live", started_at + 10))
    assert run_ownership.inspect_run_fence(path).status == "dead"


def test_fence_with_unverifiable_owner_fails_closed(monkeypatch, tmp_path):
    import run_ownership

    path = tmp_path / "active_run_fence.json"
    path.write_text(json.dumps({
        "run_id": "running", "owner_pid": 321, "owner_started_at": 123.0,
    }), encoding="utf-8")
    monkeypatch.setattr(run_ownership, "_process_start_time", lambda _pid: ("unknown", None))

    owner = run_ownership.inspect_run_fence(path)
    assert owner.status == "unknown"
    assert owner.pid == 321


def test_pre_migration_fence_is_distinct_from_corrupt_fence(tmp_path):
    import run_ownership

    path = tmp_path / "active_run_fence.json"
    path.write_text(json.dumps({"run_id": "old", "token": "old-token"}), encoding="utf-8")
    assert run_ownership.inspect_run_fence(path).status == "legacy"
    path.write_text("not JSON", encoding="utf-8")
    assert run_ownership.inspect_run_fence(path).status == "unknown"


def test_fence_tracks_a_different_process_until_it_exits(tmp_path):
    import run_ownership

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        status, started_at = run_ownership._process_start_time(child.pid)
        assert status == "live" and started_at is not None
        path = tmp_path / "active_run_fence.json"
        path.write_text(json.dumps({
            "run_id": "foreign", "owner_pid": child.pid, "owner_started_at": started_at,
        }), encoding="utf-8")
        assert run_ownership.inspect_run_fence(path).status == "live"
    finally:
        child.terminate()
        child.wait(timeout=5)
    assert run_ownership.inspect_run_fence(path).status == "dead"


def test_new_run_cannot_replace_a_foreign_live_fence(monkeypatch, tmp_path):
    import agent_loop
    import run_ownership

    class FakeSessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", FakeSessionManager())
    monkeypatch.setattr(
        run_ownership, "inspect_run_fence",
        lambda _path: run_ownership.RunFenceOwner("live", os.getpid() + 1, "foreign-run"),
    )

    with pytest.raises(RuntimeError, match="may still be owned"):
        agent_loop._register_steer_run_control("foreign-live", "new-run")
    assert not (tmp_path / "foreign-live" / "active_run_fence.json").exists()


def test_new_run_persists_owner_identity(monkeypatch, tmp_path):
    import agent_loop

    class FakeSessionManager:
        sessions_dir = tmp_path

    monkeypatch.setattr(agent_loop, "session_manager", FakeSessionManager())
    control = agent_loop._register_steer_run_control("owned", "run-1")
    path = tmp_path / "owned" / "active_run_fence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["owner_pid"] == os.getpid()
    assert isinstance(data["owner_started_at"], float)
    agent_loop._clear_steer_run_control("owned", control)
