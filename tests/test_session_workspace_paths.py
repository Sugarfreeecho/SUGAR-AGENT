"""Regressions with default and custom workspaces present at the same time."""
import asyncio
import ast
import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


@pytest.fixture
def workspaces(tmp_path, monkeypatch):
    import agent_harness as harness
    import agent_loop
    import agent_subagent
    import agent_tools
    import webui

    # Nested sessions contain multiple UUID segments; keep Windows paths short.
    directory = tempfile.TemporaryDirectory(prefix="wp-")
    roots = [Path(directory.name).resolve() / name for name in ("default", "project-B", "project-C")]
    for root in roots:
        root.mkdir()
        (root / "same.txt").write_text(root.name, encoding="utf-8")
    manager = harness.SessionManager(roots[0] / "sessions", roots[0] / "index.json")
    for module in (harness, agent_loop, agent_subagent, agent_tools, webui):
        monkeypatch.setattr(module, "WORK_DIR", roots[0])
        if hasattr(module, "session_manager"):
            monkeypatch.setattr(module, "session_manager", manager)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    sids = [manager.get_or_create_session(work_dir=str(root))[0] for root in roots[1:]]
    try:
        yield roots, manager, sids
    finally:
        directory.cleanup()


def test_children_and_legacy_children_follow_parent_root(workspaces):
    import agent_harness as h
    roots, manager, sids = workspaces
    child = manager.create_subagent_session(sids[0], "inspect", "explore", 1, readonly_strict=True)
    nested = manager.create_subagent_session(child, "nested", "generalPurpose", 2)
    assert h.session_work_dir(child) == roots[1]
    assert h.session_work_dir(nested) == roots[1]
    assert manager._get_session_path(child).is_relative_to(roots[0] / "sessions")
    manager.patch_subagent_metadata(child, {"work_dir": ""})
    manager.patch_subagent_metadata(nested, {"work_dir": ""})
    assert h.session_work_dir(nested) == roots[1]
    projection = h.session_work_dir_projection(nested)
    assert projection["effective_work_dir"] == str(roots[1])
    assert not projection["work_dir_is_default"]


def test_missing_custom_directory_is_preserved_and_returns_404(workspaces):
    import agent_harness as h
    import webui
    from fastapi.testclient import TestClient
    roots, manager, sids = workspaces
    missing = roots[1] / "removed"
    meta = manager._load_metadata(sids[0])
    meta["work_dir"] = str(missing)
    manager._save_metadata(sids[0], meta)
    assert h.session_work_dir(sids[0]) == missing
    assert h.session_work_dir_projection(sids[0])["work_dir_available"] is False
    response = TestClient(webui.fastapi_app).get("/api/workspace-files", params={"session_id": sids[0]})
    assert response.status_code == 404


def test_environment_and_fork_use_active_root_and_absolute_shared_storage(workspaces, monkeypatch):
    import agent_loop
    import agent_tokenizer
    roots, manager, sids = workspaces
    env = agent_tokenizer.build_env_static(sids[0])
    assert f"(`WORK_DIR`): {roots[1]}" in env
    assert str(manager._get_session_path(sids[0])) in env
    monkeypatch.setattr(agent_loop, "get_skills_catalog", lambda: "")
    meta = {"fork_runtime_config": {"system_segments": ["instructions", "## Environment\nold root"]}}
    segments = agent_loop._build_static_segments_for_session(sids[0], meta, "zh-CN")
    assert segments[0] == "instructions"
    assert str(roots[1]) in segments[1] and "old root" not in segments[1]


