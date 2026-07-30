import sys
import socket
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import tray_launcher  # noqa: E402


def make_launcher():
    launcher = tray_launcher.TrayLauncher.__new__(tray_launcher.TrayLauncher)
    launcher.hwnd = 1
    launcher.proc = None
    launcher.exiting = False
    launcher.lifecycle_busy = True
    launcher._lifecycle_lock = threading.Lock()
    return launcher


def test_restart_worker_stops_starts_and_reports_success(monkeypatch):
    launcher = make_launcher()
    events: list[str] = []
    messages: list[tuple[str, bool]] = []

    monkeypatch.setattr(tray_launcher, "_append_log", lambda message="": events.append(f"log:{message}"))
    launcher._stop_agent = lambda: events.append("stop")
    launcher._start_agent = lambda: events.append("start")
    launcher._watch_startup = lambda: events.append("watch") or True
    launcher._show_message = lambda message, error=False: messages.append((message, error))

    launcher._restart_agent_worker()

    assert events[1:4] == ["stop", "start", "watch"]
    assert messages == [(tray_launcher.MSG_RESTARTED, False)]
    assert launcher.lifecycle_busy is False


def test_update_launches_external_updater_then_exits(monkeypatch):
    launcher = make_launcher()
    launcher.lifecycle_busy = False
    popen_calls: list[tuple[list[str], dict]] = []
    events: list[str] = []

    launcher._confirm = lambda message: True
    launcher._show_message = lambda message, error=False: None
    launcher._exit_agent = lambda: events.append("exit")
    monkeypatch.setattr(
        tray_launcher.subprocess,
        "Popen",
        lambda command, **kwargs: popen_calls.append((list(command), kwargs)),
    )

    launcher._request_update()

    assert len(popen_calls) == 1
    command, kwargs = popen_calls[0]
    assert command[:2] == [str(tray_launcher.PYTHON_EXE), str(tray_launcher.UPDATER_PY)]
    assert "--launcher-pid" in command
    assert kwargs["creationflags"] & tray_launcher.subprocess.CREATE_NEW_CONSOLE
    assert events == ["exit"]


