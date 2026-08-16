import subprocess

from app import desktop_notify


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


def test_toast_protocol_opens_webui_without_console_process():
    source = desktop_notify._UI_CLOSED_TOAST_SCRIPT.read_text(encoding="utf-8")

    assert 'System32\\rundll32.exe' in source
    assert "url.dll,FileProtocolHandler" in source
    assert '$WebUiUrl = "http://127.0.0.1:8192/"' in source
    assert "powershell.exe -NoProfile" not in source
    assert "cmd.exe /c start" not in source
