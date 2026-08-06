from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_file_audit_ignores_legacy_full_snapshot_switch(tmp_path, monkeypatch):
    import runtime_observability as obs

    monkeypatch.delenv("FILE_AUDIT_MODE", raising=False)
    monkeypatch.setenv("FILE_AUDIT_FULL_SNAPSHOT", "1")

    def fail_git(*args, **kwargs):
        raise AssertionError("git must not run when file audit is off")

    monkeypatch.setattr(obs, "_git_output", fail_git)
    before = obs.capture_workspace_state(tmp_path)
    (tmp_path / "generated.bin").write_bytes(b"new")
    after = obs.capture_workspace_state(tmp_path)

    assert before == {"root": "", "files": {}}
    assert after == {"root": "", "files": {}}
    assert obs.diff_workspace_states(before, after) == []


def test_file_audit_defaults_to_off(tmp_path, monkeypatch):
    import runtime_observability as obs

    monkeypatch.delenv("FILE_AUDIT_MODE", raising=False)

    def fail_git(*args, **kwargs):
        raise AssertionError("git must not run when file audit is off")

    monkeypatch.setattr(obs, "_git_output", fail_git)
    before = obs.capture_workspace_state(tmp_path)
    (tmp_path / "generated.bin").write_bytes(b"new")
    after = obs.capture_workspace_state(tmp_path)

    assert before == {"root": "", "files": {}}
    assert after == {"root": "", "files": {}}
    assert obs.diff_workspace_states(before, after) == []


def test_file_audit_mode_off_disables_audit(tmp_path, monkeypatch):
    import runtime_observability as obs

    monkeypatch.setenv("FILE_AUDIT_MODE", "off")

    def fail_git(*args, **kwargs):
        raise AssertionError("git must not run when file audit is off")

    monkeypatch.setattr(obs, "_git_output", fail_git)
    before = obs.capture_workspace_state(tmp_path)
    (tmp_path / "generated.bin").write_bytes(b"new")
    after = obs.capture_workspace_state(tmp_path)

    assert before == {"root": "", "files": {}}
    assert after == {"root": "", "files": {}}
    assert obs.diff_workspace_states(before, after) == []


def test_file_audit_mode_git_detects_untracked_changes(tmp_path, monkeypatch):
    import runtime_observability as obs
    import subprocess

    monkeypatch.setenv("FILE_AUDIT_MODE", "git")
    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    before = obs.capture_workspace_state(tmp_path)
    (tmp_path / "generated.bin").write_bytes(b"new")
    after = obs.capture_workspace_state(tmp_path)

    assert {
        (row["path"], row["operation"])
        for row in obs.diff_workspace_states(before, after)
    } == {("generated.bin", "created")}


def test_file_audit_mode_full_walks_non_git_workspace(tmp_path, monkeypatch):
    import runtime_observability as obs

    monkeypatch.setenv("FILE_AUDIT_MODE", "full")
    before = obs.capture_workspace_state(tmp_path)
    (tmp_path / "generated.bin").write_bytes(b"new")
    after = obs.capture_workspace_state(tmp_path)

    assert {
        (row["path"], row["operation"])
        for row in obs.diff_workspace_states(before, after)
    } == {("generated.bin", "created")}


def test_stale_and_restart_reconciliation_are_durable(tmp_path):
    import runtime_observability as obs

    obs.configure(tmp_path)
    obs.start_run("s1", "r1")
    path = tmp_path / "s1" / "runtime_observability.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["runs"][0]["heartbeat_at"] = "2000-01-01T00:00:00Z"
    path.write_text(json.dumps(data), encoding="utf-8")
    stale = obs.scan_stale_runs(30)
    assert stale[0]["run_id"] == "r1"
    assert obs.snapshot("s1")["runs"][0]["status"] == "stale"
    obs.start_run("s2", "r2")
    orphaned = obs.reconcile_orphaned_runs()
    assert any(item["run_id"] == "r2" for item in orphaned)
    assert obs.snapshot("s2")["runs"][0]["status"] == "orphaned"


