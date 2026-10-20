"""Sequence cursors bind to the observed file across resolver and writer races."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

from app.runtime_v2.event_log import SessionEventLog


@pytest.fixture(autouse=True)
def isolated_sequence_cache(monkeypatch):
    monkeypatch.setattr(SessionEventLog, "_seq_cache", {})


def _seed(tmp_path, seq=1):
    log = SessionEventLog(tmp_path)
    log.append("s", "model_user", {"content": "x"})
    path = log.event_path("s")
    if seq != 1:
        path.write_bytes(path.read_bytes().replace(b'"seq":1', ('"seq":'+str(seq)).encode()))
        SessionEventLog._seq_cache.clear()
    return log


def test_preserved_size_mtime_replacement_invalidates_seq_cursor(tmp_path):
    log = _seed(tmp_path)
    path = log.event_path("s")
    info = path.stat()
    assert log.next_seq("s") == 2
    replacement = path.with_suffix(".replacement")
    replacement.write_bytes(path.read_bytes().replace(b'"seq":1', b'"seq":9'))
    os.utime(replacement, ns=(info.st_atime_ns, info.st_mtime_ns))
    os.replace(replacement, path)
    assert (path.stat().st_size, path.stat().st_mtime_ns) == (info.st_size, info.st_mtime_ns)
    assert path.stat().st_ino != info.st_ino
    assert log.next_seq("s") == 10
    assert log.append("s", "model_user", {"content": "after"}).seq == 10
    assert [event.seq for event in log.read_all("s")] == [9, 10]


def test_cold_cursor_keeps_the_path_that_was_read(tmp_path, monkeypatch):
    a = _seed(tmp_path / "a", 9)
    b = _seed(tmp_path / "b")
    SessionEventLog._seq_cache.clear()
    selected = [a.session_dir("s")]
    log = SessionEventLog(tmp_path, path_resolver=lambda _: selected[0])
    original = log._read_last_seq_from_tail
    def read_then_remap(path):
        result = original(path)
        selected[0] = b.session_dir("s")
        return result
    monkeypatch.setattr(log, "_read_last_seq_from_tail", read_then_remap)
    assert log.next_seq("s") == 10
    assert log.next_seq("s") == 2


def test_observer_does_not_cache_old_tail_under_new_append_metadata(tmp_path, monkeypatch):
    log = _seed(tmp_path)
    SessionEventLog._seq_cache.clear()
    original = log._read_last_seq_from_tail
    calls = []
    def read_then_append(path):
        result = original(path)
        if not calls:
            record = log.read_all("s")[-1].to_dict()
            record["seq"] = 9
            with path.open("ab") as stream:
                stream.write((json.dumps(record)+"\n").encode())
        calls.append(path)
        return result
    monkeypatch.setattr(log, "_read_last_seq_from_tail", read_then_append)
    assert log.next_seq("s") == 2
    assert log.next_seq("s") == 10


def test_unknown_identity_falls_back_to_reading_facts(tmp_path, monkeypatch):
    log = _seed(tmp_path)
    event_path = log.event_path("s")
    original_stat = Path.stat
    original_read = log._read_last_seq_from_tail
    reads = []
    def unknown_inode(path, *args, **kwargs):
        info = original_stat(path, *args, **kwargs)
        if path == event_path:
            values = {name:getattr(info, name) for name in dir(info) if name.startswith("st_")}
            values["st_ino"] = 0
            return SimpleNamespace(**values)
        return info
    def read(path):
        reads.append(path)
        return original_read(path)
    monkeypatch.setattr(Path, "stat", unknown_inode)
    monkeypatch.setattr(log, "_read_last_seq_from_tail", read)
    assert log.next_seq("s") == 2
    assert reads == [event_path]


def test_legacy_cursor_without_identity_is_rebuilt(tmp_path):
    log = _seed(tmp_path)
    info = log.event_path("s").stat()
    SessionEventLog._seq_cache[log._cache_scope_for("s")] = (info.st_mtime_ns, info.st_size, 99)
    assert log.next_seq("s") == 2


@pytest.mark.parametrize("kind", ["single", "batch", "event"])
def test_append_uses_the_transaction_path_after_resolver_changes(tmp_path, monkeypatch, kind):
    from app.runtime_v2.event_schema import RuntimeEvent
    a, b = _seed(tmp_path/"a", 9), _seed(tmp_path/"b")
    SessionEventLog._seq_cache.clear()
    selected = [a.session_dir("s")]
    log = SessionEventLog(tmp_path, path_resolver=lambda _: selected[0])
    read = log._read_last_seq_from_tail
    def remap_after_tail(path):
        result = read(path)
        selected[0] = b.session_dir("s")
        return result
    monkeypatch.setattr(log, "_read_last_seq_from_tail", remap_after_tail)
    if kind == "single":
        result = log.append("s", "model_user", {"content": "next"})
    elif kind == "batch":
        result = log.append_batch("s", [{"type": "model_user", "payload": {"content": "next"}}])[0]
    else:
        result = log.append_event(RuntimeEvent(seq=10, session_id="s", type="model_user", payload={"content": "next"}))
    assert result.seq == 10
    assert [e.seq for e in a.read_all("s")] == [9, 10]
    assert [e.seq for e in b.read_all("s")] == [1]


@pytest.mark.parametrize("kind", ["single", "batch", "event"])
def test_append_cursor_is_not_attached_to_a_replaced_source(tmp_path, monkeypatch, kind):
    from app.runtime_v2.event_schema import RuntimeEvent
    log = _seed(tmp_path)
    path = log.event_path("s")
    original_bytes = path.read_bytes()
    update = log._update_seq_cache
    def replace_before_publication(sid, last, **kwargs):
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(original_bytes)
        os.replace(replacement, path)
        return update(sid, last, **kwargs)
    monkeypatch.setattr(log, "_update_seq_cache", replace_before_publication)
    if kind == "single":
        log.append("s", "model_user", {"content": "next"})
    elif kind == "batch":
        log.append_batch("s", [{"type": "model_user", "payload": {"content": "next"}}])
    else:
        log.append_event(RuntimeEvent(seq=2, session_id="s", type="model_user", payload={"content": "next"}))
    monkeypatch.setattr(log, "_update_seq_cache", update)
    assert log.next_seq("s") == 2
    assert [event.seq for event in log.read_all("s")] == [1]
