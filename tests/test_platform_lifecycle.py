import subprocess
import json
from pathlib import Path

from app import platform_lifecycle


class _ActivationResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


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


def test_open_main_webui_reuses_live_page(monkeypatch):
    opened = []
    monkeypatch.setattr(
        platform_lifecycle.urllib_request,
        "urlopen",
        lambda request, timeout: _ActivationResponse({"ok": True, "reused": True}),
    )
    monkeypatch.setattr(
        platform_lifecycle.webbrowser,
        "open",
        lambda *args, **kwargs: opened.append((args, kwargs)),
    )

    assert platform_lifecycle.open_webui("/") is True
    assert opened == []


def test_open_main_webui_falls_back_when_no_page_is_reusable(monkeypatch):
    opened = []
    monkeypatch.setattr(
        platform_lifecycle,
        "request_webui_activation",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        platform_lifecycle.webbrowser,
        "open",
        lambda *args, **kwargs: opened.append((args, kwargs)) or True,
    )

    assert platform_lifecycle.open_webui("/") is False
    assert opened == [(('http://127.0.0.1:8192/',), {'new': 0, 'autoraise': True})]


def test_open_non_root_webui_does_not_reuse_main_page(monkeypatch):
    requests = []
    opened = []
    monkeypatch.setattr(
        platform_lifecycle,
        "request_webui_activation",
        lambda *args, **kwargs: requests.append((args, kwargs)) or True,
    )
    monkeypatch.setattr(
        platform_lifecycle.webbrowser,
        "open",
        lambda *args, **kwargs: opened.append((args, kwargs)) or True,
    )

    assert platform_lifecycle.open_webui("/setup/env") is False
    assert requests == []
    assert opened[0][0] == ('http://127.0.0.1:8192/setup/env',)
