"""Session workspace control exposed through the trusted host tool bridge."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from host_tool_registry import HostToolInvocationContext, host_tool_invokers
from tool_execution_policy import ToolExecutionPolicy
from tool_registry import ToolOutcome


async def switch_work_dir(context: HostToolInvocationContext, arguments) -> ToolOutcome:
    from security.models import DecisionOutcome
    from agent_harness import normalize_session_work_dir, session_work_dir_projection

    request = context.service("security_request")
    decision = context.service("security_decision")
    target = normalize_session_work_dir(arguments.get("work_dir"))
    previous_root = request.metadata.get("previous_root")
    if (not target or request.action != "session.switch_work_dir"
            or not isinstance(previous_root, str) or not previous_root.strip()
            or decision.outcome != DecisionOutcome.ALLOW
            or decision.rule_id != "grant.once"
            or str(Path(target).resolve()) != request.resource):
        return ToolOutcome.failed("workspace_approval_required", "切换工作目录需要用户许可，请重新发起审批。")
    if context.service("run_interrupt_check")():
        return ToolOutcome.failed("interrupted", "执行已中断，工作目录未切换。")
    try:
        # Keep this short metadata transaction on the event-loop turn so no
        # cancellation can report failure while a background write still lands.
        metadata = context.service("session_manager").set_session_work_dir(
            context.session_id, target, expected_root=previous_root)
    except (ValueError, FileNotFoundError) as exc:
        return ToolOutcome.failed("workspace_switch_failed", str(exc))
    # Remaining tools in the same assistant batch share this host-owned dict.
    # Refresh it before returning so security, native tools, MCP and audit agree.
    live_meta = context.service("session_meta")
    live_meta.update({key: metadata.get(key) for key in (
        "work_dir", "authorized_dirs", "subagent_work_dir", "git_worktree_path", "updated_at")})
    projection = session_work_dir_projection(context.session_id, metadata)
    try:
        await context.publish({"type": "session_work_dir_changed", "ephemeral": True,
                               "session_id": context.session_id, "session": {"id": context.session_id, **projection}})
    except Exception:
        # The transaction has committed. A disconnected event consumer must
        # not turn it into a reported failure; polling reads the saved root.
        logging.getLogger(__name__).warning("workspace event delivery failed for %s", context.session_id, exc_info=True)
    return ToolOutcome.completed(json.dumps({"ok": True, **projection}, ensure_ascii=False))


def workspace_tool_definitions() -> list[dict]:
    host_tool_invokers.register("switch_work_dir", switch_work_dir, replace=True,
        policy=ToolExecutionPolicy(effect="control", early_stream_safe=False), owner="core.workspace")
    return [{"type": "function", "function": {
        "name": "switch_work_dir",
        "description": "Switch this conversation's working directory after the user approves the exact target. Use an existing absolute directory. Subsequent file, shell, MCP and subagent calls use the new root; history and attachments stay in shared storage. Existing terminals/jobs keep their original cwd. Do not use shell cd to change the session root.",
        "parameters": {"type": "object", "properties": {
            "work_dir": {"type": "string", "description": "Existing absolute directory"},
            "reason": {"type": "string", "description": "Why this task needs the directory switch"}},
            "required": ["work_dir", "reason"], "additionalProperties": False}}}]
