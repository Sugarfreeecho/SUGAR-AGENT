"""Verify native feedback before the Electron message loop, including argv and handoff."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != "nt", reason="Native launcher is Windows only")
def test_native_startup_cursor_and_handoff(tmp_path):
    compiler = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    node = shutil.which("node")
    if not compiler.exists() or not node or not (ROOT / "packaging/assets/app.ico").exists():
        pytest.skip("Windows compiler, Node.js or generated desktop icons unavailable")
    build = """
const path = require('node:path');
require('./packaging/scripts/startup-launcher.cjs').buildStartupLauncher({
  output: path.join(process.argv[1], 'launcher.exe'), target: 'probe.exe', workDir: process.argv[1]
});
"""
    result = subprocess.run([node, "-e", build, str(tmp_path)], cwd=ROOT, capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([str(compiler), "/nologo", "/target:winexe", "/platform:x64",
                             "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll",
                             "/reference:System.Web.Extensions.dll", f"/out:{tmp_path / 'probe.exe'}",
                             str(ROOT / "tests/native/startup_probe.cs")], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    probe_report = tmp_path / "probe.json"
    launcher_report = tmp_path / "launcher.json"
    forwarded = ['中文 参数', 'quote"test', 'D:\\folder with spaces\\', 'sugaragent-desktop://open-ui?session=abc']
    result = subprocess.run([str(tmp_path / "launcher.exe"), "--launcher-smoke",
                             f"--launcher-report={launcher_report}", f"--probe-report={probe_report}", *forwarded],
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    assert result.returncode == 0
    launcher = json.loads(launcher_report.read_text(encoding="utf-8-sig"))
    probe = json.loads(probe_report.read_text(encoding="utf-8-sig"))
    assert launcher["nativeSplashShown"] and launcher["splashBeforeChild"]
    assert launcher["startupFlags"] & 0x40 and probe["startupFlags"] & 0x40
    # A background, transparent smoke window cannot require Windows to render
    # shell feedback on the foreground user's pointer. Verify the flag received
    # before GetMessage and the native splash's actual busy cursor instead.
    assert launcher["nativeBusyCursor"]
    assert launcher["handoff"] and launcher["childExitCode"] == 0
    assert probe["args"][1:5] == forwarded
    assert Path(str(launcher_report).replace('.json', '.png')).is_file()
