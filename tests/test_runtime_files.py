"""Runtime output allocation, recovery and process lifetime regressions."""
import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import runtime_files as files


def test_temporary_write_preserves_project_and_uses_global_root(tmp_path, monkeypatch):
    import agent_tools
    default, project = tmp_path / "default", tmp_path / "project"
    project.mkdir()
    original = project / "script.py"
    original.write_text("original")
    monkeypatch.setattr(agent_tools, "WORK_DIR", default)
    with files.run_scope(default, "session", "run") as owner:
        with agent_tools.tool_work_dir_override(project):
            result = agent_tools.write_file(str(original), content="temporary", temporary=True)
        saved = owner.temporary_path(str(original))
        assert saved.read_text() == "temporary"
        assert str(saved) in result
        assert saved.is_relative_to(default / "TempOutput" / "scratch" / "session")
        assert original.read_text() == "original"
    assert not saved.exists()
    assert not (project / ".trash").exists()


def test_run_failure_and_cancellation_release_scratch(tmp_path):
    async def run():
        with files.run_scope(tmp_path, "session", "cancelled") as owner:
            path = owner.scratch_dir
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
    assert not list((tmp_path / "TempOutput" / "scratch").rglob(files.MARKER))
    with pytest.raises(RuntimeError):
        with files.run_scope(tmp_path, "session", "failed") as owner:
            path = owner.scratch_dir
            raise RuntimeError("failure")
    assert not path.exists()


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel"])
def test_react_node_owns_threaded_tools_and_retains_results(tmp_path, monkeypatch, outcome):
    import agent_loop
    import agent_tools
    monkeypatch.setattr(agent_loop, "WORK_DIR", tmp_path)
    monkeypatch.setattr(agent_tools, "WORK_DIR", tmp_path)
    saved = {}
    async def react(state, emit=None):
        owner = files.current_run(tmp_path)
        saved["scratch"] = owner.scratch_dir
        result = await asyncio.to_thread(agent_tools.write_file, "script.py", content="pass", temporary=True)
        assert str(owner.temporary_path("script.py")) in result
        saved["result"] = files.save_tool_result(tmp_path, state["session_id"], "call", "retained")
        if outcome == "failure":
            raise RuntimeError("failed")
        if outcome == "cancel":
            raise asyncio.CancelledError()
        return state
    monkeypatch.setattr(agent_loop, "_react_node_replanning", react)
    async def run():
        state = {"session_id": "session", "_runtime_v2_run_id": "run"}
        if outcome == "success":
            assert await agent_loop.react_node(state) is state
        else:
            with pytest.raises(RuntimeError if outcome == "failure" else asyncio.CancelledError):
                await agent_loop.react_node(state)
    asyncio.run(run())
    assert not saved["scratch"].exists()
    assert saved["result"].read_text() == "retained"


def test_real_terminal_owns_scratch_until_closed(tmp_path, monkeypatch):
    pytest.importorskip("winpty" if os.name == "nt" else "ptyprocess")
    import agent_tools
    from execution_services.jobs import ExecutionService
    from execution_services.terminals import terminal_manager
    monkeypatch.setattr(agent_tools, "WORK_DIR", tmp_path / "default")
    project = tmp_path / "project"
    project.mkdir()
    async def run():
        service = ExecutionService()
        manager = terminal_manager(service)
        try:
            opened = await service.call(manager.open, "owner", cwd=str(project))
            terminal = manager.sessions[opened["id"]]
            scratch = terminal.scratch_lease.owner.path
            assert scratch.is_relative_to(agent_tools.WORK_DIR / "TempOutput" / "scratch" / "owner")
            assert scratch.exists()
            await service.call(manager.close, "owner", terminal.id)
            assert not scratch.exists()
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_background_lease_outlives_run_and_last_release_cleans(tmp_path):
    with files.run_scope(tmp_path, "session", "run") as owner:
        path = owner.temporary_path("input.txt")
        path.write_text("input")
        lease = owner.hold()
        lease.track_process(os.getpid())
    assert path.read_text() == "input"
    assert files.cleanup_stale_scratch(tmp_path) == 0
    lease.release()
    lease.release()
    assert not path.parent.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-path cleanup")
