import asyncio
import importlib.util
import json
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

from app import desktop_notify


def test_notification_plugin_delivers_off_server_loop_and_respects_lifecycle(monkeypatch):
    import desktop_notify as host_notify
    import notification_providers

    spec = importlib.util.spec_from_file_location(
        "test_notification_host", Path(__file__).resolve().parents[1] / "plugins/desktop-notifications/host.py"
    )
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    monkeypatch.setattr(notification_providers, "_providers", {})
    delivered = []
    main_thread = threading.get_ident()
    monkeypatch.setattr(host_notify, "show_desktop_notification", lambda *args: delivered.append((threading.get_ident(), args)))
    plugin = SimpleNamespace(plugin_id="desktop-notifications")

    async def scenario():
        host.install(None, None, plugin)
        assert await notification_providers.notify_user("SugarAgent", "Completed", "session-1") == []
        await host.stop(None, plugin)
        assert notification_providers.notification_provider_ids() == ()
        await host.start(None, plugin)
        assert notification_providers.notification_provider_ids() == (plugin.plugin_id,)

    asyncio.run(scenario())
    assert delivered[0][0] != main_thread
    assert delivered[0][1] == ("SugarAgent", "Completed", "session-1")


def test_desktop_shell_delivery_preserves_unicode_and_session_without_proxy(monkeypatch):
    monkeypatch.setenv("SUGARAGENT_DESKTOP", "1")
    monkeypatch.setenv("SUGARAGENT_NOTIFY_PORT", "12345")
    monkeypatch.setenv("SUGARAGENT_NOTIFY_TOKEN", "per-launch-secret")
    captured = {}

    class Opener:
        def open(self, request, timeout):
            captured.update(request=request, timeout=timeout)
            return self

        def __enter__(self):
            self.status = 200
            return self

        def __exit__(self, *args):
            pass

    def opener(handler):
        captured["proxies"] = handler.proxies
        return Opener()

    monkeypatch.setattr(desktop_notify, "build_opener", opener)
    monkeypatch.setattr(desktop_notify, "_notify_windows_toast", lambda *args: (_ for _ in ()).throw(AssertionError("unexpected fallback")))

    desktop_notify.show_desktop_notification("SugarAgent", "状态：已完成", "session-1")

    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:12345/notify"
    assert request.get_header("Authorization") == "Bearer per-launch-secret"
    assert json.loads(request.data) == {"title": "SugarAgent", "message": "状态：已完成", "session_id": "session-1"}
    assert captured["proxies"] == {}
    assert captured["timeout"] == 8


def test_desktop_shell_unavailable_falls_back_to_platform_toast(monkeypatch):
    monkeypatch.setenv("SUGARAGENT_DESKTOP", "1")
    monkeypatch.setenv("SUGARAGENT_NOTIFY_PORT", "12345")
    monkeypatch.setenv("SUGARAGENT_NOTIFY_TOKEN", "test-token")
    monkeypatch.setattr(desktop_notify.platform, "system", lambda: "Windows")

    class Opener:
        def open(self, *args, **kwargs):
            raise URLError("desktop unavailable")

    monkeypatch.setattr(desktop_notify, "build_opener", lambda _handler: Opener())
    calls = []
    monkeypatch.setattr(desktop_notify, "_notify_windows_toast", lambda *args: calls.append(args) or True)

    desktop_notify.show_desktop_notification("SugarAgent", "Completed", "session-1")

    assert calls == [("SugarAgent", "Completed", "session-1")]


def test_source_launch_keeps_platform_notification_path(monkeypatch):
    monkeypatch.delenv("SUGARAGENT_DESKTOP", raising=False)
    monkeypatch.setattr(desktop_notify.platform, "system", lambda: "Windows")
    monkeypatch.setattr(desktop_notify, "_notify_electron", lambda *args: (_ for _ in ()).throw(AssertionError("unexpected desktop IPC")))
    calls = []
    monkeypatch.setattr(desktop_notify, "_notify_windows_toast", lambda *args: calls.append(args) or True)
    desktop_notify.show_desktop_notification("SugarAgent", "Completed", "session-1")
    assert calls == [("SugarAgent", "Completed", "session-1")]


class _SuccessfulProcess:
    def __init__(self):
        self.wait_timeouts = []

    def wait(self, timeout):
        self.wait_timeouts.append(timeout)
        return 0


class _TimedOutProcess:
    def __init__(self, *, exit_after_terminate=True):
        self.wait_timeouts = []
        self.terminated = False
        self.killed = False
        self.exit_after_terminate = exit_after_terminate

    def wait(self, timeout):
        self.wait_timeouts.append(timeout)
        if len(self.wait_timeouts) == 1 or (
            self.terminated and not self.killed and not self.exit_after_terminate
        ):
            raise subprocess.TimeoutExpired("powershell.exe", timeout)
        return 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def test_windows_toast_does_not_add_action_button_environment(monkeypatch, tmp_path):
    script = tmp_path / "notify.ps1"
    script.write_text("exit 0", encoding="ascii")
    process = _SuccessfulProcess()
    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return process

    monkeypatch.setattr(desktop_notify, "_UI_CLOSED_TOAST_SCRIPT", script)
    monkeypatch.setattr(desktop_notify.subprocess, "Popen", fake_popen)

    assert desktop_notify._notify_windows_toast("SugarAgent", "message") is True
    assert "SUGARAGENT_NOTIFY_ACTION" not in captured["env"]
    assert process.wait_timeouts == [20]


def test_windows_toast_terminates_timed_out_helper(monkeypatch, tmp_path):
    script = tmp_path / "notify.ps1"
    script.write_text("exit 0", encoding="ascii")
    process = _TimedOutProcess()

    monkeypatch.setattr(desktop_notify, "_UI_CLOSED_TOAST_SCRIPT", script)
    monkeypatch.setattr(
        desktop_notify.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )

    assert desktop_notify._notify_windows_toast("SugarAgent", "message") is False
    assert process.terminated is True
    assert process.killed is False
    assert process.wait_timeouts == [20, 2.0]


def test_windows_toast_kills_helper_that_ignores_terminate(monkeypatch, tmp_path):
    script = tmp_path / "notify.ps1"
    script.write_text("exit 0", encoding="ascii")
    process = _TimedOutProcess(exit_after_terminate=False)

    monkeypatch.setattr(desktop_notify, "_UI_CLOSED_TOAST_SCRIPT", script)
    monkeypatch.setattr(
        desktop_notify.subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )

    assert desktop_notify._notify_windows_toast("SugarAgent", "message") is False
    assert process.terminated is True
    assert process.killed is True
    assert process.wait_timeouts == [20, 2.0, 2.0]


def test_powershell_toast_has_no_action_button():
    source = desktop_notify._UI_CLOSED_TOAST_SCRIPT.read_text(encoding="utf-8")

    assert "$env:SUGARAGENT_NOTIFY_ACTION" not in source
    assert "<actions>" not in source
    assert "<action " not in source


def test_toast_protocol_reuses_webui_through_windowless_tray_activation():
    source = desktop_notify._UI_CLOSED_TOAST_SCRIPT.read_text(encoding="utf-8")

    assert 'python\\pythonw.exe' in source
    assert 'app\\tray_launcher.py' in source
    assert "--activate-ui" in source
    assert '$WebUiUrl = "http://127.0.0.1:8192/"' in source
    assert "powershell.exe -NoProfile" not in source
    assert "cmd.exe /c start" not in source
