"""Warm drafts are shared by creation entry points, never by independent owners."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest


def ready(manager):
    reserve = manager._session_draft_reserve
    with reserve.condition:
        assert reserve.condition.wait_for(lambda: reserve.ready_id is not None, timeout=10)
        return reserve.ready_id


@pytest.fixture(params=[False, True], ids=["legacy", "runtime-v2"])
def manager(tmp_path, monkeypatch, request):
    import agent_harness as h

    monkeypatch.setattr(h.SessionManager, "_runtime_v2_primary", lambda self: request.param)
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(h, "WORK_DIR", root)
    instance = h.SessionManager(tmp_path / "sessions", tmp_path / "sessions.json")
    instance.start_session_draft_reserve()
    try:
        yield instance
    finally:
        instance.stop_session_draft_reserve()


def test_background_reserve_is_hidden_and_event_creation_refills(manager, tmp_path):
    sid = ready(manager)
    assert (manager.sessions_dir / sid / "metadata.json").is_file()
    assert manager.list_sessions() == []
    changes = []
    manager.add_session_state_listener(lambda sid, fields: changes.append((sid, fields)))
    custom = tmp_path / "custom"
    custom.mkdir()
    event_id, dialogue, work, history, context, metadata = manager.get_or_create_session(
        model_profile_id="event-profile", work_dir=str(custom), system_context="Event instructions",
    )
    assert event_id == sid
    assert dialogue == work == history == [] and context == ""
    assert metadata["model_profile_id"] == "event-profile"
    assert metadata["work_dir"] == str(custom.resolve())
    assert metadata["authorized_dirs"] == [str(custom.resolve())]
    assert metadata["system_context"] == "Event instructions"
    assert "draft" not in metadata and "standby_draft" not in metadata
    assert [row["id"] for row in manager.list_sessions()] == [sid]
    assert (sid, frozenset({"created"})) in changes
    next_id = ready(manager)
    assert next_id != sid
    assert manager._load_metadata(next_id)["standby_draft"] is True
    assert "system_context" not in manager._load_metadata(next_id)
    assert len([row for row in manager.index if row.get("id") == sid]) == 1
    if manager._runtime_v2_primary():
        from runtime_v2 import SnapshotStore
        snapshot = SnapshotStore(manager.sessions_dir).read(sid)
        assert snapshot["session"] == metadata


def test_user_draft_is_not_consumed_by_event_or_other_tab(manager, tmp_path):
    warm_id = ready(manager)
    user_id = manager.get_or_create_session(draft=True)[0]
    assert user_id == warm_id
    assert manager._load_metadata(user_id)["draft"] is True
    assert "standby_draft" not in manager._load_metadata(user_id)
    ready(manager)
    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(lambda _: manager.get_or_create_session()[0], range(4)))
    assert len(set(ids)) == 4 and user_id not in ids
    assert manager._load_metadata(user_id)["draft"] is True
    assert {row["id"] for row in manager.list_sessions()} == set(ids)
    assert ready(manager) not in {user_id, *ids}


def test_invalid_creation_does_not_consume_reserve(manager, tmp_path):
    sid = ready(manager)
    with pytest.raises(ValueError):
        manager.get_or_create_session(work_dir=str(tmp_path / "missing"))
    assert ready(manager) == sid


def test_restart_reuses_only_the_unclaimed_reserve(manager):
    import agent_harness as h
    user_id = manager.get_or_create_session(draft=True)[0]
    reserved_id = ready(manager)
    manager.stop_session_draft_reserve()
    restarted = h.SessionManager(manager.sessions_dir, manager.index_file)
    restarted.start_session_draft_reserve()
    try:
        assert ready(restarted) == reserved_id
        assert restarted.get_or_create_session()[0] == reserved_id
        assert restarted._load_metadata(user_id)["draft"] is True
    finally:
        restarted.stop_session_draft_reserve()


def test_api_and_plugin_claim_separate_warm_drafts_and_refresh_cached_list(manager, monkeypatch):
    import webui
    from starlette.testclient import TestClient

    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    manager.add_session_state_listener(webui._on_session_manager_state_changed)
    client = TestClient(webui.fastapi_app)
    webui._invalidate_sessions_state_cache()
    before = client.get("/sessions/state").json()
    user_ready = ready(manager)
    response = client.post("/sessions", json={"prefetch": True})
    assert response.status_code == 200
    assert response.json()["session_id"] == user_ready
    assert response.json()["session"]["draft"] is True
    event_ready = ready(manager)
    event_id = manager.get_or_create_session(model_profile_id="plugin-model")[0]
    assert event_id == event_ready != user_ready
    change = client.get("/sessions/changes", params={"after_revision": before["state_revision"]})
    assert change.status_code == 200
    assert change.json()["state_revision"] > before["state_revision"]
    after = client.get("/sessions/state").json()
    assert [row["id"] for row in after["sessions"]] == [event_id]
    assert after["state_revision"] >= change.json()["state_revision"]


def test_session_changes_wakes_all_tabs_from_a_plugin_thread(monkeypatch, tmp_path):
    import agent_harness as h
    import webui
    from session_state_signal import SessionStateSignal

    instance = h.SessionManager(tmp_path / "sessions", tmp_path / "sessions.json")
    signal = SessionStateSignal(100)
    monkeypatch.setattr(webui, "_sessions_state_signal", signal)
    instance.add_session_state_listener(webui._on_session_manager_state_changed)

    async def scenario():
        tasks = [asyncio.create_task(signal.wait(100, timeout=2)) for _ in range(2)]
        await asyncio.sleep(0)
        assert len(signal.waiters) == 2
        await asyncio.to_thread(instance.get_or_create_session)
        revisions = await asyncio.gather(*tasks)
        assert revisions[0] == revisions[1] > 100
        response = await webui.sessions_changes(after_revision=100)
        assert str(revisions[0]).encode() in response.body
        assert signal.waiters == set()
        # A notification before subscription must be observed immediately.
        assert await signal.wait(100, timeout=0) == revisions[0]
        assert await signal.wait(revisions[0], timeout=0.001) == revisions[0]
        waiting = asyncio.create_task(signal.wait(revisions[0]))
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert signal.waiters == set()

    asyncio.run(scenario())
