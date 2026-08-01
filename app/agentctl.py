"""Unified command-line lifecycle controller for Linux and macOS."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

try:
    from .platform_lifecycle import backend_for, lifecycle_name, open_webui, port_is_listening
except ImportError:
    from platform_lifecycle import backend_for, lifecycle_name, open_webui, port_is_listening


ROOT = Path(__file__).resolve().parents[1]


def _wait_for_port(expected: bool, timeout: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_listening() is expected:
            return True
        time.sleep(0.25)
    return port_is_listening() is expected


def _spawn_tray() -> None:
    tray_script = ROOT / "app" / "platform_tray.py"
    subprocess.Popen(
        [str(Path(sys.executable).resolve()), str(tray_script)],
        cwd=str(ROOT),
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "start", "stop", "restart", "status", "logs", "update", "tray",
            "security-status",
        ),
    )
    parser.add_argument("--tray", action="store_true", help="also start the desktop tray")
    parser.add_argument("--no-follow", action="store_true", help="do not follow logs")
    args = parser.parse_args(argv)

    if platform.system() not in {"Linux", "Darwin", "Windows"}:
        parser.error(f"unsupported operating system: {platform.system()}")

    backend = backend_for(ROOT)
    if args.command == "security-status":
        from security.runtime import security_status_for_session

        print(security_status_for_session(""))
        return 0
    if args.command == "status":
        status = backend.status()
        print("running" if status.running else "stopped")
        if status.detail:
            print(status.detail)
        return 0 if status.running else 3
    if args.command == "start":
        backend.start()
        if not _wait_for_port(True):
            print("SugarAgent did not become ready within 120 seconds.", file=sys.stderr)
            return 1
        if args.tray and (
            platform.system() == "Darwin"
            or os.getenv("DISPLAY")
            or os.getenv("WAYLAND_DISPLAY")
        ):
            _spawn_tray()
        if platform.system() == "Linux" and not (
            os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")
        ):
            print("SugarAgent is ready at http://127.0.0.1:8192/")
            print(
                "For remote access, run on your client: "
                "ssh -L 8192:127.0.0.1:8192 user@server"
            )
        else:
            open_webui()
        return 0
    if args.command == "stop":
        backend.stop()
        return 0 if _wait_for_port(False, 30.0) else 1
    if args.command == "restart":
        backend.restart()
        return 0 if _wait_for_port(True) else 1
    if args.command == "logs":
        return backend.logs(follow=not args.no_follow)
    if args.command == "update":
        return backend.update()
    if args.command == "tray":
        return subprocess.call(
            [str(Path(sys.executable).resolve()), str(ROOT / "app" / "platform_tray.py")],
            cwd=str(ROOT),
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
