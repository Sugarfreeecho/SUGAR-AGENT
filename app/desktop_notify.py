# -*- coding: utf-8 -*-
"""Native desktop notifications used by the SugarAgent backend.

Browsers cannot reliably run JavaScript after a tab/window is destroyed, so the
WebUI reports page close through sendBeacon and this module is responsible for
the actual system-level popup (OS notification or message box fallback).
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
from pathlib import Path


logger = logging.getLogger(__name__)

NOTIFY_TITLE = "SugarAgent"


def _tray_location_phrase() -> str:
    """User-facing location of the resident icon for the current OS."""

    system = platform.system()
    if system == "Darwin":
        return "macOS 顶部菜单栏"
    if system == "Linux":
        return "Ubuntu 顶部栏"
    return "Windows 任务栏右下角"


NOTIFY_MESSAGE = (
    "SugarAgent 正在后台运行，任务不会中断。"
    f"可从{_tray_location_phrase()}的 SugarAgent 图标重新打开。"
)
# Real Windows 10/11 Action Center toast (not a tray balloon).
_UI_CLOSED_TOAST_SCRIPT = Path(__file__).resolve().parent / "notify_ui_closed.ps1"


def show_ui_closed_notification() -> None:
    """Show a native popup after all WebUI pages have been closed."""

    show_desktop_notification()


def show_desktop_notification(
    title: str = NOTIFY_TITLE,
    message: str = NOTIFY_MESSAGE,
    session_id: str = "",
) -> None:
    """Show a native desktop notification with the given title and message."""

    system = platform.system()
    if system == "Windows":
        if _notify_windows_toast(title, message, session_id):
            return
        _notify_windows_message_box(title, message)
    elif system == "Darwin":
        _notify_macos(title, message)
    elif system == "Linux":
        _notify_linux(title, message)
    else:
        logger.info("Desktop notification is not supported on %s", system)


def _notify_windows_toast(title: str, message: str, session_id: str = "") -> bool:
    """Show a system toast in the Windows notification center.

    The actual toast is rendered by app/notify_ui_closed.ps1 so it works even
    after every browser page is gone; a message box remains as the last fallback
    when no interactive Windows notification session is available.
    """

    if not _UI_CLOSED_TOAST_SCRIPT.is_file():
        return False
    env = os.environ.copy()
    env["SUGARAGENT_NOTIFY_TITLE"] = title
    env["SUGARAGENT_NOTIFY_MESSAGE"] = message
    if str(session_id or "").strip():
        env["SUGARAGENT_NOTIFY_SESSION"] = str(session_id).strip()
    else:
        env.pop("SUGARAGENT_NOTIFY_SESSION", None)
    # Windows PowerShell 5.1 decodes UTF-8 scripts without a BOM using the
    # legacy system code page. Pass localized text through the Unicode Windows
    # environment block so the PowerShell file itself can remain ASCII-safe.
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(_UI_CLOSED_TOAST_SCRIPT),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return proc.wait(timeout=20) == 0
    except subprocess.TimeoutExpired:
        logger.warning("Windows toast helper timed out after 20 seconds")
        if proc is not None:
            _terminate_process(proc)
        return False
    except Exception as exc:
        logger.warning("Unable to show Windows toast: %s", exc)
        return False


def _terminate_process(proc: subprocess.Popen, timeout: float = 2.0) -> None:
    """Stop a timed-out notification helper before another fallback runs."""

    try:
        proc.terminate()
    except Exception:
        logger.debug("Unable to terminate notification helper", exc_info=True)
    try:
        proc.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        logger.debug("Unable to wait for notification helper exit", exc_info=True)
        return
    try:
        proc.kill()
        proc.wait(timeout=timeout)
    except Exception:
        logger.debug("Unable to kill notification helper", exc_info=True)


def _notify_windows_message_box(title: str, message: str) -> None:
    """Fallback: show a native message box in a worker thread."""

    try:
        import ctypes
    except Exception:
        return

    def worker() -> None:
        try:
            # MB_ICONINFORMATION | MB_SYSTEMMODAL | MB_TOPMOST
            ctypes.windll.user32.MessageBoxW(
                0,
                message,
                title,
                0x40 | 0x1000 | 0x40000,
            )
        except Exception as exc:
            logger.warning("Unable to show Windows message box: %s", exc)

    threading.Thread(target=worker, name="ui-closed-notify", daemon=True).start()


def _notify_macos(title: str, message: str) -> None:
    script = (
        f'display notification "{_escape_apple_script(message)}" '
        f'with title "{_escape_apple_script(title)}"'
    )
    try:
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.info("Unable to show macOS notification: %s", exc)


def _notify_linux(title: str, message: str) -> None:
    if not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
        logger.info("Skipping Linux notification: no desktop display available")
        return
    try:
        subprocess.Popen(
            ["notify-send", "-a", title, title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.info("notify-send is not available; skipping Linux notification")
    except Exception as exc:
        logger.info("Unable to show Linux notification: %s", exc)


def _escape_apple_script(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
