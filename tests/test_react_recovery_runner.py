import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_discover_recoverable_react_sessions_finds_background_sessions(monkeypatch):
    import webui
    from workflow_extensions import session_workflows

    cleaned = []

    class FakeSessionManager:
        def list_sessions(self, include_archived=False):
            assert include_archived is False
            return [{"id": sid} for sid in ("current", "background", "running", "goal", "complete", "waiting")]

        def can_continue_react_session(self, sid):
            return sid in {"current", "background", "running", "goal", "waiting"}

    monkeypatch.setattr(webui, "session_manager", FakeSessionManager())
    monkeypatch.setattr(session_workflows, "continuation_source", lambda sid: "agent-goal" if sid == "goal" else "")
    monkeypatch.setattr(webui, "_has_local_worker_activity", lambda sid: sid == "running")
    monkeypatch.setattr(webui, "_active_chat_by_session", {})
    monkeypatch.setattr(
        webui,
        "_cleanup_orphan_runtime_v2_active_runs",
        lambda sid, reason, respect_grace: cleaned.append((sid, reason, respect_grace)) or 0,
    )
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda sid: 1 if sid == "waiting" else 0)
    monkeypatch.setattr(
        webui,
        "_runtime_v2_auto_resume_pending",
        lambda sid: sid != "complete",
    )

    assert webui._discover_recoverable_react_sessions() == ["current", "background"]
    assert cleaned
    assert all(reason == "no_local_activity" and respect_grace is False for _, reason, respect_grace in cleaned)


def test_runtime_state_read_is_observational_and_never_cleans_orphans(monkeypatch):
    import runtime_v2
    import webui

    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(webui, "_active_chat_by_session", {})
    monkeypatch.setattr(
        webui,
        "_cleanup_orphan_runtime_v2_active_runs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("a state read must not append run_interrupted")
        ),
    )
    monkeypatch.setattr(
        webui,
        "_runtime_v2_active_run_info",
        lambda sid: {
            "session_id": sid,
            "run_id": "run-live",
            "run_active": True,
            "started_at": "2026-09-05T00:00:00+00:00",
        },
    )

    state = webui._session_run_state_fields("session-live")

    assert state["run_active"] is True
    assert state["stream_active"] is True
    assert state["active_run"]["run_id"] == "run-live"


def test_runtime_orphan_grace_default_is_nonzero():
    source = (APP_DIR / "webui.py").read_text(encoding="utf-8")
    env_example = (APP_DIR / ".env.example").read_text(encoding="utf-8")

    assert 'os.getenv("RUNTIME_V2_ORPHAN_GRACE_SEC", "30")' in source
    assert "RUNTIME_V2_ORPHAN_GRACE_SEC=30" in env_example


def test_recover_interrupted_react_sessions_schedules_every_candidate(monkeypatch):
    import webui

    scheduled = []
    monkeypatch.setattr(webui, "_discover_recoverable_react_sessions", lambda: ["s1", "s2"])
    monkeypatch.setattr(
        webui,
        "_schedule_react_recovery",
        lambda sid: scheduled.append(sid) is None or True,
    )

    result = asyncio.run(webui.recover_interrupted_react_sessions())

    assert result == ["s1", "s2"]
    assert scheduled == ["s1", "s2"]


def test_auto_resume_is_not_pending_while_human_interaction_waits(monkeypatch):
    import webui

    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 1)
    monkeypatch.setattr(
        webui,
        "_runtime_v2_snapshot",
        lambda _sid: (_ for _ in ()).throw(AssertionError("run state must not be inspected")),
    )

    assert webui._runtime_v2_auto_resume_pending("waiting") is False


def test_auto_resume_is_not_pending_after_manual_stop_even_if_latest_event_is_cancelled(monkeypatch):
    import webui

    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 0)
    monkeypatch.setattr(webui, "_session_was_manually_stopped", lambda _sid: True)
    monkeypatch.setattr(
        webui,
        "_runtime_v2_snapshot",
        lambda _sid: (_ for _ in ()).throw(AssertionError("run state must not override manual stop")),
    )

    assert webui._runtime_v2_auto_resume_pending("stopped") is False


def test_manual_stop_uses_the_durable_interrupt_reason(monkeypatch):
    import webui

    class FakeSessionManager:
        reason = "user_button"

        @staticmethod
        def is_interrupt_requested(_sid):
            return True

        @classmethod
        def get_interrupt_reason(cls, _sid):
            return cls.reason

    manager = FakeSessionManager()
    monkeypatch.setattr(webui, "session_manager", manager)

    assert webui._session_was_manually_stopped("stopped") is True
    FakeSessionManager.reason = "runtime_watchdog"
    assert webui._session_was_manually_stopped("recoverable") is False


