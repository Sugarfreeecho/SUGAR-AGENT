"""Dispatch to the native SugarAgent tray/menu-bar adapter."""

from __future__ import annotations

import os
import platform
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import dotenv

try:
    from .platform_lifecycle import LifecycleBackend
except ImportError:
    from platform_lifecycle import LifecycleBackend


ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_MENU_ENV = "MYAGENT_TRAY_SHOW_UPDATE_RESTART"
TRUE_VALUES = {"1", "true", "yes", "on"}


def lifecycle_menu_enabled(root: Path = ROOT) -> bool:
    raw = os.getenv(LIFECYCLE_MENU_ENV, "0")
    env_file = Path(root) / "app" / ".env"
    if env_file.is_file():
        configured = dotenv.dotenv_values(env_file).get(LIFECYCLE_MENU_ENV)
        if configured is not None:
            raw = str(configured)
    return str(raw or "").strip().lower() in TRUE_VALUES


@contextmanager
def single_instance_lock() -> Iterator[bool]:
    """Use a per-user advisory lock on POSIX desktop platforms."""

    import fcntl

    runtime = Path(os.getenv("XDG_RUNTIME_DIR") or (Path.home() / ".cache"))
    runtime.mkdir(parents=True, exist_ok=True)
    lock_path = runtime / "sugaragent-tray.lock"
    handle = lock_path.open("a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        handle.close()


def launch_updater(backend: LifecycleBackend) -> None:
    command = [
        *backend.update_command(),
        "--launcher-pid",
        str(os.getpid()),
        "--restart-tray",
    ]
    subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def open_logs_in_terminal(backend: LifecycleBackend) -> None:
    log_command = backend.logs_command(follow=True)
    system_name = platform.system()
    if system_name == "Darwin":
        shell_line = " ".join(_shell_quote(part) for part in log_command)
        apple_script_line = shell_line.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(
            [
                "osascript",
                "-e",
                f'tell application "Terminal" to do script "{apple_script_line}"',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    candidates = [
        ["gnome-terminal", "--", *log_command],
        ["konsole", "-e", *log_command],
        ["x-terminal-emulator", "-e", *log_command],
    ]
    for command in candidates:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue
    raise RuntimeError("No supported terminal emulator was found.")


def _shell_quote(value: str) -> str:
    import shlex

    return shlex.quote(str(value))


def main() -> int:
    with single_instance_lock() as owner:
        if not owner:
            return 0
        system_name = platform.system()
        if system_name == "Linux":
            try:
                from .platform_tray_linux import run
            except ImportError:
                from platform_tray_linux import run
            return run(ROOT)
        if system_name == "Darwin":
            try:
                from .platform_tray_macos import run
            except ImportError:
                from platform_tray_macos import run
            return run(ROOT)
        raise RuntimeError(
            "The cross-platform tray entry supports Linux and macOS. "
            "Windows continues to use app/tray_launcher.py."
        )


if __name__ == "__main__":
    raise SystemExit(main())
