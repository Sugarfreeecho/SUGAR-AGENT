"""Tool status adapters. Payload data is never a source-independent status."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from tool_registry import ToolOutcome, ToolOutcomeKind


# Only these host-owned legacy APIs define status fields in their result JSON.
_RESULT_ENVELOPES = {
    "run_shell", "web_fetch", "web_download", "job_output", "job_list", "job_kill",
    "terminal_open", "terminal_send", "terminal_read", "terminal_signal",
    "terminal_close", "terminal_list",
}
_TEXT_DIAGNOSTICS = {
    "read_file": r"Failed to read file:|File appears (?:to be|binary)",
    "write_file": r"Failed to write file:",
    "edit_file": r"Failed to edit file:|Regex error:",
    "ls": r"Failed to list directory:",
    "glob": r"Glob search failed:",
    "grep": r"Grep search failed:|Regex error:",
    "run_shell": r"Error executing command:",
    "delete_file": "",
    "apply_patch": "",
    "web_search": "",
    "web_fetch": "",
    "web_download": "",
    "activate_skill": "",
}


def _structured_tool_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, str) and result.lstrip().startswith("{"):
        try:
            value = json.loads(result)
            if isinstance(value, dict):
                return value
        except (ValueError, TypeError):
            pass
    return {}


def _tool_result_exit_code(tool_name: str, result: Any) -> Optional[int]:
    if tool_name not in {"run_shell", "job_output"}:
        return None
    value = _structured_tool_result(result)
    code = value.get("exit_code")
    if code is None and isinstance(value.get("job"), dict):
        code = value["job"].get("exit_code")
    if isinstance(code, int) and not isinstance(code, bool):
        return code
    if tool_name == "run_shell" and not value:
        matches = list(re.finditer(r"(?mi)^Exit code:\s*(-?\d+)\s*$", str(result or "")))
        if matches:
            return int(matches[-1].group(1))
    return None


def _tool_result_status(
    tool_name: str,
    result: Any,
    *,
    failed: Optional[bool] = None,
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Compatibility for known legacy host results, never arbitrary plugins."""
    text = result.strip() if isinstance(result, str) else ""
    value = _structured_tool_result(result) if tool_name in _RESULT_ENVELOPES else {}
    code = _tool_result_exit_code(tool_name, result)
    # A shell stdout line is not a timeout. In the legacy format the host adds
    # its timeout diagnostic immediately before its final exit-code footer.
    timed_out = tool_name == "run_shell" and (value.get("timed_out") is True or (code != 0 and bool(re.search(
        r"(?mi)^Error: Command timed out after \d[^\n]*\nExit code:\s*(?:-?\d+|unknown)\s*$", text))))
    truncated = value.get("truncated") is True
    if not value and tool_name in {"read_file", "grep", "run_shell"}:
        truncated = bool(re.search(r"(?m)^(?:\[output truncated;|\.\.\. output truncated|\.\.\. \[truncated,)", text))
    status: Dict[str, Any] = {"ok": True, "truncated": truncated, "timed_out": timed_out,
                              "source": "legacy_result"}
    if timed_out:
        status.update(ok=False, code="command_timed_out")
    elif value.get("ok") is False or (value.get("ok") is not True and value.get("error")):
        status.update(ok=False, code="tool_reported_error")
    elif tool_name == "job_output" and isinstance(value.get("job"), dict) and value["job"].get("status") == "failed":
        status.update(ok=False, code="job_failed")
    elif code is not None:
        status.update(ok=code == 0, source="exit_code")
        if code != 0:
            status["code"] = "nonzero_exit_code"
    elif tool_name in _TEXT_DIAGNOSTICS and re.match(
        r"(?i)^(?:Error\s*:" + ("|" + _TEXT_DIAGNOSTICS[tool_name] if _TEXT_DIAGNOSTICS[tool_name] else "") + r")", text
    ):
        status.update(ok=False, code="legacy_tool_error", source="legacy_diagnostic")
    if failed is not None:
        status["ok"] = not failed
        status["source"] = "explicit"
        if failed:
            status.setdefault("code", "explicit_failure")
        if not failed:
            status["timed_out"] = False
            status.pop("code", None)
    if code is not None:
        status["exit_code"] = code
    if duration_ms is not None:
        status["duration_ms"] = max(0, int(duration_ms))
    return status


def _tool_result_indicates_failure(tool_name: str, result: Any) -> bool:
    return not _tool_result_status(tool_name, result)["ok"]


def legacy_tool_outcome(tool_name: str, result: Any, *, execution_state=None) -> ToolOutcome:
    """Adapt a host API at its boundary, before generic rendering/truncation."""
    state = execution_state or {}
    terminal = str(state.get("status") or "")
    metadata = {}
    if terminal in {"completed", "failed", "timed_out", "interrupted", "unknown"}:
        status = {"ok": terminal not in {"failed", "timed_out"}, "timed_out": terminal == "timed_out",
                  "truncated": _tool_result_status(tool_name, result)["truncated"], "source": "execution_state"}
        code = state.get("exit_code")
        if isinstance(code, int) and not isinstance(code, bool):
            status["exit_code"] = code
        if not status["ok"]:
            status["code"] = "command_timed_out" if status["timed_out"] else "command_failed"
        metadata["execution_status"] = terminal
    else:
        status = _tool_result_status(tool_name, result)
    metadata["tool_status"] = status
    if not status["ok"]:
        return ToolOutcome.failed(status["code"], "Tool reported an execution failure", content=result, metadata=metadata)
    return ToolOutcome.completed(result, metadata=metadata)


def tool_outcome_status(outcome: ToolOutcome, *, duration_ms=None) -> Dict[str, Any]:
    """An explicit outcome always wins over payload fields and text."""
    status = {"ok": True, "truncated": False, "timed_out": False, "source": "tool_outcome"}
    status.update(outcome.metadata.get("tool_status") or {})
    status["ok"] = outcome.kind is not ToolOutcomeKind.FAILED
    if not status["ok"]:
        status["code"] = outcome.code
    else:
        status["timed_out"] = False
        status.pop("code", None)
    if duration_ms is not None:
        status["duration_ms"] = max(0, int(duration_ms))
    return status
