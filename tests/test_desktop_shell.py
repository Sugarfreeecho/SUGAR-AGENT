import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.proc_flags import hidden_flags


ROOT = Path(__file__).resolve().parents[1]


def test_electron_shell_runtime():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")
    result = subprocess.run(
        [node, "--test", str(ROOT / "tests/js/desktop_shell_runtime.cjs"),
         str(ROOT / "tests/js/desktop_notifications.cjs"),
         str(ROOT / "tests/js/desktop_shortcuts.cjs")],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=hidden_flags(),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_startup_feedback_in_real_electron(tmp_path):
    if os.name != "nt":
        pytest.skip("This desktop smoke uses the bundled Windows Electron runtime")
    electron = ROOT / "packaging/node_modules/electron/dist/electron.exe"
    if not electron.is_file():
        pytest.skip("Packaging dependencies are unavailable")
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)

    def run(executable):
        return subprocess.run(
            [str(executable), "--disable-gpu", str(ROOT / "tests/js/desktop_startup_electron.cjs"),
             f"--capture={tmp_path / 'startup.png'}"],
            capture_output=True, encoding="utf-8", timeout=30, env=env,
            creationflags=hidden_flags(),
        )

    result = run(electron)
    if "install_dir_access.cc" in result.stderr:
        runtime = tmp_path / "electron"
        shutil.copytree(electron.parent, runtime)
        result = run(runtime / "electron.exe")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "native busy cursor and UI transition passed" in result.stdout


@pytest.mark.skipif(
    os.name != "nt" or os.getenv("MYAGENT_TEST_DESKTOP_NOTIFY") != "1",
    reason="Native Windows notification smoke is opt-in",
)
def test_native_electron_notification_from_hidden_window(tmp_path):
    electron = ROOT / "packaging/node_modules/electron/dist/electron.exe"
    if not electron.is_file():
        pytest.skip("Packaging dependencies are unavailable")
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)

    def run(executable):
        return subprocess.run(
            [str(executable), "--disable-gpu", str(ROOT / "tests/js/desktop_notification_electron.cjs")],
            capture_output=True, encoding="utf-8", timeout=30, env=env,
            creationflags=hidden_flags(),
        )

    result = run(electron)
    if "install_dir_access.cc" in result.stderr:
        runtime = tmp_path / "electron"
        shutil.copytree(electron.parent, runtime)
        result = run(runtime / "electron.exe")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "notification delivered while the window was hidden" in result.stdout


@pytest.mark.parametrize("desktop,session", [(False, "abc-123"), (True, "abc-123"), (True, ""), (True, '"invalid')])
def test_toast_selects_matching_application_protocol(tmp_path, desktop, session):
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Windows PowerShell is unavailable")
    source = (ROOT / "app/notify_ui_closed.ps1").read_text(encoding="utf-8")
    # Evaluate the real notification configuration without emitting a toast or
    # touching the registry. The script is ASCII so PowerShell 5.1 can read it.
    configuration = source.split("# Fallback: the well-known AppID", 1)[0]
    configuration += '\n@{uri=$OpenUiLaunchUri; aumid=$SugarAgentAumid} | ConvertTo-Json -Compress\n'
    script = tmp_path / "toast-config.ps1"
    script.write_text(configuration, encoding="ascii")
    env = os.environ.copy()
    env["SUGARAGENT_DESKTOP"] = "1" if desktop else "0"
    env["SUGARAGENT_NOTIFY_SESSION"] = session
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        env=env, capture_output=True, text=True, timeout=15, creationflags=hidden_flags(),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    scheme = "sugaragent-desktop" if desktop else "sugaragent"
    suffix = "?session=abc-123" if session == "abc-123" else ""
    assert payload["uri"] == f"{scheme}://open-ui{suffix}"
    assert payload["aumid"] == ("com.sugaragent.desktop" if desktop else "SugarAgent.MyAgent.UI")
