# -*- coding: utf-8 -*-
"""Parse and validate plugin tray declarations (``capabilities.ui.tray``).

This module is the single source of truth for the tray manifest shape. It is
deliberately dependency-free so it can be imported from three very different
places:

* ``app/plugins/loader.py``  - compatibility warnings shown in the plugin list
* ``app/plugins/ui.py``      - the ``tray`` UI slot projection
* ``app/tray_plugins.py``    - the tray process, which never loads the plugin
  runtime (that would drag in the whole manager/runtime stack)

Manifest shape::

    "capabilities": {"ui": {"tray": [
        {"id": "shield", "label": "\u62a4\u5c4f\u6a21\u5f0f",
         "command": ["{pythonw}", "scripts/mode.py", "set", "shield"],
         "windowless": true,
         "check": {"file": "{state}/power-mode.json", "key": "mode", "equals": "shield"}},
        {"id": "power", "label": "\u7535\u6e90\u6a21\u5f0f", "items": [ ...actions... ]}
    ]}}

Paths are *not* resolved here: containment is a runtime concern of the tray
(``tray_plugins.TrayAction``), because it depends on the plugin root and the
caller's placeholders.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

MAX_TRAY_ROWS = 8
MAX_GROUP_ITEMS = 8
MAX_LABEL_CHARS = 40
MAX_DESCRIPTION_CHARS = 200
MAX_COMMAND_TOKENS = 16
MAX_TOKEN_CHARS = 1024

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


def _warning(row_id: str, message: str) -> str:
    if row_id:
        return f"Tray entry {row_id!r}: {message}"
    return f"Tray entry: {message}"


def _normalise_check(raw: Any, row_id: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    if raw is None:
        return None, warnings
    if not isinstance(raw, Mapping):
        warnings.append(_warning(row_id, "check must be an object; ignoring it"))
        return None, warnings
    file_value = raw.get("file")
    if not isinstance(file_value, str) or not file_value.strip():
        warnings.append(_warning(row_id, "check.file is required; ignoring check"))
        return None, warnings
    spec: Dict[str, Any] = {"file": file_value.strip()}
    key = raw.get("key")
    if key is not None:
        if not isinstance(key, str) or not key.strip():
            warnings.append(_warning(row_id, "check.key must be a non-empty string; ignoring it"))
        else:
            spec["key"] = key.strip()
    if "equals" in raw:
        expected = raw["equals"]
        if isinstance(expected, (str, int, float, bool)):
            spec["equals"] = expected
        else:
            warnings.append(_warning(row_id, "check.equals must be a scalar; ignoring it"))
    return spec, warnings


def _normalise_action(raw: Mapping[str, Any], *, context: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    row_id = str(raw.get("id") or "").strip()
    label = str(raw.get("label") or "").strip()
    if not _ID_RE.fullmatch(row_id):
        warnings.append(_warning(row_id, f"id is invalid in {context}"))
        return None, warnings
    if not label or len(label) > MAX_LABEL_CHARS:
        warnings.append(_warning(row_id, f"label must be 1-{MAX_LABEL_CHARS} characters"))
        return None, warnings
    command = raw.get("command")
    if not isinstance(command, list) or not command or len(command) > MAX_COMMAND_TOKENS:
        warnings.append(_warning(row_id, f"command must be a list of 1-{MAX_COMMAND_TOKENS} tokens"))
        return None, warnings
    tokens: List[str] = []
    for token in command:
        if not isinstance(token, str) or not token.strip() or len(token) > MAX_TOKEN_CHARS:
            warnings.append(_warning(row_id, "command tokens must be non-empty strings"))
            return None, warnings
        tokens.append(token.strip())
    check, check_warnings = _normalise_check(raw.get("check"), row_id)
    warnings.extend(check_warnings)
    description = str(raw.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS]
    return {
        "kind": "action",
        "id": row_id,
        "label": label,
        "description": description,
        "command": tokens,
        "windowless": bool(raw.get("windowless", True)),
        "check": check,
    }, warnings


def _normalise_group(raw: Mapping[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    row_id = str(raw.get("id") or "").strip()
    label = str(raw.get("label") or "").strip()
    if not _ID_RE.fullmatch(row_id):
        warnings.append(_warning(row_id, "group id is invalid"))
        return None, warnings
    if not label or len(label) > MAX_LABEL_CHARS:
        warnings.append(_warning(row_id, f"group label must be 1-{MAX_LABEL_CHARS} characters"))
        return None, warnings
    items = raw.get("items")
    if not isinstance(items, list) or not items:
        warnings.append(_warning(row_id, "group items must be a non-empty list"))
        return None, warnings
    children: List[Dict[str, Any]] = []
    for index, child in enumerate(items):
        if index >= MAX_GROUP_ITEMS:
            warnings.append(_warning(row_id, f"only the first {MAX_GROUP_ITEMS} items are kept"))
            break
        if not isinstance(child, Mapping):
            warnings.append(_warning(row_id, "group items must be objects"))
            continue
        if isinstance(child.get("items"), list):
            warnings.append(_warning(row_id, "nested tray groups are not supported"))
            continue
        action, action_warnings = _normalise_action(child, context=f"group {row_id!r}")
        warnings.extend(action_warnings)
        if action is not None:
            children.append(action)
    if not children:
        return None, warnings
    return {
        "kind": "group",
        "id": row_id,
        "label": label,
        "description": str(raw.get("description") or "").strip()[:MAX_DESCRIPTION_CHARS],
        "items": children,
    }, warnings


def parse_tray_rows(raw: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return ``(normalised_rows, warnings)`` for one plugin's tray declaration."""

    warnings: List[str] = []
    if raw is None:
        return [], warnings
    if isinstance(raw, Mapping):
        rows: Sequence[Any] = (raw,)
    elif isinstance(raw, list):
        rows = raw
    else:
        return [], ["Tray declaration must be a list of entries; ignoring it"]

    parsed: List[Dict[str, Any]] = []
    leaves = 0
    for index, row in enumerate(rows):
        if index >= MAX_TRAY_ROWS:
            warnings.append(f"Only the first {MAX_TRAY_ROWS} tray entries are kept")
            break
        if not isinstance(row, Mapping):
            warnings.append("Tray entries must be objects; ignoring one of them")
            continue
        if isinstance(row.get("items"), list):
            entry, entry_warnings = _normalise_group(row)
        else:
            entry, entry_warnings = _normalise_action(row, context="tray")
        warnings.extend(entry_warnings)
        if entry is None:
            continue
        cost = len(entry["items"]) if entry["kind"] == "group" else 1
        if leaves + cost > MAX_TRAY_ROWS:
            warnings.append("Tray entries exceed the total limit; the rest is ignored")
            break
        leaves += cost
        parsed.append(entry)
    return parsed, warnings


def iter_actions(rows: Sequence[Mapping[str, Any]]):
    """Yield every action row, flattening groups."""

    for row in rows:
        if row.get("kind") == "group":
            yield from row.get("items") or ()
        else:
            yield row


def validate_tray_slots(raw: Any) -> List[str]:
    """Warnings-only helper for callers that just need manifest diagnostics."""

    return parse_tray_rows(raw)[1]


__all__ = [
    "MAX_GROUP_ITEMS",
    "MAX_LABEL_CHARS",
    "MAX_TRAY_ROWS",
    "iter_actions",
    "parse_tray_rows",
    "validate_tray_slots",
]
