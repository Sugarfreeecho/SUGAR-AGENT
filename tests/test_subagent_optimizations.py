import asyncio
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _PathSessionManager:
    def __init__(self, root: Path):
        self.root = root

    def _get_session_path(self, session_id):
        return self.root / str(session_id)


def test_ordinary_subagent_permission_is_exact_and_consumed_once(tmp_path, monkeypatch):
    import subagent_control

    monkeypatch.setattr(
        subagent_control,
        "session_manager",
        _PathSessionManager(tmp_path),
    )
    meta = {
        "is_subagent": True,
        "parent_session_id": "parent",
        "_active_session_id": "child",
    }

    allowed, message = subagent_control.authorize_subagent_tool(
        meta,
        "run_shell",
        {"command": "git status"},
    )
    assert allowed is False
    assert "permission_id=" in message

    pending = subagent_control.list_subagent_permissions("parent", child_id="child")
    assert len(pending) == 1
    permission_id = pending[0]["permission_id"]
    subagent_control.resolve_subagent_permission(
        "parent",
        "child",
        permission_id,
        "allowed",
    )

    allowed, _ = subagent_control.authorize_subagent_tool(
        meta,
        "run_shell",
        {"command": "git status"},
    )
    assert allowed is True

    allowed, message = subagent_control.authorize_subagent_tool(
        meta,
        "run_shell",
        {"command": "git status"},
    )
    assert allowed is False
    assert permission_id not in message
    assert subagent_control.subagent_tool_requires_permission(
        "mcp_slack_send_message", {"channel": "dev"}
    )
    assert not subagent_control.subagent_tool_requires_permission(
        "mcp_drive_search_files", {"query": "design"}
    )


def test_tool_workspace_override_is_context_local(tmp_path):
    import agent_tools

    root = tmp_path / "isolated"
    root.mkdir()
    with agent_tools.tool_work_dir_override(root):
        assert agent_tools.safe_work_path("a.txt") == (root / "a.txt").resolve()
        assert agent_tools.resolve_unrestricted_path("/") == root.resolve()
    assert agent_tools.active_tool_work_dir() == agent_tools.WORK_DIR.resolve()


def test_task_steer_reuses_durable_session_inbox(monkeypatch):
    import agent_loop
    import agent_subagent

    class _SessionManager:
        def validate_subagent_resume(self, parent, child):
            return child if parent == "parent" else None

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent.subagent_registry, "is_running", lambda child: True)
    monkeypatch.setattr(
        agent_loop,
        "enqueue_session_steer",
        lambda *args, **kwargs: {"ok": True, "item": {"id": "steer-1"}},
    )
    monkeypatch.setattr(agent_loop, "abort_session_steer_run", lambda *args, **kwargs: True)

    result = asyncio.run(
        agent_subagent._run_single_subagent(
            tool_args={
                "action": "steer",
                "resume": "child",
                "prompt": "Use the narrower implementation.",
                "steer_mode": "interrupt",
            },
            parent_session_id="parent",
        )
    )
    assert "steer-1" in result
    assert "interrupted_current_step=True" in result


def test_reconcile_marks_persisted_running_task_orphaned(tmp_path, monkeypatch):
    import agent_subagent

    parent_dir = tmp_path / "parent"
    task_dir = parent_dir / "subagents"
    child_dir = task_dir / "child"
    child_dir.mkdir(parents=True)
    (task_dir / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "child",
                    "agent_id": "child",
                    "parent_session_id": "parent",
                    "run_id": "old-run",
                    "status": "running",
                }
            ]
        ),
        encoding="utf-8",
    )

    patches = []
    task_patches = []

    class _SessionManager:
        sessions_dir = tmp_path

        def _load_metadata(self, child_id):
            return {
                "is_subagent": True,
                "parent_session_id": "parent",
                "subagent_run_instance_id": "old-process",
            }

        def patch_subagent_metadata(self, child_id, patch):
            patches.append((child_id, dict(patch)))

        def upsert_subagent_task(self, parent_id, child_id, patch):
            task_patches.append((parent_id, child_id, dict(patch)))

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent.subagent_registry, "is_running", lambda child: False)
    result = agent_subagent.reconcile_orphaned_subagent_runs()

    assert result["reconciled"] == ["child"]
    assert any(patch.get("subagent_run_status") == "orphaned" for _, patch in patches)
    assert task_patches[0][2]["status"] == "orphaned"


def test_managed_worktree_can_diff_and_merge_cleanly(tmp_path, monkeypatch):
    import agent_subagent

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args, cwd=repo):
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )

    git("init")
    git("config", "user.email", "tests@example.invalid")
    git("config", "user.name", "MyAgent Tests")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt")
    git("commit", "-m", "base")

    monkeypatch.setattr(agent_subagent, "WORK_DIR", repo)
    created = agent_subagent._create_managed_worktree("child")
    assert created is not None
    worktree_root, work_dir, branch, base_commit = created
    assert worktree_root.parent.parent.name == ".myagent-worktrees"
    (work_dir / "child.txt").write_text("from child\n", encoding="utf-8")

    metadata = {
        "git_worktree_path": str(worktree_root),
        "subagent_work_dir": str(work_dir),
        "git_worktree_branch": branch,
        "git_worktree_base_commit": base_commit,
        "git_worktree_main_root": str(repo),
        "git_worktree_state": "active",
        "git_worktree_managed": True,
    }

    class _SessionManager:
        sessions_dir = tmp_path / "sessions"

        def validate_subagent_resume(self, parent, child):
            return child if parent == "parent" else None

        def _load_metadata(self, child):
            return dict(metadata)

        def patch_subagent_metadata(self, child, patch):
            metadata.update(patch)

    monkeypatch.setattr(agent_subagent, "session_manager", _SessionManager())
    monkeypatch.setattr(agent_subagent.subagent_registry, "is_running", lambda child: False)

    diff = agent_subagent.manage_subagent_worktree("parent", "child", "diff")
    assert "child.txt" in diff
    merged = agent_subagent.manage_subagent_worktree("parent", "child", "merge")
    assert "Merged subagent child" in merged
    assert (repo / "child.txt").read_text(encoding="utf-8") == "from child\n"
    assert metadata["git_worktree_state"] == "merged"
    assert not worktree_root.exists()


def test_managed_worktree_can_start_from_dirty_main_checkout(tmp_path, monkeypatch):
    import agent_subagent

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        )

    git("init")
    git("config", "user.email", "tests@example.invalid")
    git("config", "user.name", "MyAgent Tests")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt")
    git("commit", "-m", "base")
    (repo / "base.txt").write_text("dirty user change\n", encoding="utf-8")

    monkeypatch.setattr(agent_subagent, "WORK_DIR", repo)
    created = agent_subagent._create_managed_worktree("dirty-child")

    assert created is not None
    worktree_root, work_dir, _branch, base_commit = created
    assert worktree_root.is_dir()
    assert work_dir.is_dir()
    assert base_commit == git("rev-parse", "HEAD").stdout.strip()
    assert (repo / "base.txt").read_text(encoding="utf-8") == "dirty user change\n"
