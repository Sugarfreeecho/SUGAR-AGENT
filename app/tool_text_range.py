"""Sparse text cookies avoid rereading the prefix on successive range reads."""
from bisect import bisect_right
from collections import OrderedDict
from pathlib import Path
import threading

from file_read_signature import signature, stat_signature


_cache = OrderedDict()
_lock = threading.Lock()
_STRIDE = 128
_MAX_FILES = 128


def read_range(path: Path, start: int, end: int, *, width: int = 1000):
    key = (str(path), width)
    selected = []
    with path.open('r', encoding='utf-8', errors='replace') as stream:
        stamp = signature(stream)
        with _lock:
            cached = _cache.get(key) if stamp is not None else None
            if cached and cached[0] == stamp:
                _cache.move_to_end(key)
            else:
                cached = None
        if cached:
            _stamp, total, checkpoints = cached
            pos = bisect_right(checkpoints, (start, float('inf'))) - 1
            first, cookie = checkpoints[max(0, pos)]
            stream.seek(cookie)
            number = first - 1
        else:
            total = None
            checkpoints = [(1, 0)]
            number = 0
        physical_count = 0
        while True:
            if cached and number >= end:
                break
            if not cached and physical_count and physical_count % _STRIDE == 0:
                checkpoints.append((number + 1, stream.tell()))
            physical = stream.readline()
            if not physical:
                break
            physical_count += 1
            has_newline = physical.endswith('\n')
            body = physical[:-1] if has_newline else physical
            count = max(1, (len(body) + width - 1) // width)
            # Virtualize only the lines being returned; the rest only need a count.
            for index in range(max(0, start - number - 1), min(count, end - number)):
                chunk = body[index * width:(index + 1) * width]
                if index + 1 < count or has_newline:
                    chunk += '\n'
                selected.append(chunk)
            number += count
        if total is None:
            total = number
        final = signature(stream)
        same_source = (stamp is not None and stamp == final
                       and stat_signature(path.stat()) == stamp[:5])
        if not cached and same_source:
            with _lock:
                _cache[key] = (stamp, total, checkpoints)
                _cache.move_to_end(key)
                while len(_cache) > _MAX_FILES:
                    _cache.popitem(last=False)
        return total, selected, same_source
