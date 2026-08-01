import plistlib
from pathlib import Path

from app import platform_install


def _fake_venv(root: Path) -> None:
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")


def test_linux_install_writes_user_service_and_desktop_entry(tmp_path):
    root = tmp_path / "Sugar Agent"
    home = tmp_path / "home"
    root.mkdir()
    _fake_venv(root)

    installed = platform_install.install_linux(
        root,
        mode="desktop",
        home=home,
        run_commands=False,
    )

    unit = home / ".config" / "systemd" / "user" / "sugaragent.service"
    desktop = home / ".config" / "autostart" / "sugaragent-tray.desktop"
    assert installed == [unit, desktop]
    unit_text = unit.read_text(encoding="utf-8")
    assert f"WorkingDirectory={platform_install._systemd_quote(root)}" in unit_text
    assert "Restart=on-failure" in unit_text
    assert "MYAGENT_SERVER_PORT=8192" in unit_text
    assert platform_install._systemd_quote(
        root / "app" / "platform_tray.py"
    ) in desktop.read_text(encoding="utf-8")


def test_server_install_removes_desktop_autostart(tmp_path):
    root = tmp_path / "agent"
    home = tmp_path / "home"
    root.mkdir()
    _fake_venv(root)
    desktop = home / ".config" / "autostart" / "sugaragent-tray.desktop"
    desktop.parent.mkdir(parents=True)
    desktop.write_text("old", encoding="utf-8")

    platform_install.install_linux(
        root,
        mode="server",
        home=home,
        run_commands=False,
    )

    assert not desktop.exists()


def test_macos_install_writes_server_and_aqua_tray_launch_agents(tmp_path):
    root = tmp_path / "agent"
    home = tmp_path / "home"
    root.mkdir()
    _fake_venv(root)

    installed = platform_install.install_macos(
        root,
        home=home,
        run_commands=False,
    )

    assert len(installed) == 2
    server = plistlib.loads(installed[0].read_bytes())
    tray = plistlib.loads(installed[1].read_bytes())
    assert server["Label"] == "com.sugaragent.server"
    assert server["KeepAlive"] == {"SuccessfulExit": False}
    assert tray["Label"] == "com.sugaragent.tray"
    assert tray["LimitLoadToSessionType"] == "Aqua"


def test_uninstall_preserves_workspace_and_configuration(tmp_path):
    root = tmp_path / "agent"
    home = tmp_path / "home"
    root.mkdir()
    _fake_venv(root)
    workspace_file = root / "workspace" / "keep.txt"
    workspace_file.parent.mkdir()
    workspace_file.write_text("keep", encoding="utf-8")
    env_file = root / "app" / ".env"
    env_file.parent.mkdir()
    env_file.write_text("SECRET=keep", encoding="utf-8")
    platform_install.install_linux(
        root,
        mode="desktop",
        home=home,
        run_commands=False,
    )

    platform_install.uninstall(
        root,
        system_name="Linux",
        home=home,
        run_commands=False,
    )

    assert workspace_file.read_text(encoding="utf-8") == "keep"
    assert env_file.read_text(encoding="utf-8") == "SECRET=keep"
    assert not (root / ".venv").exists()
