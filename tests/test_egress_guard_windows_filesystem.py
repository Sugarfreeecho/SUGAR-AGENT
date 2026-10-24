"""Exercise filesystem provisioning and network denial with the real native helper."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows AppContainer integration")


@pytest.fixture(scope="module")
def helper(tmp_path_factory):
    compiler = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not compiler.is_file():
        pytest.skip("Windows C# compiler unavailable")
    output = tmp_path_factory.mktemp("filesystem-helper") / "helper.exe"
    source = Path(__file__).resolve().parents[1] / "app/native/windows/SugarAgentEgressHelper.cs"
    result = subprocess.run([str(compiler), "/nologo", "/optimize+", "/target:exe", f"/out:{output}",
                             "/reference:System.Web.Extensions.dll", str(source)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return output


def active(workspace):
    from security.models import CapabilityRequest, SecurityDecision, DecisionOutcome, PermissionMode, PERMISSION_PRESETS
    request = CapabilityRequest.create(action="process.exec", resource="filesystem test", effect="workspace_write",
                                       arguments={}, metadata={"egress_intent": "none"})
    return {"session_id": "filesystem-test", "workspace": workspace,
            "context": PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL], "request": request,
            "decision": SecurityDecision(DecisionOutcome.ALLOW, "test", "test", request.digest(4))}


def prepare(helper, monkeypatch, workspace, argv, env=None):
    from security import egress_guard as guard
    monkeypatch.setenv("SUGAR_AGENT_EGRESS_HELPER", str(helper))
    monkeypatch.setenv("EGRESS_HELPER_ENABLED", "1")
    monkeypatch.setattr(guard, "_HEALTH_CACHE", None)
    return guard.prepare_egress_launch(argv, env or os.environ, command="filesystem test", active_context=active(workspace))


def invoke(launch, workspace):
    return subprocess.run(launch.argv, env=launch.env, cwd=workspace, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=30)


def test_new_workspace_authorized_directory_and_scratch_work_without_install_acl(helper, tmp_path, monkeypatch):
    import runtime_files
    import session_authorized_dirs
    workspace = tmp_path / "中文 workspace 'quoted'"
    approved = tmp_path / "approved"
    denied = tmp_path / "not authorized"
    for path in (workspace, approved, denied):
        path.mkdir()
    (workspace / "input.txt").write_text("workspace input", encoding="utf-8")
    (denied / "secret.txt").write_text("private", encoding="utf-8")
    monkeypatch.setattr(session_authorized_dirs, "get_authorized_dirs_for_session", lambda *_: [workspace, approved])
    with runtime_files.run_scope(tmp_path / "global", "filesystem-test", "run") as owner:
        scratch = owner.scratch_dir
        program = (
            "from pathlib import Path; import os; "
            "assert Path('input.txt').read_text() == 'workspace input'; "
            "Path('output.txt').write_text('workspace output'); "
            f"Path({str(approved / 'approved.txt')!r}).write_text('approved output'); "
            "Path(os.environ['SUGAR_AGENT_EGRESS_SCRATCH'], 'scratch.txt').write_text('scratch output'); "
            "print('filesystem-ok', flush=True)\n"
            f"try: Path({str(denied / 'secret.txt')!r}).read_text()\n"
            "except PermissionError: print('outside-denied')\n"
            "else: raise RuntimeError('unauthorized sibling was readable')"
        )
        env = dict(os.environ, TEMP=str(scratch), TMP=str(scratch))
        launch = prepare(helper, monkeypatch, workspace, [sys.executable, "-I", "-c", program], env)
        payload = json.loads(base64.urlsafe_b64decode(launch.argv[launch.argv.index("--ticket") + 1]))["payload"]
        assert set(payload["filesystem"]["write_dirs"]) == {str(path.resolve()) for path in (workspace, approved, scratch)}
        result = invoke(launch, workspace)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "filesystem-ok" in result.stdout and "outside-denied" in result.stdout
        assert (workspace / "output.txt").read_text() == "workspace output"
        assert (approved / "approved.txt").read_text() == "approved output"
        assert (scratch / "scratch.txt").read_text() == "scratch output"
        assert not (tmp_path / "output.txt").exists()


def test_workspace_access_does_not_enable_network(helper, tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    # A live listener makes this a denial test rather than a connection-refused test.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=3):
            pass
        program = (
            "import socket; from pathlib import Path; "
            "Path('local.txt').write_text('ok'); print('child-started', flush=True)\n"
            f"try: socket.create_connection(('127.0.0.1', {port}), 3)\n"
            "except OSError as exc:\n"
            " assert isinstance(exc, TimeoutError) or exc.winerror == 10013, repr(exc)\n"
            " print('network-denied')\n"
            "else: raise RuntimeError('network unexpectedly allowed')"
        )
        result = invoke(prepare(helper, monkeypatch, workspace, [sys.executable, "-I", "-c", program]), workspace)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "child-started" in result.stdout and "network-denied" in result.stdout
        assert (workspace / "local.txt").read_text() == "ok"


def test_powershell_uses_a_new_working_directory(helper, tmp_path, monkeypatch):
    import runtime_files
    from agent_tools import _powershell_script_with_utf8_prelude
    workspace = tmp_path / "中文 'powershell' workdir"
    workspace.mkdir()
    powershell = str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
    script = _powershell_script_with_utf8_prelude(
        "$ErrorActionPreference='Stop'; Set-Content -LiteralPath ./new.txt -Value success; Get-Content -LiteralPath ./new.txt",
        workdir=str(workspace))
    script += "; Get-Content -LiteralPath '" + str(workspace / "new.txt").replace("'", "''") + "'"
    with runtime_files.run_scope(tmp_path / "global", "filesystem-test", "run") as owner:
        scratch = owner.scratch_dir
        script += "; [IO.File]::WriteAllText((Join-Path $env:TEMP 'ps-scratch.txt'), 'ps scratch'); "
        script += "& '" + sys.executable.replace("'", "''") + "' -c \"import os; from pathlib import Path; Path(os.environ['TEMP'], 'child-scratch.txt').write_text('child scratch')\""
        result = invoke(prepare(helper, monkeypatch, workspace, [powershell, "-NoProfile", "-NonInteractive", "-Command", script]), workspace)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "success" in result.stdout and (workspace / "new.txt").is_file()
        assert (scratch / "ps-scratch.txt").read_text() == "ps scratch"
        assert (scratch / "child-scratch.txt").read_text() == "child scratch"


def test_unsigned_filesystem_change_is_rejected_before_acl_changes(helper, tmp_path, monkeypatch):
    from dataclasses import replace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    launch = prepare(helper, monkeypatch, workspace, ["cmd.exe", "/d", "/c", "echo should-not-run"])
    arguments = list(launch.argv)
    index = arguments.index("--ticket") + 1
    envelope = json.loads(base64.urlsafe_b64decode(arguments[index]))
    envelope["payload"]["filesystem"]["write_dirs"].append(str(tmp_path))
    arguments[index] = base64.urlsafe_b64encode(json.dumps(envelope).encode()).decode()
    result = invoke(replace(launch, argv=tuple(arguments)), workspace)
    assert result.returncode == 69 and "signature mismatch" in result.stderr
    assert "should-not-run" not in result.stdout


def test_repeated_provisioning_is_idempotent_and_leaves_parent_acl_unchanged(helper, tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    def acl(path):
        # A separate host process reads the ACL without granting anything.
        script = "[IO.Directory]::GetAccessControl('" + str(path).replace("'", "''") + "').GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All)"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, encoding="utf-8", timeout=10)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    parent_before = acl(tmp_path)
    command = ["cmd.exe", "/d", "/c", "echo idempotent-ok"]
    def provision():
        from dataclasses import replace
        from security import egress_guard as guard
        launch = prepare(helper, monkeypatch, workspace, command)
        arguments = list(launch.argv)
        filesystem = json.loads(base64.urlsafe_b64decode(arguments[3]))["payload"]["filesystem"]
        # Existing system AppContainer read access needs no admin ACL changes.
        filesystem["read_dirs"].append(os.environ["WINDIR"])
        context = active(workspace)
        arguments[3], _ = guard._ticket_for("filesystem test", context["request"], context["decision"],
                                           context["session_id"], filesystem=filesystem)
        return invoke(replace(launch, argv=tuple(arguments)), workspace)
    first = provision()
    assert first.returncode == 0, first.stderr
    granted_acl = acl(workspace)
    second = provision()
    assert second.returncode == 0, second.stderr
    assert acl(workspace) == granted_acl
    assert acl(tmp_path) == parent_before


def test_run_shell_production_pipeline_uses_new_workspace_and_owned_temp(helper, tmp_path, monkeypatch):
    import asyncio
    import agent_tools
    import runtime_files
    from execution_services import shell
    from security import egress_guard as guard
    from security.runtime import execution_scope
    from security.models import CapabilityRequest, SecurityDecision, DecisionOutcome
    workspace = tmp_path / "new tool workspace"
    workspace.mkdir()
    monkeypatch.setenv("SUGAR_AGENT_EGRESS_HELPER", str(helper))
    monkeypatch.setenv("EGRESS_HELPER_ENABLED", "1")
    monkeypatch.setattr(guard, "_HEALTH_CACHE", None)
    monkeypatch.setattr(agent_tools, "WORK_DIR", tmp_path / "global")
    monkeypatch.setattr(shell, "jobs_enabled", lambda: False)
    command = "$ErrorActionPreference='Stop'; Set-Content -LiteralPath './tool.txt' -Value tool-ok; "
    command += "[IO.File]::WriteAllText((Join-Path $env:TEMP 'owned.txt'), 'owned-temp'); Write-Output tool-finished"
    context = active(workspace)
    context["request"] = CapabilityRequest.create(action="process.exec", resource=command,
        effect="workspace_write", arguments={"command": command}, metadata={"egress_intent": "none"})
    context["decision"] = SecurityDecision(DecisionOutcome.ALLOW, "test", "test", context["request"].digest(4))
    with runtime_files.run_scope(tmp_path / "global", "filesystem-test", "tool") as owner:
        with execution_scope(**context), agent_tools.tool_work_dir_override(workspace):
            result = asyncio.run(agent_tools.run_shell(command, timeout_ms=15000))
        assert "tool-finished" in result, result
        assert "tool-ok" in (workspace / "tool.txt").read_text(encoding="utf-8-sig")
        assert (owner.scratch_dir / "owned.txt").read_text() == "owned-temp"
