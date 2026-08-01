"""Generate or remove per-user Linux/macOS service integration."""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .platform_lifecycle import (
        LAUNCHD_SERVER_LABEL,
        LAUNCHD_TRAY_LABEL,
        SYSTEMD_UNIT,
    )
except ImportError:
    from platform_lifecycle import (
        LAUNCHD_SERVER_LABEL,
        LAUNCHD_TRAY_LABEL,
        SYSTEMD_UNIT,
    )


def _systemd_quote(value: Path | str) -> str:
    raw = str(value)
    return '"' + raw.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def _write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def install_linux(
    root: Path,
    *,
    mode: str,
    home: Path | None = None,
    run_commands: bool = True,
) -> list[Path]:
    root = Path(root).resolve()
    home = Path.home() if home is None else Path(home).resolve()
    python_exe = root / ".venv" / "bin" / "python"
    if not python_exe.is_file():
        raise FileNotFoundError(f"virtual environment Python not found: {python_exe}")

    unit_dir = home / ".config" / "systemd" / "user"
    unit_path = unit_dir / SYSTEMD_UNIT
    unit = f"""[Unit]
Description=SugarAgent local AI agent
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
WorkingDirectory={_systemd_quote(root)}
ExecStart={_systemd_quote(python_exe)} {_systemd_quote(root / "app" / "main.py")}
Environment=PYTHONIOENCODING=utf-8
Environment=OPEN_BROWSER=0
Environment=MYAGENT_SERVER_PORT=8192
Restart=on-failure
RestartSec=2
TimeoutStopSec=15
KillMode=mixed

[Install]
WantedBy=default.target
"""
    _write_if_changed(unit_path, unit)
    installed = [unit_path]

    autostart_path = home / ".config" / "autostart" / "sugaragent-tray.desktop"
    if mode == "desktop":
        desktop = f"""[Desktop Entry]
Type=Application
Name=SugarAgent
Comment=SugarAgent menu and lifecycle controls
Exec={_systemd_quote(python_exe)} {_systemd_quote(root / "app" / "platform_tray.py")}
Icon={root / "app" / "assets" / "sugar-logo.png"}
Terminal=false
X-GNOME-Autostart-enabled=true
"""
        _write_if_changed(autostart_path, desktop)
        installed.append(autostart_path)
    elif autostart_path.exists():
        autostart_path.unlink()

    if run_commands:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", SYSTEMD_UNIT], check=True)
    return installed


def _write_plist(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False)
    if path.is_file() and path.read_bytes() == encoded:
        return
    path.write_bytes(encoded)


def install_macos(
    root: Path,
    *,
    home: Path | None = None,
    run_commands: bool = True,
) -> list[Path]:
    root = Path(root).resolve()
    home = Path.home() if home is None else Path(home).resolve()
    python_exe = root / ".venv" / "bin" / "python"
    if not python_exe.is_file():
        raise FileNotFoundError(f"virtual environment Python not found: {python_exe}")

    launch_agents = home / "Library" / "LaunchAgents"
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    server_plist = launch_agents / f"{LAUNCHD_SERVER_LABEL}.plist"
    tray_plist = launch_agents / f"{LAUNCHD_TRAY_LABEL}.plist"
    common_env = {
        "PYTHONIOENCODING": "utf-8",
        "OPEN_BROWSER": "0",
        "MYAGENT_SERVER_PORT": "8192",
        "PATH": os.environ.get(
            "PATH",
            "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        ),
    }
    _write_plist(
        server_plist,
        {
            "Label": LAUNCHD_SERVER_LABEL,
            "ProgramArguments": [str(python_exe), str(root / "app" / "main.py")],
            "WorkingDirectory": str(root),
            "EnvironmentVariables": common_env,
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "ThrottleInterval": 2,
            "ProcessType": "Interactive",
            "StandardOutPath": str(logs / "agent_terminal.log"),
            "StandardErrorPath": str(logs / "agent_terminal.log"),
        },
    )
    _write_plist(
        tray_plist,
        {
            "Label": LAUNCHD_TRAY_LABEL,
            "ProgramArguments": [str(python_exe), str(root / "app" / "platform_tray.py")],
            "WorkingDirectory": str(root),
            "EnvironmentVariables": common_env,
            "RunAtLoad": True,
            "KeepAlive": False,
            "LimitLoadToSessionType": "Aqua",
            "StandardOutPath": str(logs / "tray.log"),
            "StandardErrorPath": str(logs / "tray.log"),
        },
    )
    if run_commands:
        domain = f"gui/{os.getuid()}"
        for plist in (server_plist, tray_plist):
            subprocess.run(
                ["launchctl", "bootout", domain, str(plist)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)
    return [server_plist, tray_plist]


def uninstall(
    root: Path,
    *,
    system_name: str | None = None,
    home: Path | None = None,
    remove_venv: bool = True,
    run_commands: bool = True,
) -> list[Path]:
    root = Path(root).resolve()
    home = Path.home() if home is None else Path(home).resolve()
    system_name = system_name or platform.system()
    removed: list[Path] = []
    if system_name == "Linux":
        unit = home / ".config" / "systemd" / "user" / SYSTEMD_UNIT
        autostart = home / ".config" / "autostart" / "sugaragent-tray.desktop"
        if run_commands:
            subprocess.run(["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT], check=False)
        for path in (unit, autostart):
            if path.exists():
                path.unlink()
                removed.append(path)
        if run_commands:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    elif system_name == "Darwin":
        domain = f"gui/{os.getuid()}"
        for label in (LAUNCHD_SERVER_LABEL, LAUNCHD_TRAY_LABEL):
            plist = home / "Library" / "LaunchAgents" / f"{label}.plist"
            if run_commands:
                subprocess.run(["launchctl", "bootout", domain, str(plist)], check=False)
            if plist.exists():
                plist.unlink()
                removed.append(plist)
    else:
        raise RuntimeError(f"Unsupported uninstall platform: {system_name}")

    venv = root / ".venv"
    if remove_venv and venv.is_dir():
        shutil.rmtree(venv)
        removed.append(venv)
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--mode", choices=("desktop", "server"), default="desktop")
    parser.add_argument("--keep-venv", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    system_name = platform.system()
    if args.action == "uninstall":
        uninstall(root, remove_venv=not args.keep_venv)
        return 0
    if system_name == "Linux":
        install_linux(root, mode=args.mode)
    elif system_name == "Darwin":
        if args.mode != "desktop":
            parser.error("macOS source installs currently support desktop mode only")
        install_macos(root)
    else:
        parser.error(f"unsupported operating system: {system_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
