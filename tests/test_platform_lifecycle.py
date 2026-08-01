import subprocess
from pathlib import Path

from app import platform_lifecycle


class FakeRunner:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def __call__(self, command, **kwargs):
        self.calls.append((list(command), dict(kwargs)))
        if self.responses:
            return self.responses.pop(0)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def test_systemd_backend_uses_user_service_commands(tmp_path):
    runner = FakeRunner(
        [subprocess.CompletedProcess([], 0, stdout="active\n", stderr="")]
    )
    backend = platform_lifecycle.SystemdUserBackend(tmp_path, runner=runner)

    assert backend.status().running is True
    backend.restart()
    backend.reload()

    commands = [call[0] for call in runner.calls]
    assert commands[0] == [
        "systemctl",
        "--user",
        "is-active",
        platform_lifecycle.SYSTEMD_UNIT,
    ]
    assert commands[1] == [
        "systemctl",
        "--user",
        "restart",
        platform_lifecycle.SYSTEMD_UNIT,
    ]
    assert commands[2] == ["systemctl", "--user", "daemon-reload"]


def test_backend_selection_is_explicit_and_platform_independent(tmp_path):
    assert isinstance(
        platform_lifecycle.backend_for(tmp_path, name="systemd-user"),
        platform_lifecycle.SystemdUserBackend,
    )
    assert isinstance(
        platform_lifecycle.backend_for(tmp_path, name="launchd-user"),
        platform_lifecycle.LaunchdUserBackend,
    )
    assert isinstance(
        platform_lifecycle.backend_for(tmp_path, name="windows-tray"),
        platform_lifecycle.WindowsLauncherBackend,
    )


def test_update_command_preserves_root_with_spaces(tmp_path):
    root = tmp_path / "Sugar Agent"
    root.mkdir()
    backend = platform_lifecycle.SystemdUserBackend(root)

    command = backend.update_command()

    assert command[1] == str(root / "app" / "agent_updater.py")
    assert command[command.index("--root") + 1] == str(root)
    assert command[-1] == "systemd-user"