@pytest.mark.parametrize("held", [False, True])
def test_owned_scratch_cleans_long_native_names_only_after_last_lease(tmp_path, held):
    outside = tmp_path / "retained.txt"
    outside.write_text("keep", encoding="utf8")
    with files.run_scope(tmp_path, "s"*36, "r"*36) as owner:
        scratch = owner.scratch_dir
        leaf = scratch / ("native-" + "n"*150)
        native_leaf = Path("\\\\?\\" + str(leaf))
        assert len(str(leaf)) > 260
        native_leaf.write_bytes(b"exclusive marker")
        assert native_leaf.is_file()
        lease = owner.hold() if held else None
    if held:
        assert native_leaf.is_file()
        lease.release()
    assert not scratch.exists()
    assert outside.read_text(encoding="utf8") == "keep"


@pytest.mark.parametrize("cancel", [False, True])
def test_real_background_process_keeps_scratch_until_exit(tmp_path, monkeypatch, cancel):
    import agent_tools
    from execution_services import jobs, shell
    from execution_services.jobs import ExecutionService
    default, project = tmp_path / "default", tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(agent_tools, "WORK_DIR", default)
    service = ExecutionService()
    monkeypatch.setattr(jobs, "_SERVICE", service)
    async def run():
        try:
            with files.run_scope(default, "owner", "run") as owner:
                scratch = owner.scratch_dir
                source = scratch / "input.txt"
                source.write_text("input")
                code = "import os,time,pathlib; time.sleep(%s); print(pathlib.Path(os.environ['TEMP'],'input.txt').read_text()); print(os.getcwd())" % (10 if cancel else .3)
                prepared = SimpleNamespace(argv=[sys.executable, "-c", code], env=agent_tools._subprocess_env_for_shell())
                result = await shell.execute_prepared(prepared, project, {}, "probe", 1, True, [],
                    {"session_id": "owner", "context": SimpleNamespace(mode="full_access")})
                identifier = result.split("started background job ")[1].splitlines()[0]
            assert source.exists()
            if cancel:
                await service.call(service.kill, "owner", identifier, "test cancellation")
            output = await service.call(service.output, "owner", identifier, True, 5000)
            assert not scratch.exists()
            if not cancel:
                assert output["job"]["exit_code"] == 0
                assert "input" in output["text"] and str(project) in output["text"]
            assert not (project / "TempOutput").exists()
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_results_are_retained_and_same_call_does_not_overwrite(tmp_path):
    with files.run_scope(tmp_path, "session", "run"):
        first = files.save_tool_result(tmp_path, "session", "call", "first")
        second = files.save_tool_result(tmp_path, "session", "call", "second")
    assert first != second
    assert first.read_text() == "first"
    assert second.read_text() == "second"
    assert first.parent == tmp_path / "TempOutput" / "tool-results" / "session" / "call"
    files.cleanup_stale_scratch(tmp_path)
    assert first.exists()


def test_custom_project_authorizes_only_current_run_scratch(tmp_path):
    from security.runtime import classify_tool
    from security.policy import PolicyEngine
    from security.models import PERMISSION_PRESETS, PermissionMode, DecisionOutcome
    project, default = tmp_path / "project", tmp_path / "default"
    project.mkdir()
    context = PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL]
    with files.run_scope(default, "owner", "run") as owner:
        path = owner.temporary_path("input.txt")
        path.write_text("input")
        request = classify_tool("write_file", {"path": str(path), "contents": "next"}, project)
        assert not request.metadata.get("required_dirs")
        engine = PolicyEngine(project, authorized_dirs=files.authorized_scratch_dirs([project], "owner"))
        assert engine.decide(request, context).outcome == DecisionOutcome.ALLOW
        for external in (default / "TempOutput" / "other.txt", default / "TempOutput" / "scratch" / "other" / "run" / "file.txt"):
            request = classify_tool("write_file", {"path": str(external), "contents": "blocked"}, project)
            assert engine.decide(request, context).outcome == DecisionOutcome.ASK
        assert files.authorized_scratch_dirs([project], "other") == [project]
        shell = classify_tool("run_shell", {"command": 'python "' + str(path) + '"'}, project)
        assert not shell.metadata["external_workspace"]


