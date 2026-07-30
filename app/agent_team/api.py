"""FastAPI routes for the Agent Team control plane."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from .config import AgentTeamDisabledError
from .models import (
    AgentTeamConflictError,
    AgentTeamNotFoundError,
    AgentTeamValidationError,
)
from .service import AgentTeamService


def create_agent_team_router(
    service_factory: Callable[[], AgentTeamService],
    session_exists: Callable[[str], bool] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/agent-team", tags=["agent-team"])

    async def invoke(method: str, *args, **kwargs) -> JSONResponse:
        if session_exists is not None and args:
            session_id = str(args[0] or "").strip()
            try:
                exists = await asyncio.to_thread(session_exists, session_id)
            except Exception:
                exists = False
            if not exists:
                return JSONResponse(
                    {"ok": False, "error": "session not found", "code": "not_found"},
                    status_code=404,
                )
        try:
            service = service_factory()
            result = await asyncio.to_thread(getattr(service, method), *args, **kwargs)
        except AgentTeamDisabledError as exc:
            return JSONResponse({"ok": False, "error": str(exc), "code": "feature_disabled"}, status_code=403)
        except AgentTeamValidationError as exc:
            return JSONResponse({"ok": False, "error": str(exc), "code": "validation_error"}, status_code=400)
        except AgentTeamNotFoundError as exc:
            return JSONResponse({"ok": False, "error": str(exc), "code": "not_found"}, status_code=404)
        except AgentTeamConflictError as exc:
            return JSONResponse({"ok": False, "error": str(exc), "code": "conflict"}, status_code=409)
        return JSONResponse({"ok": True, "data": result})

    async def body(request: Request) -> dict[str, Any] | JSONResponse:
        try:
            value = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
        if not isinstance(value, dict):
            return JSONResponse({"ok": False, "error": "json body must be an object"}, status_code=400)
        return value

    @router.get("/{session_id}")
    async def get_team(session_id: str):
        return await invoke("read_team", session_id)

    @router.post("/{session_id}")
    async def create_team(session_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke("create_team", session_id, str(data.get("title") or ""))

    @router.post("/{session_id}/members")
    async def add_member(session_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke(
            "add_member",
            session_id,
            name=data.get("name"),
            role=data.get("role"),
            prompt=data.get("prompt") or "",
            child_session_id=data.get("child_session_id") or "",
            model_profile_id=data.get("model_profile_id") or "",
        )

    @router.patch("/{session_id}/members/{member_id}")
    async def set_member_state(session_id: str, member_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke(
            "set_member_state",
            session_id,
            member_id,
            data.get("state"),
            detail=data.get("detail") or "",
        )

    @router.delete("/{session_id}/members/{member_id}")
    async def remove_member(session_id: str, member_id: str, reason: str = Query("")):
        return await invoke("remove_member", session_id, member_id, reason=reason)

    @router.post("/{session_id}/tasks")
    async def create_task(session_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        dependencies = data.get("depends_on") or []
        if not isinstance(dependencies, list):
            return JSONResponse({"ok": False, "error": "depends_on must be an array"}, status_code=400)
        return await invoke(
            "create_task",
            session_id,
            title=data.get("title"),
            description=data.get("description") or "",
            priority=data.get("priority") or "normal",
            depends_on=dependencies,
        )

    @router.patch("/{session_id}/tasks/{task_id}")
    async def update_task(session_id: str, task_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke(
            "update_task",
            session_id,
            task_id,
            status=data.get("status"),
            result=data.get("result") or "",
            detail=data.get("detail") or "",
        )

    @router.post("/{session_id}/tasks/{task_id}/claim")
    async def claim_task(session_id: str, task_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke("claim_task", session_id, task_id, data.get("member_id"))

    @router.post("/{session_id}/tasks/{task_id}/release")
    async def release_task(session_id: str, task_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke(
            "release_task",
            session_id,
            task_id,
            data.get("member_id"),
            data.get("reason") or "",
        )

    @router.post("/{session_id}/messages")
    async def send_message(session_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        recipients = data.get("recipient_ids") or []
        if not isinstance(recipients, list):
            return JSONResponse({"ok": False, "error": "recipient_ids must be an array"}, status_code=400)
        return await invoke(
            "send_message",
            session_id,
            sender_id=data.get("sender_id"),
            recipient_ids=recipients,
            content=data.get("content"),
            reply_to=data.get("reply_to") or "",
        )

    @router.get("/{session_id}/inbox/{recipient_id}")
    async def list_inbox(
        session_id: str,
        recipient_id: str,
        include_consumed: bool = Query(False),
    ):
        return await invoke(
            "list_inbox", session_id, recipient_id, include_consumed=include_consumed
        )

    @router.post("/{session_id}/messages/{message_id}/delivery")
    async def update_delivery(session_id: str, message_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke(
            "update_message_delivery",
            session_id,
            message_id,
            data.get("recipient_id"),
            data.get("status"),
            error=data.get("error") or "",
        )

    @router.post("/{session_id}/shutdown")
    async def request_shutdown(session_id: str, request: Request):
        data = await body(request)
        if isinstance(data, JSONResponse):
            return data
        return await invoke("request_shutdown", session_id, data.get("reason") or "")

    @router.post("/{session_id}/shutdown/complete")
    async def complete_shutdown(session_id: str):
        return await invoke("complete_shutdown", session_id)

    @router.post("/{session_id}/archive")
    async def archive_team(session_id: str):
        return await invoke("archive_team", session_id)

    return router
