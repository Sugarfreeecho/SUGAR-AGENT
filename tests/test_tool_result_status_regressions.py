import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest


# Import the pure adapters without starting the configured agent/application.
source = Path(__file__).resolve().parents[1] / "app/agent_loop.py"
sys.path.insert(0, str(source.parent)) if str(source.parent) not in sys.path else None
from tool_registry import ToolOutcome, ToolOutcomeKind
from tool_result_status import _tool_result_status as status, legacy_tool_outcome, tool_outcome_status


@pytest.mark.parametrize("tool,result", [
    ("terminal_read", '{"text":"timeout error: example", "truncated":false}'),
    ("read_file", '4716: def _tool_result_status():\n Error: Command timed out after 30\n Exit code: 1'),
    ("read_file", 'source code contains timeout, truncated, Error: and Exit code: 15'),
    ("run_shell", 'stdout mentions Error: example and timeout\nExit code: 0'),
    ("terminal_send", '{"waitReason":"timeout", "truncated":false, "command_state":"unknown"}'),
    ("read_file", '[lines 1-1 of 1]\n{"error": "data", "exit_code": 7}'),
    ("read_file", '{"error": false, "exit_code": 7, "timed_out": true}'),
    ("plugin_example", '{"error": "business data", "ok": false, "exit_code": 7, "timed_out": true}'),
    ("plugin_example", 'Error: this is returned data'),
    ("mcp_example", 'Regex error: documentation example'),
    ("run_shell", 'Error: Command timed out after 30 seconds\nExit code: 0'),
    ("grep", 'No matches found'),
    ("glob", 'No matching files found'),
    ("web_fetch", '{"ok":true, "error":false}'),
    ("web_fetch", '{"error":"", "text":"normal"}'),
])
def test_data_does_not_become_failure_timeout_or_truncation(tool, result):
    actual = status(tool, result)
    assert actual["ok"] is True and actual["truncated"] is False and actual["timed_out"] is False
    if tool == "run_shell":
        assert actual["exit_code"] == 0


@pytest.mark.parametrize("tool,result,expected", [
    ("run_shell", 'failed\nExit code: 7', {"ok": False, "exit_code": 7}),
    ("job_output", '{"job":{"exit_code":7}, "truncated":true}', {"ok": False, "exit_code": 7, "truncated": True}),
    ("run_shell", 'Error: Command timed out after 30 seconds\nExit code: 1', {"ok": False, "timed_out": True}),
    ("terminal_read", '{"truncated":true}', {"truncated": True}),
    ("read_file", 'Error: file not found', {"ok": False}),
    ("read_file", 'Failed to read file: not a file: missing.txt', {"ok": False}),
    ("write_file", 'Failed to write file: permission denied', {"ok": False}),
    ("edit_file", 'Failed to edit file: permission denied', {"ok": False}),
    ("ls", 'Failed to list directory: permission denied', {"ok": False}),
    ("glob", 'Glob search failed: invalid pattern', {"ok": False}),
    ("grep", 'Grep search failed: unavailable path', {"ok": False}),
    ("grep", 'Regex error: missing bracket', {"ok": False}),
    ("web_fetch", '{"error":"connection refused", "url":"https://example.test"}', {"ok": False}),
    ("job_output", '{"job":{"status":"failed", "exit_code":null}}', {"ok": False}),
    ("grep", 'a match\n... output truncated (100 lines shown)', {"truncated": True}),
])
def test_real_result_metadata_and_diagnostics_are_retained(tool, result, expected):
    actual = status(tool, result)
    for key, value in expected.items():
        assert actual[key] == value


@pytest.mark.parametrize("payload", [
    {"error": False}, {"error": "", "ok": True}, {"error": "business data"},
    {"ok": False, "exit_code": 7, "timed_out": True}, 'Error: example',
])
def test_explicit_completed_outcome_is_never_overridden_by_payload(payload):
    actual = tool_outcome_status(ToolOutcome.completed(payload))
    assert actual["ok"] is True and actual["timed_out"] is False
    assert "exit_code" not in actual and "code" not in actual


def test_explicit_failure_wins_over_payload_and_metadata():
    outcome = ToolOutcome.failed("provider_error", "connection failed", content={"ok": True},
        metadata={"tool_status": {"ok": True}})
    assert tool_outcome_status(outcome)["ok"] is False
    assert tool_outcome_status(outcome)["code"] == "provider_error"


@pytest.mark.parametrize("terminal,exit_code,failed", [
    ("completed", 0, False), ("failed", 7, True), ("timed_out", -1, True),
    ("interrupted", -1, False), ("unknown", None, False),
])
def test_shell_process_state_wins_over_stdout(terminal, exit_code, failed):
    outcome = legacy_tool_outcome("run_shell", 'Error: Command timed out after 30 seconds\nExit code: 7',
        execution_state={"status": terminal, "exit_code": exit_code})
    actual = tool_outcome_status(outcome)
    assert actual["ok"] is not failed
    assert actual["timed_out"] is (terminal == "timed_out")
    assert outcome.metadata["execution_status"] == terminal
    assert actual.get("exit_code") == exit_code


def test_background_start_and_terminal_wait_do_not_prove_failure():
    background = legacy_tool_outcome("run_shell", 'started background job job-1', execution_state={"status": "running"})
    assert background.kind is ToolOutcomeKind.COMPLETED
    assert "execution_status" not in background.metadata
    for wait in ("timeout", "inferred_idle"):
        outcome = legacy_tool_outcome("terminal_send", json.dumps({"waitReason": wait,
            "text": "Error: output from another command\nExit code: 7", "command_state": "unknown"}))
        assert outcome.kind is ToolOutcomeKind.COMPLETED
        assert not tool_outcome_status(outcome)["timed_out"]


def test_generic_response_uses_outcome_without_reclassifying_formatted_text():
    # Exercise the production response adapter, including formatting/truncation.
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_response_from_outcome")
    scope = dict(Any=Any, Dict=Dict, ToolOutcome=ToolOutcome, ToolOutcomeKind=ToolOutcomeKind,
        json=json, tool_outcome_status=tool_outcome_status, tool_name="plugin_example", tool_args={},
        tool_id="call-1", tool_call_index=0, state={}, _timing_ms=lambda _: 12,
        redact_sensitive_tool_text=lambda value: value, redact_sensitive_tool_obj=lambda value: value,
        _wrap_read_only_tool_output_lines=lambda value: value,
        _tool_result_details_for_views=lambda value, *_: (value, value, value))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
    response = scope["_response_from_outcome"]
    for payload in ({"error": False}, {"error": "business data"}, "Error: example", None):
        actual = response(ToolOutcome.completed(payload), 0, json_output=True)
        assert actual["tool_failed"] is False and actual["tool_status"]["ok"] is True
        assert actual["result"] != "Error: "
    actual = response(legacy_tool_outcome("read_file", "Failed to read file: missing"), 0)
    assert actual["tool_failed"] is True and actual["tool_status"]["code"] == "legacy_tool_error"