def test_stale_heartbeat_does_not_mark_a_locally_live_run(tmp_path):
    import runtime_observability as obs

    obs.configure(tmp_path)
    obs.start_run("sleeping", "r-sleep")
    path = tmp_path / "sleeping" / "runtime_observability.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["runs"][0]["heartbeat_at"] = "2000-01-01T00:00:00Z"
    path.write_text(json.dumps(data), encoding="utf-8")

    stale = obs.scan_stale_runs(
        30,
        live_checker=lambda session_id, run_id: (
            session_id == "sleeping" and run_id == "r-sleep"
        ),
    )

    assert stale == []
    assert obs.snapshot("sleeping")["runs"][0]["status"] == "running"


def test_runtime_watchdog_has_no_wall_clock_hard_timeout():
    import runtime_observability as obs

    main_source = (APP_DIR / "main.py").read_text(encoding="utf-8")
    assert not hasattr(obs, "scan_timed_out_runs")
    assert "AGENT_RUN_TIMEOUT_SECONDS" not in main_source
    assert "live_checker=runtime_run_is_locally_active" in main_source
    assert "subagent_registry.is_running(session_id)" in main_source


def test_reference_fork_uses_immutable_parent_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_ENABLED", "1")
    from runtime_v2.history_ops import RuntimeHistoryOps
    from runtime_v2.model_projection import RuntimeModelProjection

    ops = RuntimeHistoryOps(tmp_path)
    ops.append_model_message("parent", "user", "u1")
    ops.append_model_message("parent", "assistant", "a1")
    anchor = ops.event_log.next_seq("parent") - 1
    ops.create_reference_branch("child", "parent", anchor)
    ops.append_model_message("child", "user", "child")
    ops.append_model_message("parent", "user", "later")

    projection = RuntimeModelProjection(tmp_path)
    assert [row["content"] for row in projection.read_message_dicts("child")] == [
        "u1",
        "a1",
        "child",
    ]

    ops.replace_model_history(
        "child",
        [{"type": "user", "content": "materialized"}],
        reason="test_compaction",
    )
    assert [row["content"] for row in projection.read_message_dicts("child")] == [
        "materialized"
    ]


def test_session_fork_freezes_prompt_tools_and_model_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_VERSION", "2")
    import agent_harness
    from agent_harness import SessionManager
    from runtime_v2.history_ops import RuntimeHistoryOps
    from runtime_v2.model_projection import RuntimeModelProjection

    parent = str(uuid.uuid4())
    manager = SessionManager(tmp_path, tmp_path / "sessions.json")
    parent_dir = tmp_path / parent
    parent_dir.mkdir()
    (parent_dir / "metadata.json").write_text("{}", encoding="utf-8")
    ops = RuntimeHistoryOps(tmp_path, path_resolver=manager._resolve_session_path)
    ops.append_model_message(parent, "user", "parent-prefix")
    runtime_config = {
        "version": 1,
        "system_segments": ["system-a", "system-b"],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "demo",
                    "description": "demo",
                    "parameters": {"type": "object"},
                },
            }
        ],
        "model_runtime": {
            "profile_id": "profile-1",
            "model": "model-1",
            "temperature": 0.25,
            "reasoning_effort": "high",
            "extra_body": {"thinking": {"type": "enabled"}},
            "max_output_tokens": 4096,
            "context_window": 200000,
        },
    }
    child = manager.fork_subagent_from_parent(
        parent,
        "fork",
        "generalPurpose",
        1,
        model_profile_id="profile-1",
        parent_runtime_config=runtime_config,
    )
    runtime_config["system_segments"][0] = "mutated-after-fork"

    metadata = manager._load_metadata(child)
    assert metadata["fork_runtime_config"]["system_segments"] == [
        "system-a",
        "system-b",
    ]
    assert metadata["fork_runtime_config"]["tools"][0]["function"]["name"] == "demo"
    assert metadata["fork_model_runtime"]["reasoning_effort"] == "high"
    assert metadata["fork_model_runtime"]["extra_body"] == {
        "thinking": {"type": "enabled"}
    }
    assert metadata["fork_prefix_mode"] == "immutable_model_prefix"
    projected = RuntimeModelProjection(
        tmp_path,
        path_resolver=manager._resolve_session_path,
    ).read_message_dicts(child)
    assert [row["content"] for row in projected] == ["parent-prefix"]

    monkeypatch.setattr(
        agent_harness,
        "executor_runtime_snapshot_for_session",
        lambda session_id: {
            "profile_id": "profile-special",
            "model": "special-model",
            "reasoning_effort": "max",
        }
        if session_id != parent
        else runtime_config["model_runtime"],
    )
    selected_child = manager.fork_subagent_from_parent(
        parent,
        "selected fork",
        "generalPurpose",
        1,
        model_profile_id="profile-special",
        parent_runtime_config=runtime_config,
        inherit_parent_model_runtime=False,
    )
    selected_meta = manager._load_metadata(selected_child)
    assert selected_meta["fork_model_runtime"]["model"] == "special-model"
    assert selected_meta["fork_model_runtime"]["reasoning_effort"] == "max"
    assert selected_meta["fork_runtime_config"]["system_segments"] == [
        "mutated-after-fork",
        "system-b",
    ]


