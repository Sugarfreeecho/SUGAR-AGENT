"""Model-facing Agent Team tool dispatcher."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any

from .models import AgentTeamError
from .service import AgentTeamService


_LEAD_ONLY_ACTIONS = {
    "create",
    "spawn_member",
    "dispatch",
    "remove_member",
    "shutdown",
    "complete_shutdown",
    "archive",
    "auto_schedule",
}

_SCHEDULER_LOCKS_GUARD = threading.Lock()
_SCHEDULER_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_SCHEDULER_TASK: asyncio.Task | None = None
_SCHEDULER_STOP: asyncio.Event | None = None


def _scheduler_lock(root_id: str) -> asyncio.Lock:
    loop_key = id(asyncio.get_running_loop())
    key = (loop_key, root_id)
    with _SCHEDULER_LOCKS_GUARD:
        lock = _SCHEDULER_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _SCHEDULER_LOCKS[key] = lock
        return lock


def _auto_schedule_enabled() -> bool:
    return str(os.getenv("AGENT_TEAM_AUTO_SCHEDULE", "1")).strip().lower() not in {
        "0", "false", "no", "off",
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
        result = await _spawn_member(
            service,
            root_id,
            name=str(args.get("name") or ""),
            role=str(args.get("role") or ""),
            prompt=str(args.get("prompt") or ""),
            model_profile_id=str(args.get("model_profile_id") or ""),
            readonly=bool(args.get("readonly", False)),
        )
        await _auto_schedule_team(
            service,
            root_id,
            parent_key_context=parent_key_context,
            emit=emit,
            parent_run_id=parent_run_id,
        )
        return result
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
        created = service.create_task(
                root_id,
                title=str(args.get("title") or ""),
                description=str(args.get("description") or ""),
                priority=str(args.get("priority") or "normal"),
                depends_on=depends_on,
            )
        scheduled = await _auto_schedule_team(
            service,
            root_id,
            parent_key_context=parent_key_context,
            emit=emit,
            parent_run_id=parent_run_id,
        )
        created = dict(created)
        created["auto_scheduled"] = scheduled
        return _json_result(action, created)
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
        updated = service.update_task(
                root_id,
                str(args.get("task_id") or ""),
                status=str(args.get("status") or ""),
                result=str(args.get("result") or ""),
                detail=str(args.get("detail") or ""),
            )
        scheduled = await _auto_schedule_team(
            service,
            root_id,
            parent_key_context=parent_key_context,
            emit=emit,
            parent_run_id=parent_run_id,
        )
        updated = dict(updated)
        updated["auto_scheduled"] = scheduled
        return _json_result(action, updated)
    if action == "auto_schedule":
        return _json_result(
            action,
            await _auto_schedule_team(
                service,
                root_id,
                parent_key_context=parent_key_context,
                emit=emit,
                parent_run_id=parent_run_id,
                force=True,
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
    from agent_harness import inherited_executor_selection, session_manager

    if not model_profile_id:
        model_profile_id = str(
            inherited_executor_selection(root_id).get("model_profile_id") or ""
        )

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
        if not readonly:
            try:
                from agent_subagent import (
                    _create_managed_worktree,
                    _persist_managed_worktree,
                )

                worktree = await asyncio.to_thread(_create_managed_worktree, child_id)
                if worktree is not None:
                    wt_root, wt_work_dir, branch, base_commit = worktree
                    _persist_managed_worktree(
                        child_id,
                        wt_root,
                        wt_work_dir,
                        branch,
                        base_commit,
                    )
            except Exception:
                # A dirty/non-Git root remains usable, but the member will still
                # be protected by write locks and external-tool contracts.
                pass
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
    auto_continue: bool = True,
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
        + "Use the team tool to read your inbox, coordinate, and update task status.\n"
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
            from agent_harness import session_manager

            async def monitor_background_member() -> None:
                try:
                    completed_result = await subagent_registry.wait(child_id)
                    current_team = await asyncio.to_thread(service.read_team, root_id)
                    current = (
                        ((current_team or {}).get("members") or {}).get(member_id) or {}
                    )
                    # A member that stopped to request permission must remain
                    # visibly blocked until the lead resolves and redispatches.
                    if current.get("state") != "waiting_permission":
                        metadata = (
                            await asyncio.to_thread(
                                session_manager._load_metadata,
                                child_id,
                            )
                            if task_id
                            else {}
                        )
                        current_task = (
                            ((current_team or {}).get("tasks") or {}).get(task_id) or {}
                        )
                        if (
                            task_id
                            and str((metadata or {}).get("subagent_run_status") or "")
                            == "completed"
                            and current_task.get("status") == "in_progress"
                            and current_task.get("assignee_id") == member_id
                        ):
                            await asyncio.to_thread(
                                service.update_task,
                                root_id,
                                task_id,
                                status="completed",
                                result=str(completed_result or "")[:64_000],
                                detail="completed by automatic Team dispatch",
                            )
                        await asyncio.to_thread(
                            service.set_member_state,
                            root_id,
                            member_id,
                            "idle",
                        )
                        if auto_continue:
                            await _auto_schedule_team(
                                service,
                                root_id,
                                parent_key_context=parent_key_context,
                                emit=emit,
                                parent_run_id=parent_run_id,
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
            from agent_harness import session_manager

            metadata = (
                await asyncio.to_thread(
                    session_manager._load_metadata,
                    child_id,
                )
                if task_id
                else {}
            )
            current_team = await asyncio.to_thread(service.read_team, root_id)
            current_member = (
                ((current_team or {}).get("members") or {}).get(member_id) or {}
            )
            current_task = (
                ((current_team or {}).get("tasks") or {}).get(task_id) or {}
            )
            if (
                task_id
                and current_member.get("state") != "waiting_permission"
                and str((metadata or {}).get("subagent_run_status") or "")
                == "completed"
                and current_task.get("status") == "in_progress"
                and current_task.get("assignee_id") == member_id
            ):
                await asyncio.to_thread(
                    service.update_task,
                    root_id,
                    task_id,
                    status="completed",
                    result=str(result or "")[:64_000],
                    detail="completed by automatic Team dispatch",
                )
            service.set_member_state(root_id, member_id, "idle")
            if auto_continue:
                await _auto_schedule_team(
                    service,
                    root_id,
                    parent_key_context=parent_key_context,
                    emit=emit,
                    parent_run_id=parent_run_id,
                )
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


async def _auto_schedule_team(
    service: AgentTeamService,
    root_id: str,
    *,
    parent_key_context: str,
    emit,
    parent_run_id: str,
    force: bool = False,
) -> list[dict]:
    """Claim ready tasks for idle members and wake their persistent sessions."""
    if not force and not _auto_schedule_enabled():
        return []
    scheduled: list[dict] = []
    async with _scheduler_lock(root_id):
        while True:
            team = await asyncio.to_thread(service.read_team, root_id)
            if not isinstance(team, dict) or team.get("status") != "active":
                break
            idle_members = [
                member
                for member in (team.get("members") or {}).values()
                if isinstance(member, dict)
                and member.get("state") == "idle"
                and member.get("child_session_id")
                and not member.get("removed")
            ]
            idle_members.sort(key=lambda row: int(row.get("seq") or 0))
            if not idle_members:
                break
            progress = False
            for member in idle_members:
                member_id = str(member.get("member_id") or "")
                claimed = await asyncio.to_thread(
                    service.claim_next_task,
                    root_id,
                    member_id,
                )
                if not claimed:
                    continue
                task_id = str(claimed.get("task_id") or "")
                try:
                    dispatch_result = await _dispatch_member(
                        service,
                        root_id,
                        member_id=member_id,
                        prompt="",
                        task_id=task_id,
                        run_in_background=True,
                        parent_key_context=parent_key_context,
                        emit=emit,
                        parent_run_id=parent_run_id,
                        auto_continue=True,
                    )
                    scheduled.append(
                        {
                            "member_id": member_id,
                            "task_id": task_id,
                            "dispatch": json.loads(dispatch_result),
                        }
                    )
                    progress = True
                except Exception as exc:
                    try:
                        await asyncio.to_thread(
                            service.release_task,
                            root_id,
                            task_id,
                            member_id,
                            f"automatic dispatch failed: {exc}",
                        )
                    except Exception:
                        pass
            if not progress:
                break
    return scheduled


async def start_auto_scheduler() -> bool:
    """Start the durable Team task auto-claim/wake loop."""
    global _SCHEDULER_TASK, _SCHEDULER_STOP
    if _SCHEDULER_TASK is not None and not _SCHEDULER_TASK.done():
        return False
    if not _auto_schedule_enabled():
        return False
    _SCHEDULER_STOP = asyncio.Event()

    async def loop() -> None:
        from agent_harness import session_manager

        interval = max(
            2.0,
            float(os.getenv("AGENT_TEAM_SCHEDULER_INTERVAL_SECONDS", "5")),
        )
        service = _service()
        while _SCHEDULER_STOP is not None and not _SCHEDULER_STOP.is_set():
            roots = []
            try:
                roots = [
                    str(row.get("id") or "")
                    for row in list(session_manager.index)
                    if isinstance(row, dict) and str(row.get("id") or "")
                ]
            except Exception:
                roots = []
            for root_id in roots:
                try:
                    team = await asyncio.to_thread(service.read_team, root_id)
                    if isinstance(team, dict) and team.get("status") == "active":
                        await _auto_schedule_team(
                            service,
                            root_id,
                            parent_key_context="",
                            emit=None,
                            parent_run_id="team_scheduler",
                        )
                except Exception:
                    continue
            await asyncio.sleep(interval)

    _SCHEDULER_TASK = asyncio.create_task(loop())
    return True


async def stop_auto_scheduler() -> None:
    global _SCHEDULER_TASK, _SCHEDULER_STOP
    if _SCHEDULER_STOP is not None:
        _SCHEDULER_STOP.set()
    task = _SCHEDULER_TASK
    _SCHEDULER_TASK = None
    _SCHEDULER_STOP = None
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
