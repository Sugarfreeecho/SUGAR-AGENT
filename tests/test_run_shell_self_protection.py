import asyncio
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import agent_tools  # noqa: E402


def test_agent_process_targets_and_broad_python_kills_are_blocked(monkeypatch):
    monkeypatch.setenv("MYAGENT_TRAY_PID", "43210")
    server_pid = os.getpid()

    blocked = [
        "Get-Process -Name python | Stop-Process -Force",
        "taskkill /IM python.exe /T /F",
        f"Stop-Process -Id {server_pid} -Force",
        "Stop-Process -Id 43210 -Force",
        "Get-NetTCPConnection -LocalPort 8192 | "
        "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }",
        "python -c \"import os; os.kill(os.getppid(), 9)\"",
        "cmd /c RUN.bat",
        "bash RUN.sh",
        "scripts/agentctl restart",
        "systemctl --user restart sugaragent.service",
        "launchctl kickstart -k gui/501/com.sugaragent.server",
        "python app/tray_launcher.py --daemon",
        "python app/platform_tray.py",
        "Remove-Item app/main.py -Force",
        "del RUN.bat",
    ]

    for command in blocked:
        assert agent_tools._agent_self_protection_reason(command), command


def test_explicit_unrelated_process_kill_remains_allowed(monkeypatch):
    monkeypatch.setenv("MYAGENT_TRAY_PID", "43210")

    allowed = [
        "Stop-Process -Id 54321 -Force",
        "taskkill /PID 54321 /F",
        "Stop-Process -Name notepad -Force",
        "Get-Process -Name python",
        "python -c \"print('safe')\"",
        "Remove-Item temporary-output.txt -Force",
    ]

    for command in allowed:
        assert agent_tools._agent_self_protection_reason(command) is None, command


def test_run_shell_blocks_self_termination_before_spawning(monkeypatch):
    async def fail_spawn(*_args, **_kwargs):
        raise AssertionError("blocked command must not spawn a subprocess")

    monkeypatch.setattr(agent_tools.asyncio, "create_subprocess_exec", fail_spawn)
    result = asyncio.run(
        agent_tools.run_shell(
            "Get-Process -Name python | Stop-Process -Force",
            restrict_to_workspace=False,
        )
    )

    assert "Agent self-protection" in result
    assert "Get-CimInstance Win32_Process" in result
    assert "Stop-Process -Id <非 Agent PID> -Force" in result


def test_normal_shell_command_still_executes():
    result = asyncio.run(
        agent_tools.run_shell("echo self-protection-ok", restrict_to_workspace=False)
    )

    assert "self-protection-ok" in result
    assert "Exit code: 0" in result


def test_shell_child_environment_hides_controller_identity(monkeypatch):
    monkeypatch.setenv("MYAGENT_TRAY_PID", "43210")
    monkeypatch.setenv("MYAGENT_SUPERVISOR_PID", "43210")
    monkeypatch.setenv("MYAGENT_SERVER_PID", "12345")
    monkeypatch.setenv("MYAGENT_PROTECTED_PIDS", "12345,43210")

    child_env = agent_tools._subprocess_env_for_shell()

    assert "MYAGENT_TRAY_PID" not in child_env
    assert "MYAGENT_SUPERVISOR_PID" not in child_env
    assert "MYAGENT_SERVER_PID" not in child_env
    assert "MYAGENT_PROTECTED_PIDS" not in child_env


def test_internal_process_tree_cleanup_never_targets_agent_pid(monkeypatch):
    class FakeProcess:
        pid = os.getpid()

        @staticmethod
        def kill():
            raise AssertionError("protected Agent process must not be killed")

    async def fail_spawn(*_args, **_kwargs):
        raise AssertionError("taskkill must not be spawned for the Agent PID")

    monkeypatch.setattr(agent_tools.asyncio, "create_subprocess_exec", fail_spawn)

    asyncio.run(agent_tools._kill_process_tree(FakeProcess()))


def test_blocked_dangerous_command_includes_recoverable_alternative():
    result = asyncio.run(
        agent_tools.run_shell(
            "Remove-Item temporary-output -Recurse -Force",
            restrict_to_workspace=False,
        )
    )

    assert "Command blocked by safety guard" in result
    assert "delete_file" in result
    assert ".trash" in result
