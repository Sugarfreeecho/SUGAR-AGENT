"""Keep long-running SSE producers and admission checks off the HTTP loop."""
import asyncio
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture
def transport(monkeypatch):
    import webui

    for name in ("_active_chat_by_session", "_active_chat_last_seen",
                 "_active_chat_tasks_by_session", "_chat_starting_by_session"):
        monkeypatch.setattr(webui, name, {})
    monkeypatch.setattr(webui, "is_run_active", lambda _sid: False)
    monkeypatch.setattr(webui, "_invalidate_sessions_state_cache", lambda: None)
    return webui


def expire_connections(webui):
    for sid in webui._active_chat_last_seen:
        webui._active_chat_last_seen[sid] = time.time() - webui._CHAT_ACTIVE_TIMEOUT_SEC - 1


def test_quiet_live_producer_survives_stale_cleanup(transport):
    async def scenario():
        task = transport._register_active_chat_connection("s")
        transport._chat_starting_by_session["s"] = (0, "run")
        expire_connections(transport)
        transport._cleanup_stale_active_chat()
        assert transport._active_chat_by_session == {"s": 1}
        assert "s" in transport._chat_starting_by_session
        assert transport._active_chat_last_seen["s"] > time.time() - 1
        transport._unregister_active_chat_connection("s", task)
        assert transport._active_chat_by_session == {}
        assert transport._active_chat_last_seen == {}
        assert transport._active_chat_tasks_by_session == {}

    asyncio.run(scenario())


def test_stale_cleanup_removes_dead_producers_and_zombie_reservations(transport):
    async def scenario():
        live = transport._register_active_chat_connection("s")

        async def abandoned(sid):
            transport._register_active_chat_connection(sid)

        await asyncio.create_task(abandoned("s"))
        await asyncio.create_task(abandoned("dead"))
        transport._chat_starting_by_session["dead"] = (0, "run")
        expire_connections(transport)
        transport._cleanup_stale_active_chat()
        assert transport._active_chat_by_session == {"s": 1}
        assert transport._active_chat_tasks_by_session == {"s": {live}}
        assert "dead" not in transport._chat_starting_by_session
        transport._unregister_active_chat_connection("s", live)

    asyncio.run(scenario())


def test_old_producer_cannot_decrement_a_replacement_connection(transport):
    async def scenario():
        registered, release = asyncio.Event(), asyncio.Event()

        async def old_connection():
            task = transport._register_active_chat_connection("s")
            registered.set()
            await release.wait()
            transport._unregister_active_chat_connection("s", task)

        old = asyncio.create_task(old_connection())
        await registered.wait()
        transport._clear_active_chat_connections("s")
        replacement = transport._register_active_chat_connection("s")
        release.set()
        await old
        assert transport._active_chat_by_session == {"s": 1}
        assert transport._active_chat_tasks_by_session == {"s": {replacement}}
        transport._unregister_active_chat_connection("s", replacement)

    asyncio.run(scenario())


def test_chat_admission_waits_for_storage_without_blocking_the_loop(transport, monkeypatch, tmp_path):
    import runtime_v2
    from runtime_v2.event_log import SessionEventLog

    log = SessionEventLog(tmp_path)
    log.append("s", "message_user", {"content": "test"})
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(transport, "_is_subagent_execution_active", lambda _sid: False)
    monkeypatch.setattr(transport, "session_manager", SimpleNamespace(
        repository=SimpleNamespace(sessions_dir=tmp_path),
        _resolve_session_path=lambda sid: tmp_path / sid,
        get_interrupt_reason=lambda _sid: "",
    ))
    entered, locked, release = threading.Event(), threading.Event(), threading.Event()
    observed_threads = []
    original = transport._runtime_v2_snapshot

    def read_snapshot(sid):
        observed_threads.append(threading.get_ident())
        entered.set()
        return original(sid)

    monkeypatch.setattr(transport, "_runtime_v2_snapshot", read_snapshot)

    def hold_storage_lock():
        with log.session_transaction("s"):
            locked.set()
            release.wait(3)

    holder = threading.Thread(target=hold_storage_lock)
    holder.start()
    assert locked.wait(2)

    async def scenario():
        caller_thread = threading.get_ident()
        reservation = asyncio.create_task(transport._reserve_session_chat_start_off_loop("s", "run"))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            # This assertion executes while another thread still owns the lock.
            assert not reservation.done()
            assert len(observed_threads) == 1
            assert observed_threads[0] != caller_thread
        finally:
            release.set()
            token = await reservation
            transport._release_session_chat_start("s", token)
        assert token == "run"

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        holder.join(3)
        from runtime_v2.snapshot_store import SnapshotStore
        SnapshotStore(tmp_path).wait_for_checkpoint("s", timeout_seconds=2)


