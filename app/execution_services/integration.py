"""Small loop/lifecycle seams; feature implementation stays outside ReAct."""
from . import jobs


def prompt_guidance():
    from .shell import jobs_enabled
    parts = []
    if jobs_enabled():
        parts.append("Track every background job id you start. Completion is notified in-session; do not busy-poll or sleep on a job. "
            "Continue independent work. Before finalizing, collect still-relevant results with job_output; use wait=true only when blocked. "
            "Cancel obsolete jobs with job_kill. Use persistent terminals for interactive stdin or state across calls; prefer run_shell for one-shot commands. "
            "Close unused terminal sessions. A pty-send job completes a send observation, not the command's lifetime. "
            "inferred_idle or timeout does not prove the foreground command exited; use terminal_read for subsequent output. "
            "A signal's delivered flag alone does not prove interruption; inspect interruptVerified and terminal_read. "
            "Windows SIGINT may forcibly end owned child programs after Ctrl+C fails to restore the shell prompt; "
            "check forced/fallback. In-process shell commands have no separate termination target; explicit terminal_close stops the shell.")
    from .computer import _MANAGER, GUIDANCE
    if _MANAGER is not None and _MANAGER.state == "ready" and _MANAGER._plugin_enabled():
        parts.append(GUIDANCE)
    return "\n\n".join(parts)


async def consume_notices(state, persist_append):
    service = jobs._SERVICE
    if service is None or service._closing:
        return False
    owner = state["session_id"]
    notices = await service.call(service.notices, owner)
    if not notices:
        return False
    from agent_harness import SystemMessage
    added = False
    for notice in notices:
        marker = f"[background job {notice['id']}]"
        # Persistence precedes acknowledgement. If the process stops between
        # the two, an existing model message deduplicates redelivery.
        if not any(isinstance(m, SystemMessage) and marker in str(m.content)
                   for m in state.get("llm_history", [])):
            message = SystemMessage(content=notice["text"])
            state["llm_history"].append(message)
            state["work_messages"].append(message)
            persist_append(state, message)
            added = True
    await service.call(service.acknowledge, owner, [n["id"] for n in notices])
    return added


async def resume_execution(owner):
    service = jobs._SERVICE
    if service is not None and not service._closing:
        await service.call(service.resume_owner, owner)


async def stop_execution(owners, *, deleted=False, reason="user_stop"):
    service = jobs._SERVICE
    if service is not None and not service._closing:
        for owner in owners:
            await service.call(service.stop_owner, owner, close_terminals=deleted, reason=reason)


async def permissions_changed(mode):
    service = jobs._SERVICE
    if service is None or service._closing:
        return
    async def apply():
        affected = {job.owner for job in service.jobs.values()
                    if job.status in jobs.ACTIVE and job.permission_mode == "full_access" and mode != "full_access"}
        if service.terminals:
            for terminal in tuple(service.terminals.sessions.values()):
                if terminal.actor == "model" and terminal.status == "running" and terminal.permission_mode != mode:
                    await service.terminals.close(terminal.owner, terminal.id)
        for owner in affected:
            await service.stop_owner(owner, reason="permission_mode_changed")
    await service.call(apply)