def test_menu_is_compact_with_groups_default_action_and_cleanup(monkeypatch):
    launcher = make_launcher()
    launcher.lifecycle_busy = False
    launcher._is_listening = lambda: True
    calls: list[tuple] = []
    menu_handle = 321

    monkeypatch.setattr(tray_launcher.win32gui, "CreatePopupMenu", lambda: menu_handle)
    monkeypatch.setattr(
        tray_launcher.win32gui,
        "AppendMenu",
        lambda *args: calls.append(("append", *args)),
    )
    monkeypatch.setattr(
        tray_launcher.win32gui,
        "SetMenuDefaultItem",
        lambda *args: calls.append(("default", *args)),
    )
    monkeypatch.setattr(tray_launcher.win32gui, "GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr(tray_launcher.win32gui, "SetForegroundWindow", lambda hwnd: None)
    monkeypatch.setattr(
        tray_launcher.win32gui,
        "TrackPopupMenu",
        lambda *args: calls.append(("track", *args)) or 0,
    )
    monkeypatch.setattr(tray_launcher.win32gui, "PostMessage", lambda *args: None)
    monkeypatch.setattr(
        tray_launcher.win32gui,
        "DestroyMenu",
        lambda menu: calls.append(("destroy", menu)),
    )
    monkeypatch.setattr(tray_launcher, "_tray_lifecycle_menu_enabled", lambda: False)

    launcher._show_menu()

    appended_labels = [call[-1] for call in calls if call[0] == "append"]
    assert appended_labels[0] == tray_launcher.MENU_TEXT_WEBUI
    assert tray_launcher.MENU_TEXT_WEBUI in appended_labels
    assert tray_launcher.MENU_TEXT_RESTART not in appended_labels
    assert tray_launcher.MENU_TEXT_UPDATE not in appended_labels
    assert max(len(label) for label in appended_labels) <= len(tray_launcher.MENU_TEXT_WEBUI)
    assert ("default", menu_handle, tray_launcher.MENU_OPEN_WEBUI, 0) in calls
    assert calls[-1] == ("destroy", menu_handle)


def test_menu_shows_restart_and_update_when_enabled(monkeypatch):
    launcher = make_launcher()
    launcher.lifecycle_busy = False
    calls: list[tuple] = []

    monkeypatch.setattr(tray_launcher, "_tray_lifecycle_menu_enabled", lambda: True)
    monkeypatch.setattr(tray_launcher.win32gui, "CreatePopupMenu", lambda: 321)
    monkeypatch.setattr(tray_launcher.win32gui, "AppendMenu", lambda *args: calls.append(args))
    monkeypatch.setattr(tray_launcher.win32gui, "SetMenuDefaultItem", lambda *args: None)
    monkeypatch.setattr(tray_launcher.win32gui, "GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr(tray_launcher.win32gui, "SetForegroundWindow", lambda hwnd: None)
    monkeypatch.setattr(tray_launcher.win32gui, "TrackPopupMenu", lambda *args: 0)
    monkeypatch.setattr(tray_launcher.win32gui, "PostMessage", lambda *args: None)
    monkeypatch.setattr(tray_launcher.win32gui, "DestroyMenu", lambda menu: None)

    launcher._show_menu()

    appended_labels = [call[-1] for call in calls]
    assert tray_launcher.MENU_TEXT_RESTART in appended_labels
    assert tray_launcher.MENU_TEXT_UPDATE in appended_labels


def test_lifecycle_menu_setting_defaults_off_and_reads_app_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(tray_launcher, "TRAY_ENV_FILE", env_file)
    monkeypatch.delenv(tray_launcher.TRAY_LIFECYCLE_MENU_ENV_VAR, raising=False)

    assert tray_launcher._tray_lifecycle_menu_enabled() is False

    env_file.write_text(
        f"{tray_launcher.TRAY_LIFECYCLE_MENU_ENV_VAR}=on\n",
        encoding="utf-8",
    )
    assert tray_launcher._tray_lifecycle_menu_enabled() is True


def test_menu_dispatches_returned_command_directly(monkeypatch):
    launcher = make_launcher()
    launcher.lifecycle_busy = False
    selected: list[int] = []

    monkeypatch.setattr(tray_launcher.win32gui, "CreatePopupMenu", lambda: 321)
    monkeypatch.setattr(tray_launcher.win32gui, "AppendMenu", lambda *args: None)
    monkeypatch.setattr(tray_launcher.win32gui, "SetMenuDefaultItem", lambda *args: None)
    monkeypatch.setattr(tray_launcher.win32gui, "GetCursorPos", lambda: (10, 20))
    monkeypatch.setattr(tray_launcher.win32gui, "SetForegroundWindow", lambda hwnd: None)
    monkeypatch.setattr(
        tray_launcher.win32gui,
        "TrackPopupMenu",
        lambda *args: tray_launcher.MENU_RESTART,
    )
    monkeypatch.setattr(tray_launcher.win32gui, "PostMessage", lambda *args: None)
    monkeypatch.setattr(tray_launcher.win32gui, "DestroyMenu", lambda menu: None)
    launcher._dispatch_command = lambda command: selected.append(command)

    launcher._show_menu()

    assert selected == [tray_launcher.MENU_RESTART]


def test_real_restart_replaces_process_and_restores_listener(tmp_path, monkeypatch):
    with socket.socket() as probe:
        probe.bind((tray_launcher.HOST, 0))
        port = probe.getsockname()[1]

    server_script = tmp_path / "temporary_server.py"
    server_script.write_text(
        "import socket\n"
        f"server = socket.socket()\nserver.bind(('127.0.0.1', {port}))\n"
        "server.listen()\n"
        "while True:\n"
        "    connection, _ = server.accept()\n"
        "    connection.close()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tray_launcher, "MAIN_PY", server_script)
    monkeypatch.setattr(tray_launcher, "PORT", port)
    monkeypatch.setattr(tray_launcher, "LOG_DIR", tmp_path)
    monkeypatch.setattr(tray_launcher, "LOG_FILE", tmp_path / "agent.log")

    launcher = make_launcher()
    launcher.lifecycle_busy = False
    try:
        launcher._start_agent()
        assert launcher._watch_startup() is True
        first_pid = launcher.proc.pid

        launcher._stop_agent()
        assert launcher._is_listening() is False

        launcher._start_agent()
        assert launcher._watch_startup() is True
        second_pid = launcher.proc.pid

        assert second_pid != first_pid
        assert launcher._is_listening() is True
    finally:
        launcher._stop_agent()


def test_start_agent_marks_tray_as_protected_supervisor(tmp_path, monkeypatch):
    launcher = make_launcher()
    captured = {}

    class FakeProcess:
        pid = 12345

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(tray_launcher, "LOG_DIR", tmp_path)
    monkeypatch.setattr(tray_launcher, "LOG_FILE", tmp_path / "agent.log")
    monkeypatch.setattr(
        tray_launcher.subprocess,
        "Popen",
        lambda _command, **kwargs: captured.update(kwargs) or FakeProcess(),
    )

    launcher._start_agent()

    assert captured["env"]["MYAGENT_TRAY_PID"] == str(tray_launcher.os.getpid())
    assert captured["env"]["MYAGENT_SUPERVISOR_PID"] == str(tray_launcher.os.getpid())
    assert captured["env"]["MYAGENT_SERVER_PORT"] == str(tray_launcher.PORT)


def test_process_watchdog_restarts_unexpected_exit_but_stops_crash_loop(monkeypatch):
    launcher = make_launcher()
    launcher.lifecycle_busy = False
    starts = []
    logs = []

    class DeadProcess:
        returncode = -9
        pid = 100

        @staticmethod
        def poll():
            return -9

    launcher.proc = DeadProcess()
    launcher._is_listening = lambda: False

    def start_agent():
        starts.append("start")
        launcher.proc = DeadProcess()

    launcher._start_agent = start_agent
    launcher._watch_startup = lambda: True
    monkeypatch.setattr(tray_launcher, "_append_log", lambda message="": logs.append(message))
    monkeypatch.setattr(tray_launcher.time, "sleep", lambda _seconds: None)

    launcher._watch_agent_process()

    assert len(starts) == tray_launcher.UNEXPECTED_EXIT_RESTART_LIMIT
    assert launcher.proc is None
    assert any(tray_launcher.MSG_CRASH_LOOP_STOPPED in row for row in logs)
