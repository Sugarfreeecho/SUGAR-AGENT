"""Paired sidebar adapters for the application's durable human interactions."""
from __future__ import annotations

import asyncio
import json

from fastapi import HTTPException, Request


def approval_decisions(record):
    if record.get("force_approval"):
        return {"allow_once", "deny"}
    workspace = bool(record.get("external_workspace_grantable"))
    decisions = {"deny", "allow_external_workspace_once" if workspace else "allow_once"}
    if record.get("allow_session_available", True):
        decisions.add("allow_external_workspace" if workspace else
                      "allow_always" if record.get("allow_always_available") and record.get("rule_pattern") else "allow_session")
    return decisions


def install_human_routes(router, authenticate, authorize_session, control):
    def service():
        from human_interaction import get_human_interaction_service
        return get_human_interaction_service()

    def error_response(error):
        from webui import _human_interaction_error_response
        return _human_interaction_error_response(error)

    @router.post("/human/list")
    async def human_list(request: Request):
        principal, _ = authenticate(request)
        data = await control().body(request, 4096)
        sid = str(data.get("session_id") or "")
        def authorize_target(method, target):
            try:
                authorize_session(principal, method, target)
            except HTTPException as error:
                if target == sid and error.status_code == 404:
                    raise HTTPException(404, "当前会话已不存在，请从会话列表重新选择。") from None
                raise
        authorize_target("session.history", sid)
        ids = [sid]
        if data.get("include_descendants", True):
            ids.extend(await asyncio.to_thread(control().service.manager.list_subagent_descendants, sid))
        records = []
        for target in dict.fromkeys(ids):
            target_records = []
            try:
                authorize_target("session.history", target)
                for kind in ("question", "approval"):
                    if kind == "approval":
                        try:
                            authorize_target("approval.list", target)
                        except HTTPException as error:
                            if error.status_code == 403:
                                continue
                            raise
                    rows = await asyncio.to_thread(service().list, target, kind=kind)
                    terminal = [row for row in rows if row.get("status") != "pending"][-100:]
                    target_records.extend([{**row, "session_id": target} for row in rows if row.get("status") == "pending"] + terminal)
                # A child may disappear or lose its grant while disk reads yield.
                authorize_target("session.history", target)
            except HTTPException as error:
                if target != sid and error.status_code in {403, 404}:
                    continue
                raise
            records.extend(target_records)
        authorize_target("session.history", sid)
        return {"records": records}

    async def action(request, kind, operation):
        principal, _ = authenticate(request)
        data = await control().body(request, 65536)
        sid = str(data.get("session_id") or "")
        identity = str(data.get("approval_id" if kind == "approval" else "interaction_id") or "")
        authorize_session(principal, "approval.resolve" if kind == "approval" else "session.send", sid)
        try:
            record = await asyncio.to_thread(service().get, sid, identity, kind=kind)
            if not data.get("request_digest") or data["request_digest"] != record.get("request_digest"):
                raise HTTPException(409, "请求内容已变化，请刷新卡片后重试")
            if kind == "approval" and record.get("status") == "pending" and data.get("decision") not in approval_decisions(record):
                raise HTTPException(422, "此审批不支持所选授权范围")
            # The existing handlers own waiter wakeup, grants, durable terminal
            # facts and recovery after a backend restart. Do not duplicate them.
            from webui import resolve_session_interaction, cancel_session_interaction, resolve_session_approval
            handler = resolve_session_approval if kind == "approval" else cancel_session_interaction if operation == "cancel" else resolve_session_interaction
            payload = {"decision": data.get("decision"), "rejection_reason": data.get("rejection_reason", "")} if kind == "approval" else {"reason": "user_cancelled"} if operation == "cancel" else {"answers": data.get("answers")}
            encoded = json.dumps(payload, ensure_ascii=False).encode()
            scope = dict(request.scope)
            scope["headers"] = [(key, value) for key, value in request.scope.get("headers", []) if key not in {b"content-length", b"x-client-id"}]
            scope["headers"].append((b"x-client-id", ("browser-use:" + principal.id).encode()))
            async def receive():
                return {"type": "http.request", "body": encoded, "more_body": False}
            return await handler(sid, identity, Request(scope, receive))
        except HTTPException:
            raise
        except Exception as error:
            return error_response(error)

    @router.post("/questions/resolve")
    async def question_resolve(request: Request):
        return await action(request, "question", "resolve")

    @router.post("/questions/cancel")
    async def question_cancel(request: Request):
        return await action(request, "question", "cancel")

    @router.post("/approvals/resolve")
    async def approval_resolve(request: Request):
        return await action(request, "approval", "resolve")

    @router.get("/question-image")
    async def question_image(request: Request, session_id: str, interaction_id: str, question_id: str, image_index: int):
        principal, _ = authenticate(request)
        authorize_session(principal, "session.history", session_id)
        from attachments import get_attachment_store, AttachmentError
        from fastapi.responses import Response
        from human_interaction import HumanInteractionNotFound
        try:
            def read():
                record = service().get(session_id, interaction_id)
                question = next((row for row in record.get("questions", []) if row.get("question_id") == question_id), {})
                images = question.get("images", [])
                if not 0 <= image_index < len(images):
                    raise HumanInteractionNotFound("question image not found")
                return get_attachment_store().read_image_sync(images[image_index]["attachment"])
            stored = await asyncio.to_thread(read)
            return Response(stored.data, media_type=stored.ref["mediaType"], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        except (HumanInteractionNotFound, AttachmentError, KeyError, ValueError):
            raise HTTPException(404, "提问图片不存在") from None
