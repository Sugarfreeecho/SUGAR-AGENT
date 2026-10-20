"""Assign readable hook IDs without changing their execution identities."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from typing import Iterable

from .models import HookDefinition

try:
    from resource_naming import allocate_resource_names
except ImportError:  # package-style imports
    from ..resource_naming import allocate_resource_names


def name_hook_definitions(definitions: Iterable[HookDefinition]) -> tuple[HookDefinition, ...]:
    rows = tuple(definitions)
    project_counts = Counter((row.local_id or row.id) for row in rows if not row.plugin_id)
    reserved = {name for name, count in project_counts.items() if count == 1}
    candidates = {}
    keys = []
    for row in rows:
        local_id = row.local_id or row.id
        key = json.dumps([row.source_id, row.plugin_id, row.event, row.execution_id])
        keys.append(key)
        if not row.plugin_id and local_id in reserved:
            continue
        owner = row.plugin_id or "project"
        source = row.source_id.rsplit(":", 1)[-1]
        candidates[key] = (local_id, f"{owner}:{local_id}", f"{owner}:{row.event}:{local_id}",
                           f"{owner}:{source}:{row.event}:{local_id}")
    names = allocate_resource_names(candidates, reserved=reserved)
    return tuple(replace(row, id=names.get(key, row.local_id or row.id),
                         local_id=row.local_id or row.id, source_hook_id=row.execution_id)
                 for row, key in zip(rows, keys))
