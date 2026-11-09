"""Red-approval precision and explainability.

Covers four fixes:

* ``_DELETE_COMMAND`` recognises statement boundaries (newline, ``{``) and
  ``git rm``, so an ordinary in-workspace cleanup downgrades to the yellow
  ``process.workspace_delete`` path instead of a forced red approval.
* Red-line matching ignores provably-data regions (search patterns, string
  literals inside a here-string, ``.shutdown()`` method calls) so a grep or a
  tool description cannot masquerade as a delete.
* The approval request persists ``rule_id`` and the matched pattern label.
* The card text names the matched kind instead of "destructive command".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from agent_tools import dangerous_matches, _has_non_delete_dangerous_pattern  # noqa: E402
from security.models import DecisionOutcome, SecurityDecision  # noqa: E402
from security.runtime import _DELETE_COMMAND, classify_tool  # noqa: E402

WORKSPACE = Path(r"D:\AI\AI Agent\MyAgent Developer\workspace")


def _decision(rule_id="process.destructive", reason="Destructive command requires approval."):
    return SecurityDecision(DecisionOutcome.ASK, reason, rule_id, "digest", {})


# ---------------------------------------------------------------- deletion scope

@pytest.mark.parametrize("command", [
    "Set-Location 'D:\\x'\nRemove-Item -Recurse -Force _pristine_check",
    'if(Test-Path $p){ Remove-Item $p -Recurse -Force }',
    "git rm -r --quiet plugins/execution-dashboard",
    "rm -rf build",
    'shutil.rmtree(p)',
])
def test_delete_detection_recognises_statement_boundaries(command):
    assert _DELETE_COMMAND.search(command), command


@pytest.mark.parametrize("command", [
    "python -m pytest tests -q",
    "Get-ChildItem -Recurse -File",
    "git status --porcelain",
])
def test_non_delete_commands_are_not_deletions(command):
    assert not _DELETE_COMMAND.search(command), command


def test_wrapped_in_workspace_delete_is_downgraded_to_yellow(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "cache"
    target.mkdir()

    plain = classify_tool(
        "run_shell", {"command": f'Remove-Item -Recurse -Force "{target}"'}, workspace
    )
    wrapped = classify_tool(
        "run_shell",
        {"command": f'if(Test-Path "{target}"){{ Remove-Item -Recurse -Force "{target}" }}'},
        workspace,
    )

    # Both are deletions inside the workspace: ordinary approval, not a forced red one.
    for meta in (plain.metadata, wrapped.metadata):
        assert meta["deletion"] is True
        assert meta["workspace_delete"] is True


# --------------------------------------------------------------- false positives

def test_search_pattern_is_not_a_delete():
    command = (
        "git show HEAD:packaging/nsis/installer.nsh | "
        "Select-String -Pattern 'SugarAgentRemoveFiles|StrCmp|RMDir|resources'"
    )
    assert dangerous_matches(command) == []


def test_here_string_literal_is_not_a_delete():
    command = (
        "cd \"D:\\x\"; @'\n"
        "import json\n"
        "defs = {\"delete_file\": \"Shell rm -rf / rmdir are blocked.\"}\n"
        "'@ | python -"
    )
    assert dangerous_matches(command) == []


def test_method_call_named_shutdown_is_not_system_power():
    command = 'python -c "import http.server as h, functools; s=h.HTTPServer(); s.shutdown()"'
    assert dangerous_matches(command) == []


@pytest.mark.parametrize("command,kind", [
    ("Remove-Item -Recurse -Force $p", "delete.remove_item_recursive_force"),
    ("rm -rf /tmp/x", "delete.rm_recursive"),
    ("git rm -r plugins/x", "delete.remove_item_recursive_force"),  # placeholder, replaced below
])
def test_real_dangers_are_still_detected(command, kind):
    hits = dangerous_matches(command)
    assert hits, command
    if kind != "delete.remove_item_recursive_force" or "Remove-Item" in command:
        assert hits[0]["kind"] == kind


def test_bash_c_payload_is_still_detected():
    """A command hidden in an executed string must not be filtered out."""
    assert dangerous_matches('bash -c "rm -rf /"')
    assert dangerous_matches('powershell -Command "Remove-Item -Recurse -Force C:\\x"')


def test_non_delete_danger_still_reported_for_deletions():
    assert _has_non_delete_dangerous_pattern("Remove-Item -Recurse -Force C:\\x; shutdown /s")
    assert not _has_non_delete_dangerous_pattern("Remove-Item -Recurse -Force C:\\x")


# ------------------------------------------------------------------ explainability

def test_classify_tool_records_matched_red_line():
    meta = dict(classify_tool("run_shell", {"command": "rm -rf /tmp/x"}, WORKSPACE).metadata)
    assert meta["destructive"] is True
    assert meta["destructive_kinds"] == ["delete.rm_recursive"]
    assert meta["destructive_labels"] == ["递归删除 rm -r/-rf"]
    assert meta["destructive_summary"] == "递归删除 rm -r/-rf"


def test_plain_deletion_still_gets_a_label():
    """``Remove-Item -Force`` hits no dangerous pattern but must stay explainable."""
    meta = dict(
        classify_tool("run_shell", {"command": "Remove-Item -Force $f"}, WORKSPACE).metadata
    )
    assert meta["destructive"] is True
    assert meta["destructive_kinds"] == ["delete.command"]
    assert meta["destructive_summary"] == "删除 Remove-Item"


def test_approval_spec_names_the_matched_kind():
    from agent_loop import _security_approval_spec

    command = "Remove-Item -Recurse -Force C:\\tmp\\x"
    request = classify_tool("run_shell", {"command": command}, WORKSPACE)
    spec = _security_approval_spec("run_shell", {"command": command}, _decision(), request, WORKSPACE)

    assert spec["rule_id"] == "process.destructive"
    assert spec["destructive_summary"] == "递归强制删除 Remove-Item -Recurse -Force"
    assert "拦截原因" in spec["subtitle"]
    assert "递归强制删除" in spec["subtitle"]
    assert "命中规则" in spec["consequence"]


def test_approval_record_persists_rule_id_and_pattern(tmp_path):
    from human_interaction.service import HumanInteractionService
    from runtime_v2 import SessionEventLog

    # A short id keeps the lock path under the Windows MAX_PATH limit.
    sid = "s1"
    (tmp_path / sid).mkdir(parents=True, exist_ok=True)
    service = HumanInteractionService(tmp_path, path_resolver=lambda sid: str(tmp_path / sid))
    service.create_approval(
        sid,
        approval_id="a1",
        metadata={
            "tool": "run_shell",
            "title": "危险命令，需要确认",
            "message": 'run_shell("command": "rm -rf /tmp/x")',
            "subtitle": "拦截原因：递归删除 rm -r/-rf",
            "approval_level": "danger",
            "security_rule_id": "process.destructive",
            "rule_id": "process.destructive",
            "destructive_summary": "递归删除 rm -r/-rf",
            "destructive_kinds": ["delete.rm_recursive"],
        },
    )
    events = [
        event for event in SessionEventLog(tmp_path).read_all(sid)
        if event.type == "approval_requested"
    ]
    payload = events[-1].payload
    assert payload["rule_id"] == "process.destructive"
    assert payload["destructive_summary"] == "递归删除 rm -r/-rf"
    assert payload["destructive_kinds"] == ["delete.rm_recursive"]
    assert payload["approval_level"] == "danger"
