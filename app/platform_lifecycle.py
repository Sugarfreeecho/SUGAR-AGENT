"""Cross-platform lifecycle controls for the SugarAgent backend service."""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys
import webbrowser
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


HOST = "127.0.0.1"
PORT = 8192
BASE_URL = f"http://{HOST}:{PORT}"
SYSTEMD_UNIT = "sugaragent.service"
LAUNCHD_SERVER_LABEL = "com.sugaragent.server"
LAUNCHD_TRAY_LABEL = "com.sugaragent.tray"


@dataclass(frozen=True)
class LifecycleStatus:
    running: bool
    detail: str = ""


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def port_is_listening(host: str = HOST, port: int = PORT) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.4):
            return True
    except OSError:
        return False


def open_webui(path: str = "/") -> None:
    suffix = path if str(path).startswith("/") else f"/{path}"
    webbrowser.open(f"{BASE_URL}{suffix}", new=0, autoraise=True)


def _run(
    command: Sequence[str],
    *,
    runner: CommandRunner = subprocess.run,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return runner(
        list(command),
        check=check,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class LifecycleBackend(ABC):
    """Small lifecycle contract shared by CLI and native tray adapters."""

    def __init__(
        self,
        root: Path,
        *,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        self.root = Path(root).resolve()
        self.runner = runner

    @abstractmethod
    def status(self) -> LifecycleStatus:
        raise NotImplementedError

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    def restart(self) -> None:
        self.stop()
        self.start()

    @abstractmethod
    def reload(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def logs_command(self, *, follow: bool = True) -> list[str]:
        raise NotImplementedError

    def logs(self, *, follow: bool = True) -> int:
        return subprocess.call(self.logs_command(follow=follow))

    def update_command(self) -> list[str]:
        if isinstance(self, SystemdUserBackend):
            selected = "systemd-user"
        elif isinstance(self, LaunchdUserBackend):
            selected = "launchd-user"
        else:
            selected = "windows-tray"
        return [
            str(Path(sys.executable).resolve()),
            str(self.root / "app" / "agent_updater.py"),
            "--root",
            str(self.root),
            "--lifecycle",
            selected,
        ]

    def update(self) -> int:
        return subprocess.call(self.update_command(), cwd=str(self.root))


class SystemdUserBackend(LifecycleBackend):
    def _systemctl(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return _run(
            ["systemctl", "--user", *args],
            runner=self.runner,
            check=check,
        )

    def status(self) -> LifecycleStatus:
        result = self._systemctl("is-active", SYSTEMD_UNIT, check=False)
        detail = (result.stdout or result.stderr or "").strip()
        return LifecycleStatus(result.returncode == 0 and detail == "active", detail)

    def start(self) -> None:
        self._systemctl("start", SYSTEMD_UNIT)

    def stop(self) -> None:
        self._systemctl("stop", SYSTEMD_UNIT, check=False)

    def restart(self) -> None:
        self._systemctl("restart", SYSTEMD_UNIT)

    def reload(self) -> None:
        self._systemctl("daemon-reload")

    def logs_command(self, *, follow: bool = True) -> list[str]:
        command = ["journalctl", "--user", "-u", SYSTEMD_UNIT, "-n", "200"]
        if follow:
            command.append("-f")
        return command


class LaunchdUserBackend(LifecycleBackend):
    @property
    def domain(self) -> str:
        return f"gui/{os.getuid()}"

    @property
    def plist(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_SERVER_LABEL}.plist"

    def _launchctl(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return _run(
            ["launchctl", *args],
            runner=self.runner,
            check=check,
        )

    def status(self) -> LifecycleStatus:
        result = self._launchctl(
            "print",
            f"{self.domain}/{LAUNCHD_SERVER_LABEL}",
            check=False,
        )
        detail = (result.stdout or result.stderr or "").strip()
        return LifecycleStatus(result.returncode == 0 and port_is_listening(), detail)

    def start(self) -> None:
        printed = self._launchctl(
            "print",
            f"{self.domain}/{LAUNCHD_SERVER_LABEL}",
            check=False,
        )
        if printed.returncode != 0:
            self._launchctl("bootstrap", self.domain, str(self.plist))
        self._launchctl(
            "kickstart",
            "-k",
            f"{self.domain}/{LAUNCHD_SERVER_LABEL}",
        )

    def stop(self) -> None:
        self._launchctl("bootout", self.domain, str(self.plist), check=False)

    def restart(self) -> None:
        self.stop()
        self.start()

    def reload(self) -> None:
        self.stop()

    def logs_command(self, *, follow: bool = True) -> list[str]:
        log_file = self.root / "logs" / "agent_terminal.log"
        command = ["tail", "-n", "200"]
        if follow:
            command.append("-f")
        command.append(str(log_file))
        return command


class WindowsLauncherBackend(LifecycleBackend):
    """Controller for the existing Win32 tray launcher.

    The Win32 tray remains the process supervisor. This backend is intentionally
    thin and is primarily useful for shared status/start/update code.
    """

    def status(self) -> LifecycleStatus:
        running = port_is_listening()
        return LifecycleStatus(running, "listening" if running else "stopped")

    def start(self) -> None:
        subprocess.Popen(
            ["cmd.exe", "/c", str(self.root / "RUN.bat")],
            cwd=str(self.root),
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )

    def stop(self) -> None:
        raise RuntimeError("Stop the Windows Agent from its tray menu.")

    def reload(self) -> None:
        return None

    def logs_command(self, *, follow: bool = True) -> list[str]:
        return [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(self.root / "app" / "colored_log_viewer.ps1"),
        ]


def lifecycle_name(system_name: str | None = None) -> str:
    name = system_name or platform.system()
    if name == "Linux":
        return "systemd-user"
    if name == "Darwin":
        return "launchd-user"
    if name == "Windows":
        return "windows-tray"
    raise RuntimeError(f"Unsupported operating system: {name}")


def backend_for(
    root: Path,
    *,
    name: str | None = None,
    runner: CommandRunner = subprocess.run,
) -> LifecycleBackend:
    selected = name or lifecycle_name()
    if selected == "systemd-user":
        return SystemdUserBackend(root, runner=runner)
    if selected == "launchd-user":
        return LaunchdUserBackend(root, runner=runner)
    if selected == "windows-tray":
        return WindowsLauncherBackend(root, runner=runner)
    raise ValueError(f"Unknown lifecycle backend: {selected}")


def child_environment(
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env["PYTHONIOENCODING"] = "utf-8"
    env["OPEN_BROWSER"] = "0"
    env["MYAGENT_SERVER_PORT"] = str(PORT)
    return env
