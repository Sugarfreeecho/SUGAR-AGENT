"""Durable execution drafts, independent of provider message history.

The journal appends small updates to the existing event log. It does not write
a snapshot for every token, and UI indexes never include these update events.
"""
from __future__ import annotations

import copy
import json
import threading
from typing import Any

from .event_log import SessionEventLog
from .event_schema import now_iso


EVENT_TYPE = "execution_recorded"
TERMINAL = {"completed", "failed", "timed_out", "interrupted", "unknown"}
STREAM_TYPES = {
    "llm_reasoning_delta", "llm_response_delta", "tool_call_delta",
    "tool_pending", "tool_command_delta", "tool_call", "tool_execution_state",
    "llm_reasoning", "llm_response",
    "approval_requested", "interaction_requested",
}


def apply_execution_update(records: dict, payload: dict, seq: int = 0) -> dict | None:
    identity = str(payload.get("execution_id") or "")
    if not identity:
        return None
    row = records.setdefault(identity, {"execution_id": identity, "first_runtime_seq": seq})
    if seq and seq <= int(row.get("last_runtime_seq") or 0):
        return row
    prior_status = row.get("status")
    already_started = bool(row.get("executed"))
    for key, value in payload.items():
        if key not in {"text_delta", "name_delta", "arguments_delta", "output_delta", "stdout_delta", "stderr_delta"}:
            row[key] = copy.deepcopy(value)
    for delta_key, target in (("text_delta", "content"), ("name_delta", "tool"),
                              ("arguments_delta", "arguments_raw"), ("output_delta", "output"),
                              ("stdout_delta", "stdout"), ("stderr_delta", "stderr")):
        if delta_key in payload:
            row[target] = str(row.get(target) or "") + str(payload[delta_key] or "")
    row["last_runtime_seq"] = seq
    if already_started:
        row["executed"] = True
    if prior_status in TERMINAL and payload.get("status") not in TERMINAL:
        row["status"] = prior_status
    elif payload.get("status") == "generating" and prior_status and prior_status != "generating":
        row["status"] = prior_status
    return row


