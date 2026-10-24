import asyncio
import copy
from contextlib import contextmanager
from pathlib import Path
import threading
from types import MethodType, SimpleNamespace

import pytest


@pytest.fixture
def native(tmp_path, monkeypatch):
    import runtime_v2
    import session_lifecycle
    from agent_harness import SessionManager
    from runtime_v2 import RuntimeHistoryOps
    monkeypatch.setenv("RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS", "false")
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)
    monkeypatch.setattr(session_lifecycle, "is_session_deleted", lambda _: False)
    manager = SessionManager.__new__(SessionManager)
    manager.sessions_dir = tmp_path
    manager.repository = SimpleNamespace(sessions_dir=tmp_path)
    manager._resolve_session_path = lambda sid: tmp_path/sid
    RuntimeHistoryOps(tmp_path).append_model_message("s", "user", "seed")
    return manager


def rows(count=4):
    return [{"type":"tool_call", "run_id":"r", "react_iter":1, "tool_call_id":str(i),
             "tool_call_index":i, "tool":"read_file", "args":{"path":f'{i}.txt'},
             "result":"中文😀", "status":{"ok":True}, "ui":{"plugin":"change-review"}}
            for i in range(count)]


def verify(manager):
    from runtime_v2 import RuntimeProjector, SessionEventLog, SnapshotStore
    from runtime_v2.execution_journal import ExecutionJournal
    events = SessionEventLog(manager.sessions_dir).read_all("s")
    snapshot = SnapshotStore(manager.sessions_dir).read_for_update("s")
    assert {k:v for k,v in snapshot.items() if k not in ("_event_log", "_projection")} == RuntimeProjector().project(events)
    state = ExecutionJournal(manager.sessions_dir)._state("s")
    assert state["seq"] == events[-1].seq
    assert all("_runtime_v2_committed" not in event.payload for event in events)
    return events, state


@pytest.mark.parametrize("kind", ["tool_call", "llm_reasoning", "llm_response"])
def test_single_native_display_commit_appends_both_facts_once(native, monkeypatch, kind):
    from runtime_v2.event_log import SessionEventLog
    calls = []
    original = SessionEventLog._append_many_unlocked
    def many(self, sid, events):
        calls.append(copy.deepcopy(events))
        return original(self, sid, events)
    monkeypatch.setattr(SessionEventLog, "_append_many_unlocked", many)
    event = rows(1)[0] if kind == "tool_call" else {
        "type":kind, "run_id":"r", "react_iter":1, "content":"complete text"}
    committed = native.commit_execution_ui_event("s", event)
    assert committed["_runtime_v2_committed"]
    assert len(calls) == 1 and len(calls[0]) == 2
    events, state = verify(native)
    assert len(events) == 3 and events[1].type == "execution_recorded"
    assert committed["execution_runtime_seq"] == events[1].seq


def test_native_batch_flushes_once_and_keeps_each_fact_and_execution_reference(native, monkeypatch):
    import runtime_v2.event_log as module
    from runtime_v2 import SessionEventLog
    path = SessionEventLog(native.sessions_dir).event_path("s")
    original = module.open_append_writer
    flushes, writers = [], []
    class Writer:
        def __init__(self, file):
            self.file = file
        def __getattr__(self, key):
            return getattr(self.file, key)
        def flush(self):
            flushes.append(True)
            return self.file.flush()
    @contextmanager
    def opened(target):
        with original(target) as file:
            if target == path:
                writers.append(file)
                yield Writer(file)
            else:
                yield file
    monkeypatch.setattr(module, "open_append_writer", opened)
    result = native.commit_execution_ui_events("s", rows())
    assert len(flushes) == 1 and all(file.closed for file in writers)
    facts, state = verify(native)
    assert [e.type for e in facts[1:]] == ["execution_recorded", "tool_finished"]*4
    assert [r["execution_runtime_seq"] for r in result] == [2,4,6,8]
    assert [e.payload["execution_runtime_seq"] for e in facts[2::2]] == [2,4,6,8]
    assert len(state["records"]) == 4


def test_duplicate_complete_row_preserves_journal_deduplication(native):
    event = rows(1)[0]
    result = native.commit_execution_ui_events("s", [event, dict(event)])
    facts, state = verify(native)
    assert len(facts) == 4
    assert result[0]["execution_id"] == result[1]["execution_id"]
    assert result[0]["execution_runtime_seq"] == result[1]["execution_runtime_seq"] == 2
    assert len(state["records"]) == 1


def test_nonstream_calls_without_indexes_keep_separate_execution_ids(native):
    events = rows(2)
    for event in events:
        event.pop("tool_call_index")
    result = native.commit_execution_ui_events("s", events)
    assert len({row["execution_id"] for row in result}) == 2
    verify(native)


