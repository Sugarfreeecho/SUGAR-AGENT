"""Validation and atomic publication for rebuildable event-log derivatives."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path


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


def source_boundary(path: Path, offset: int) -> dict:
    """Capture cheap append guards; callers capture under their state lock.

    Event writers append or atomically replace logs. The complete prefix hash
    additionally verifies a persisted derivative on its first use in a process.
    """
    stat = path.stat()
    offset = int(offset)
    if offset < 0 or offset > stat.st_size:
        raise ValueError("invalid event boundary")
    with path.open("rb") as fh:
        opened_stat = os.fstat(fh.fileno())
        if file_identity(opened_stat) != file_identity(stat):
            raise ValueError("event source changed while opening its boundary")
        head = fh.read(min(4096, offset))
        fh.seek(max(0, offset - 4096))
        tail = fh.read(min(4096, offset))
    if offset and not tail.endswith(b"\n"):
        raise ValueError("event boundary is not a complete fact")
    return {"identity": file_identity(stat), "offset": offset,
            "mtime_ns": int(stat.st_mtime_ns), "size": int(stat.st_size),
            "head": hashlib.sha256(head).hexdigest(),
            "tail": hashlib.sha256(tail).hexdigest()}


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