def test_background_recovery_drains_generator_without_a_ui(monkeypatch):
    import webui

    observed = {"events": 0, "released": None}

    class FakeSessionManager:
        def can_continue_react_session(self, sid):
            return sid == "background"

        def is_interrupt_requested(self, _sid):
            return False

    async def fake_continuation(session_id, **kwargs):
        assert session_id == "background"
        assert kwargs["continuation_source"] == "recovery"
        assert kwargs["recovery_reason"] == "process_or_network_interruption"
        for _ in range(2):
            observed["events"] += 1
            yield {"type": "status"}

    monkeypatch.setattr(webui, "session_manager", FakeSessionManager())
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 0)
    monkeypatch.setattr(webui, "_runtime_v2_auto_resume_pending", lambda sid: sid == "background")
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda sid, run_id: "token")
    monkeypatch.setattr(
        webui,
        "_release_session_chat_start",
        lambda sid, token: observed.update(released=(sid, token)),
    )
    monkeypatch.setattr(webui, "astream_events_continuation", fake_continuation)

    asyncio.run(webui._run_react_recovery_background("background"))

    assert observed["events"] == 2
    assert observed["released"] == ("background", "token")


def test_background_recovery_stops_when_human_interaction_is_pending(monkeypatch):
    import webui

    observed = {"continuations": 0, "released": None}

    class FakeSessionManager:
        def can_continue_react_session(self, _sid):
            return True

    async def fake_continuation(_session_id, **_kwargs):
        observed["continuations"] += 1
        yield {"type": "status"}

    monkeypatch.setattr(webui, "session_manager", FakeSessionManager())
    monkeypatch.setattr(webui, "_session_pending_human_count", lambda _sid: 1)
    monkeypatch.setattr(webui, "_runtime_v2_auto_resume_pending", lambda _sid: True)
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id: "token")
    monkeypatch.setattr(
        webui,
        "_release_session_chat_start",
        lambda sid, token: observed.update(released=(sid, token)),
    )
    monkeypatch.setattr(webui, "astream_events_continuation", fake_continuation)

    asyncio.run(webui._run_react_recovery_background("waiting"))

    assert observed["continuations"] == 0
    assert observed["released"] == ("waiting", "token")


def test_recover_sessions_endpoint_reports_all_scheduled_sessions(monkeypatch):
    import webui

    async def fake_recover():
        return ["s1", "s2"]

    monkeypatch.setattr(webui, "recover_interrupted_react_sessions", fake_recover)

    response = asyncio.run(webui.recover_sessions())
    payload = json.loads(response.body.decode("utf-8"))

    assert payload == {"ok": True, "scheduled": ["s1", "s2"], "count": 2}


def test_http_continue_uses_same_start_reservation_as_background_recovery(monkeypatch):
    import webui
    from workflow_extensions import session_workflows

    released = []

    class FakeSessionManager:
        def can_continue_react_session(self, _sid):
            return True

        def is_interrupt_requested(self, _sid):
            return False

    class FakeRequest:
        async def is_disconnected(self):
            return False

    async def fake_continuation(_session_id, **_kwargs):
        yield {"type": "status", "content": "running"}

    monkeypatch.setattr(webui, "session_manager", FakeSessionManager())
    monkeypatch.setattr(
        webui,
        "_session_pending_human_counts",
        lambda _sid: {"questions": 0, "approvals": 0, "total": 0},
    )
    monkeypatch.setattr(session_workflows, "continuation_source", lambda _sid: "")
    monkeypatch.setattr(webui, "_reserve_session_chat_start", lambda _sid, _run_id: "token")
    monkeypatch.setattr(webui, "_release_session_chat_start", lambda sid, token: released.append((sid, token)))
    monkeypatch.setattr(webui, "astream_events_continuation", fake_continuation)
    monkeypatch.setattr(webui, "_active_chat_by_session", {})
    monkeypatch.setattr(webui, "_active_chat_last_seen", {})

    async def run():
        response = await webui.continue_react_session("s1", FakeRequest(), recovery=True)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())

    assert any('"type": "status"' in str(chunk) for chunk in chunks)
    assert released == [("s1", "token")]


def test_http_continue_rejects_pending_human_interaction(monkeypatch):
    import webui

    class FakeRequest:
        pass

    monkeypatch.setattr(
        webui,
        "_session_pending_human_counts",
        lambda _sid: {"questions": 1, "approvals": 0, "total": 1},
    )

    response = asyncio.run(webui.continue_react_session("waiting", FakeRequest(), recovery=True))
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 409
    assert payload["reason"] == "pending_human_interaction"
    assert payload["pending_human_interactions"]["questions"] == 1


def test_http_auto_recovery_rejects_manually_stopped_session(monkeypatch):
    import webui

    class FakeRequest:
        pass

    monkeypatch.setattr(
        webui,
        "_session_pending_human_counts",
        lambda _sid: {"questions": 0, "approvals": 0, "total": 0},
    )
    monkeypatch.setattr(webui, "_session_was_manually_stopped", lambda _sid: True)

    response = asyncio.run(webui.continue_react_session("stopped", FakeRequest(), recovery=True))
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 409
    assert payload["reason"] == "manually_stopped"
