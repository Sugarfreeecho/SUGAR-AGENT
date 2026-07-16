# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import argparse
import os
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

import win32api
import win32con
import win32event
import win32gui
import winerror

from python_runtime import configure_agent_python_environment, preferred_python


APP_NAME = "Agent \u667a\u80fd\u4f1a\u8bdd\u52a9\u624b"
MSG_STARTING = "\u6b63\u5728\u542f\u52a8 Agent\uff0c\u8bf7\u7a0d\u5019..."
MSG_LOG = "\u7ec8\u7aef\u65e5\u5fd7"
MSG_RUNNING = "Agent \u6258\u76d8\u542f\u52a8\u5668\u5df2\u5728\u8fd0\u884c\uff0c\u6b63\u5728\u6253\u5f00 WebUI..."
MSG_PRESS_ENTER = "\u6309\u56de\u8f66\u9000\u51fa..."
MSG_DETECTED = "\u68c0\u6d4b\u5230 Agent \u5df2\u5728\u8fd0\u884c\uff0c\u63a5\u7ba1\u6258\u76d8\u83dc\u5355\u3002"
MSG_FAILED = "Agent \u542f\u52a8\u5931\u8d25\uff0c\u9000\u51fa\u7801"
MSG_CHECK_LOG = "\u8bf7\u67e5\u770b\u65e5\u5fd7"
MSG_READY = "Agent \u5df2\u542f\u52a8\uff0c\u6b63\u5728\u6253\u5f00 WebUI \u5e76\u6536\u8d77\u7ec8\u7aef\u7a97\u53e3..."
MSG_LOADING = "\u52a0\u8f7d\u4e2d"
MSG_TIMEOUT = "\u7b49\u5f85 Agent \u542f\u52a8\u8d85\u65f6\uff0c\u8bf7\u67e5\u770b\u65e5\u5fd7"
MSG_NOT_READY = "Agent \u5c1a\u672a\u5c31\u7eea\uff0c\u8bf7\u7a0d\u5019\u3002"
MSG_EMPTY_LOG = "Agent \u7ec8\u7aef\u65e5\u5fd7\u5c1a\u672a\u751f\u6210\u3002\n"
TITLE_TERMINAL = "Agent \u7ec8\u7aef\u4fe1\u606f"

MENU_TEXT_WEBUI = "\u6253\u5f00 Agent"
MENU_TEXT_ENV = "\u9ad8\u7ea7\u8bbe\u7f6e"
MENU_TEXT_MCP = "MCP \u914d\u7f6e"
MENU_TEXT_TERMINAL = "\u8fd0\u884c\u65e5\u5fd7"
MENU_TEXT_RESTART = "\u91cd\u542f"
MENU_TEXT_UPDATE = "\u66f4\u65b0"
MENU_TEXT_EXIT = "\u9000\u51fa Agent"

MSG_RESTART_CONFIRM = "\u91cd\u542f\u4f1a\u4e2d\u65ad\u5f53\u524d\u6b63\u5728\u8fd0\u884c\u7684\u4efb\u52a1\uff0c\u662f\u5426\u7ee7\u7eed\uff1f"
MSG_RESTARTING = "\u6b63\u5728\u91cd\u542f Agent..."
MSG_RESTARTED = "Agent \u5df2\u91cd\u542f\u3002"
MSG_RESTART_FAILED = "Agent \u91cd\u542f\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u7ec8\u7aef\u65e5\u5fd7\u3002"
MSG_UPDATE_CONFIRM = (
    "\u66f4\u65b0\u4f1a\u4e2d\u65ad\u5f53\u524d\u4efb\u52a1\uff0c\u5e76\u4ece Git \u8fdc\u7a0b\u62c9\u53d6\u6700\u65b0\u4ee3\u7801\u540e\u81ea\u52a8\u91cd\u542f\u3002\n\n"
    "\u672c\u5730\u4fee\u6539\u4e0d\u4f1a\u88ab\u5f3a\u5236\u8986\u76d6\u3002\u662f\u5426\u7ee7\u7eed\uff1f"
)
MSG_OPERATION_BUSY = "Agent \u6b63\u5728\u6267\u884c\u91cd\u542f\u6216\u66f4\u65b0\uff0c\u8bf7\u7a0d\u5019\u3002"