def test_temporary_cleanup_does_not_touch_default_same_name(workspaces):
    import agent_loop
    import agent_tools
    roots, manager, sids = workspaces
    state = {"session_id": sids[0]}
    with agent_tools.tool_work_dir_override(roots[1]):
        assert not agent_tools.write_file(path="same.txt", content="temporary", temporary=True).startswith("Error:")
    agent_loop._record_temporary_write_file(state, "write_file", {"path": "same.txt", "temporary": True}, False)
    assert state["_temporary_write_files"] == [str(roots[1] / "same.txt")]
    assert agent_loop._cleanup_temporary_write_files(state) == [str(roots[1] / "same.txt")]
    assert not (roots[1] / "same.txt").exists()
    assert (roots[0] / "same.txt").read_text() == "default"


def test_long_result_stays_global_and_can_be_read_from_custom_root(workspaces):
    import agent_loop
    import agent_tools
    roots, manager, sids = workspaces
    state = {"session_id": sids[0]}
    content = "tool output\n" * 100
    view = agent_loop._save_result_to_tempfile(content, "test/tool", state, preview_chars=10)
    saved = Path(state["_temporary_write_files"][0])
    assert saved.parent == roots[0] / ".tool_results"
    assert str(saved) in view
    with agent_tools.tool_work_dir_override(roots[1]):
        assert agent_tools.resolve_unrestricted_path(str(saved)).read_text() == content
    assert agent_loop._cleanup_temporary_write_files(state) == [str(saved)]
    assert not saved.exists()


def test_file_list_text_media_and_html_siblings_use_owning_session(workspaces):
    import webui
    from fastapi.testclient import TestClient
    from PIL import Image
    roots, manager, sids = workspaces
    client = TestClient(webui.fastapi_app)
    for index, root in enumerate(roots):
        Image.new("RGB", (index + 2, index + 3)).save(root / "same.png")
        (root / "page.html").write_text('<link rel="stylesheet" href="style.css">', encoding="utf-8")
        (root / "style.css").write_text(root.name, encoding="utf-8")
    for index, sid in enumerate(sids, start=1):
        params = {"session_id": sid, "rel": "same.txt"}
        assert client.get("/api/workspace-file-text", params=params).json()["text"] == roots[index].name
        tree = client.get("/api/workspace-files", params={"session_id": sid}).json()
        assert tree["root"] == str(roots[index])
        assert all(Path(row["path"]).is_relative_to(roots[index]) for row in tree["files"])
        metadata = client.post("/api/workspace-image-metadata", json={"session_id": sid, "rels": ["same.png"]}).json()
        assert metadata["images"][0]["width"] == index + 2
        assert client.get("/api/workspace-image", params={"session_id": sid, "rel": "same.png"}).content == (roots[index] / "same.png").read_bytes()
        base = f"/api/sessions/{sid}/workspace-assets/"
        assert client.get(base + "page.html").status_code == 200
        assert client.get(base + "style.css").text == roots[index].name
        assert client.get("/api/open-workspace-dir", params={**params, "probe": 1}).json()["path"] == str(roots[index] / "same.txt")
    assert client.get("/api/workspace-file-text", params={"rel": "same.txt", "work_dir": str(roots[2])}).json()["text"] == roots[2].name
    assert client.get("/api/workspace-files", params={"session_id": "unknown"}).status_code == 404


def test_snapshot_reads_custom_source_and_persists_in_shared_storage(workspaces):
    from workspace_media_snapshots import snapshot_workspace_images
    import webui
    roots, manager, sids = workspaces
    (roots[0] / "same.png").write_bytes(b"default image")
    (roots[1] / "same.png").write_bytes(b"project image")
    rewritten = snapshot_workspace_images("![image](same.png)", roots[0], source_root=roots[1])
    raw = rewritten.split("(<", 1)[1].split(">)", 1)[0]
    snapshot = webui._resolve_workspace_view_path(raw, roots[1])
    assert snapshot.is_relative_to(roots[0]) and snapshot.read_bytes() == b"project image"


