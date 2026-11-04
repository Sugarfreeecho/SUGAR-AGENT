"""Authorized, lightweight navigation over the same subagent task store as the main UI."""
from __future__ import annotations

import asyncio
from fastapi import HTTPException, Request


def build_catalog(application, principal, session_id):
    service, manager = application.service, application.service.manager
    def authorize(sid):
        service.authorize(principal, "session.history", {"session_id": sid})
    def summary(sid):
        meta = manager._load_metadata(sid) or {}
        return {"id": sid, "name": str(meta.get("name") or meta.get("subagent_description") or sid[:12])}
    authorize(session_id)
    ancestors, seen, cursor = [], set(), session_id
    parent_unavailable = False
    from session_control.errors import ControlError
    while cursor and cursor not in seen and len(ancestors) < 32:
        authorize(cursor)
        seen.add(cursor)
        ancestors.append(summary(cursor))
        parent = manager.get_subagent_parent_id(cursor)
        if not parent:
            break
        try:
            authorize(parent)
        except ControlError as error:
            if error.status not in {403, 404}:
                raise
            parent_unavailable = cursor == session_id
            break
        cursor = parent
    breadcrumbs = list(reversed(ancestors))
    root = breadcrumbs[0]
    index = manager._load_subagent_index()
    frontier, visited, entries = [(root["id"], 0)], {root["id"]}, []
    try:
        from agent_subagent import subagent_registry
        registry_running = subagent_registry.is_running
    except ImportError:
        registry_running = lambda _sid: False
    while frontier and len(entries) < 512:
        parent, depth = frontier.pop(0)
        if depth >= 32:
            continue
        authorize(parent)
        tasks = {str(row.get("task_id") or row.get("agent_id") or row.get("id") or ""): row
                 for row in manager.list_subagent_tasks(parent) if isinstance(row, dict)}
        for child, owner in index.items():
            if owner == parent:
                tasks.setdefault(child, {})
        for child, task in tasks.items():
            if not child or child in visited:
                continue
            try:
                child = manager._normalize_session_id(child)
            except ValueError:
                continue
            visited.add(child)
            meta, selectable = {}, True
            try:
                authorize(child)
                meta = manager._load_metadata(child) or {}
                if not meta.get("is_subagent") or str(meta.get("parent_session_id") or "") != parent:
                    continue
            except ControlError as error:
                if error.status == 403:
                    continue
                if error.status != 404:
                    raise
                if not task or manager._is_deleted_session(child):
                    continue
                selectable = False  # Aggregate/one-shot task with no independent session.
            running = selectable and bool(service.deps.is_stream_active(child) or registry_running(child))
            status = "running" if running else str(task.get("status") or meta.get("subagent_run_status") or "unknown")
            pending = service.callbacks.get("pending_human", lambda _sid: 0)(child) if selectable else 0
            entries.append({"id": child, "parent_id": parent, "depth": depth + 1,
                "name": str(meta.get("subagent_description") or task.get("description") or meta.get("name") or task.get("subagent_type") or child[:12])[:160],
                "status": status, "running": running, "selectable": selectable,
                "pending_human_count": int(pending or 0), "virtual_task": not selectable,
                "updated_at": task.get("updated_at") or meta.get("updated_at")})
            if selectable:
                frontier.append((child, depth + 1))
            if len(entries) >= 512:
                break
    # Grants and session membership can change while the directory is read.
    valid = []
    for row in entries:
        try:
            authorize(row["id"] if row["selectable"] else row["parent_id"])
            valid.append(row)
        except ControlError as error:
            if error.status not in {403, 404}:
                raise
    for breadcrumb in breadcrumbs:
        authorize(breadcrumb["id"])
    authorize(session_id)
    return {"session_id": session_id, "root": root, "parent": breadcrumbs[-2] if len(breadcrumbs) > 1 else None,
            "breadcrumbs": breadcrumbs, "entries": valid, "parent_available": not parent_unavailable}


def install_subagent_routes(router, authenticate, control):
    @router.post("/subagents")
    async def subagent_catalog(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        data = await control().body(request, 4096)
        session_id = data.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise HTTPException(422, "session_id is required")
        try:
            return await asyncio.to_thread(build_catalog, control(), principal, session_id)
        except Exception as error:
            return control().error(error)
