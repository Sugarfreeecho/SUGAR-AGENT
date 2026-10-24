from pathlib import Path
import json
import os
import threading

import pytest

from runtime_v2.derived_cache import (source_boundary, source_boundary_window, source_matches,
                                     extend_source_window, estimate_bytes)
from runtime_v2.event_log import SessionEventLog
from runtime_v2.execution_journal import ExecutionJournal
from runtime_v2.recovery_checkpoint import RecoveryCheckpoint


def append_bytes(path, data):
    with path.open("ab") as file:
        before = os.fstat(file.fileno())
        file.write(data)
        file.flush()
        after = os.fstat(file.fileno())
    return {"before": before, "after": after, "encoded": data}


@pytest.mark.parametrize("size", [0, 1, 4095, 4096, 4097, 19000])
@pytest.mark.parametrize("data", ["汉字😀\n".encode(), ("界😀" * 3000 + "\n").encode()], ids=["unicode_short", "unicode_long"])
def test_incremental_boundary_matches_independent_disk_validation(tmp_path, size, data):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b"x" * (size - 1) + b"\n" if size else b"")
    source, window = source_boundary_window(path, size)
    receipt = append_bytes(path, data)
    extended = extend_source_window(source, window, receipt, path.stat())
    assert extended is not None
    boundary, window = extended
    assert boundary == source_boundary(path, path.stat().st_size)
    assert source_matches(path, boundary)
    assert len(window.head) <= 4096 and len(window.tail) <= 4096
    assert estimate_bytes(window) >= len(window.head) + len(window.tail)


@pytest.mark.parametrize("change", ["prior_append", "replace", "length", "modified_after_write", "guard", "missing"])
def test_unknown_or_inconsistent_writer_receipt_cannot_extend(tmp_path, change):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b"old\n")
    source, window = source_boundary_window(path, path.stat().st_size)
    if change == "prior_append":
        append_bytes(path, b"external\n")
    if change == "replace":
        replacement = tmp_path / "replacement"
        replacement.write_bytes(path.read_bytes())
        replacement.replace(path)
    receipt = append_bytes(path, b"new\n")
    if change == "length":
        receipt["encoded"] = b"wrong length\n"
    if change == "modified_after_write":
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000))
    if change == "guard":
        source["tail"] = "invalid"
    if change == "missing":
        receipt = {}
    assert extend_source_window(source, window, receipt, path.stat()) is None


def test_writer_receipt_is_exact_and_never_persisted(tmp_path):
    log = SessionEventLog(tmp_path)
    receipt = {}
    with log.session_transaction("s"):
        event = log._append_unlocked("s", "execution_recorded", {"text": "中文😀\n"}, append_receipt=receipt)
    assert log.event_path("s").read_bytes() == receipt["encoded"]
    assert receipt["after"].st_size == receipt["before"].st_size + len(receipt["encoded"])
    assert "append_receipt" not in event.to_dict()
    assert "encoded" not in json.loads(receipt["encoded"])


def event(delta, seq):
    return {"type": "llm_response_delta", "run_id": "r", "react_iter": 1,
            "stream_seq": 1, "delta_seq": seq, "delta": delta}


def test_warm_owned_appends_need_no_new_boundary_read(tmp_path, monkeypatch):
    import runtime_v2.execution_journal as module
    journal = ExecutionJournal(tmp_path)
    journal.record("s", event("first", 1))
    original = module.source_boundary_window
    def unexpected(*a, **k):
        pytest.fail("known append reopened the log to build its boundary")
    monkeypatch.setattr(module, "source_boundary_window", unexpected)
    for seq in range(2, 8):
        journal.record("s", event("汉字😀" * seq, seq))
    monkeypatch.setattr(module, "source_boundary_window", original)
    with journal._session_lock("s"):
        state = journal._state("s")
        assert source_matches(journal.log.event_path("s"), state["source"])
        assert state["source"]["offset"] == state["offset"]