HOST = "127.0.0.1"
PORT = 8192
BASE_URL = f"http://{HOST}:{PORT}"
WM_TRAY = win32con.WM_USER + 20
WM_RESTORE_TRAY = win32con.WM_USER + 21
TASKBAR_CREATED = win32gui.RegisterWindowMessage("TaskbarCreated")

MENU_OPEN_WEBUI = 1001
MENU_OPEN_ENV = 1002
MENU_OPEN_MCP = 1003
MENU_VIEW_TERMINAL = 1004
MENU_EXIT = 1005
MENU_RESTART = 1006
MENU_UPDATE = 1007

SW_HIDE = 0
SW_SHOW = 5
CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 1
CTRL_CLOSE_EVENT = 2
CTRL_LOGOFF_EVENT = 5
CTRL_SHUTDOWN_EVENT = 6
GRACEFUL_STOP_TIMEOUT_SECONDS = 2

ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = preferred_python(ROOT)
MAIN_PY = ROOT / "app" / "main.py"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "agent_terminal.log"
PYTHONW_EXE = preferred_python(ROOT, windowed=True)
COLORED_LOG_VIEWER = ROOT / "app" / "colored_log_viewer.ps1"
UPDATER_PY = ROOT / "app" / "agent_updater.py"
TRAY_ICON_FILE = ROOT / "app" / "assets" / "sugar_tray.ico"
WINDOW_CLASS_NAME = "MyAgentTrayLauncherWindow"


def _append_log(line: str = "") -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8", buffering=1) as f:
        f.write(line + "\n")


def _reset_log() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")


def _is_port_listening() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.4):
            return True
    except OSError:
        return False


def _open_url_in_browser(path: str = "/", refresh: bool = True) -> None:
    url = f"{BASE_URL}{path}"
    if refresh:
        url = f"{url}{'&' if '?' in url else '?'}_={int(time.time())}"
    try:
        os.startfile(url)
    except OSError:
        webbrowser.open(url, new=0, autoraise=True)


def _find_existing_tray_window() -> int:
    try:
        return int(win32gui.FindWindow(WINDOW_CLASS_NAME, None) or 0)
    except win32gui.error:
        return 0


def _notify_existing_instance(open_browser: bool = True) -> bool:
    hwnd = _find_existing_tray_window()
    if not hwnd:
        return False
    try:
        win32gui.PostMessage(hwnd, WM_RESTORE_TRAY, int(bool(open_browser)), 0)
        return True
    except win32gui.error as exc:
        _append_log(f"Unable to notify existing tray launcher: {exc}")
        return False


