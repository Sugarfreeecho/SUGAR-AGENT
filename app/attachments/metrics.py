"""Bounded, payload-free attachment stage counters."""
import threading
import time
from collections import Counter
from contextlib import contextmanager

_guard = threading.Lock()
_counts = Counter()
_duration = Counter()


def count(event, amount=1):
    with _guard:
        _counts[event] += amount


def duration(stage, seconds):
    with _guard:
        _duration[stage] += seconds


@contextmanager
def measure(stage):
    started = time.monotonic()
    try:
        yield
    except Exception:
        count(stage + ".failed")
        raise
    else:
        count(stage + ".completed")
    finally:
        with _guard:
            _duration[stage] += time.monotonic() - started


def snapshot():
    with _guard:
        return {"counts": dict(_counts), "totalSeconds": dict(_duration)}
