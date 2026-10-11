"""Passively record brief Windows windows and their process ancestry.

Run with the project's Python on the affected computer. No commands, windows,
or child processes are launched by this recorder. Command lines and environment
variables are deliberately omitted from the JSONL output.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=600, help="Recording time (default: 600 seconds)")
    parser.add_argument("--output", type=Path, help="Optional JSONL output path")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This recorder requires Windows.")
    if not 1 <= args.seconds <= 86400:
        parser.error("--seconds must be between 1 and 86400.")
    output = args.output or (
        Path(__file__).resolve().parents[1] / "logs"
        / ("console-flashes-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".jsonl")
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    own_pid = os.getpid()
    lock = threading.RLock()
    stop = threading.Event()
    process_cache: dict[int, dict] = {}
    recent_processes: list[dict] = []
    windows: dict[int, dict] = {}
    counts = {"window_show": 0, "window_hide": 0, "window_destroy": 0,
              "window_event_unresolved": 0, "process_start": 0}
    stream = output.open("w", encoding="utf-8", buffering=1)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        getattr(kernel32, name).argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        getattr(kernel32, name).restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                  wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL

    def write(event: str, **data) -> None:
        with lock:
            stream.write(json.dumps({"time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                                     "event": event, **data}, ensure_ascii=False) + "\n")
            if event in counts:
                counts[event] += 1

    def process_info(pid: int) -> dict:
        with lock:
            row = dict(process_cache.get(pid, {"pid": pid}))
        if "ppid" not in row:
            snapshot()
            with lock:
                row = dict(process_cache.get(pid, row))
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            row["exited_or_inaccessible"] = True
            return row
        try:
            image = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(image))
            if kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
                row.update(exe=image.value, name=Path(image.value).name)
            times = [wintypes.FILETIME() for _ in range(4)]
            if kernel32.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
                ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
                row["created_at"] = ticks / 10000000 - 11644473600
            with lock:
                process_cache[pid] = dict(row)
        finally:
            kernel32.CloseHandle(handle)
        return row

    def ancestry(pid: int) -> list[dict]:
        rows = []
        seen = set()
        for _ in range(8):
            if pid <= 0 or pid in seen:
                break
            seen.add(pid)
            row = process_info(pid)
            rows.append(row)
            pid = int(row.get("ppid") or 0)
        return rows

    def snapshot() -> dict[tuple, dict]:
        rows = {}
        handle = kernel32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            more = kernel32.Process32FirstW(handle, ctypes.byref(entry))
            while more:
                row = {"pid": int(entry.th32ProcessID), "name": entry.szExeFile,
                       "ppid": int(entry.th32ParentProcessID)}
                with lock:
                    cached = process_cache.get(row["pid"], {})
                    if (cached.get("name"), cached.get("ppid")) == (row["name"], row["ppid"]):
                        row = {**cached, **row}
                    process_cache[row["pid"]] = row
                rows[(row["pid"], row["name"], row["ppid"])] = row
                more = kernel32.Process32NextW(handle, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(handle)
        return rows

    previous = snapshot()

    def watch_processes() -> None:
        nonlocal previous
        try:
            while not stop.wait(0.1):
                current = snapshot()
                for key in current.keys() - previous.keys():
                    row = current[key]
                    if row["pid"] == own_pid:
                        continue
                    parents = ancestry(row["pid"])
                    with lock:
                        recent_processes.append({"observed_at": time.monotonic(), "process": parents[0]})
                        recent_processes[:] = [item for item in recent_processes
                                               if time.monotonic() - item["observed_at"] < 5]
                    write("process_start", ancestry=parents)
                previous = current
        except Exception as exc:
            write("recorder_error", component="process_poll", error=str(exc))

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                     wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
    user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                                      callback_type, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
    user32.SetWinEventHook.restype = wintypes.HANDLE
    user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    user32.UnhookWinEvent.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    for name in ("GetClassNameW", "GetWindowTextW"):
        function = getattr(user32, name)
        function.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        function.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                   wintypes.UINT, wintypes.UINT, wintypes.UINT]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.restype = ctypes.c_ssize_t

    @callback_type
    def on_window(_hook, event, hwnd, object_id, child_id, thread_id, event_timestamp):
        if not hwnd or object_id != 0 or child_id != 0:
            return
        try:
            handle = int(hwnd)
            if event in (0x8001, 0x8003):  # EVENT_OBJECT_DESTROY / EVENT_OBJECT_HIDE
                row = windows.pop(handle, None)
                if row is not None:
                    write("window_destroy" if event == 0x8001 else "window_hide",
                          hwnd=hex(handle), window_class=row["window_class"],
                          process=row["process"], lifetime_ms=round((time.monotonic() - row["shown_at"]) * 1000))
                return
            root = user32.GetAncestor(hwnd, 2)
            if root and root != hwnd:
                return
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                write("window_event_unresolved", hwnd=hex(handle), thread_id=thread_id,
                      event_timestamp_ms=event_timestamp,
                      reason="Window disappeared before its process could be read.")
                return
            if pid.value == own_pid:
                return
            class_name, title = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(512)
            user32.GetClassNameW(hwnd, class_name, len(class_name))
            user32.GetWindowTextW(hwnd, title, len(title))
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            parents = ancestry(pid.value)
            now = time.monotonic()
            with lock:
                nearby = [item["process"] for item in recent_processes if now - item["observed_at"] < 3][-30:]
            windows[handle] = {"shown_at": now, "window_class": class_name.value, "process": parents[0]}
            write("window_show", hwnd=hex(handle), window_class=class_name.value, title=title.value,
                  rect=[rect.left, rect.top, rect.right, rect.bottom], ancestry=parents,
                  visible_when_read=bool(user32.IsWindowVisible(hwnd)),
                  thread_id=thread_id, event_timestamp_ms=event_timestamp,
                  nearby_processes=nearby)
            print(f"{datetime.now():%H:%M:%S}  window: {class_name.value}  process: {parents[0].get('name', pid.value)}", flush=True)
        except Exception as exc:
            write("recorder_error", component="window_hook", error=str(exc))

    hook = user32.SetWinEventHook(0x8001, 0x8003, None, on_window, 0, 0, 2)
    if not hook:
        stream.close()
        raise ctypes.WinError(ctypes.get_last_error())
    write("capture_start", windows=platform.platform(), python=sys.executable,
          recorder_pid=own_pid, seconds=args.seconds, process_poll_ms=100,
          notes="Top-level window show/hide/destroy events; process polling may miss very short-lived processes. Windows that vanish before inspection are logged unresolved. No command lines or environment variables.")
    worker = threading.Thread(target=watch_processes, name="flash-process-recorder", daemon=True)
    worker.start()
    print(f"Recording for {args.seconds:g} seconds. Leave the affected app idle; Ctrl+C stops early.\nLog: {output}", flush=True)
    deadline = time.monotonic() + args.seconds
    try:
        message = wintypes.MSG()
        while time.monotonic() < deadline:
            while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
            stop.wait(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnhookWinEvent(hook)
        stop.set()
        worker.join()
        write("capture_end", counts=counts)
        stream.close()
    print(f"Done: {counts}\nLog: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