def _spawn_daemon() -> None:
    daemon_python = PYTHONW_EXE
    env = os.environ.copy()
    configure_agent_python_environment(env, ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(
        [str(daemon_python), str(Path(__file__).resolve()), "--daemon"],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )


def run_starter() -> int:
    print("=" * 50)
    print(f"              {APP_NAME}")
    print("=" * 50)
    print(MSG_STARTING)
    print(f"{MSG_LOG}: {LOG_FILE}")

    if not MAIN_PY.exists():
        print(f"Missing: {MAIN_PY}")
        input(MSG_PRESS_ENTER)
        return 1

    if _is_port_listening():
        print(MSG_RUNNING)
        _append_log(MSG_RUNNING)
        notified = _notify_existing_instance(open_browser=True)
        if not notified:
            _spawn_daemon()
        _open_url_in_browser("/", refresh=True)
        return 0

    _reset_log()
    _append_log("=" * 50)
    _append_log(f"              {APP_NAME}")
    _append_log("=" * 50)
    _append_log(MSG_STARTING)
    _append_log(f"{MSG_LOG}: {LOG_FILE}")

    _spawn_daemon()

    deadline = time.monotonic() + 120
    dots = 0
    while time.monotonic() < deadline:
        if _is_port_listening():
            print(f"\n{MSG_READY}")
            _append_log(MSG_READY)
            _open_url_in_browser("/", refresh=True)
            return 0
        print("." if dots else MSG_LOADING, end="", flush=True)
        dots = (dots + 1) % 24
        time.sleep(0.5)

    print(f"\n{MSG_TIMEOUT}: {LOG_FILE}")
    _append_log(f"{MSG_TIMEOUT}: {LOG_FILE}")
    input(MSG_PRESS_ENTER)
    return 1


class TrayLauncher:
    def __init__(self) -> None:
        self.hwnd = None
        self.hicon = None
        self.proc = None
        self.exiting = False
        self.lifecycle_busy = False
        self._lifecycle_lock = threading.Lock()
        self.mutex = win32event.CreateMutex(None, True, "MyAgentTrayLauncher")
        self.already_running = win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
        self.console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        self._ctrl_handler = self._make_ctrl_handler()
        ctypes.windll.kernel32.SetConsoleCtrlHandler(self._ctrl_handler, True)

    def run(self) -> int:
        if self.already_running:
            _append_log(MSG_RUNNING)
            _notify_existing_instance(open_browser=True)
            _open_url_in_browser("/", refresh=True)
            return 0
        if not self._check_files():
            return 1

        self._create_window()
        self._add_tray_icon()
        if self._is_listening():
            _append_log(MSG_DETECTED)
        else:
            self._start_agent()
        self._watch_startup()
        win32gui.PumpMessages()
        return 0

    def _print_banner(self) -> None:
        print("=" * 50)
        print(f"              {APP_NAME}")
        print("=" * 50)
        print(MSG_STARTING)
        print(f"{MSG_LOG}: {LOG_FILE}")

    def _check_files(self) -> bool:
        ok = True
        if not PYTHON_EXE.exists():
            print(f"Missing: {PYTHON_EXE}")
            ok = False
        if not MAIN_PY.exists():
            print(f"Missing: {MAIN_PY}")
            ok = False
        return ok

    def _create_window(self) -> None:
        message_map = {
            WM_TRAY: self._on_tray,
            WM_RESTORE_TRAY: self._on_restore_tray,
            TASKBAR_CREATED: self._on_taskbar_created,
            win32con.WM_COMMAND: self._on_command,
            win32con.WM_DESTROY: self._on_destroy,
        }
        wnd_class = win32gui.WNDCLASS()
        wnd_class.hInstance = win32api.GetModuleHandle(None)
        wnd_class.lpszClassName = WINDOW_CLASS_NAME
        wnd_class.lpfnWndProc = message_map
        try:
            win32gui.RegisterClass(wnd_class)
        except win32gui.error:
            pass
        self.hwnd = win32gui.CreateWindow(
            wnd_class.lpszClassName,
            APP_NAME,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            wnd_class.hInstance,
            None,
        )

    def _add_tray_icon(self) -> None:
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
        except win32gui.error:
            pass
        if self.hicon:
            try:
                win32gui.DestroyIcon(self.hicon)
            except win32gui.error:
                pass
            self.hicon = None
        self.hicon = self._create_icon()
        nid = (
            self.hwnd,
            0,
            win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
            WM_TRAY,
            self.hicon,
            APP_NAME,
        )
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        except win32gui.error as exc:
            _append_log(f"Unable to add tray icon: {exc}")
            raise

    def _create_icon(self) -> int:
        if not TRAY_ICON_FILE.exists():
            _append_log(f"Missing tray icon: {TRAY_ICON_FILE}")
            return win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        return win32gui.LoadImage(
            0,
            str(TRAY_ICON_FILE),
            win32con.IMAGE_ICON,
            0,
            0,
            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
        )

    def _start_agent(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log = LOG_FILE.open("a", encoding="utf-8", buffering=1)
        log.write("\n" + "=" * 80 + "\n")
        log.write(time.strftime("Agent started by tray launcher at %Y-%m-%d %H:%M:%S\n"))
        env = os.environ.copy()
        configure_agent_python_environment(env, ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        env["OPEN_BROWSER"] = "0"
        try:
            self.proc = subprocess.Popen(
                [str(PYTHON_EXE), str(MAIN_PY)],
                cwd=str(ROOT),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            )
        finally:
            log.close()

    def _watch_startup(self) -> bool:
        deadline = time.monotonic() + 120
        dots = 0
        while time.monotonic() < deadline:
            if self.proc and self.proc.poll() is not None:
                _append_log(f"{MSG_FAILED}: {self.proc.returncode}")
                _append_log(f"{MSG_CHECK_LOG}: {LOG_FILE}")
                return False
            if self._is_listening():
                _append_log(MSG_READY)
                return True
            dots = (dots + 1) % 24
            time.sleep(0.5)
        _append_log(f"{MSG_TIMEOUT}: {LOG_FILE}")
        return False

    def _is_listening(self) -> bool:
        return _is_port_listening()

    def _on_tray(self, hwnd, msg, wparam, lparam):
        try:
            if lparam == win32con.WM_LBUTTONDBLCLK:
                self._open_url("/", refresh=True)
            elif lparam in (win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
                self._show_menu()
        except Exception as exc:
            print(f"Tray handler error: {exc}")
        return True

    def _on_restore_tray(self, hwnd, msg, wparam, lparam):
        try:
            self._add_tray_icon()
            if int(wparam or 0):
                self._open_url("/", refresh=True)
        except Exception as exc:
            _append_log(f"Tray restore error: {exc}")
        return True

    def _on_taskbar_created(self, hwnd, msg, wparam, lparam):
        try:
            self._add_tray_icon()
        except Exception as exc:
            _append_log(f"Taskbar tray restore error: {exc}")
        return True

    def _show_menu(self) -> None:
        menu = win32gui.CreatePopupMenu()
        try:
            win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_OPEN_WEBUI, MENU_TEXT_WEBUI)
            win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_OPEN_ENV, MENU_TEXT_ENV)
            win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_OPEN_MCP, MENU_TEXT_MCP)
            win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_VIEW_TERMINAL, MENU_TEXT_TERMINAL)
            win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")

            lifecycle_flags = win32con.MF_GRAYED if self.lifecycle_busy else win32con.MF_STRING
            win32gui.AppendMenu(menu, lifecycle_flags, MENU_RESTART, MENU_TEXT_RESTART)
            win32gui.AppendMenu(menu, lifecycle_flags, MENU_UPDATE, MENU_TEXT_UPDATE)
            win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
            win32gui.AppendMenu(menu, win32con.MF_STRING, MENU_EXIT, MENU_TEXT_EXIT)

            # Windows renders the default item in bold, giving the primary action
            # a clear visual hierarchy while retaining native theme and DPI support.
            win32gui.SetMenuDefaultItem(menu, MENU_OPEN_WEBUI, 0)
            pos = win32gui.GetCursorPos()
            win32gui.SetForegroundWindow(self.hwnd)
            popup_flags = (
                win32con.TPM_LEFTALIGN
                | win32con.TPM_RIGHTBUTTON
                | win32con.TPM_RETURNCMD
                | win32con.TPM_NONOTIFY
            )
            command = win32gui.TrackPopupMenu(
                menu,
                popup_flags,
                pos[0],
                pos[1],
                0,
                self.hwnd,
                None,
            )
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
            if command:
                self._dispatch_command(int(command))
        finally:
            win32gui.DestroyMenu(menu)

    def _on_command(self, hwnd, msg, wparam, lparam):
        self._dispatch_command(win32api.LOWORD(wparam))
        return True

    def _dispatch_command(self, command: int) -> None:
        _append_log(f"Tray menu command selected: {command}")
        if command == MENU_OPEN_WEBUI:
            self._open_url("/", refresh=True)
        elif command == MENU_OPEN_ENV:
            self._open_url("/setup/env", refresh=True)
        elif command == MENU_OPEN_MCP:
            self._open_url("/setup/mcp", refresh=True)
        elif command == MENU_VIEW_TERMINAL:
            self._open_terminal_viewer()
        elif command == MENU_RESTART:
            self._request_restart()
        elif command == MENU_UPDATE:
            self._request_update()
        elif command == MENU_EXIT:
            self._exit_agent()

    def _open_url(self, path: str, refresh: bool = False) -> None:
        if not self._is_listening():
            self._show_console()
            print(MSG_NOT_READY)
            return
        url = f"{BASE_URL}{path}"
        if refresh:
            url = f"{url}{'&' if '?' in url else '?'}_={int(time.time())}"
        self._open_named_browser_window(url)

    def _open_named_browser_window(self, url: str) -> None:
        _open_url_in_browser(url.replace(BASE_URL, "", 1) or "/", refresh=False)

    def _open_terminal_viewer(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if not LOG_FILE.exists():
            LOG_FILE.write_text(MSG_EMPTY_LOG, encoding="utf-8")
        if COLORED_LOG_VIEWER.exists():
            args = [
                "-NoExit",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(COLORED_LOG_VIEWER),
                "-Path",
                str(LOG_FILE),
            ]
        else:
            log_path = str(LOG_FILE).replace("'", "''")
            ps = (
                "chcp 65001 > $null; "
                "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); "
                f"$Host.UI.RawUI.WindowTitle='{TITLE_TERMINAL}'; "
                f"Get-Content -LiteralPath '{log_path}' -Encoding UTF8 -Wait"
            )
            args = ["-NoExit", "-ExecutionPolicy", "Bypass", "-Command", ps]
        subprocess.Popen(
            ["powershell.exe", *args],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    def _hide_console(self) -> None:
        if self.console_hwnd:
            ctypes.windll.user32.ShowWindow(self.console_hwnd, SW_HIDE)

    def _show_console(self) -> None:
        if self.console_hwnd:
            ctypes.windll.user32.ShowWindow(self.console_hwnd, SW_SHOW)
            ctypes.windll.user32.SetForegroundWindow(self.console_hwnd)

    def _confirm(self, message: str) -> bool:
        result = win32gui.MessageBox(
            self.hwnd,
            message,
            APP_NAME,
            win32con.MB_YESNO | win32con.MB_ICONQUESTION | win32con.MB_DEFBUTTON2,
        )
        return result == win32con.IDYES

    def _show_message(self, message: str, *, error: bool = False) -> None:
        icon = win32con.MB_ICONERROR if error else win32con.MB_ICONINFORMATION
        win32gui.MessageBox(self.hwnd, message, APP_NAME, win32con.MB_OK | icon)

    def _claim_lifecycle_action(self) -> bool:
        with self._lifecycle_lock:
            if self.lifecycle_busy:
                return False
            self.lifecycle_busy = True
            return True

    def _request_restart(self) -> None:
        if self.lifecycle_busy:
            self._show_message(MSG_OPERATION_BUSY)
            return
        if not self._confirm(MSG_RESTART_CONFIRM):
            return
        if not self._claim_lifecycle_action():
            self._show_message(MSG_OPERATION_BUSY)
            return
        threading.Thread(target=self._restart_agent_worker, name="agent-restart", daemon=True).start()

    def _restart_agent_worker(self) -> None:
        _append_log(MSG_RESTARTING)
        try:
            previous_pid = self.proc.pid if self.proc and self.proc.poll() is None else None
            self._stop_agent()
            self._start_agent()
            if self._watch_startup():
                current_pid = self.proc.pid if self.proc and self.proc.poll() is None else None
                _append_log(f"{MSG_RESTARTED} old_pid={previous_pid} new_pid={current_pid}")
                self._show_message(MSG_RESTARTED)
            else:
                self._show_message(MSG_RESTART_FAILED, error=True)
        except Exception as exc:
            _append_log(f"{MSG_RESTART_FAILED} {type(exc).__name__}: {exc}")
            self._show_message(MSG_RESTART_FAILED, error=True)
        finally:
            with self._lifecycle_lock:
                self.lifecycle_busy = False

    def _request_update(self) -> None:
        if self.lifecycle_busy:
            self._show_message(MSG_OPERATION_BUSY)
            return
        if not UPDATER_PY.exists():
            self._show_message(f"Missing: {UPDATER_PY}", error=True)
            return
        if not self._confirm(MSG_UPDATE_CONFIRM):
            return
        if not self._claim_lifecycle_action():
            self._show_message(MSG_OPERATION_BUSY)
            return

        env = os.environ.copy()
        configure_agent_python_environment(env, ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            subprocess.Popen(
                [
                    str(PYTHON_EXE),
                    str(UPDATER_PY),
                    "--root",
                    str(ROOT),
                    "--launcher-pid",
                    str(os.getpid()),
                ],
                cwd=str(ROOT),
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except Exception as exc:
            with self._lifecycle_lock:
                self.lifecycle_busy = False
            _append_log(f"Unable to launch updater: {type(exc).__name__}: {exc}")
            self._show_message("\u65e0\u6cd5\u542f\u52a8\u66f4\u65b0\u7a0b\u5e8f\uff0c\u8bf7\u67e5\u770b\u7ec8\u7aef\u65e5\u5fd7\u3002", error=True)
            return

        self._exit_agent()

    def _exit_agent(self) -> None:
        self.exiting = True
        self._stop_agent()
        win32gui.DestroyWindow(self.hwnd)

    def _stop_agent(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.send_signal(CTRL_BREAK_EVENT)
                self.proc.wait(timeout=GRACEFUL_STOP_TIMEOUT_SECONDS)
            except Exception:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    try:
                        self.proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
        else:
            self._stop_process_on_port()
        self.proc = None
        if not self._wait_until_port_stops(timeout_seconds=5):
            self._stop_process_on_port()
            if not self._wait_until_port_stops(timeout_seconds=5):
                _append_log(f"Port {PORT} is still listening after stopping Agent.")

    def _wait_until_port_stops(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self._is_listening():
                return True
            time.sleep(0.2)
        return not self._is_listening()

    def _stop_process_on_port(self) -> None:
        try:
            output = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as exc:
            print(f"Unable to inspect port {PORT}: {exc}")
            return

        pids = set()
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 5 or parts[0].upper() != "TCP":
                continue
            local_addr = parts[1]
            state = parts[3].upper()
            pid = parts[4]
            if state == "LISTENING" and local_addr.endswith(f":{PORT}") and pid.isdigit():
                pids.add(pid)

        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/PID", pid, "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as exc:
                print(f"Unable to stop PID {pid}: {exc}")

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
        except win32gui.error:
            pass
        if self.hicon:
            win32gui.DestroyIcon(self.hicon)
        win32gui.PostQuitMessage(0)
        return True

    def _make_ctrl_handler(self):
        def handler(ctrl_type):
            if ctrl_type in (
                CTRL_C_EVENT,
                CTRL_BREAK_EVENT,
                CTRL_CLOSE_EVENT,
                CTRL_LOGOFF_EVENT,
                CTRL_SHUTDOWN_EVENT,
            ):
                if not self.exiting:
                    self._hide_console()
                    return True
            return False

        return ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--daemon", action="store_true")
    args, _ = parser.parse_known_args()
    try:
        if args.daemon:
            raise SystemExit(TrayLauncher().run())
        raise SystemExit(run_starter())
    except SystemExit:
        raise
    except Exception as exc:
        _append_log(f"Tray launcher fatal error: {type(exc).__name__}: {exc}")
        raise
