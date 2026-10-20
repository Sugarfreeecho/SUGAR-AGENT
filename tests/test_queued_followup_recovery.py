import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture
def queue_start(monkeypatch):
    import runtime_v2
    import webui

    state = {"runs": {}, "unfinished": False, "stopped": False, "human": 0, "local": False}
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(webui, "_runtime_v2_snapshot", lambda _sid, **kwargs: {"runs": state["runs"]})
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: state["human"])
    monkeypatch.setattr(webui, "_session_was_manually_stopped", lambda _sid: state["stopped"])
    monkeypatch.setattr(webui, "_has_local_worker_activity", lambda _sid: state["local"])
    monkeypatch.setattr(webui, "_react_recovery_workers", {})
    monkeypatch.setattr(webui, "_human_interaction_recovery_workers", {})
    monkeypatch.setattr(webui, "session_manager", SimpleNamespace(
        can_continue_react_session=lambda _sid: state["unfinished"],
    ))
    return webui, state


@pytest.mark.parametrize("status,reason,unfinished,expected", [
    ("running", "", True, "recovering"),
    ("running", "", False, "recovering"),
    ("interrupted", "no_local_activity", True, "recovering"),
    ("interrupted", "process_restart", True, "recovering"),
    ("interrupted", "process_restart", False, "ready"),
    ("interrupted", "user_button", True, "paused"),
    ("failed", "provider_error", False, "paused"),
    ("finished", "", True, "recovering"),
    ("finished", "", False, "ready"),
])
def test_queue_start_requires_a_durable_completed_boundary(queue_start, status, reason, unfinished, expected):
    webui, state = queue_start
    state["runs"] = {"old": {"status": status, "reason": reason, "started_seq": 1}}
    state["unfinished"] = unfinished
    assert webui._queued_followup_start_state("s") == expected


def test_completed_recovery_releases_the_queue_and_ignores_late_old_terminals(queue_start):
    webui, state = queue_start
    state["runs"] = {
        "old": {"status": "interrupted", "reason": "no_local_activity", "started_seq": 1, "finished_seq": 30},
        "recovery": {"status": "finished", "started_seq": 10, "finished_seq": 20},
    }
    assert webui._queued_followup_start_state("s") == "ready"


@pytest.mark.parametrize("blocked,expected", [("stopped", "paused"), ("human", "paused"), ("local", "busy")])
def test_queue_start_preserves_stop_interaction_and_running_boundaries(queue_start, blocked, expected):
    webui, state = queue_start
    state[blocked] = True
    assert webui._queued_followup_start_state("s") == expected


def test_scheduled_recovery_blocks_queue_before_run_registration(queue_start):
    webui, _ = queue_start

    async def run():
        task = asyncio.create_task(asyncio.Event().wait())
        webui._react_recovery_workers["s"] = task
        try:
            assert webui._queued_followup_start_state("s") == "recovering"
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert webui._queued_followup_start_state("s") == "ready"

    asyncio.run(run())


def test_unreadable_runtime_state_never_grants_queue_start(queue_start, monkeypatch):
    webui, _ = queue_start

    def unreadable(_sid, *, fail_closed=False):
        assert fail_closed
        raise OSError("transient storage failure")

    monkeypatch.setattr(webui, "_runtime_v2_snapshot", unreadable)
    assert webui._queued_followup_start_state("s") == "unknown"


def test_manual_queue_send_can_resume_a_pause_but_cannot_bypass_recovery_or_interactions(queue_start):
    webui, state = queue_start
    state["runs"] = {"old": {"status": "interrupted", "reason": "no_local_activity", "started_seq": 1}}
    state["unfinished"] = True
    assert webui._queued_followup_start_state("s", allow_paused=True) == "recovering"
    state["stopped"] = True
    assert webui._queued_followup_start_state("s") == "paused"
    assert webui._queued_followup_start_state("s", allow_paused=True) == "ready"
    state["human"] = 1
    assert webui._queued_followup_start_state("s", allow_paused=True) == "paused"


def test_session_detail_exposes_queue_recovery_before_orphan_cleanup(queue_start, monkeypatch):
    webui, state = queue_start
    state["runs"] = {"old": {"status": "running", "started_seq": 1}}
    state["unfinished"] = True
    webui.session_manager.get_session_summary = lambda sid: {"id": sid}
    monkeypatch.setattr(webui, "_cleanup_stale_active_chat", lambda: None)
    monkeypatch.setattr(webui, "_session_run_state_fields", lambda _sid: {
        "stream_active": False, "run_active": False, "run_started_at": None, "active_run": None,
    })
    monkeypatch.setattr(webui, "_session_pending_human_counts", lambda _sid: {"total": 0})
    monkeypatch.setattr(webui, "is_session_title_generation_pending", lambda _sid: False)
    from workflow_extensions import session_workflows
    monkeypatch.setattr(session_workflows, "continuation_source", lambda _sid: "")
    response = asyncio.run(webui.get_session_detail("s", include_subagents=False))
    detail = json.loads(response.body)
    assert detail["react_auto_resume"] is False
    assert detail["run_active"] is False
    assert detail["queued_followup_state"] == "recovering"
