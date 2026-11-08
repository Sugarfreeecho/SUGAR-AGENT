"""Minimal JSON Pointer / JSON Patch helpers shared by Runtime V2 writers.

Two writers need the same semantics:

* ``ExtensionStateStore`` diffs a whole namespace value into a patch so a
  high-frequency counter does not rewrite its full array on every event.
* ``RuntimeProjector`` replays those patches when rebuilding a snapshot.

Keeping one implementation avoids the projector and the writer drifting apart
on pointer escaping or list handling.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable, List


class PatchError(ValueError):
    """Raised when a patch cannot be applied to the given document."""


def escape_token(token: Any) -> str:
    return str(token).replace("~", "~0").replace("/", "~1")


def unescape_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _split_pointer(path: str) -> List[str]:
    if path == "":
        return []
    if not path.startswith("/"):
        raise PatchError(f"patch path must be a JSON Pointer: {path}")
    return [unescape_token(part) for part in path[1:].split("/")]


def apply_operation(document: Any, operation: dict) -> Any:
    """Apply one RFC 6902 operation and return the new document."""
    if not isinstance(operation, dict):
        raise PatchError("patch operation must be an object")
    op = str(operation.get("op") or "").strip().lower()
    path = str(operation.get("path") or "")
    if op not in {"add", "replace", "remove"}:
        raise PatchError(f"unsupported patch operation: {op}")
    tokens = _split_pointer(path)
    if not tokens:
        if op == "remove":
            return None
        if "value" not in operation:
            raise PatchError(f"{op} requires value")
        return copy.deepcopy(operation.get("value"))
    root = copy.deepcopy(document)
    parent = root
    for token in tokens[:-1]:
        if isinstance(parent, dict) and token in parent:
            parent = parent[token]
        elif isinstance(parent, list):
            try:
                parent = parent[int(token)]
            except (ValueError, IndexError) as exc:
                raise PatchError(f"patch path does not exist: {path}") from exc
        else:
            raise PatchError(f"patch path does not exist: {path}")
    leaf = tokens[-1]
    if isinstance(parent, dict):
        exists = leaf in parent
        if op in {"replace", "remove"} and not exists:
            raise PatchError(f"patch path does not exist: {path}")
        if op == "remove":
            parent.pop(leaf)
        else:
            if "value" not in operation:
                raise PatchError(f"{op} requires value")
            parent[leaf] = copy.deepcopy(operation.get("value"))
        return root
    if isinstance(parent, list):
        if leaf == "-" and op == "add":
            parent.append(copy.deepcopy(operation.get("value")))
            return root
        try:
            index = int(leaf)
        except ValueError as exc:
            raise PatchError(f"invalid list index in patch path: {path}") from exc
        if op == "add":
            if index < 0 or index > len(parent):
                raise PatchError(f"patch path does not exist: {path}")
            parent.insert(index, copy.deepcopy(operation.get("value")))
        elif 0 <= index < len(parent):
            if op == "remove":
                parent.pop(index)
            else:
                parent[index] = copy.deepcopy(operation.get("value"))
        else:
            raise PatchError(f"patch path does not exist: {path}")
        return root
    raise PatchError(f"patch parent is not a container: {path}")


def apply_patch(document: Any, operations: Iterable[dict]) -> Any:
    value = document
    for operation in list(operations or []):
        value = apply_operation(value, operation)
    return value


def _is_append_only(before: Any, after: Any) -> bool:
    """True when ``after`` is ``before`` plus items appended at the end."""
    if not isinstance(before, list) or not isinstance(after, list):
        return False
    if len(after) < len(before):
        return False
    return after[:len(before)] == before


def _is_trimmed_prefix(before: Any, after: Any) -> bool:
    """True when ``after`` is a contiguous tail slice of ``before``."""
    if not isinstance(before, list) or not isinstance(after, list):
        return False
    if not after or len(after) >= len(before):
        return False
    return before[-len(after):] == after


def top_level_patch(before: Any, after: Any) -> List[dict]:
    """Diff two namespace values into top-level operations.

    Appended list items become ``add`` operations with a ``/-`` pointer so an
    append-only counter (goal usage ids, run ids, ...) costs one small
    operation instead of the whole array. A rolling window that drops old
    items keeps the compact ``replace`` form: the caller's array is bounded,
    and a replace is easier to reason about than a remove/add pair.
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        return [{"op": "replace", "path": "", "value": copy.deepcopy(after)}]
    operations: List[dict] = []
    for key in sorted(set(before) - set(after)):
        operations.append({"op": "remove", "path": f"/{escape_token(key)}"})
    for key in sorted(after):
        if key in before and before.get(key) == after.get(key):
            continue
        old = before.get(key)
        new = after.get(key)
        if key in before and _is_append_only(old, new):
            path = f"/{escape_token(key)}"
            for item in new[len(old):]:
                operations.append({"op": "add", "path": f"{path}/-", "value": copy.deepcopy(item)})
            continue
        operations.append(
            {
                "op": "replace" if key in before else "add",
                "path": f"/{escape_token(key)}",
                "value": copy.deepcopy(new),
            }
        )
    return operations


__all__ = [
    "PatchError",
    "apply_operation",
    "apply_patch",
    "escape_token",
    "top_level_patch",
    "unescape_token",
]