def test_chat_busy_response_checks_durable_state_off_loop(transport, monkeypatch):
    import runtime_v2

    caller_thread = threading.get_ident()
    observed = []

    def checked(value):
        def check(*_args, **_kwargs):
            observed.append(threading.get_ident())
            return value
        return check

    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(transport, "_runtime_v2_chat_protocol_enabled", lambda *_args: False)
    monkeypatch.setattr(transport, "_runtime_v2_legacy_only_migration_pending", checked({"pending": False}))
    monkeypatch.setattr(transport, "_reserve_session_chat_start", checked(None))
    monkeypatch.setattr(transport, "_session_run_state_fields", checked({
        "active_run": {"run_id": "existing"}, "stream_connections": 1,
    }))
    response = asyncio.run(transport.chat(
        request=SimpleNamespace(), message="next", session_id="s", client_run_id="run",
        stream_protocol="runtime_v2", followup_steer=False, queued_followup=False,
        steer_id="", selected_skills="[]", ui_message="next", ui_language="zh-CN",
        attachments="[]", preserve_unread_result=False,
    ))
    assert response.status_code == 409
    assert json.loads(response.body)["active_run"]["run_id"] == "existing"
    assert len(observed) == 3
    assert all(thread != caller_thread for thread in observed)


@pytest.mark.parametrize("replacement", [False, True])
def test_cancelled_admission_releases_only_its_own_late_reservation(transport, monkeypatch, replacement):
    entered, release = threading.Event(), threading.Event()

    def reserve(_sid, _run):
        entered.set()
        assert release.wait(3)
        return "old"

    monkeypatch.setattr(transport, "_reserve_session_chat_start", reserve)

    async def scenario():
        cleaned = asyncio.Event()
        original_release = transport._release_session_chat_start

        def cleanup(sid, token):
            original_release(sid, token)
            cleaned.set()

        monkeypatch.setattr(transport, "_release_session_chat_start", cleanup)
        transport._chat_starting_by_session["s"] = (time.time(), "new" if replacement else "old")
        reservation = asyncio.create_task(transport._reserve_session_chat_start_off_loop("s", "old"))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            reservation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await reservation
        finally:
            release.set()
        await asyncio.wait_for(cleaned.wait(), 2)
        assert bool(transport._chat_starting_by_session) is replacement

    asyncio.run(scenario())


def test_native_stream_reads_storage_off_loop(transport, monkeypatch):
    caller_thread = threading.get_ident()
    threads = []

    def read_events(*_args, **_kwargs):
        threads.append(threading.get_ident())
        return []

    async def disconnected():
        return False

    monkeypatch.setattr(transport, "_runtime_v2_event_dicts", read_events)
    monkeypatch.setattr(transport, "_has_local_worker_activity", lambda _sid: False)

    async def scenario():
        response = await transport.runtime_v2_session_stream("s", SimpleNamespace(is_disconnected=disconnected), 1, 50)
        chunks = [chunk async for chunk in response.body_iterator]
        assert chunks == ["data: [DONE]\n\n"]

    asyncio.run(scenario())
    assert len(threads) == 1
    assert threads[0] != caller_thread


def test_native_event_page_stops_decoding_at_the_requested_limit(transport, monkeypatch):
    from runtime_v2.event_log import SessionEventLog

    decoded = []

    def events(_self, _sid, after):
        assert after == 10
        for seq in range(11, 1000):
            decoded.append(seq)
            yield SimpleNamespace(to_dict=lambda seq=seq: {"seq": seq})

    monkeypatch.setattr(SessionEventLog, "iter_after_seq", events)
    assert transport._runtime_v2_event_dicts("s", after_seq=10, limit=2) == [{"seq": 11}, {"seq": 12}]
    assert decoded == [11, 12]
