"""Transaction-scoped Windows handles for short fact validation probes.

No bytes, signatures or validation results are cached. Each borrower gets a
fresh buffer and rechecks file identity. Streaming iterators must keep their own
handles: they can yield while other operations change the file position.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import io
import os
from pathlib import Path
import threading

_MAX_READERS = 32
_guard = threading.Lock()
_pool = ContextVar("event_probe_readers", default=None)


def probe_owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return threading.get_ident(), task


@contextmanager
def read_probe_scope():
    """Retain readers only while the owning event transaction is locked."""
    current = _pool.get()
    if current is not None and current[2][0] and current[0] == probe_owner():
        yield
        return
    lease = [True]
    token = _pool.set((probe_owner(), OrderedDict(), lease))
    try:
        yield
    finally:
        try:
            close_probe_readers()
        finally:
            lease[0] = False
            _pool.reset(token)


class _Reader:
    def __init__(self):
        self.lock = threading.Lock()
        self.raw = None
        self.retired = False

    def close(self):
        if self.raw is not None:
            self.raw.close()
            self.raw = None


@lru_cache(maxsize=1)
def _windows_api():
    import ctypes
    from ctypes import wintypes
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    create = library.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = library.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    return create, close


def _open_shared_read(path):
    import ctypes
    import msvcrt
    create, close = _windows_api()
    name = os.path.abspath(path)
    if len(name) >= 260 and not name.startswith("\\\\?\\"):
        name = "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
    # Request permissive sharing, but Windows replacement can still reject an
    # open destination. The outer transaction closes these before unlocking;
    # never retain them across idle periods or independent commits.
    handle = create(name, 0x80000000, 1 | 2 | 4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
    except BaseException:
        close(handle)
        raise
    try:
        return os.fdopen(descriptor, "rb", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


def _identity(stat):
    return stat.st_dev, stat.st_ino


def _retire(reader):
    reader.retired = True
    if reader.lock.acquire(blocking=False):
        try:
            reader.close()
        finally:
            reader.lock.release()
    # An active borrower closes it on exit; never close underneath its read.


def close_probe_readers():
    current = _pool.get()
    if current is None or not current[2][0] or current[0] != probe_owner():
        return
    readers = current[1]
    with _guard:
        entries = list(readers.values())
        readers.clear()
    for reader in entries:
        _retire(reader)


@contextmanager
def open_probe_reader(path: Path):
    if os.name != "nt":
        with path.open("rb") as file:
            yield file
        return
    key = os.path.normcase(os.path.abspath(path))
    retired = []
    current = _pool.get()
    if current is not None and current[2][0] and current[0] == probe_owner():
        readers = current[1]
        with _guard:
            reader = readers.pop(key, None) or _Reader()
            readers[key] = reader
            while len(readers) > _MAX_READERS:
                retired.append(readers.popitem(last=False)[1])
    else:
        reader = _Reader()
        reader.retired = True
    for old in retired:
        _retire(old)
    with reader.lock:
        try:
            current = path.stat()
            if (reader.raw is None or reader.raw.closed
                    or not current.st_ino
                    or _identity(os.fstat(reader.raw.fileno())) != _identity(current)):
                reader.close()
                reader.raw = _open_shared_read(path)
            # Recheck the named path after opening/acquiring the cached handle,
            # including replacement while waiting for another borrower.
            if _identity(os.fstat(reader.raw.fileno())) != _identity(path.stat()):
                reader.close()
                raise ValueError("event source changed while opening a read probe")
            reader.raw.seek(0)
            buffered = io.BufferedReader(reader.raw)
            try:
                yield buffered
            finally:
                if not buffered.closed:
                    buffered.detach()  # Discard read-ahead; never retain bytes across probes.
        except BaseException:
            reader.close()
            raise
        finally:
            if reader.retired:
                reader.close()