def test_startup_reclaims_dead_owner_but_keeps_live_child_and_foreign_data(tmp_path):
    owners = [files.RunFiles(tmp_path, "session", name) for name in ("dead", "live")]
    paths = [owner.scratch_dir for owner in owners]
    current = files._identity()
    dead = {**current, "created": current["created"] - 100}
    for path in paths:
        (path / files.MARKER).write_text(json.dumps({"version": 1, "host": dead, "processes": []}))
    (paths[1] / files.MARKER).write_text(json.dumps({"version": 1, "host": dead, "processes": [current]}))
    foreign = paths[1].parent / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("keep")
    assert files.cleanup_stale_scratch(tmp_path) == 1
    assert not paths[0].exists()
    assert paths[1].exists() and (foreign / "keep.txt").exists()


def test_cleanup_failure_is_retried_without_removing_pending_startup(tmp_path, monkeypatch):
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise PermissionError("temporarily locked")
        patch.setattr(files.shutil, "rmtree", fail)
        with files.run_scope(tmp_path, "session", "finished") as owner:
            path = owner.scratch_dir
    assert path.exists()
    assert files.cleanup_stale_scratch(tmp_path) == 1
    pending = files.RunFiles(tmp_path, "session", "pending").scratch_dir
    dead = {**files._identity(), "created": -1}
    (pending / files.MARKER).write_text(json.dumps({"version": 1, "host": dead, "closed": True, "pending": 1, "processes": []}))
    assert files.cleanup_stale_scratch(tmp_path) == 0
    assert pending.exists()


def test_path_traversal_and_symlinked_roots_are_rejected(tmp_path):
    with files.run_scope(tmp_path, "../../session", "../run") as owner:
        with pytest.raises(ValueError):
            owner.temporary_path("../escape.txt")
        with pytest.raises(ValueError):
            owner.temporary_path(files.MARKER)
        assert owner.scratch_dir.is_relative_to(tmp_path / "TempOutput")
    other = tmp_path / "other"
    other.mkdir()
    root = tmp_path / "linked"
    root.mkdir()
    try:
        (root / "TempOutput").symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError):
        files.output_root(root)
    assert files.cleanup_stale_scratch(root) == 0


def test_shell_environment_and_materialized_python_use_scratch(tmp_path, monkeypatch):
    import agent_tools
    monkeypatch.setattr(agent_tools, "WORK_DIR", tmp_path / "default")
    with files.run_scope(agent_tools.WORK_DIR, "session", "run") as owner:
        env = agent_tools._subprocess_env_for_shell()
        assert all(Path(env[key]) == owner.scratch_dir for key in ("TEMP", "TMP", "TMPDIR"))
        command, paths = agent_tools._maybe_materialize_python_c_script(
            'python -c "print(1)\\nprint(2)"', tmp_path / "project")
        assert len(paths) == 1 and paths[0].parent == owner.scratch_dir
        assert "print(2)" in paths[0].read_text()
        assert str(paths[0]) in command
    assert not paths[0].exists()


def test_atomic_replace_failure_cleans_only_its_unique_staging(tmp_path, monkeypatch):
    import agent_tools
    target = tmp_path / "data.txt"
    target.write_text("original")
    unrelated = tmp_path / "data.txt.tmp"
    unrelated.write_text("unrelated")
    def fail(*args):
        raise PermissionError("target locked")
    monkeypatch.setattr(agent_tools.os, "replace", fail)
    with pytest.raises(PermissionError):
        agent_tools._atomic_write_text(target, "replacement")
    assert target.read_text() == "original"
    assert unrelated.read_text() == "unrelated"
    assert {p.name for p in tmp_path.iterdir()} == {"data.txt", "data.txt.tmp"}


def test_default_search_and_picker_skip_runtime_outputs(tmp_path, monkeypatch):
    import agent_tools
    import webui
    source = tmp_path / "app.py"
    source.write_text("unique_runtime_probe")
    result = files.save_tool_result(tmp_path, "session", "call", "unique_runtime_probe")
    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: None)
    with agent_tools.tool_work_dir_override(tmp_path):
        found = agent_tools.grep("unique_runtime_probe", path=str(tmp_path), include_ignored=True)
        matched = agent_tools.glob("**/*", path=str(tmp_path))
        assert "app.py" in found and "TempOutput" not in found
        assert "app.py" in matched and "TempOutput" not in matched
        assert "unique_runtime_probe" in agent_tools.read_file(str(result))
    assert not webui._is_workspace_visible_dir("TempOutput")