@pytest.mark.parametrize("external_change", ["append", "replace"])
def test_external_source_change_refreshes_window_before_next_owned_append(tmp_path, monkeypatch, external_change):
    import runtime_v2.execution_journal as module
    journal = ExecutionJournal(tmp_path)
    journal.record("s", event("first", 1))
    # This case exercises source invalidation after a completed external edit.
    # Windows readers can briefly deny replacement; settle our own checkpoint
    # reader before constructing that edit instead of racing its open handle.
    assert RecoveryCheckpoint.wait(journal, "s", 5)
    path = journal.log.event_path("s")
    if external_change == "append":
        record = journal.log.read_all("s")[-1].to_dict()
        record.update(seq=record["seq"] + 1, type="model_assistant", payload={"content": "interleaved"})
        with path.open("ab") as file:
            file.write((json.dumps(record, ensure_ascii=False) + "\n").encode("utf8"))
    else:
        stat = path.stat()
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(path.read_bytes())
        os.utime(replacement, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        replacement.replace(path)
    reads = []
    original = module.source_boundary_window
    def observed(*a, **k):
        reads.append(True)
        return original(*a, **k)
    monkeypatch.setattr(module, "source_boundary_window", observed)
    journal.record("s", event("second", 2))
    assert reads
    state = journal._state("s")
    assert source_matches(path, state["source"])
    assert next(iter(state["records"].values()))["content"] == "firstsecond"


def test_incremental_guard_still_rejects_same_size_restored_mtime_edit(tmp_path):
    journal = ExecutionJournal(tmp_path)
    journal.record("s", event("first", 1))
    journal.record("s", event("second", 2))
    state = journal._state("s")
    path = journal.log.event_path("s")
    stat = path.stat()
    path.write_bytes(path.read_bytes().replace(b"second", b"forged"))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert not source_matches(path, state["source"])


def test_checkpoint_serializes_original_contract_and_recovers_incremental_updates(tmp_path):
    journal = ExecutionJournal(tmp_path)
    for seq in range(1, 9):
        journal.record("s", event(f"片段{seq}😀", seq))
    state = journal._state("s")
    RecoveryCheckpoint.schedule(journal, "s", state, force=True)
    assert RecoveryCheckpoint.wait(journal, "s", 5)
    checkpoint = RecoveryCheckpoint.path(journal, "s").read_bytes()
    assert b"_source_window" not in checkpoint
    expected = next(iter(state["records"].values()))["content"]
    with ExecutionJournal._guard:
        ExecutionJournal._cache.pop(str(journal.log.event_path("s").resolve()), None)
    diagnostics = {}
    restored = journal.read("s", diagnostics=diagnostics)
    assert restored["execution_records"][0]["content"] == expected
    assert diagnostics["source"] == "checkpoint"
    journal.record("s", event("after restart", 9))
    assert journal.read("s")["execution_records"][0]["content"] == expected + "after restart"


def test_checkpoint_boundary_validation_does_not_hold_the_live_journal_lock(tmp_path, monkeypatch):
    import runtime_v2.recovery_checkpoint as module
    journal = ExecutionJournal(tmp_path)
    journal.record("s", event("first", 1))
    assert RecoveryCheckpoint.wait(journal, "s", 5)
    state = journal._state("s")
    entered, release, committed = threading.Event(), threading.Event(), threading.Event()
    original = module.source_matches
    errors = []
    def blocked(*a, **k):
        entered.set()
        assert release.wait(3)
        return original(*a, **k)
    monkeypatch.setattr(module, "source_matches", blocked)
    def checkpoint():
        try:
            RecoveryCheckpoint._write(journal, "s", state)
        except BaseException as exc:
            errors.append(exc)
    def append():
        try:
            journal.record("s", event("second", 2))
            committed.set()
        except BaseException as exc:
            errors.append(exc)
    worker = threading.Thread(target=checkpoint)
    worker.start()
    assert entered.wait(3)
    writer = threading.Thread(target=append)
    writer.start()
    try:
        assert committed.wait(.5), "checkpoint validation blocked live append"
    finally:
        release.set()
        worker.join(3)
        writer.join(3)
    assert not errors
    with ExecutionJournal._guard:
        ExecutionJournal._cache.pop(str(journal.log.event_path("s").resolve()), None)
    assert journal.read("s")["execution_records"][0]["content"] == "firstsecond"