class ExecutionJournal:
    _guard = threading.RLock()
    _cache: dict[str, dict] = {}
    _session_locks: dict[str, threading.RLock] = {}

    def __init__(self, root, path_resolver=None):
        self.log = SessionEventLog(root, path_resolver=path_resolver)

    def _session_lock(self, session_id: str):
        key = str(self.log.event_path(session_id).resolve())
        with self._guard:
            return self._session_locks.setdefault(key, threading.RLock())

    def _state(self, session_id: str) -> dict:
        key = str(self.log.event_path(session_id).resolve())
        with self._guard:
            state = self._cache.get(key)
        latest = self.log.next_seq(session_id) - 1
        try:
            stat = self.log.event_path(session_id).stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            signature = None
        if (state is None or state["seq"] > latest
                or (state["seq"] == latest and state.get("signature") != signature)):
            state = {"seq": 0, "records": {}, "group": "legacy:0", "turn": "", "revision": 0,
                     "last_final_seq": 0, "ui_ids": {}, "boundaries": []}
            with self._guard:
                if len(self._cache) >= 64:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[key] = state
        elif state["seq"] == latest and state.get("signature") == signature:
            return state
        for event in self.log.read_after_seq(session_id, state["seq"],
                                             end_offset=signature[1] if signature else 0):
            payload = event.payload or {}
            if event.type in {"message_user", "user_turn_committed"} and payload.get("ui_type") != "user_steer":
                state["turn"] = str(event.seq)
                state["group"] = "turn:" + str(event.seq)
                state["boundaries"].append((event.seq, "user"))
            elif event.type in {"assistant_final_committed", "message_assistant_final"}:
                state["group"] = "after-final:" + str(event.seq)
                state["last_final_seq"] = event.seq
                state["boundaries"].append((event.seq, "final"))
            elif event.type == EVENT_TYPE:
                apply_execution_update(state["records"], payload, event.seq)
            elif event.type in {"approval_requested", "interaction_requested"} and payload.get("execution_id"):
                row = state["records"].get(payload["execution_id"])
                if row and row.get("status") not in TERMINAL:
                    apply_execution_update(state["records"], {"execution_id": row["execution_id"],
                        "status": "waiting_approval" if event.type == "approval_requested" else "waiting_input",
                        "request_digest": payload.get("request_digest")}, event.seq)
            elif event.type in {"message_deleted", "message_rewritten", "visible_range_changed",
                                "legacy_truncate_observed", "runtime_snapshot_compacted", "history_branch_created"}:
                state["revision"] = event.seq
                if event.type == "message_deleted":
                    identity = state["ui_ids"].get(int(payload.get("target_seq") or 0))
                    if identity:
                        state["records"].pop(identity, None)
                if event.type == "visible_range_changed" and payload.get("to_seq") is not None:
                    end = int(payload["to_seq"])
                    state["records"] = {key: value for key, value in state["records"].items()
                                        if int(value.get("first_runtime_seq") or 0) <= end}
                    state["boundaries"] = [item for item in state["boundaries"] if item[0] <= end]
                    boundary_seq, boundary_kind = state["boundaries"][-1] if state["boundaries"] else (0, "legacy")
                    state["group"] = ("turn:" if boundary_kind == "user" else "after-final:" if boundary_kind == "final" else "legacy:") + str(boundary_seq)
                    state["last_final_seq"] = max((seq for seq, kind in state["boundaries"] if kind == "final"), default=0)
                    state["turn"] = str(max((seq for seq, kind in state["boundaries"] if kind == "user"), default=0))
                if event.type == "legacy_truncate_observed" and payload.get("before_index") == 0:
                    state["records"].clear()
                    state.update(group="legacy:0", turn="", last_final_seq=0, boundaries=[])
                if event.type == "runtime_snapshot_compacted":
                    baseline = payload.get("snapshot") or {}
                    state["records"] = copy.deepcopy(baseline.get("executions") or {})
                    state["boundaries"] = []
                    for ui in payload.get("ui_events") or []:
                        seq = int(ui.get("runtime_seq") or 0)
                        if ui.get("execution_id") and seq:
                            state["ui_ids"][seq] = ui["execution_id"]
                        if ui.get("type") in {"user", "final"} and seq:
                            state["boundaries"].append((seq, "user" if ui["type"] == "user" else "final"))
                    if state["boundaries"]:
                        seq, kind = state["boundaries"][-1]
                        state["group"] = ("turn:" if kind == "user" else "after-final:") + str(seq)
                        state["last_final_seq"] = max((seq for seq, kind in state["boundaries"] if kind == "final"), default=0)
                        state["turn"] = str(max((seq for seq, kind in state["boundaries"] if kind == "user"), default=0))
            if event.type != EVENT_TYPE and payload.get("execution_id"):
                state["ui_ids"][event.seq] = payload["execution_id"]
                row = state["records"].get(payload["execution_id"])
                if row and event.type not in {"approval_requested", "interaction_requested"}:
                    row["ui_runtime_seq"] = event.seq
            state["seq"] = event.seq
        state["signature"] = signature
        return state

    def read(self, session_id: str) -> dict:
        with self._session_lock(session_id):
            state = self._state(session_id)
            return {"last_runtime_seq": state["seq"], "projection_revision": state["revision"],
                    "last_final_seq": state["last_final_seq"],
                    "process_group_id": state["group"],
                    "execution_records": copy.deepcopy(list(state["records"].values()))}

    def record(self, session_id: str, event: dict) -> dict:
        if event.get("_subagent_forward"):
            return event
        kind = str(event.get("type") or "")
        if kind not in STREAM_TYPES and kind not in {"llm_stream_aborted", "run_interrupted", "run_failed"}:
            return event
        with self.log.session_transaction(session_id), self._session_lock(session_id):
            state = self._state(session_id)
            run = str(event.get("run_id") or "legacy")
            attempt = str(event.get("stream_seq") or event.get("react_iter") or "0")
            base = {"process_group_id": event.get("process_group_id") or state["group"],
                    "turn_id": state["turn"], "run_id": run, "attempt_id": attempt,
                    "react_iter": event.get("react_iter"), "stream_seq": event.get("stream_seq"),
                    "updated_at": now_iso()}
            if kind in {"llm_stream_aborted", "run_interrupted", "run_failed"}:
                for row in list(state["records"].values()):
                    if row.get("run_id") == run and row.get("status") not in TERMINAL:
                        if event.get("reason") in {"output_length", "truncated_after_closed_tool_call", "transport_after_closed_tool_call"} and row.get("status") != "generating":
                            continue
                        self._append(session_id, state, {
                            "execution_id": row["execution_id"],
                            "status": "unknown" if kind == "run_failed" and row.get("executed") else "interrupted",
                            "reason": event.get("reason") or kind,
                        }, run)
                event["preserve_execution_records"] = True
                event["cleanup_scope"] = "none"
                return event
            tool_id = str(event.get("tool_call_id") or event.get("id") or "")
            is_tool = kind.startswith("tool_") or kind in {"approval_requested", "interaction_requested"}
            category = "tool" if is_tool else "reasoning" if "reasoning" in kind else "response"
            row = state["records"].get(str(event.get("execution_id") or ""))
            if is_tool and tool_id:
                row = row or next((r for r in reversed(list(state["records"].values()))
                            if r.get("tool_call_id") == tool_id and r.get("run_id") == run
                            and r.get("attempt_id") == attempt), None)
            if row is None and is_tool and kind != "tool_call_delta":
                index = event.get("tool_call_index")
                row = next((r for r in reversed(list(state["records"].values()))
                            if r.get("kind") == "tool" and r.get("run_id") == run
                            and r.get("attempt_id") == attempt
                            and r.get("react_iter") == event.get("react_iter")
                            and r.get("tool_call_index") == index and not r.get("tool_call_id")), None)
            index = event.get("tool_call_index", event.get("index", 0))
            identity = (row or {}).get("execution_id") or event.get("execution_id") or f"{run}:{category}:{attempt}:{index}"
            occupied = state["records"].get(identity, {})
            if is_tool and tool_id and occupied.get("tool_call_id") not in {None, "", tool_id}:
                # Non-streaming providers need not supply call indexes. Two
                # complete calls in the same request must still remain distinct.
                identity = f"{run}:{category}:{attempt}:call:{tool_id}"
            update = {**base, "execution_id": identity, "kind": category}
            prior = state["records"].get(identity, {})
            if event.get("delta_seq") is not None:
                delta_seq = int(event["delta_seq"])
                # Argument and shell-output counters both start at 1. They
                # belong to different streams even for the same execution.
                counter = "last_" + kind + "_delta_seq"
                if delta_seq <= int(prior.get(counter) or 0):
                    event.update(execution_id=identity, process_group_id=prior.get("process_group_id"),
                                 execution_runtime_seq=prior.get("last_runtime_seq"))
                    return event
                update[counter] = delta_seq
            update["started_at"] = prior.get("started_at") or now_iso()
            if tool_id:
                update["tool_call_id"] = tool_id
            if is_tool:
                update["tool_call_index"] = index
                if kind == "tool_call_delta":
                    update.update(status="generating", name_delta=event.get("name_delta", ""),
                                  arguments_delta=event.get("arguments_delta", ""))
                elif kind == "tool_command_delta":
                    update.update(output_delta=event.get("delta", ""), executed=True, status="running")
                    channel = "stderr" if event.get("stream") == "stderr" else "stdout"
                    update[channel + "_delta"] = event.get("raw_delta", event.get("delta", ""))
                elif kind in {"approval_requested", "interaction_requested"}:
                    update.update(status="waiting_approval" if kind == "approval_requested" else "waiting_input")
                elif kind == "tool_execution_state":
                    update.update(status=event.get("status", "running"), executed=event.get("executed", False))
                    update.update({key: event[key] for key in
                        ("result", "stdout", "stderr", "process_state", "exit_code", "duration_ms") if key in event})
                elif kind == "tool_pending":
                    update.update(status="waiting_execution", tool=event.get("tool"), args=event.get("args"),
                                  command_preview=event.get("command_preview"), executed=False)
                else:
                    result = event.get("raw_content", event.get("result", ""))
                    status = event.get("execution_status") or (
                        "timed_out" if (event.get("status") or {}).get("timed_out") else
                        "failed" if (event.get("status") or {}).get("ok") is False else "completed")
                    update.update(status=status, tool=event.get("tool"), args=event.get("args", event.get("tool_args")),
                                  result=result, ui_committed=True, command_preview=event.get("command_preview"),
                                  attachments=event.get("attachments", []),
                                  duration_ms=(event.get("status") or {}).get("duration_ms"))
            elif kind.endswith("_delta"):
                update.update(status="generating", text_delta=event.get("delta", ""))
            else:
                # Final events often omit stream_seq. Upgrade the matching live
                # attempt instead of creating a second reasoning/response row.
                match = next((r for r in reversed(list(state["records"].values()))
                              if r.get("kind") == category and r.get("run_id") == run
                              and r.get("react_iter") == event.get("react_iter")
                              and (event.get("stream_seq") is None or r.get("stream_seq") == event.get("stream_seq"))), None)
                if match:
                    identity = update["execution_id"] = match["execution_id"]
                content = event.get("content", "")
                received = (match or {}).get("content")
                if received is not None and str(received).strip() == str(content).strip():
                    content = received
                elif received is not None:
                    update["received_content"] = received
                update.update(status=event.get("execution_status", "completed"), content=content, ui_committed=True)
            prior = state["records"].get(identity, {})
            if (kind == "tool_call" and prior.get("ui_committed")
                    and all(prior.get(key) == update.get(key) for key in
                            ("status", "result", "tool", "args", "attachments"))):
                event.update(execution_id=identity, process_group_id=prior.get("process_group_id"),
                             attempt_id=attempt, execution_runtime_seq=prior.get("last_runtime_seq"))
                return event
            saved = self._append(session_id, state, update, run)
            event.update(execution_id=identity, process_group_id=update["process_group_id"],
                         attempt_id=attempt, execution_runtime_seq=saved.seq)
            return event

    def _append(self, session_id, state, update, run):
        event = self.log._append_unlocked(session_id, EVENT_TYPE, update, run_id=run)
        apply_execution_update(state["records"], update, event.seq)
        state["seq"] = event.seq
        stat = self.log.event_path(session_id).stat()
        state["signature"] = (stat.st_mtime_ns, stat.st_size)
        return event

    def anchor(self, session_id: str, tool_call_id: str, run_id: str = "") -> dict:
        """Return durable ownership for a separately persisted human request."""
        with self._session_lock(session_id):
            rows = self._state(session_id)["records"].values()
            row = next((r for r in reversed(list(rows)) if r.get("tool_call_id") == tool_call_id
                        and (not run_id or r.get("run_id") == run_id)), {})
            return {key: row[key] for key in ("execution_id", "process_group_id", "turn_id") if key in row}

    def uncertain_execution(self, session_id: str, tool: str, arguments: dict) -> str:
        with self._session_lock(session_id):
            for row in self._state(session_id)["records"].values():
                if (row.get("kind") == "tool" and row.get("tool") == tool
                        and row.get("args") == arguments and row.get("executed")
                        and row.get("status") in {"unknown", "interrupted"}
                        and row.get("process_state") != "stopped"):
                    return row["execution_id"]
        return ""

    def checkpoint_continuation(self, session_id: str, run_id: str, state: dict,
                                *, status="generating") -> None:
        with self.log.session_transaction(session_id), self._session_lock(session_id):
            current = self._state(session_id)
            self._append(session_id, current, {"execution_id": current["group"] + ":continuation",
                "kind": "continuation", "process_group_id": current["group"], "run_id": run_id,
                "status": status, "extra_requests": int(state.get("_output_length_retries") or 0),
                "content": str(state.get("_output_continuation") or ""), "updated_at": now_iso()}, run_id)