def test_team_claim_next_is_priority_and_dependency_aware(tmp_path, monkeypatch):
    from agent_team.service import AgentTeamService

    monkeypatch.setenv("AGENT_TEAM_ENABLED", "1")
    service = AgentTeamService(tmp_path)
    service.create_team("root")
    member = service.add_member("root", name="worker", role="implementation")
    service.bind_member_session("root", member["member_id"], "child")
    service.set_member_state("root", member["member_id"], "idle")
    dependency = service.create_task("root", title="dependency", priority="low")
    blocked = service.create_task(
        "root",
        title="blocked urgent",
        priority="urgent",
        depends_on=[dependency["task_id"]],
    )
    ready = service.create_task("root", title="ready high", priority="high")

    claimed = service.claim_next_task("root", member["member_id"])
    assert claimed["task_id"] == ready["task_id"]
    service.update_task("root", ready["task_id"], status="completed")
    service.set_member_state("root", member["member_id"], "idle")
    service.update_task("root", dependency["task_id"], status="completed")
    claimed = service.claim_next_task("root", member["member_id"])
    assert claimed["task_id"] == blocked["task_id"]


def test_mcp_worktree_contract_injects_root_and_rejects_escape(monkeypatch, tmp_path):
    import agent_mcp

    calls = []

    class Server:
        _task = type("Task", (), {"done": lambda self: False})()

        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return None

    async def no_start():
        return None

    monkeypatch.setattr(agent_mcp, "ensure_started", no_start)
    agent_mcp._fname_to_tool["mcp_demo_write"] = ("demo", "write")
    agent_mcp._servers["demo"] = Server()
    agent_mcp._tool_contracts["mcp_demo_write"] = {
        "declared": True,
        "effect": "workspace_write",
        "path_arguments": ["path"],
        "resource_arguments": ["path"],
        "workspace_root_argument": "workspace_root",
        "worktree_compatible": True,
    }
    result = asyncio.run(
        agent_mcp.invoke_tool_by_fname(
            "mcp_demo_write",
            {"path": "a.txt"},
            work_dir=str(tmp_path),
            require_worktree_isolation=True,
        )
    )
    assert "Error:" not in result
    assert calls[0][1]["workspace_root"] == str(tmp_path.resolve())
    assert calls[0][1]["path"] == str((tmp_path / "a.txt").resolve())

    escaped = asyncio.run(
        agent_mcp.invoke_tool_by_fname(
            "mcp_demo_write",
            {"path": str(tmp_path.parent / "outside.txt")},
            work_dir=str(tmp_path),
            require_worktree_isolation=True,
        )
    )
    assert "escapes the managed worktree" in escaped
