"""Human requests must reach the sidebar without a per-session SSE reader."""

import asyncio
import json

import pytest


@pytest.mark.parametrize("event_type", [
    "interaction_requested", "interaction_resolved", "interaction_cancelled", "interaction_expired",
    "approval_requested", "approval_resolved", "approval_cancelled", "approval_expired",
])
def test_human_lifecycle_invalidates_cached_summary_and_wakes_sidebar(monkeypatch, event_type):
    import webui
    from session_state_signal import SessionStateSignal

    revision = webui._sessions_state_cache_generation
    signal = SessionStateSignal(revision)
    monkeypatch.setattr(webui, "_sessions_state_signal", signal)
    cache = {key: {"ts": 123.0, "payload": {"sessions": []}} for key in (False, True)}
    monkeypatch.setattr(webui, "_sessions_state_cache", cache)
    monkeypatch.setattr(webui, "_sessions_state_cache_generation", revision)

    webui._on_session_lifecycle_event_invalidate_state("background-session", {"type": event_type})

    assert signal.changes_since(revision)["state_revision"] > revision
    assert all(entry["payload"] is None for entry in cache.values())
    assert "terminal_events" not in signal.changes_since(revision)


@pytest.mark.parametrize("event_type", ["llm_response_delta", "status", "approval_analyzed"])
def test_progress_does_not_force_sidebar_rebuild(monkeypatch, event_type):
    import webui

    invalidations = []
    monkeypatch.setattr(webui, "_invalidate_sessions_state_cache", lambda **kw: invalidations.append(kw))
    webui._on_session_lifecycle_event_invalidate_state("background-session", {"type": event_type})
    assert invalidations == []


@pytest.mark.parametrize("kind", ["question", "approval"])
def test_sidebar_http_recovers_request_and_cancellation_without_session_stream(tmp_path, monkeypatch, kind):
    import human_interaction
    import webui
    from agent_harness import SessionManager
    from human_interaction.service import HumanInteractionService
    from session_event_bus import publish_session_event
    from session_state_signal import SessionStateSignal
    from starlette.testclient import TestClient

    sid = "27272727-2727-4272-8272-272727272727"
    root = tmp_path / "sessions"
    (root / sid).mkdir(parents=True)
    metadata = {"id": sid, "name": "Long-running session"}
    (root / sid / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    index = tmp_path / "sessions.json"
    index.write_text(json.dumps({"sessions": [metadata]}), encoding="utf-8")
    manager = SessionManager(root, index)
    service = HumanInteractionService(root, path_resolver=lambda session_id: root / session_id)
    monkeypatch.setenv("ASK_USER_ENABLED", "1")
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    monkeypatch.setattr(human_interaction, "get_human_interaction_service", lambda: service)
    monkeypatch.setattr(webui, "_sessions_state_cache", {
        key: {"ts": 0.0, "payload": None} for key in (False, True)
    })
    signal = SessionStateSignal(webui._sessions_state_cache_generation)
    monkeypatch.setattr(webui, "_sessions_state_signal", signal)
    monkeypatch.setattr(webui, "_sessions_state_cache_generation", signal.revision)
    client = TestClient(webui.fastapi_app)
    baseline = client.get("/sessions/state").json()
    assert baseline["sessions"][0]["pending_human_interactions"]["total"] == 0
    if kind == "question":
        record = service.create_question(sid, {"questions": [{"header": "Continue", "question": "Continue?",
            "options": [{"label": "Yes", "description": "Continue the task"},
                        {"label": "No", "description": "Stop the task"}]}]})
    else:
        record = service.create_approval(sid, approval_id="pending-approval", metadata={"tool": "run_shell"})
    prefix = "interaction" if kind == "question" else "approval"
    # No browser has opened /sessions/{id}/stream. Forwarded child requests
    # use this same sidebar invalidation path without forwarding them again.
    asyncio.run(publish_session_event(sid, {"type": prefix + "_requested", **record, "_subagent_forward": True}))
    assert signal.revision > baseline["state_revision"]
    notice = client.get("/sessions/changes", params={"after_revision": baseline["state_revision"]}).json()
    assert notice["state_revision"] == signal.revision
    pending = client.get("/sessions/state").json()
    assert pending["sessions"][0]["pending_human_interactions"] == {
        "questions": int(kind == "question"), "approvals": int(kind == "approval"), "total": 1,
    }
    cancelled = service.cancel(sid, record[prefix + "_id"], kind=kind)
    asyncio.run(publish_session_event(sid, {"type": prefix + "_cancelled", **cancelled, "_subagent_forward": True}))
    assert signal.revision > pending["state_revision"]
    cleared = client.get("/sessions/state").json()
    assert cleared["sessions"][0]["pending_human_interactions"]["total"] == 0