@pytest.mark.parametrize("kind", ["llm_reasoning", "llm_response"])
def test_complete_display_preserves_its_stream_attempt_and_received_prefix(native, kind):
    from runtime_v2.execution_journal import ExecutionJournal
    journal = ExecutionJournal(native.sessions_dir)
    draft = journal.record("s", {"type":kind+"_delta", "run_id":"r", "react_iter":1,
                                 "stream_seq":5, "delta_seq":1, "delta":"prefix"})
    result = native.commit_execution_ui_event("s", {"type":kind, "run_id":"r", "react_iter":1,
                                                   "stream_seq":5, "content":"prefix plus"})
    assert result["execution_id"] == draft["execution_id"]
    _, state = verify(native)
    row = state["records"][result["execution_id"]]
    assert row["status"] == "completed" and row["content"] == "prefix plus"
    assert row["received_content"] == "prefix"


def test_failed_native_append_does_not_publish_planned_journal_or_projection(native, monkeypatch):
    from runtime_v2 import SessionEventLog, SnapshotStore
    from runtime_v2.execution_journal import ExecutionJournal
    snapshot = copy.deepcopy(SnapshotStore(native.sessions_dir).read_for_update("s"))
    prior = copy.deepcopy(ExecutionJournal(native.sessions_dir)._state("s"))
    def fail(*args):
        raise OSError("append failed")
    monkeypatch.setattr(SessionEventLog, "_append_many_unlocked", fail)
    events = rows()
    with pytest.raises(OSError, match="append failed"):
        native.commit_execution_ui_events("s", events)
    assert SnapshotStore(native.sessions_dir).read_for_update("s") == snapshot
    assert ExecutionJournal(native.sessions_dir)._state("s")["records"] == prior["records"]
    assert all("execution_id" not in row for row in events)


@pytest.mark.parametrize("phase", ["before", "planning", "after_append"])
def test_cancellation_has_no_premature_receipt_or_inconsistent_projection(native, monkeypatch, phase):
    import threading
    from runtime_v2 import RuntimeMirror, SessionEventLog
    flag = threading.Event()
    if phase == "before":
        flag.set()
    if phase == "planning":
        original = RuntimeMirror._map_ui_event
        def mapped(*args, **kwargs):
            result = original(*args, **kwargs)
            flag.set()
            return result
        monkeypatch.setattr(RuntimeMirror, "_map_ui_event", mapped)
    if phase == "after_append":
        original = SessionEventLog._append_many_unlocked
        def appended(*args, **kwargs):
            result = original(*args, **kwargs)
            flag.set()
            return result
        monkeypatch.setattr(SessionEventLog, "_append_many_unlocked", appended)
    with pytest.raises(asyncio.CancelledError):
        native.commit_execution_ui_events("s", rows(), cancel_event=flag)
    facts, state = verify(native)
    assert len(facts) == (9 if phase == "after_append" else 1)


def test_source_change_during_planning_stops_before_the_prepared_rows_are_written(native, monkeypatch):
    from runtime_v2 import RuntimeMirror, SessionEventLog, SnapshotStore
    original = RuntimeMirror._map_ui_event
    changed = []
    def mapped(*args, **kwargs):
        result = original(*args, **kwargs)
        if not changed:
            changed.append(True)
            SessionEventLog(native.sessions_dir).append("s", "context_tokens", {"estimated":3})
        return result
    monkeypatch.setattr(RuntimeMirror, "_map_ui_event", mapped)
    with pytest.raises(RuntimeError, match="source changed"):
        native.commit_execution_ui_events("s", rows())
    facts = SessionEventLog(native.sessions_dir).read_all("s")
    assert [event.type for event in facts] == ["model_user", "context_tokens"]
    assert SnapshotStore(native.sessions_dir).read_for_update("s")["last_seq"] == 1
    # A subsequent operation rebuilds its plan against the new durable source.
    native.commit_execution_ui_events("s", rows())
    verify(native)


