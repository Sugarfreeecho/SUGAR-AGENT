from contextvars import copy_context
import os
from pathlib import Path
import threading

import pytest

from runtime_v2.event_log import SessionEventLog
from runtime_v2 import write_probe


def test_batch_reuses_writer_and_closes_before_transaction_unlock(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    path = log.event_path("s")
    opens = []
    original, unlock = Path.open, log._unlock_file
    def opened(self, mode="r", *a, **k):
        if self == path and mode == "a":
            opens.append(True)
        return original(self, mode, *a, **k)
    def unlocked(*a, **k):
        assert writer.closed
        return unlock(*a, **k)
    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(log, "_unlock_file", unlocked)
    with log.session_transaction("s"), write_probe.batch_append_scope(path):
        for index in range(4):
            log.append("s", "model_tool", {"content": str(index)})
            assert len(log.read_all("s")) == index + 1  # Every fact was flushed.
        writer = write_probe._writer.get()["file"]
        assert not writer.closed
    assert opens == [True]
    assert writer.closed
    replacement = path.with_suffix(".new")
    replacement.write_bytes(path.read_bytes())
    os.replace(replacement, path)
    assert len(log.read_all("s")) == 4


def test_error_and_copied_expired_scope_do_not_retain_writer(tmp_path):
    path = tmp_path / "events.jsonl"
    with pytest.raises(ValueError, match="stop"):
        with write_probe.batch_append_scope(path):
            with write_probe.open_append_writer(path) as writer:
                writer.write("before\n")
                writer.flush()
            context = copy_context()
            raise ValueError("stop")
    assert writer.closed
    def later():
        with write_probe.open_append_writer(path) as fresh:
            assert fresh is not writer
            fresh.write("after\n")
        assert fresh.closed
    context.run(later)
    assert path.read_text() == "before\nafter\n"


def test_another_thread_cannot_borrow_parent_append_handle(tmp_path):
    path = tmp_path / "events.jsonl"
    with write_probe.batch_append_scope(path):
        with write_probe.open_append_writer(path) as parent:
            parent.write("parent\n")
            parent.flush()
        context = copy_context()
        errors = []
        def child():
            try:
                with write_probe.open_append_writer(path) as own:
                    assert own is not parent
                    own.write("child\n")
                assert own.closed
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=lambda: context.run(child))
        thread.start()
        thread.join(3)
        assert not thread.is_alive() and not errors
        assert not parent.closed
    assert parent.closed
