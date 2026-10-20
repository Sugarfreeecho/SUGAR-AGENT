"""Allocate short model tool names while keeping source identities separate."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


_UNSAFE = re.compile(r"[^a-zA-Z0-9_-]+")
_MAX_NAME = 64


def _safe_name(value: str) -> str:
    name = _UNSAFE.sub("_", value).strip("_") or "tool"
    if len(name) > _MAX_NAME:
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:10]
        name = f"{name[:_MAX_NAME - 11]}_{digest}"
    return name


@dataclass(frozen=True)
class ToolNameSource:
    source_name: str
    local_name: str
    plugin_id: str = ""
    server_name: str = ""

    def candidates(self) -> tuple[str, ...]:
        parts = [self.local_name]
        names = [_safe_name(self.local_name)]
        if self.plugin_id:
            parts.insert(0, self.plugin_id)
            names.append(_safe_name("__".join(parts)))
        if self.server_name:
            parts.insert(1 if self.plugin_id else 0, self.server_name)
            names.append(_safe_name("__".join(parts)))
        return tuple(dict.fromkeys(names))


def allocate_tool_names(
    sources: Iterable[ToolNameSource], *, reserved: Iterable[str] = ()
) -> dict[str, str]:
    """Qualify every conflicting name, independent of registration order."""
    rows = {source.source_name: source for source in sources}
    identity_counts = Counter((row.plugin_id, row.server_name, row.local_name) for row in rows.values())
    candidates = {key: row.candidates() for key, row in rows.items()}
    levels = dict.fromkeys(rows, 0)
    reserved_names = frozenset(reserved)
    while True:
        names = {}
        for key, choices in candidates.items():
            level = levels[key]
            if level < len(choices):
                names[key] = choices[level]
            else:
                # Normalization can collapse distinct plugin/server names.
                row = rows[key]
                source_identity = (row.plugin_id, row.server_name, row.local_name)
                identity = json.dumps([*source_identity, level, key if identity_counts[source_identity] > 1 else ""])
                digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
                names[key] = f"{choices[-1][:_MAX_NAME - 11]}_{digest}"
        counts = Counter(names.values())
        conflicts = [key for key, name in names.items()
                     if name in reserved_names or counts[name] > 1]
        if not conflicts:
            return names
        for key in conflicts:
            levels[key] += 1
