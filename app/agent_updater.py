# -*- coding: utf-8 -*-
"""Pull a safe fast-forward update, refresh dependencies, and restart Agent."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

try:
    from .platform_lifecycle import backend_for, lifecycle_name, open_webui
except ImportError:
    from platform_lifecycle import backend_for, lifecycle_name, open_webui


APP_NAME = "Agent 智能会话助手"
HOST = "127.0.0.1"
PORT = 8192
PROCESS_SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102
CREATE_FLAGS = (
    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    if os.name == "nt"
    else 0
)


@dataclass(frozen=True)
class UpdateResult:
    previous_revision: str
    current_revision: str
    dependencies_updated: bool

    @property
    def changed(self) -> bool:
        return self.previous_revision != self.current_revision


class UpdateLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a", encoding="utf-8", buffering=1)

    def write(self, message: str = "") -> None:
        print(message, flush=True)
        self._file.write(message + "\n")

    def close(self) -> None:
        self._file.close()


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: Sequence[str], cwd: Path, log: UpdateLog) -> str:
    log.write(f"> {' '.join(command)}")
    proc = subprocess.Popen(
        list(command),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output: list[str] = []
    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.rstrip("\r\n")
        output.append(line)
        log.write(line)
    return_code = proc.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, list(command), "\n".join(output))
    return "\n".join(output).strip()


def update_repository(
    root: Path,
    python_exe: Path,
    log: UpdateLog,
    *,
    runner: Callable[[Sequence[str], Path, UpdateLog], str] = run_command,
) -> UpdateResult:
    if not (root / ".git").exists():
        raise RuntimeError(f"当前目录不是 Git 仓库：{root}")

    requirements = root / "app" / "requirements.txt"
    requirements_before = _sha256(requirements)
    previous_revision = runner(["git", "rev-parse", "HEAD"], root, log).splitlines()[-1].strip()
    runner(["git", "pull", "--ff-only"], root, log)
    current_revision = runner(["git", "rev-parse", "HEAD"], root, log).splitlines()[-1].strip()

    dependencies_updated = requirements_before != _sha256(requirements)
    if dependencies_updated:
        log.write("检测到 Python 依赖清单变化，正在同步依赖...")
        runner([str(python_exe), "-m", "pip", "install", "-r", str(requirements)], root, log)

    return UpdateResult(previous_revision, current_revision, dependencies_updated)


def wait_for_launcher_exit(pid: int, timeout_seconds: float = 30.0) -> None:
    if pid <= 0:
        return
    if os.name != "nt":
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                return
            time.sleep(0.1)
        raise TimeoutError(f"Timed out waiting for launcher PID {pid} to exit")
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        result = ctypes.windll.kernel32.WaitForSingleObject(handle, int(timeout_seconds * 1000))
        if result == WAIT_TIMEOUT:
            raise TimeoutError("等待旧的常驻图标进程退出超时")
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def is_agent_listening() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.4):
            return True
    except OSError:
        return False


def wait_for_agent(timeout_seconds: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_agent_listening():
            return True
        time.sleep(0.5)
    return False


def launch_agent(
    root: Path,
    python_exe: Path,
    log: UpdateLog,
    *,
    lifecycle: str = "windows-tray",
) -> bool:
    if lifecycle != "windows-tray":
        backend = backend_for(root, name=lifecycle)
        backend.reload()
        backend.start()
        return wait_for_agent()
    tray_launcher = root / "app" / "tray_launcher.py"
    if not tray_launcher.is_file():
        raise RuntimeError(f"更新后缺少托盘启动器：{tray_launcher}")
    pythonw = python_exe.with_name("pythonw.exe")
    launcher_python = pythonw if pythonw.is_file() else python_exe
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    log.write("正在重新启动 Agent...")
    subprocess.Popen(
        [str(launcher_python), str(tray_launcher), "--daemon"],
        cwd=str(root),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_FLAGS,
    )
    return wait_for_agent()


def show_result(message: str, *, error: bool = False) -> None:
    flags = 0x00000010 if error else 0x00000040
    try:
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, flags)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--launcher-pid", type=int, default=0)
    parser.add_argument(
        "--lifecycle",
        choices=("windows-tray", "systemd-user", "launchd-user"),
        default=None,
    )
    parser.add_argument("--restart-tray", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    python_exe = Path(sys.executable).resolve()
    log_path = root / "logs" / "agent_update.log"
    log = UpdateLog(log_path)
    update_result: UpdateResult | None = None
    update_error: Exception | None = None
    restarted = False
    selected_lifecycle = args.lifecycle or lifecycle_name()
    backend = (
        backend_for(root, name=selected_lifecycle)
        if selected_lifecycle != "windows-tray"
        else None
    )

    log.write("")
    log.write("=" * 72)
    log.write(time.strftime("Agent update started at %Y-%m-%d %H:%M:%S"))
    try:
        wait_for_launcher_exit(args.launcher_pid)
        if backend is not None:
            backend.stop()
        update_result = update_repository(root, python_exe, log)
    except Exception as exc:
        update_error = exc
        log.write(f"更新失败：{type(exc).__name__}: {exc}")
    finally:
        try:
            if selected_lifecycle == "windows-tray":
                restarted = launch_agent(root, python_exe, log)
            else:
                restarted = launch_agent(
                    root,
                    python_exe,
                    log,
                    lifecycle=selected_lifecycle,
                )
        except Exception as exc:
            log.write(f"重新启动失败：{type(exc).__name__}: {exc}")
        log.close()

    if args.restart_tray and selected_lifecycle != "windows-tray":
        try:
            subprocess.Popen(
                [
                    str(python_exe),
                    str(root / "app" / "platform_tray.py"),
                ],
                cwd=str(root),
                env=os.environ.copy(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    if not restarted:
        show_result(f"Agent 更新后未能重新启动。\n\n请查看日志：\n{log_path}", error=True)
        return 1
    if update_error is not None:
        show_result(
            f"更新未完成，但 Agent 已恢复启动。\n\n原因：{update_error}\n\n详情：{log_path}",
            error=True,
        )
        return 1

    assert update_result is not None
    if update_result.changed:
        message = "Agent 已更新到最新版本并重新启动。"
    else:
        message = "Agent 已是最新版本，并已重新启动。"
    if update_result.dependencies_updated:
        message += "\nPython 依赖也已同步。"
    show_result(message)
    try:
        open_webui("/", base_url=f"http://{HOST}:{PORT}")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
