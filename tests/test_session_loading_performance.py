"""Behavioral checks for loading a live turn while other sessions keep working."""
import asyncio
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from runtime_v2.event_log import SessionEventLog
from runtime_v2.execution_journal import ExecutionJournal
from runtime_v2.mirror import RuntimeMirror
from runtime_v2.ui_projection import RuntimeUiProjection


def test_selected_facts_do_not_decode_intervening_stream_payloads(tmp_path, monkeypatch):
    import runtime_v2.event_log as module
    log = SessionEventLog(tmp_path)
    events = log.append_batch("s", [
        {"type": "execution_recorded", "payload": {"text_delta": "x" * 4096}}
        for _ in range(256)
    ] + [{"type": "message_user", "payload": {"content": "visible"}}])
    log._read_or_build_seq_offset_index("s")
    decoded = []
    original = module.event_from_record

    def decode(record):
        decoded.append(record["seq"])
        return original(record)

    monkeypatch.setattr(module, "event_from_record", decode)
    selected = log.read_by_seqs("s", [events[19].seq, events[-1].seq, events[19].seq])
    assert [event.seq for event in selected] == [events[19].seq, events[-1].seq]
    # One additional fact verifies the existing sparse index anchor.
    assert len(decoded) <= 3


def test_older_pages_use_visible_index_instead_of_full_projection(tmp_path, monkeypatch):
    mirror = RuntimeMirror(tmp_path)
    for turn in range(8):
        mirror.mirror_ui_event("s", {"type": "user", "content": f"u{turn}"})
        mirror.mirror_ui_event("s", {"type": "final", "content": f"a{turn}"})
    projection = RuntimeUiProjection(tmp_path)
    projection._read_or_build_ui_index("s")
    monkeypatch.setattr(projection, "read_ui_events", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("older-page requests must not project the entire session")))
    page = projection.read_ui_page("s", before_index=14, turns=2)
    assert [row["content"] for row in page["events"]] == ["u5", "a5", "u6", "a6"]
    assert page["range_start"] == 10 and page["range_end"] == 14
    assert page["has_older"] and page["has_newer"]


def test_run_lifecycle_extends_index_without_replaying_old_runs(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append("s", "message_user", {"content": "old"}, run_id="r1")
    projection = RuntimeUiProjection(tmp_path)
    projection._read_or_build_ui_index("s")
    log.append_batch("s", [
        {"type": "run_started", "run_id": "r2"},
        {"type": "message_user", "payload": {"content": "new"}},
        {"type": "run_finished", "run_id": "r2"},
    ])
    monkeypatch.setattr(projection, "_build_ui_index", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("run boundaries must not force full-history reconstruction")))
    page = projection.read_ui_page("s", turns=1)
    assert page["events"][0]["content"] == "new"
    assert page["events"][0]["run_id"] == "r2"
    assert page["last_runtime_seq"] == 4


