"""Check custom/native menu arbitration against the installed Electron runtime."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_context_menu_in_real_electron(tmp_path):
    if os.name != "nt":
        pytest.skip("This desktop smoke uses the bundled Windows Electron runtime")
    electron = ROOT / "packaging/node_modules/electron/dist/electron.exe"
    if not electron.exists():
        pytest.skip("Packaging dependencies are unavailable")
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    def run(executable):
        return subprocess.run(
            [str(executable), "--disable-gpu", str(ROOT / "tests/js/desktop_context_menu_electron.cjs")],
            capture_output=True, encoding="utf-8", timeout=30, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    result = run(electron)
    if "install_dir_access.cc" in result.stderr:
        # A developer checkout can inherit AppContainer ACLs incompatible with
        # Chromium. Copy into the test's own temporary directory; keep the
        # production sandbox and the source directory's permissions intact.
        runtime = tmp_path / "electron"
        shutil.copytree(electron.parent, runtime)
        result = run(runtime / "electron.exe")
    assert result.returncode == 0, result.stdout + result.stderr
