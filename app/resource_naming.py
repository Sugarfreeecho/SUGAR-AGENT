"""Choose the shortest unambiguous names for instruction and hook catalogs."""
from __future__ import annotations

import hashlib
from collections import Counter
from typing import Iterable, Mapping


def allocate_resource_names(
    candidates: Mapping[str, Iterable[str]], *, reserved: Iterable[str] = ()
) -> dict[str, str]:
    choices = {key: tuple(dict.fromkeys(names)) for key, names in candidates.items()}
    if any(not names or any(not name for name in names) for names in choices.values()):
        raise ValueError("Resource names must be non-empty")
    levels = dict.fromkeys(choices, 0)
    reserved = frozenset(reserved)
    while True:
        names = {}
        for key, options in choices.items():
            level = levels[key]
            if level < len(options):
                names[key] = options[level]
            else:
                digest = hashlib.sha256(f"{key}:{level}".encode("utf-8")).hexdigest()[:10]
                names[key] = f"{options[-1]}:{digest}"
        counts = Counter(names.values())
        conflicts = [key for key, name in names.items() if name in reserved or counts[name] > 1]
        if not conflicts:
            return names
        for key in conflicts:
            levels[key] += 1