def test_cold_journal_read_does_not_block_another_sessions_generation(tmp_path, monkeypatch):
    journal = ExecutionJournal(tmp_path)
    journal.log.append("slow", "message_user", {"content": "slow"})
    entered, release = threading.Event(), threading.Event()
    original = journal.log.read_after_seq

    def gated_read(session_id, seq, **kwargs):
        if session_id == "slow":
            entered.set()
            assert release.wait(5)
        return original(session_id, seq, **kwargs)

    monkeypatch.setattr(journal.log, "read_after_seq", gated_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(journal.read, "slow")
        try:
            assert entered.wait(2)
            fast = pool.submit(journal.record, "fast", {
                "type": "llm_response_delta", "run_id": "r", "delta": "keeps working"
            })
            assert fast.result(timeout=2)["execution_id"]
        finally:
            release.set()
        slow.result(timeout=2)


def test_unchanged_journal_does_not_rescan_on_every_token(tmp_path, monkeypatch):
    journal = ExecutionJournal(tmp_path)
    journal.log.append("s", "message_user", {"content": "work"})
    journal.read("s")
    monkeypatch.setattr(journal.log, "read_after_seq", lambda *a: (_ for _ in ()).throw(
        AssertionError("an already-applied log must not be reread")))
    journal.record("s", {"type": "llm_response_delta", "run_id": "r", "delta": "hello"})
    assert journal.read("s")["execution_records"][0]["content"] == "hello"


def test_snapshot_prefers_current_turn_only_while_session_is_active(tmp_path, monkeypatch):
    import runtime_v2
    import webui
    from tests.test_webui_messages import _NoLegacyUiSessionManager
    mirror = RuntimeMirror(tmp_path)
    for turn in range(4):
        mirror.mirror_ui_event("s", {"type": "user", "content": f"old{turn}"})
        mirror.mirror_ui_event("s", {"type": "final", "content": "done"})
    mirror.mirror_ui_event("s", {"type": "user", "content": "current"})
    mirror.mirror_ui_event("s", {"type": "status", "content": "working"})
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(webui, "session_manager", _NoLegacyUiSessionManager(tmp_path, []))
    active = True
    monkeypatch.setattr(webui, "_session_run_state_fields_light", lambda _: {
        "run_active": active, "stream_active": active, "active_run": {"run_id": "r"} if active else None
    })

    def load():
        response = asyncio.run(webui.get_session_history_snapshot(
            "s", limit=200, before_index=None, after_index=None, turns=5,
            event_budget=500, include_aux=False, prefer_active_turn=True,
        ))
        assert response.status_code == 200
        return json.loads(response.body)

    live = load()
    assert live["history_mode"] == "current_turn"
    assert [row["content"] for row in live["messages"]["events"]] == ["current", "working"]
    assert live["messages"]["range_start"] == 8 and live["messages"]["has_older"]
    assert live["count"] == 10 and len(live["user_turns"]) == 5
    active = False
    idle = load()
    assert idle["history_mode"] == "recent_turns"
    assert len(idle["messages"]["events"]) == 10


def test_cold_index_does_not_acknowledge_an_append_after_its_snapshot(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append("s", "message_user", {"content": "first"})
    projection = RuntimeUiProjection(tmp_path)
    original = projection.event_log.iter_events
    appended = False

    def append_during_read(session_id, **kwargs):
        nonlocal appended
        yield from original(session_id, **kwargs)
        if not appended:
            appended = True
            log.append("s", "message_user", {"content": "new"})

    monkeypatch.setattr(projection.event_log, "iter_events", append_during_read)
    first = projection.read_ui_page("s", turns=1)
    assert first["last_runtime_seq"] == 1
    assert [row["content"] for row in first["events"]] == ["first"]
    next_page = projection.read_ui_page("s", turns=1)
    assert next_page["last_runtime_seq"] == 2
    assert [row["content"] for row in next_page["events"]] == ["new"]


def test_incremental_index_stops_at_its_published_file_boundary(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append("s", "message_user", {"content": "first"})
    projection = RuntimeUiProjection(tmp_path)
    projection._read_or_build_ui_index("s")
    log.append("s", "message_user", {"content": "second"})
    original = projection.event_log.read_after_seq
    appended = False

    def append_before_read(session_id, seq, **kwargs):
        nonlocal appended
        if not appended:
            appended = True
            log.append("s", "message_user", {"content": "third"})
        return original(session_id, seq, **kwargs)

    monkeypatch.setattr(projection.event_log, "read_after_seq", append_before_read)
    second = projection.read_ui_page("s", turns=1)
    assert second["last_runtime_seq"] == 2
    assert [row["content"] for row in second["events"]] == ["second"]
    third = projection.read_ui_page("s", turns=1)
    assert third["last_runtime_seq"] == 3
    assert [row["content"] for row in third["events"]] == ["third"]


def test_cold_index_retains_terminal_run_state_for_the_next_extension(tmp_path):
    log = SessionEventLog(tmp_path)
    log.append_batch("s", [
        {"type": "run_started", "run_id": "ended"},
        {"type": "message_user", "payload": {"content": "run"}},
        {"type": "run_finished", "run_id": "ended"},
    ])
    projection = RuntimeUiProjection(tmp_path)
    assert projection._read_or_build_ui_index("s")["last_run_id"] == ""
    log.append("s", "message_user", {"content": "outside the run"})
    assert "run_id" not in projection.read_ui_page("s", turns=1)["events"][0]


def test_bounded_log_reader_defers_partial_trailing_fact(tmp_path):
    log = SessionEventLog(tmp_path)
    log.append_batch("s", [
        {"type": "message_user", "payload": {"content": "first"}},
        {"type": "message_user", "payload": {"content": "second"}},
    ])
    lines = log.event_path("s").read_bytes().splitlines(keepends=True)
    cutoff = len(lines[0]) + len(lines[1]) // 2
    assert [row.seq for row in log.iter_events("s", end_offset=cutoff)] == [1]
    assert [row.seq for row in log.read_after_seq("s", 0, end_offset=cutoff)] == [1]
    assert [row.seq for row in log.read_after_seq("s", 1)] == [2]


@pytest.mark.parametrize("writer_kind", ["mirror", "batch", "gateway"])
def test_visible_commit_catches_up_execution_gap_without_full_replay(tmp_path, monkeypatch, writer_kind):
    from runtime_v2.gateway import RuntimeGateway
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s", {"type": "user", "content": "work"})
    published_before_gap = mirror.snapshots.read_for_update("s")
    journal = ExecutionJournal(tmp_path)
    journal.record("s", {"type": "llm_response_delta", "run_id": "r", "delta": "one"})
    journal.record("s", {"type": "llm_response_delta", "run_id": "r", "delta": "two"})
    writer = RuntimeGateway(tmp_path) if writer_kind == "gateway" else mirror
    monkeypatch.setattr(writer.event_log, "read_all", lambda *a: (_ for _ in ()).throw(
        AssertionError("execution gaps must replay only the suffix, not every old event")))
    monkeypatch.setattr(writer.projector, "project", lambda *a: (_ for _ in ()).throw(
        AssertionError("a valid snapshot with a journal gap must not be rebuilt")))
    if writer_kind == "gateway":
        event = asyncio.run(writer.append_event("s", "ui_event", {"type": "status", "content": "next"}))
    elif writer_kind == "batch":
        event = writer.append_batch("s", [{"type": "ui_event", "payload": {"type": "status", "content": "next"}}])[0]
    else:
        event = writer.append("s", "ui_event", {"type": "status", "content": "next"}, raise_on_error=True)
    current = writer.snapshots.read("s")
    assert current["last_seq"] == event.seq
    assert next(iter(current["executions"].values()))["content"] == "onetwo"
    assert published_before_gap["last_seq"] == 1 and not published_before_gap["executions"]