def test_task_attachments_and_terminal_cwd_follow_effective_root(workspaces):
    import agent_subagent
    import agent_tools
    from session_authorized_dirs import get_authorized_dirs_for_session
    roots, manager, sids = workspaces
    root = agent_subagent._task_workspace(sids[0])
    assert "project-B" in agent_subagent.load_file_attachments_block(["same.txt"], root)
    assert agent_tools._resolve_shell_working_dir("", root) == root
    assert agent_tools._resolve_shell_working_dir(".", root) == root
    assert get_authorized_dirs_for_session(sids[0]) == [root]


def test_worktree_lifecycle_belongs_to_custom_git_repo(workspaces, monkeypatch):
    import agent_subagent as sub
    roots, manager, sids = workspaces
    def git(root, *args):
        return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    for root in roots[:2]:
        git(root, "init")
        git(root, "config", "user.name", "Workspace Tests")
        git(root, "config", "user.email", "tests@example.invalid")
        git(root, "add", "same.txt")
        git(root, "commit", "-m", "base")
    before = git(roots[0], "rev-parse", "HEAD")
    child = manager.create_subagent_session(sids[0], "worktree", "generalPurpose", 1)
    created = sub._create_managed_worktree(child, sub._task_workspace(sids[0]))
    assert created
    wt, work_dir, branch, commit = created
    try:
        sub._persist_managed_worktree(child, wt, work_dir, branch, commit)
        assert manager._load_metadata(child)["git_worktree_main_root"] == str(roots[1])
        (work_dir / "child.txt").write_text("custom change", encoding="utf-8")
        monkeypatch.setattr(sub.subagent_registry, "is_running", lambda sid: False)
        assert "Merged subagent" in sub.manage_subagent_worktree(sids[0], child, "merge")
        assert (roots[1] / "child.txt").read_text() == "custom change"
        assert not (roots[0] / "child.txt").exists() and not wt.exists()
        assert git(roots[0], "rev-parse", "HEAD") == before
    finally:
        if wt.exists():
            sub._git_worktree_remove(wt, branch, roots[1])


def test_normal_mcp_arguments_receive_custom_root(workspaces, monkeypatch):
    import agent_mcp as mcp
    roots, manager, sids = workspaces
    class Server:
        _task = type("Task", (), {"done": lambda self: False})()
        async def call_tool(self, name, arguments):
            self.arguments = arguments
            return {"content": []}
    server = Server()
    monkeypatch.setattr(mcp, "_fname_to_tool", {"mcp_test_write": ("test", "write")})
    monkeypatch.setattr(mcp, "_servers", {"test": server})
    monkeypatch.setattr(mcp, "_load_disabled_mcp_tools", lambda: set())
    monkeypatch.setattr(mcp, "get_tool_contract", lambda name: {"declared": True, "effect": "workspace_write", "workspace_root_argument": "root", "path_arguments": ["path"]})
    asyncio.run(mcp._invoke_tool_by_fname_impl("mcp_test_write", {"path": "same.txt", "root": str(roots[0])}, work_dir=str(roots[1])))
    assert server.arguments == {"path": str(roots[1] / "same.txt"), "root": str(roots[1])}


