"""Cross-process identity for the active ReAct run fence.

The fence token rejects late writes.  PID alone is not enough to decide whether
the writer still exists because operating systems reuse PIDs after a crash.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RunFenceOwner:
    status: str  # absent, live, dead, legacy, or unknown/unverifiable
    pid: Optional[int] = None
    run_id: str = ""


def _process_start_time(pid: int) -> tuple[str, Optional[float]]:
    """Return (live/dead/unknown, creation time) without requiring psutil."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class FileTime(ctypes.Structure):
            _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_times = kernel32.GetProcessTimes
        get_times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(FileTime)] * 4
        get_times.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ("dead" if ctypes.get_last_error() in {87, 1168} else "unknown", None)
        try:
            created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
            if not get_times(handle, created, exited, kernel, user):
                return "unknown", None
            if (exited.high << 32) | exited.low:
                return "dead", None
            ticks = (created.high << 32) | created.low
            return "live", ticks / 10_000_000 - 11_644_473_600
        finally:
            close_handle(handle)
    if sys.platform.startswith("linux"):
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            start_ticks = int(stat.rsplit(")", 1)[1].split()[19])
            boot_line = next(
                line for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines()
                if line.startswith("btime ")
            )
            return "live", int(boot_line.split()[1]) + start_ticks / os.sysconf("SC_CLK_TCK")
        except FileNotFoundError:
            return "dead", None
        except (OSError, ValueError, IndexError, StopIteration):
            return "unknown", None
    try:
        import psutil

        return "live", float(psutil.Process(pid).create_time())
    except Exception as exc:
        try:
            import psutil

            if isinstance(exc, psutil.NoSuchProcess):
                return "dead", None
        except ImportError:
            pass
        return "unknown", None


def current_process_identity() -> tuple[int, Optional[float]]:
    pid = os.getpid()
    status, started_at = _process_start_time(pid)
    return pid, started_at if status == "live" else None


def inspect_run_fence(path: Path) -> RunFenceOwner:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return RunFenceOwner("absent")
    except (OSError, ValueError, TypeError):
        return RunFenceOwner("unknown")
    if not isinstance(data, dict):
        return RunFenceOwner("unknown")
    run_id = str(data.get("run_id") or "")
    if "owner_pid" not in data and "owner_started_at" not in data:
        return RunFenceOwner("legacy", run_id=run_id)
    try:
        pid = int(data.get("owner_pid"))
        if pid <= 0:
            raise ValueError("invalid process identity")
    except (TypeError, ValueError):
        return RunFenceOwner("unknown", run_id=run_id)
    try:
        started_at = float(data.get("owner_started_at"))
        if started_at <= 0:
            raise ValueError("invalid process start time")
    except (TypeError, ValueError):
        return RunFenceOwner("unknown", pid, run_id)
    status, actual_start = _process_start_time(pid)
    if status != "live" or actual_start is None:
        return RunFenceOwner(status, pid, run_id)
    # A live process with a reused PID must not be mistaken for the old owner.
    return RunFenceOwner("live" if abs(actual_start - started_at) < 0.01 else "dead", pid, run_id)