def interrupted_tool_text(record: dict | None, *, reason="user_steer") -> str:
    row = record or {}
    executed = bool(row.get("executed"))
    lines = ["工具调用已被用户追问打断。" if reason == "user_steer" else "工具调用在运行恢复前未完成。",
             "工具已开始执行；仅以下输出和进度已确认。" if executed else "工具尚未开始执行。"]
    if executed:
        lines.append("进程已确认停止。" if row.get("process_state") == "stopped"
                     else "停止状态尚未确认，请核实外部状态后再决定是否重复执行。")
    if row.get("output"):
        lines.extend(["已收到的输出：", str(row["output"])])
    if row.get("duration_ms") is not None:
        lines.append(f"已记录耗时：{row['duration_ms']} ms。")
    return "\n".join(lines)


def close_unfinished_calls(messages: list, records: list, *, reason="user_steer") -> tuple[list, list]:
    from agent_messages import AssistantMessage, ToolMessage
    by_id = {r.get("tool_call_id"): r for r in records if r.get("tool_call_id")}
    out, added = [], []
    i = 0
    while i < len(messages):
        message = messages[i]
        out.append(message)
        i += 1
        if not isinstance(message, AssistantMessage) or not message.tool_calls:
            continue
        results = []
        while i < len(messages) and isinstance(messages[i], ToolMessage):
            results.append(messages[i])
            i += 1
        seen = {r.tool_call_id for r in results}
        for call in message.tool_calls:
            identity = str(call.get("id") or "")
            if identity and identity not in seen:
                record = by_id.get(identity)
                text = (record or {}).get("result") or interrupted_tool_text(record, reason=reason)
                result = ToolMessage(content=text, tool_call_id=identity)
                results.append(result)
                added.append(result)
        out.extend(results)
    return out, added


