"""Validation and atomic publication for rebuildable event-log derivatives."""
from __future__ import annotations

import hashlib
import os
import sys
from typing import NamedTuple
from pathlib import Path
from .read_probe import open_probe_reader


def estimate_bytes(value) -> int:
    """Estimate retained Python objects once when publishing a cache entry."""
    seen = set()
    def visit(item):
        identity = id(item)
        if identity in seen:
            return 0
        seen.add(identity)
        size = sys.getsizeof(item)
        if isinstance(item, dict):
            size += sum(visit(key) + visit(val) for key, val in item.items())
        elif isinstance(item, (list, tuple)):
            size += sum(visit(val) for val in item)
        return size
    return visit(value)


def file_identity(stat) -> list[int]:
    return [int(stat.st_dev), int(stat.st_ino)]


def prefix_digest(path: Path, offset: int) -> str:
    digest = hashlib.sha256()
    remaining = int(offset)
    with path.open("rb") as fh:
        while remaining:
            chunk = fh.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("event prefix was truncated")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


class SourceWindow(NamedTuple):
    """At most 8 KiB of validated boundary bytes for our next owned append."""
    identity: tuple[int, int]
    offset: int
    mtime_ns: int
    size: int
    head: bytes
    tail: bytes

    def boundary(self) -> dict:
        return {"identity": list(self.identity), "offset": self.offset,
                "mtime_ns": self.mtime_ns, "size": self.size,
                "head": hashlib.sha256(self.head).hexdigest(),
                "tail": hashlib.sha256(self.tail).hexdigest()}


def source_boundary_window(path: Path, offset: int) -> tuple[dict, SourceWindow]:
    """Capture cheap append guards; callers capture under their state lock.

    Event writers append or atomically replace logs. The complete prefix hash
    additionally verifies a persisted derivative on its first use in a process.
    """
    stat = path.stat()
    offset = int(offset)
    if offset < 0 or offset > stat.st_size:
        raise ValueError("invalid event boundary")
    with open_probe_reader(path) as fh:
        opened_stat = os.fstat(fh.fileno())
        if file_identity(opened_stat) != file_identity(stat):
            raise ValueError("event source changed while opening its boundary")
        head = fh.read(min(4096, offset))
        fh.seek(max(0, offset - 4096))
        tail = fh.read(min(4096, offset))
    if offset and not tail.endswith(b"\n"):
        raise ValueError("event boundary is not a complete fact")
    window = SourceWindow(tuple(file_identity(stat)), offset, int(stat.st_mtime_ns),
                          int(stat.st_size), head, tail)
    return window.boundary(), window


def source_boundary(path: Path, offset: int) -> dict:
    return source_boundary_window(path, offset)[0]


def extend_source_window(source, window, receipt, current_stat):
    """Derive the same guard from bytes the locked writer actually appended.

    No read-validation verdict is reused for an external append. Any mismatch
    in the prior guard, writer identity, length or final named file falls back
    to the normal disk boundary read at the caller. Checkpoints still validate
    and hash the real prefix independently before publication and on load.
    """
    if not isinstance(window, SourceWindow) or not isinstance(source, dict):
        return None
    if window.boundary() != {key: source.get(key) for key in
                             ("identity", "offset", "mtime_ns", "size", "head", "tail")}:
        return None
    before, after, encoded = receipt.get("before"), receipt.get("after"), receipt.get("encoded")
    if before is None or after is None or not isinstance(encoded, bytes) or not encoded.endswith(b"\n"):
        return None
    if (not before.st_ino or window.identity != tuple(file_identity(before))
            or window.identity != tuple(file_identity(after))
            or window.identity != tuple(file_identity(current_stat))
            or window.offset != window.size or window.size != before.st_size
            or window.mtime_ns != before.st_mtime_ns
            or before.st_size + len(encoded) != after.st_size
            or after.st_size != current_stat.st_size
            or after.st_mtime_ns != current_stat.st_mtime_ns):
        return None
    head = window.head if len(window.head) == 4096 else window.head + encoded[:4096 - len(window.head)]
    tail = encoded[-4096:] if len(encoded) >= 4096 else (window.tail + encoded)[-4096:]
    updated = SourceWindow(window.identity, current_stat.st_size, current_stat.st_mtime_ns,
                           current_stat.st_size, head, tail)
    return updated.boundary(), updated


def source_matches(path: Path, source: dict, *, full: bool = False) -> bool:
    try:
        current = source_boundary(path, int(source["offset"]))
        if any(current[key] != source[key] for key in ("identity", "offset", "head", "tail")):
            return False
        # Equal-size changes cannot be an append. Never trust a repaired log.
        if current["size"] == source["size"] and current["mtime_ns"] != source["mtime_ns"]:
            return False
        if current["size"] < source["size"]:
            return False
        return not full or prefix_digest(path, source["offset"]) == source["sha256"]
    except (OSError, KeyError, TypeError, ValueError, OverflowError):
        return False


def seal_source(path: Path, source: dict) -> dict:
    if not source_matches(path, source):
        raise ValueError("event source changed before publication")
    sealed = {**source, "sha256": prefix_digest(path, source["offset"])}
    if not source_matches(path, sealed):
        raise ValueError("event source changed during publication")
    return sealed


