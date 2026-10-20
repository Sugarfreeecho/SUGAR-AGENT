"""One append handle for an explicit synchronous, already locked result batch."""
from contextlib import contextmanager
from contextvars import ContextVar
import os

from .read_probe import probe_owner

_writer = ContextVar("runtime_batch_append_writer", default=None)


def _key(path):
    return os.path.normcase(os.path.abspath(path))


@contextmanager
def batch_append_scope(path):
    """Close before the outer fact transaction unlocks; never span an await."""
    current = _writer.get()
    key, owner = _key(path), probe_owner()
    if current is not None and current["active"] and current["owner"] == owner and current["key"] == key:
        yield
        return
    state = {"key": key, "owner": owner, "active": True, "file": None}
    token = _writer.set(state)
    try:
        yield
    finally:
        state["active"] = False
        try:
            if state["file"] is not None:
                state["file"].close()
        finally:
            _writer.reset(token)


@contextmanager
def open_append_writer(path):
    state = _writer.get()
    if (state is None or not state["active"] or state["owner"] != probe_owner()
            or state["key"] != _key(path)):
        with path.open("a", encoding="utf8", newline="\n") as file:
            yield file
        return
    if state["file"] is None:
        state["file"] = path.open("a", encoding="utf8", newline="\n")
    file = state["file"]
    named, opened = path.stat(), os.fstat(file.fileno())
    if not opened.st_ino:
        file.close()
        state["file"] = None
        with path.open("a", encoding="utf8", newline="\n") as ordinary:
            yield ordinary
        return
    if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
        raise ValueError("batch event source changed while its transaction was locked")
    # The caller still flushes every fact before publishing its receipt. Only
    # the open/close operation is shared, with no data buffered across facts.
    yield file