def test_configured_paths_are_independent_of_launch_cwd(tmp_path, monkeypatch):
    from workspace_paths import configured_paths
    (tmp_path / "app").mkdir()
    (tmp_path / "app/.env").write_text("WORK_DIR=./custom\nSKILLS_DIR=\nLOG_DIR=./custom-logs\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "app")
    paths = configured_paths(tmp_path, environment={})
    assert paths["work_dir"] == str(tmp_path / "custom")
    assert paths["skills_dir"] == str(tmp_path / "custom/skills")
    explicit = configured_paths(tmp_path, environment={"MYAGENT_DOTENV_OVERRIDE": "0", "WORK_DIR": str(tmp_path / "test")})
    assert explicit["work_dir"] == str(tmp_path / "test")


def test_frontend_pins_worktree_draft_media_and_async_context():
    result = subprocess.run(["node", str(ROOT / "tests/js/session_workspace_paths.cjs")],
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_command_hook_execution_and_security_use_the_same_project(tmp_path):
    from hooks import CommandHookExecutor, HookDefinition, CommandSpec
    from security import classify_hook
    project = tmp_path / "project"
    project.mkdir()
    script = tmp_path / "hook.py"
    script.write_text("import json,os\nprint(json.dumps({'additional_context': os.getcwd()+'|'+os.environ['MYAGENT_PROJECT_ROOT']}))", encoding="utf-8")
    command = subprocess.list2cmdline([sys.executable, str(script)])
    definition = HookDefinition(id="paths", event="PreToolUse", source_root=tmp_path,
                                command=CommandSpec(command=command, cwd="${MYAGENT_PROJECT_ROOT}"))
    payload = {"workspace_root": str(project), "project_root": str(project), "app_root": str(tmp_path)}
    result = asyncio.run(CommandHookExecutor(tmp_path).execute(definition, payload))
    assert result.success and result.additional_context == f"{project}|{project}"
    request = classify_hook(definition, payload, project)
    assert request.metadata["cwd"] == str(project)


def test_normal_plugin_arguments_receive_custom_root(workspaces, monkeypatch):
    import agent_extensions as extensions
    roots, manager, sids = workspaces
    captured = {}
    contract = {"declared": True, "effect": "workspace_write", "workspace_root_argument": "root", "path_arguments": ["path"]}
    def invoke(name, arguments, plugins, *, context):
        captured.update(arguments=arguments, context=context)
        return {"ok": True}
    registry = SimpleNamespace(tool_contract=lambda *args: contract, invoke=invoke)
    monkeypatch.setattr(extensions, "load_plugins", lambda **kwargs: SimpleNamespace(plugins=[]))
    monkeypatch.setattr(extensions, "get_plugin_runtime_registry", lambda: registry)
    result = asyncio.run(extensions.invoke_plugin_tool("write", {"path": "same.txt"}, work_dir=str(roots[1])))
    assert result["ok"]
    assert captured["arguments"] == {"path": str(roots[1] / "same.txt"), "root": str(roots[1])}
    assert captured["context"]["workspace_root"] == str(roots[1])


@pytest.mark.parametrize("cwd", ["", ".", "subdir"])
def test_user_terminal_endpoint_uses_session_root(workspaces, cwd):
    from fastapi import HTTPException
    roots, manager, sids = workspaces
    (roots[1] / "subdir").mkdir()
    # Exercise the actual nested route, with a fake terminal backend only.
    tree = ast.parse((ROOT / "plugins/execution-tools/host.py").read_text(encoding="utf-8"))
    handler = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "open_terminal")
    handler.decorator_list = []
    async def body(request):
        return {"cwd": cwd}
    async def call(function, *args, **kwargs):
        return function(*args, **kwargs)
    service = SimpleNamespace(call=call)
    tm = SimpleNamespace(open=lambda *args, **kwargs: kwargs)
    namespace = {"Request": object, "HTTPException": HTTPException, "body": body, "checked": lambda sid: service,
                 "terminal_manager": lambda instance: tm, "manager": manager}
    exec(compile(ast.Module(body=[handler], type_ignores=[]), "terminal-route", "exec"), namespace)
    result = asyncio.run(namespace["open_terminal"](sids[0], object()))
    assert result["cwd"] == str(roots[1] / ("subdir" if cwd == "subdir" else ""))


def test_native_picker_initial_directory_follows_session(workspaces, monkeypatch):
    import webui
    from fastapi.testclient import TestClient
    roots, manager, sids = workspaces
    monkeypatch.setattr(webui, "pick_native_path", lambda kind, initial, multiple: initial)
    client = TestClient(webui.fastapi_app)
    for root, sid in zip(roots[1:], sids):
        response = client.post("/api/pick-path", json={"kind": "directory", "session_id": sid})
        assert response.json()["path"] == str(root)
