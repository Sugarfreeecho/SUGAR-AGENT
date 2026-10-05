import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

import pytest


# Load the status seam without starting the configured agent/application.
source = Path(__file__).resolve().parents[1] / "app/agent_loop.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
names = {"_structured_tool_result", "_tool_result_exit_code", "_tool_result_indicates_failure", "_tool_result_status"}
module = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
scope = dict(json=json, re=re, Any=Any, Dict=Dict, Optional=Optional)
exec(compile(module, str(source), "exec"), scope)
status = scope["_tool_result_status"]


@pytest.mark.parametrize("tool,result", [
    ("terminal_read", '{"text":"timeout error: example", "truncated":false}'),
    ("read_file", '4716: def _tool_result_status():\n Error: Command timed out after 30\n Exit code: 1'),
    ("read_file", 'source code contains timeout, truncated, Error: and Exit code: 15'),
    ("run_shell", 'stdout mentions Error: example and timeout\nExit code: 0'),
    ("terminal_send", '{"waitReason":"timeout", "truncated":false, "command_state":"unknown"}'),
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
    ("grep", 'a match\n... output truncated (100 lines shown)', {"truncated": True}),
])
def test_real_result_metadata_and_diagnostics_are_retained(tool, result, expected):
    actual = status(tool, result)
    for key, value in expected.items():
        assert actual[key] == value
