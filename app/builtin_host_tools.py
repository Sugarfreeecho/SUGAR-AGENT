"""Built-in host service invokers.

These handlers intentionally contain capability-specific behavior, keeping it
out of ``agent_loop.py`` while preserving the host's authorization boundary.
"""
from __future__ import annotations

import json
import queue
from typing import Any, Mapping

from host_tool_registry import HostToolInvocationContext, host_tool_invokers
from human_interaction import HumanInteractionValidationError, ask_user_enabled, wait_for_user_answers
from tool_registry import ToolOutcome
from tool_execution_policy import ToolExecutionPolicy


async def _invoke_ask_user(
    context: HostToolInvocationContext,
    arguments: Mapping[str, Any],
) -> ToolOutcome:
    context.state["_runtime_stage"] = "waiting_user:ask_user"
    try:
        interaction = await wait_for_user_answers(
            context.session_id,
            dict(arguments),
            run_id=context.run_id,
            tool_call_id=context.tool_call_id,
            emit=context.services.get("raw_emit"),
            interrupt_check=context.service("interaction_interrupt_check"),
        )
        status = str(interaction.get("status") or "resolved")
        payload = {
            "status": status,
            "interaction_id": interaction.get("interaction_id"),
            "answers": interaction.get("answers") or [],
        }
        if interaction.get("reason"):
            payload["reason"] = interaction.get("reason")
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if status in {"resolved", "cancelled"}:
            return ToolOutcome.completed(content)
        return ToolOutcome.failed("interaction_failed", status, content=content)
    except HumanInteractionValidationError as exc:
        content = json.dumps(
            {"status": "invalid_request", "error": str(exc)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return ToolOutcome.failed("invalid_interaction", str(exc), content=content)


async def _invoke_context_manage(
    context: HostToolInvocationContext,
    arguments: Mapping[str, Any],
) -> ToolOutcome:
    mode = str(arguments.get("mode") or "compact").strip().lower()
    await_thread = context.service("await_thread_keepalive")

    if mode == "compact":
        await context.publish(
            {
                "type": "status",
                "content": "【context_manage·compact】正在进行上下文裁剪（可能需数秒，请稍候）…",
            }
        )
        hints: queue.Queue = queue.Queue()

        def hint_sink(item: Any) -> None:
            hints.put(context.service("progress_hint_event")(item))

        state = context.state
        history = context.service("llm_history")
        result = await await_thread(
            lambda: context.service("run_context_policy")(
                history,
                state.get("key_context", ""),
                context.session_id,
                force_user_compact=True,
                hint_sink=hint_sink,
                context_window=int(context.service("context_window")),
                prompt_language=state.get("_prompt_language", "zh-CN"),
                should_stop=context.service("run_interrupt_check"),
            ),
            hints,
            {
                "type": "context_summary_progress",
                "content": "【context_manage·compact】摘要模型仍在生成或等待响应中，请稍候…",
                "ephemeral": True,
            },
        )
        new_history, new_key_context, changed, _, used_summary, new_recap = result
        metadata = {"lifecycle_events": ["PostCompact"]}
        if changed:
            state["llm_history"] = new_history
            state["dialogue"] = context.service("derive_dialogue")(new_history)
            state["key_context"] = new_key_context
            callback = context.services.get("context_changed")
            if callable(callback):
                callback(context.state)
            metadata["control_result"] = {
                "type": "compact",
                "new_llm_history": new_history,
                "new_recap": new_recap,
                "used_llm_summary": used_summary,
            }
        else:
            metadata["control_result"] = {"type": "compact_noop"}
        completion_message = (
            "手动压缩已完成"
            if changed
            else "手动压缩已完成：当前上下文无需进一步裁剪或摘要"
        )
        return ToolOutcome.completed(completion_message, metadata=metadata)

    if mode == "edit_key_context":
        instruction = str(arguments.get("edit_instruction") or "").strip()
        if not instruction:
            return ToolOutcome.failed(
                "missing_edit_instruction",
                "edit_key_context 模式需要提供非空的 edit_instruction。",
                content="edit_key_context 模式需要提供非空的 edit_instruction。",
            )
        hints = queue.Queue()

        def hint_sink(item: Any) -> None:
            hints.put(context.service("progress_hint_event")(item))

        new_key_context, message = await await_thread(
            lambda: context.service("edit_key_context")(
                context.session_id,
                instruction,
                hint_sink=hint_sink,
                current_key_context=context.state.get("key_context", ""),
                prompt_language=context.state.get("_prompt_language", "zh-CN"),
            ),
            hints,
            {
                "type": "key_context_progress",
                "content": "【要点】模型仍在更新要点或等待响应中，请稍候…",
                "ephemeral": True,
            },
        )
        context.state["key_context"] = new_key_context
        context.service("persist_state")(context.state)
        return ToolOutcome.completed(message)

    message = f"无效的 mode：{mode!r}；仅支持 compact、edit_key_context。"
    return ToolOutcome.failed("invalid_context_mode", message, content=message)


def _context_before_hooks(arguments: Mapping[str, Any]) -> tuple[str, ...]:
    if str(arguments.get("mode") or "compact").strip().lower() == "compact":
        return ("PreCompact",)
    return ()


async def _invoke_task(
    context: HostToolInvocationContext,
    arguments: Mapping[str, Any],
) -> ToolOutcome:
    from agent_subagent import run_subagent_task

    try:
        result = await context.service("await_steerable")(
            run_subagent_task(
                tool_args=dict(arguments),
                parent_session_id=context.session_id,
                parent_key_context=context.state.get("key_context", ""),
                emit=context.services.get("raw_emit"),
                parent_run_id=context.run_id,
            ),
            "tool_task",
        )
    except Exception as exc:
        if context.service("should_propagate_exception")(exc):
            raise
        message = f"subagent 执行异常：{exc}"
        return ToolOutcome.failed("subagent_error", message, content=message)
    return ToolOutcome.completed(
        result,
        metadata={"lifecycle_events": ["SubagentStop"]},
    )


def register_builtin_host_tools() -> None:
    if not host_tool_invokers.has("ask_user"):
        host_tool_invokers.register(
            "ask_user",
            _invoke_ask_user,
            policy=ToolExecutionPolicy(
                effect="control",
                interactive=True,
                early_stream_safe=False,
                interruptibility="cooperative",
            ),
            enabled=ask_user_enabled,
        )
    if not host_tool_invokers.has("context_manage"):
        host_tool_invokers.register(
            "context_manage",
            _invoke_context_manage,
            emit_pending=False,
            before_hooks=_context_before_hooks,
            policy=ToolExecutionPolicy(
                effect="control",
                early_stream_safe=False,
                interruptibility="cooperative",
            ),
        )
    if not host_tool_invokers.has("task"):
        host_tool_invokers.register(
            "task",
            _invoke_task,
            before_hooks=lambda _arguments: ("SubagentStart",),
            policy=ToolExecutionPolicy(effect="control", interruptibility="cooperative"),
        )


register_builtin_host_tools()


__all__ = ["register_builtin_host_tools"]