def merge_continuation(prefix: str, suffix: str) -> str:
    if not prefix:
        return suffix
    if suffix.startswith(prefix):
        return suffix
    # A single matching letter/punctuation is not evidence of repeated text.
    for size in range(min(len(prefix), len(suffix)), 3, -1):
        if prefix[-size:] == suffix[:size]:
            return prefix + suffix[size:]
    return prefix + suffix


def register_output_continuation(state: dict, content: str, *, tool_drafts: bool,
                                 max_extra_requests: int = 2) -> tuple[int, bool]:
    """Count requests for one logical generation, including mixed tool turns."""
    attempt = int(state.get("_output_length_retries") or 0) + 1
    state["_output_length_retries"] = attempt
    if not tool_drafts:
        state["_output_continuation"] = merge_continuation(
            str(state.get("_output_continuation") or ""), content)
    return attempt, attempt <= max(0, max_extra_requests)


def execution_progress_note(records: list, *, reason: str) -> str:
    """Provider-neutral progress when reasoning/drafts are not API messages."""
    parts = []
    for row in records:
        if row.get("kind") == "reasoning" and row.get("status") != "completed":
            parts.append("已收到的思考进度：" + str(row.get("content") or ""))
        elif row.get("kind") == "tool" and "args" not in row and row.get("arguments_raw"):
            parts.append(f"未执行的参数草稿（{row.get('tool') or '工具'}）：{row['arguments_raw']}")
    return (f"[生成中断：{reason}。以下片段已保留；参数草稿未执行，必须重新生成完整调用。]\n"
            + "\n".join(parts)) if parts else ""


def response_tool_drafts(response) -> list[dict]:
    """Keep raw non-streaming arguments before the parser normalizes them."""
    def value(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    choices = value(response, "choices", []) or []
    if not choices:
        return []
    message = value(choices[0], "message", {})
    rows = []
    for index, call in enumerate(value(message, "tool_calls", []) or []):
        function = value(call, "function", {})
        arguments = value(function, "arguments", "")
        rows.append({"type": "tool_call_delta", "index": index, "id": value(call, "id", ""),
                     "name_delta": value(function, "name", ""),
                     "arguments_delta": arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False),
                     "ephemeral": True})
    return rows
