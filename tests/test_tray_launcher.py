import sys
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
