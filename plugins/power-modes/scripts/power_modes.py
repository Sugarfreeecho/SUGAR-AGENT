"""三种电源模式的守护进程（供 power-modes 插件使用）。

模式（互斥）：
    shield     护屏：铺满全屏的纯黑遮罩，系统保持唤醒与联网
    awake      常亮：挂住显示器与系统唤醒锁，屏幕不熄灭、不进待机
    autosleep  任务完成后睡眠：等 Agent 全部任务结束后关屏并进入睡眠，不关机
    none       关闭所有模式

设计要点：
* 状态写在 ``%LOCALAPPDATA%\\SugarAgent\\state\\power-mode.json``，托盘菜单据此显示勾选；
* 单实例守护：命名互斥体保证同一时间只有一个 daemon；
* autosleep 是一次性动作——触发睡眠后模式自动回落 ``none``，避免唤醒后立刻又睡；
* 后端不可达时不睡眠（状态未知 ≠ 空闲）。
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

MODE_NONE = "none"
MODE_SHIELD = "shield"
MODE_AWAKE = "awake"
MODE_AUTOSLEEP = "autosleep"
MODES = (MODE_NONE, MODE_SHIELD, MODE_AWAKE, MODE_AUTOSLEEP)

DEFAULT_IDLE_SECONDS = 180
POLL_SECONDS = 2.0
STATUS_POLL_SECONDS = 5.0
MUTEX_NAME = "SugarAgentPowerModes"
ERROR_ALREADY_EXISTS = 183

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

SCRIPT_DIR = Path(__file__).resolve().parent
SHIELD_SCRIPT = SCRIPT_DIR / "shield.ps1"


def state_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "SugarAgent" / "state"


def state_path() -> Path:
    return state_dir() / "power-mode.json"


def log_path() -> Path:
    return state_dir() / "power-modes.log"


def log(message: str) -> None:
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
        path = log_path()
        if path.exists() and path.stat().st_size > 512_000:
            path.unlink()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
    except OSError:
        pass


def read_state() -> dict:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def write_state(**updates) -> dict:
    data = read_state()
    data.update(updates)
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
        target = state_path()
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, target)
    except OSError as exc:
        log(f"state write failed: {exc}")
    return data


def current_mode() -> str:
    mode = str(read_state().get("mode") or MODE_NONE).strip().lower()
    return mode if mode in MODES else MODE_NONE


def idle_seconds_setting() -> int:
    try:
        value = int(read_state().get("idle_seconds") or DEFAULT_IDLE_SECONDS)
    except (TypeError, ValueError):
        value = DEFAULT_IDLE_SECONDS
    return max(15, min(3600, value))


def _set_thread_state(flags: int) -> bool:
    try:
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags)))
    except Exception as exc:  # pragma: no cover - platform guard
        log(f"SetThreadExecutionState failed: {exc}")
        return False


def backend_busy() -> Optional[bool]:
    """True/False when the backend answers, None when the state is unknown."""

    try:
        port = int(os.getenv("MYAGENT_SERVER_PORT") or 8192)
    except (TypeError, ValueError):
        port = 8192
    url = f"http://127.0.0.1:{port}/api/runtime-status"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return None
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    try:
        return int(payload.get("active_run_count") or 0) > 0
    except (TypeError, ValueError):
        return None


def sleep_now() -> bool:
    """Suspend the machine (screen off, session preserved, no shutdown)."""

    try:
        ok = bool(ctypes.windll.powrprof.SetSuspendState(False, False, False))
        log(f"SetSuspendState -> {ok}")
        return ok
    except Exception as exc:  # pragma: no cover - platform guard
        log(f"SetSuspendState failed: {exc}")
        return False


class ShieldProcess:
    """Owns the optional full-screen overlay child process."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._attempted = False

    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        # One start attempt per mode activation: a second attempt after the user
        # dismissed the overlay would fight the user's key press.
        if self.running() or self._attempted:
            return
        self._attempted = True
        powershell = str(
            Path(os.getenv("SystemRoot") or r"C:\Windows")
            / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        )
        try:
            self._proc = subprocess.Popen(
                [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-WindowStyle", "Hidden", "-File", str(SHIELD_SCRIPT)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            log(f"shield started pid={self._proc.pid}")
            write_state(shield_pid=self._proc.pid)
        except Exception as exc:
            log(f"shield start failed: {exc}")
            self._proc = None

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        self._attempted = False
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            log(f"shield stopped pid={proc.pid}")
        except Exception as exc:
            log(f"shield stop failed: {exc}")


def _mutex_handle():
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    already = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
    return handle, already


def run_daemon() -> int:
    handle, already = _mutex_handle()
    if already:
        log("daemon already running; exit")
        return 0
    log(f"daemon start pid={os.getpid()}")
    shield = ShieldProcess()
    last_mode = ""
    idle_started: Optional[float] = None
    last_status_poll = 0.0
    try:
        while True:
            mode = current_mode()
            if mode != last_mode:
                log(f"mode -> {mode}")
                last_mode = mode
                idle_started = None
            if mode == MODE_NONE:
                shield.stop()
                _set_thread_state(ES_CONTINUOUS)
                break
            if mode == MODE_SHIELD:
                _set_thread_state(ES_CONTINUOUS)
                shield.start()
                if not shield.running():
                    # The overlay exits on any key press; fall back to no mode so
                    # the tray checkmark tells the truth.
                    log("shield exited; reset mode to none")
                    write_state(mode=MODE_NONE)
                    break
                time.sleep(POLL_SECONDS)
                continue
            if mode == MODE_AWAKE:
                shield.stop()
                _set_thread_state(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                )
                time.sleep(POLL_SECONDS)
                continue
            # autosleep
            shield.stop()
            _set_thread_state(ES_CONTINUOUS)
            now = time.monotonic()
            if now - last_status_poll >= STATUS_POLL_SECONDS:
                last_status_poll = now
                busy = backend_busy()
                if busy is None:
                    log("runtime status unavailable; stay awake")
                    idle_started = None
                elif busy:
                    idle_started = None
                elif idle_started is None:
                    idle_started = now
                    log("tasks idle; counting down")
                else:
                    waited = now - idle_started
                    if waited >= idle_seconds_setting():
                        log(f"idle {waited:.0f}s >= threshold; sleeping")
                        write_state(mode=MODE_NONE, last_sleep_at=time.strftime("%Y-%m-%d %H:%M:%S"))
                        if sleep_now():
                            break
                        idle_started = now
            time.sleep(POLL_SECONDS)
    finally:
        shield.stop()
        _set_thread_state(ES_CONTINUOUS)
        log("daemon exit")
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
    return 0


def ensure_daemon() -> None:
    handle, already = _mutex_handle()
    try:
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass
    if already:
        return
    pythonw = Path(sys.executable)
    candidates = [pythonw.with_name("pythonw.exe"), pythonw]
    exe = next((path for path in candidates if path.exists()), pythonw)
    try:
        subprocess.Popen(
            [str(exe), str(Path(__file__).resolve()), "daemon"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        log("daemon spawned")
    except Exception as exc:
        log(f"daemon spawn failed: {exc}")


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "status"
    if command == "daemon":
        return run_daemon()
    if command == "set":
        mode = (argv[2] if len(argv) > 2 else "").strip().lower()
        if mode not in MODES:
            print(f"unknown mode: {mode!r}; expected one of {', '.join(MODES)}")
            return 2
        idle = None
        if "--idle-seconds" in argv:
            try:
                idle = int(argv[argv.index("--idle-seconds") + 1])
            except (IndexError, ValueError):
                idle = None
        updates = {"mode": mode}
        if idle is not None:
            updates["idle_seconds"] = idle
        write_state(**updates)
        if mode == MODE_NONE:
            print("mode: none")
            return 0
        ensure_daemon()
        print(f"mode: {mode}")
        return 0
    if command == "status":
        print(json.dumps(read_state(), ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
