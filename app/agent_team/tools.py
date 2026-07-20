"""Model-facing Agent Team tool dispatcher."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .models import AgentTeamError
from .service import AgentTeamService


_LEAD_ONLY_ACTIONS = {
    "create",
    "spawn_member",
    "dispatch",
    "remove_member",
    "resolve_permission",
    "shutdown",
    "complete_shutdown",
    "archive",
}


def _service() -> AgentTeamService:
    from agent_harness import session_manager

    return AgentTeamService(
        session_manager.repository.sessions_dir,
        path_resolver=session_manager._resolve_session_path,
    )


def _identity(session_id: str, session_meta: dict | None) -> tuple[str, str]:
    meta = session_meta if isinstance(session_meta, dict) else {}
    if meta.get("is_subagent"):
        root_id = str(meta.get("agent_team_root_session_id") or "").strip()
        member_id = str(meta.get("agent_team_member_id") or "").strip()
        if not root_id or not member_id:
            raise AgentTeamError("this subagent is not an Agent Team member")
        return root_id, member_id
    return str(session_id or "").strip(), "lead"


def _json_result(action: str, data: Any) -> str:
    return json.dumps({"ok": True, "action": action, "data": data}, ensure_ascii=False)


async def execute_team_tool(
    tool_args: dict,
    *,
    session_id: str,
    session_meta: dict | None = None,
    parent_key_context: str = "",
    emit=None,
    parent_run_id: str = "",
) -> str:
    """Execute a model ``team`` action with session-derived identity."""

    args = tool_args if isinstance(tool_args, dict) else {}
    action = str(args.get("action") or "status").strip().lower()
    root_id, actor_id = _identity(session_id, session_meta)
    if action in _LEAD_ONLY_ACTIONS and actor_id != "lead":
        raise AgentTeamError(f"only the team lead may perform action={action}")
    service = _service()

    if action == "status":
        return _json_result(action, service.read_team(root_id))
    if action == "create":
        return _json_result(action, service.create_team(root_id, str(args.get("title") or "")))
    if action == "spawn_member":
        return await _spawn_member(
            service,
            root_id,
            name=str(args.get("name") or ""),
            role=str(args.get("role") or ""),
            prompt=str(args.get("prompt") or ""),
            model_profile_id=str(args.get("model_profile_id") or ""),
            readonly=bool(args.get("readonly", False)),
        )
    if action == "dispatch":
        return await _dispatch_member(
            service,
            root_id,
            member_id=str(args.get("member_id") or ""),
            prompt=str(args.get("prompt") or ""),
            task_id=str(args.get("task_id") or ""),
            run_in_background=bool(args.get("run_in_background", False)),
            parent_key_context=parent_key_context,
            emit=emit,
            parent_run_id=parent_run_id,
        )
    if action == "remove_member":
        return _json_result(
            action,
            service.remove_member(
                root_id,
                str(args.get("member_id") or ""),
                reason=str(args.get("reason") or ""),
            ),
        )
    if action == "set_member_state":
        member_id = str(args.get("member_id") or actor_id)
        if actor_id != "lead" and member_id != actor_id:
            raise AgentTeamError("members may update only their own state")
        return _json_result(
            action,
            service.set_member_state(
                root_id,
                member_id,
                str(args.get("state") or ""),
                detail=str(args.get("detail") or ""),
            ),
        )
    if action == "create_task":
        depends_on = args.get("depends_on") or []
        if not isinstance(depends_on, list):
            raise AgentTeamError("depends_on must be an array")
        return _json_result(
            action,
            service.create_task(
                root_id,
                title=str(args.get("title") or ""),
                description=str(args.get("description") or ""),
                priority=str(args.get("priority") or "normal"),
                depends_on=depends_on,
            ),
        )
    if action == "claim_task":
        member_id = str(args.get("member_id") or actor_id)
        if actor_id != "lead" and member_id != actor_id:
            raise AgentTeamError("members may claim tasks only for themselves")
        return _json_result(
            action,
            service.claim_task(root_id, str(args.get("task_id") or ""), member_id),
        )
    if action == "release_task":
        member_id = str(args.get("member_id") or actor_id)
        if actor_id != "lead" and member_id != actor_id:
            raise AgentTeamError("members may release tasks only for themselves")
        return _json_result(
            action,
            service.release_task(
                root_id,
                str(args.get("task_id") or ""),
                member_id,
                str(args.get("reason") or ""),
            ),
        )
    if action == "update_task":
        return _json_result(
            action,
            service.update_task(
                root_id,
                str(args.get("task_id") or ""),
                status=str(args.get("status") or ""),
                result=str(args.get("result") or ""),
                detail=str(args.get("detail") or ""),
            ),
        )
    if action == "send_message":
        recipients = args.get("recipient_ids") or []
        if not isinstance(recipients, list):
            raise AgentTeamError("recipient_ids must be an array")
        return _json_result(
            action,
            service.send_message(
                root_id,
                sender_id=actor_id,
                recipient_ids=recipients,
                content=str(args.get("content") or ""),
                reply_to=str(args.get("reply_to") or ""),
            ),
        )
    if action == "read_inbox":
        recipient = str(args.get("member_id") or actor_id)
        if actor_id != "lead" and recipient != actor_id:
            raise AgentTeamError("members may read only their own inbox")
        return _json_result(
            action,
            service.list_inbox(
                root_id,
                recipient,
                include_consumed=bool(args.get("include_consumed", False)),
            ),
        )
    if action == "consume_message":
        recipient = str(args.get("member_id") or actor_id)
        if actor_id != "lead" and recipient != actor_id:
            raise AgentTeamError("members may consume only their own messages")
        return _json_result(
            action,
            service.update_message_delivery(
                root_id,
                str(args.get("message_id") or ""),
                recipient,
                "consumed",
            ),
        )
    if action == "request_permission":
        member_id = str(args.get("member_id") or actor_id)
        if member_id == "lead":
            raise AgentTeamError("lead does not need to request member permission")
        if actor_id != "lead" and member_id != actor_id:
            raise AgentTeamError("members may request permission only for themselves")
        return _json_result(
            action,
            service.request_permission(
                root_id,
                member_id=member_id,
                action=str(args.get("permission_action") or args.get("detail") or ""),
                resource=str(args.get("resource") or ""),
                detail=str(args.get("detail") or ""),
            ),
        )
    if action == "resolve_permission":
        return _json_result(
            action,
            service.resolve_permission(
                root_id,
                str(args.get("permission_id") or ""),
                decision=str(args.get("decision") or ""),
                resolved_by="lead",
                reason=str(args.get("reason") or ""),
            ),
        )
    if action == "shutdown":
        return _json_result(action, service.request_shutdown(root_id, str(args.get("reason") or "")))
    if action == "complete_shutdown":
        return _json_result(action, service.complete_shutdown(root_id))
    if action == "archive":
        return _json_result(action, service.archive_team(root_id))
    raise AgentTeamError(f"unsupported team action: {action}")


async def _spawn_member(
    service: AgentTeamService,
    root_id: str,
    *,
    name: str,
    role: str,
    prompt: str,
    model_profile_id: str,
    readonly: bool,
) -> str:
    from agent_harness import session_manager

    member = service.add_member(
        root_id,
        name=name,
        role=role,
        prompt=prompt,
        model_profile_id=model_profile_id,
    )
    member_id = str(member["member_id"])
    try:
        child_id = session_manager.create_subagent_session(
            root_id,
            name,
            "generalPurpose",
            1,
            model_profile_id=model_profile_id,
            readonly_strict=readonly,
        )
        metadata = session_manager._load_metadata(child_id) or {}
        metadata.update(
            {
                "agent_team_root_session_id": root_id,
                "agent_team_member_id": member_id,
                "agent_team_role": role,
                "agent_team_prompt": prompt,
            }
        )
        session_manager._save_metadata(child_id, metadata)
        member = service.bind_member_session(root_id, member_id, child_id)
        member = service.set_member_state(root_id, member_id, "idle")
    except Exception as exc:
        service.set_member_state(root_id, member_id, "failed", detail=str(exc))
        raise
    return _json_result("spawn_member", member)


async def _dispatch_member(
    service: AgentTeamService,
    root_id: str,
    *,
    member_id: str,
    prompt: str,
    task_id: str,
    run_in_background: bool,
    parent_key_context: str,
    emit,
    parent_run_id: str,
) -> str:
    from agent_subagent import run_subagent_task

    team = service.read_team(root_id) or {}
    member = (team.get("members") or {}).get(member_id)
    if not isinstance(member, dict):
        raise AgentTeamError(f"member not found: {member_id}")
    child_id = str(member.get("child_session_id") or "")
    if not child_id:
        raise AgentTeamError("member has no persistent child session")
    task = (team.get("tasks") or {}).get(task_id) if task_id else None
    if task_id and not isinstance(task, dict):
        raise AgentTeamError(f"task not found: {task_id}")
    if task_id and not task.get("assignee_id"):
        service.claim_task(root_id, task_id, member_id)
    role = str(member.get("role") or "team member")
    member_prompt = str(member.get("prompt") or "")
    assignment = prompt.strip() or (str(task.get("description") or task.get("title") or "") if task else "")
    if not assignment:
        raise AgentTeamError("dispatch requires prompt or task_id")
    full_prompt = (
        f"You are persistent Agent Team member {member.get('name')} ({member_id}), role: {role}.\n"
        f"Root team session: {root_id}.\n"
        + (f"Standing member instruction: {member_prompt}\n" if member_prompt else "")
        + (f"Assigned team task: {task_id}.\n" if task_id else "")
        + "Use the team tool to read your inbox, coordinate, update task status, and request permissions.\n"
        + f"Current assignment:\n{assignment}"
    )
    service.set_member_state(root_id, member_id, "working", detail=assignment[:1000])
    try:
        result = await run_subagent_task(
            tool_args={
                "action": "resume",
                "resume": child_id,
                "description": str(member.get("name") or "team member"),
                "prompt": full_prompt,
                "run_in_background": run_in_background,
            },
            parent_session_id=root_id,
            parent_key_context=parent_key_context,
            emit=emit,
            parent_run_id=parent_run_id,
        )
        if run_in_background:
            from agent_subagent import subagent_registry

            async def monitor_background_member() -> None:
                try:
                    await subagent_registry.wait(child_id)
                    current_team = await asyncio.to_thread(service.read_team, root_id)
                    current = (
                        ((current_team or {}).get("members") or {}).get(member_id) or {}
                    )
                    # A member that stopped to request permission must remain
                    # visibly blocked until the lead resolves and redispatches.
                    if current.get("state") != "waiting_permission":
                        await asyncio.to_thread(
                            service.set_member_state,
                            root_id,
                            member_id,
                            "idle",
                        )
                except Exception as monitor_exc:
                    try:
                        await asyncio.to_thread(
                            service.set_member_state,
                            root_id,
                            member_id,
                            "failed",
                            detail=str(monitor_exc),
                        )
                    except Exception:
                        pass

            asyncio.create_task(monitor_background_member())
        else:
            service.set_member_state(root_id, member_id, "idle")
        return _json_result(
            "dispatch",
            {
                "member_id": member_id,
                "child_session_id": child_id,
                "task_id": task_id or None,
                "background": run_in_background,
                "result": result,
            },
        )
    except Exception as exc:
        service.set_member_state(root_id, member_id, "failed", detail=str(exc))
        raise