@pytest.mark.parametrize("method", ["append_ui_event", "_mirror_ui_event_to_runtime_v2", "_apply_appended_ui_event_side_effects"])
def test_customized_manager_protocol_keeps_its_original_path(native, monkeypatch, method):
    from runtime_v2 import SessionEventLog
    calls = []
    original = getattr(native, method)
    def wrapped(self, *args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(native, method, MethodType(wrapped, native))
    def forbidden(*args):
        pytest.fail("custom manager must not use native bulk append")
    monkeypatch.setattr(SessionEventLog, "_append_many_unlocked", forbidden)
    native.commit_execution_ui_events("s", rows())
    assert len(calls) == 4
    verify(native)


def test_unknown_native_source_identity_keeps_the_original_commit_path(native, monkeypatch):
    import runtime_v2.execution_ui_batch as module
    from runtime_v2 import SessionEventLog
    signature = module._signature
    monkeypatch.setattr(module, "_signature", lambda st: (*signature(st)[:1], 0, *signature(st)[2:]))
    def forbidden(*args):
        pytest.fail("unknown source must not use the planned bulk writer")
    monkeypatch.setattr(SessionEventLog, "_append_many_unlocked", forbidden)
    native.commit_execution_ui_events("s", rows())
    verify(native)


def test_source_can_be_replaced_after_the_native_transaction_releases_its_writer(native):
    from runtime_v2 import SessionEventLog
    from runtime_v2.execution_journal import ExecutionJournal
    from runtime_v2.recovery_checkpoint import RecoveryCheckpoint
    native.commit_execution_ui_events("s", rows())
    assert RecoveryCheckpoint.wait(ExecutionJournal(native.sessions_dir), "s", 5)
    path = SessionEventLog(native.sessions_dir).event_path("s")
    replacement = path.with_suffix(".new")
    replacement.write_bytes(path.read_bytes())
    replacement.replace(path)
    event = rows(1)[0]
    event["tool_call_id"] = "next"
    event["react_iter"] = 2
    native.commit_execution_ui_event("s", event)
    verify(native)


def test_projection_failure_after_flush_is_recoverable_without_a_false_commit_receipt(native, monkeypatch):
    from runtime_v2 import RuntimeProjector, SessionEventLog
    original = RuntimeProjector.project_incremental
    with monkeypatch.context() as patcher:
        def failed(self, snapshot, event):
            if event.seq == 4:
                raise OSError("projection failed")
            return original(self, snapshot, event)
        patcher.setattr(RuntimeProjector, "project_incremental", failed)
        with pytest.raises(OSError, match="projection failed"):
            native.commit_execution_ui_events("s", rows())
    assert len(SessionEventLog(native.sessions_dir).read_all("s")) == 9
    # Replaying the durable suffix repairs the projection; no ready result is lost.
    native.commit_execution_ui_events("s", rows())
    verify(native)


def test_failed_private_update_does_not_change_live_record_or_nested_payload(native, monkeypatch):
    from runtime_v2 import SessionEventLog
    from runtime_v2.execution_journal import ExecutionJournal
    from runtime_v2.mirror import RuntimeMirror
    event = rows(1)[0]
    event['args'] = {'nested': {'values': ['before']}}
    native.commit_execution_ui_event('s', event)
    state = ExecutionJournal(native.sessions_dir)._state('s')
    original_records, original_seq = copy.deepcopy(state['records']), state['seq']
    fact_count = len(SessionEventLog(native.sessions_dir).read_all('s'))
    updated = {**event, 'result': 'after', 'args': {'nested': {'values': ['after']}}}
    def fail(*args, **kwargs):
        raise OSError('UI planning rejected')
    with monkeypatch.context() as patcher:
        patcher.setattr(RuntimeMirror, '_map_ui_event', fail)
        with pytest.raises(OSError, match='UI planning rejected'):
            native.commit_execution_ui_event('s', updated)
    assert state['seq'] == original_seq and state['records'] == original_records
    assert len(SessionEventLog(native.sessions_dir).read_all('s')) == fact_count
    native.commit_execution_ui_event('s', updated)
    facts, saved = verify(native)
    assert next(iter(saved['records'].values()))['args'] == updated['args']


def test_private_planning_avoids_event_name_resolution_but_keeps_real_fact_transactions(native, monkeypatch):
    import runtime_v2.execution_ui_batch as module
    from runtime_v2 import SessionEventLog
    planning = threading.local()
    transactions = []
    original_record = module._ExecutionPlan.record
    original_resolve = Path.resolve
    original_transaction = SessionEventLog.session_transaction
    def record(*args, **kwargs):
        planning.active = True
        try:
            return original_record(*args, **kwargs)
        finally:
            planning.active = False
    def resolve(path, *args, **kwargs):
        if getattr(planning, 'active', False) and path.name == 'events.jsonl':
            pytest.fail('Private state must not resolve a shared journal cache key per result')
        return original_resolve(path, *args, **kwargs)
    @contextmanager
    def transaction(self, sid, *args, **kwargs):
        if getattr(planning, 'active', False):
            transactions.append(sid)
        with original_transaction(self, sid, *args, **kwargs):
            yield
    monkeypatch.setattr(module._ExecutionPlan, 'record', record)
    monkeypatch.setattr(Path, 'resolve', resolve)
    monkeypatch.setattr(SessionEventLog, 'session_transaction', transaction)
    native.commit_execution_ui_events('s', rows())
    assert transactions == ['s'] * 4
    verify(native)


def test_private_complete_event_plan_rejects_other_journal_protocols(native):
    from runtime_v2.execution_journal import ExecutionJournal
    from runtime_v2.execution_ui_batch import _ExecutionPlan
    journal = ExecutionJournal(native.sessions_dir)
    with journal.log.session_transaction('s'), journal._session_lock('s'):
        state = journal._state('s')
        records = copy.deepcopy(state['records'])
        plan = _ExecutionPlan(journal, state)
        with pytest.raises(ValueError, match='only accepts complete'):
            plan.record('s', {'type': 'run_failed', 'run_id': 'r'})
        assert not plan.rows and state['records'] == records
