import copy
import json
import os

import pytest

from runtime_v2.event_log import SessionEventLog
from runtime_v2.execution_journal import ExecutionJournal
from runtime_v2.derived_cache import source_boundary, source_matches


def stream(delta, seq):
    return {"type": "llm_response_delta", "run_id": "r", "react_iter": 1,
            "stream_seq": 1, "delta_seq": seq, "delta": delta}


def test_owned_tail_replays_interleaved_model_and_ui_without_boundary_opens(tmp_path, monkeypatch):
    import runtime_v2.execution_journal as module
    journal = ExecutionJournal(tmp_path)
    journal.record("s", stream("first", 1))
    first = journal._state("s")
    source = copy.deepcopy(first["source"])
    for index in range(3):
        SessionEventLog(tmp_path).append("s", "model_assistant", {"content": f"answer{index}"})
    path = journal.log.event_path("s")
    receipt = journal.log.recent_owned_append("s", source, path.stat())
    assert receipt is not None
    assert len(receipt["encoded"]) == path.stat().st_size - source["offset"]
    assert b'answer2' in receipt["encoded"]
    monkeypatch.setattr(module, "source_boundary_window", lambda *a: pytest.fail("boundary reopen"))
    monkeypatch.setattr(module, "source_matches", lambda *a: pytest.fail("independent reopen"))
    journal.record("s", stream("second", 2))
    state = journal._state("s")
    assert next(iter(state["records"].values()))["content"] == "firstsecond"
    assert source_matches(path, state["source"])
    # A new journal without memory/receipt history still reconstructs from disk.
    with journal._guard:
        journal._cache.pop(str(path.resolve()))
    monkeypatch.undo()
    with SessionEventLog._owned_appends_guard:
        SessionEventLog._owned_appends.clear()
    recovered = ExecutionJournal(tmp_path).read("s")
    assert recovered["execution_records"][0]["content"] == "firstsecond"


@pytest.mark.parametrize("change", ["external_append", "replace", "touch", "wrong_source", "evict"])
def test_ambiguous_or_missing_owned_tail_requires_disk_read(tmp_path, monkeypatch, change):
    log = SessionEventLog(tmp_path)
    log.append("s", "model_user", {"content": "one"})
    path = log.event_path("s")
    source = source_boundary(path, path.stat().st_size)
    log.append("s", "model_assistant", {"content": "two"})
    if change == "external_append":
        record = log.read_all("s")[-1].to_dict()
        record.update(seq=3, payload={"content": "external"})
        with path.open("ab") as file:
            file.write((json.dumps(record) + "\n").encode())
        # A later owned append must not bridge the unknown external write.
        log.append("s", "model_assistant", {"content": "four"})
    elif change == "replace":
        replacement = path.with_suffix(".new")
        replacement.write_bytes(path.read_bytes())
        os.replace(replacement, path)
    elif change == "touch":
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    elif change == "wrong_source":
        source["mtime_ns"] -= 1
    else:
        monkeypatch.setattr(SessionEventLog, "_OWNED_APPEND_ROWS", 1)
        log.append("s", "model_assistant", {"content": "three"})
    assert log.recent_owned_append("s", source, path.stat()) is None


def test_owned_cache_is_bounded_by_rows_bytes_and_paths(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    monkeypatch.setattr(SessionEventLog, "_owned_appends", __import__('collections').OrderedDict())
    monkeypatch.setattr(SessionEventLog, "_OWNED_APPEND_PATHS", 2)
    monkeypatch.setattr(SessionEventLog, "_OWNED_APPEND_BYTES", 2048)
    monkeypatch.setattr(SessionEventLog, "_OWNED_APPEND_ROWS", 3)
    for sid in ['a', 'b', 'c']:
        for i in range(10):
            log.append(sid, "context_tokens", {"padding": "x" * 500})
    assert len(log._owned_appends) == 2
    for rows, retained in log._owned_appends.values():
        assert len(rows) <= 3
        assert sum(len(row[2]) for row in rows) == retained <= 2048
    log.append('c', "context_tokens", {"padding": "x" * 3000})
    assert len(log._owned_appends) == 1


def test_failed_append_does_not_publish_receipt_as_success(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append("s", "model_user", {"content": "one"})
    path = log.event_path("s")
    source = source_boundary(path, path.stat().st_size)
    def fail(*a, **k):
        raise OSError("failed append finalization")
    monkeypatch.setattr(log, "_update_seq_offset_index_after_append", fail)
    with pytest.raises(OSError):
        log.append("s", "model_assistant", {"content": "two"})
    assert log.recent_owned_append("s", source, path.stat()) is None
