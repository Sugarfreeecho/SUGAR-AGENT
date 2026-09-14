"""Per-key thread and process coordination for local attachment files."""
import hashlib
import os
import threading
import time
from contextlib import contextmanager
from weakref import WeakValueDictionary

from .errors import AttachmentError

_locks = WeakValueDictionary()
_guard = threading.Lock()
_held = threading.local()


@contextmanager
def attachment_lock(directory, key, timeout=30):
    name = hashlib.sha256(str(key).encode()).hexdigest()
    lock_path = directory / ".locks" / name
    identity = str(lock_path)
    with _guard:
        lock = _locks.get(identity)
        if lock is None:
            lock = threading.RLock()
            _locks[identity] = lock
    with lock:
        held = getattr(_held, "keys", set())
        if identity in held:
            yield
            return
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + timeout
            while True:
                handle.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise AttachmentError("Attachment lock timed out", "ATTACHMENT_BUSY") from None
                    time.sleep(0.025)
            try:
                _held.keys = held | {identity}
                yield
            finally:
                _held.keys = held
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
