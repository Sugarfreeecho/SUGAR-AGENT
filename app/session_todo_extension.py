"""Compatibility bridge while Todo migrates to generic extension state."""
from __future__ import annotations

from typing import Any, Iterable

from runtime_v2 import SessionExtensionStateStore


TODO_EXTENSION_ID = "session-todo"
TODO_NAMESPACE = "plan"


def _sessions_root(session_manager: Any):
    repository = getattr(session_manager, "repository", None)
    return getattr(repository, "sessions_dir", None) or session_manager.sessions_dir


def _path_resolver(session_manager: Any):
    repository = getattr(session_manager, "repository", None)
    if repository is not None:
        return getattr(repository, "_path_resolver", None)
    return getattr(session_manager, "_resolve_session_path", None)


def todo_extension_value(items: Iterable[dict], *, cleared: bool = False) -> dict:
    rows = [
        {
            "id": str(item.get("id") or ""),
            "text": str(item.get("text") or ""),
            "status": str(item.get("status") or "pending"),
        }
        for item in items
        if isinstance(item, dict)
    ]
    done = sum(1 for item in rows if item["status"] == "completed")
    return {
        "schema_version": 1,
        "has_plan": bool(rows),
        "items": rows,
        "done": done,
        "total": len(rows),
        "cleared": bool(cleared),
    }


def write_todo_extension(
    session_manager: Any,
    session_id: str,
    items: Iterable[dict],
    *,
    run_id: str = "",
    cleared: bool = False,
) -> dict:
    store = SessionExtensionStateStore(
        _sessions_root(session_manager), path_resolver=_path_resolver(session_manager)
    )
    return store.set_latest(
        session_id,
        TODO_EXTENSION_ID,
        TODO_NAMESPACE,
        todo_extension_value(items, cleared=cleared),
        run_id=run_id,
    )


def read_todo_extension(session_manager: Any, session_id: str) -> dict | None:
    store = SessionExtensionStateStore(
        _sessions_root(session_manager), path_resolver=_path_resolver(session_manager)
    )
    row = store.get(session_id, TODO_EXTENSION_ID, TODO_NAMESPACE)
    value = row.get("value")
    return dict(value) if isinstance(value, dict) else None


__all__ = [
    "TODO_EXTENSION_ID",
    "TODO_NAMESPACE",
    "read_todo_extension",
    "todo_extension_value",
    "write_todo_extension",
]
