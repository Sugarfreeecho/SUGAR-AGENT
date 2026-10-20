import os
import asyncio
from contextvars import copy_context
from pathlib import Path
import shutil
import subprocess
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))
from runtime_v2 import read_probe as probe
from runtime_v2.derived_cache import source_boundary, source_matches
from runtime_v2.event_log import SessionEventLog


@pytest.fixture(autouse=True)
def clear_handles():
    probe.close_probe_readers()
    yield
    probe.close_probe_readers()


def test_each_probe_reads_new_bytes_even_when_size_and_mtime_are_restored(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b"first\n")
    boundary = source_boundary(path, path.stat().st_size)
    before = path.stat()
    path.write_bytes(b"other\n")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    with probe.open_probe_reader(path) as reader:
        assert reader.read() == b"other\n"
    assert not source_matches(path, boundary)


def test_cross_process_replace_and_delete_remain_possible(tmp_path):
    path, replacement = tmp_path / "events.jsonl", tmp_path / "replacement"
    path.write_bytes(b"before\n")
    replacement.write_bytes(b"after!\n")
    before = path.stat()
    old = source_boundary(path, before.st_size)
    command = [sys.executable, "-c", "import os,sys; os.replace(sys.argv[1],sys.argv[2])",
               str(replacement), str(path)]
    subprocess.run(command, check=True, capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    with probe.open_probe_reader(path) as reader:
        assert reader.read() == b"after!\n"
    assert not source_matches(path, old)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        with probe.open_probe_reader(path):
            pass
    path.write_bytes(b"new\n")
    with probe.open_probe_reader(path) as reader:
        assert reader.read() == b"new\n"


@pytest.mark.skipif(os.name != "nt", reason="Windows handle pool")
def test_pool_reuses_handles_without_retaining_read_ahead(tmp_path, monkeypatch):
    path = tmp_path / "facts"
    path.write_bytes(b"a" * 12000)
    opens = []
    original = probe._open_shared_read
    def opened(path):
        opens.append(path)
        return original(path)
    monkeypatch.setattr(probe, "_open_shared_read", opened)
    with probe.read_probe_scope():
        for _ in range(4):
            with probe.open_probe_reader(path) as reader:
                assert reader.read(1) == b"a"
        assert len(opens) == 1
        path.write_bytes(b"b" * 12000)
        with probe.open_probe_reader(path) as reader:
            raw = reader.raw
            assert reader.read(1) == b"b"
        assert len(opens) == 1
    assert raw.closed


@pytest.mark.skipif(os.name != "nt", reason="Windows handle pool")
def test_active_reader_survives_eviction_and_then_closes(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_MAX_READERS", 1)
    first, second = tmp_path / "a", tmp_path / "b"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    with probe.read_probe_scope(), probe.open_probe_reader(first) as reader:
        raw = reader.raw
        with probe.open_probe_reader(second) as other:
            assert other.read() == b"two"
        assert not raw.closed
        assert reader.read() == b"one"
        assert len(probe._pool.get()[1]) == 1
    assert raw.closed


def test_concurrent_positions_and_directory_removal(tmp_path):
    directory = tmp_path / "session"
    directory.mkdir()
    path = directory / "events.jsonl"
    path.write_bytes(b"0123456789" * 1000)
    errors = []
    def read(offset):
        try:
            for _ in range(20):
                with probe.open_probe_reader(path) as reader:
                    reader.seek(offset)
                    assert reader.read(4) == b"0123456789"[offset % 10:offset % 10 + 4]
        except BaseException as exc:
            errors.append(exc)
    workers = [threading.Thread(target=read, args=(n,)) for n in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(5)
    assert not errors
    assert all(not worker.is_alive() for worker in workers)
    shutil.rmtree(directory)
    assert not directory.exists()


def test_buffered_suffix_matches_streaming_cursor_and_partial_line_behavior(tmp_path):
    log = SessionEventLog(tmp_path)
    log.append("s", "model_user", {"content": "中文"})
    start = log.event_path("s").stat().st_size
    log.append("s", "model_assistant", {"content": "answer"})
    end = log.event_path("s").stat().st_size
    with log.event_path("s").open("ab") as file:
        file.write(b'{"seq":3')
    regular, buffered = {}, {}
    a = list(log.iter_from_offset("s", start, end_offset=end, read_metadata=regular))
    b = list(log.iter_from_offset("s", start, end_offset=end, read_metadata=buffered, buffer_suffix=True))
    assert [x.to_dict() for x in a] == [x.to_dict() for x in b]
    assert regular == buffered
    assert buffered["byte_offset"] == end
    assert len(list(log.iter_from_offset("s", start, end_offset=end + 8, buffer_suffix=True))) == 1


def test_nested_transaction_owns_one_os_lock_and_closes_readers_before_unlock(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    entered, released = [], []
    original_lock, original_unlock = log._lock_file, log._unlock_file
    def lock(*a, **k):
        entered.append(True)
        return original_lock(*a, **k)
    def unlock(*a, **k):
        assert raw.closed
        released.append(True)
        return original_unlock(*a, **k)
    monkeypatch.setattr(log, "_lock_file", lock)
    monkeypatch.setattr(log, "_unlock_file", unlock)
    with log.session_transaction("s", timeout_seconds=0.1), probe.read_probe_scope():
        log.append("s", "model_user", {"content": "one"})
        with probe.open_probe_reader(log.event_path("s")) as reader:
            raw = reader.raw
        context = copy_context()
        assert not raw.closed if os.name == "nt" else raw.closed
    assert len(entered) == len(released) == 1
    # A saved context after scope exit cannot bypass lock acquisition or retain
    # fresh readers as if the old transaction were still open.
    monkeypatch.setattr(log, "_unlock_file", original_unlock)
    context.run(log.append, "s", "model_assistant", {"content": "two"})
    assert len(entered) == 2


def test_inherited_context_in_another_async_task_does_not_own_parent_lock(tmp_path):
    from runtime_v2.event_log import RuntimeEventLogBusyError
    log = SessionEventLog(tmp_path)
    async def child():
        with pytest.raises(RuntimeEventLogBusyError):
            with log.session_transaction("s", timeout_seconds=0.02):
                pytest.fail("child inherited its parent's file lock")
    async def parent():
        with log.session_transaction("s", timeout_seconds=0.1):
            await asyncio.create_task(child())
    asyncio.run(parent())


def test_ordinary_maintenance_transaction_does_not_pin_its_source(tmp_path):
    log = SessionEventLog(tmp_path)
    with log.session_transaction("s", timeout_seconds=0.1):
        log.append("s", "model_user", {"content": "before"})
        path = log.event_path("s")
        with probe.open_probe_reader(path) as reader:
            raw = reader.raw
            reader.read(1)
        assert raw.closed
        replacement = path.with_name("replacement")
        replacement.write_bytes(path.read_bytes())
        os.replace(replacement, path)
    assert log.read_all("s")[0].payload["content"] == "before"
