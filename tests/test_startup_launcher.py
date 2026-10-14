"""Verify native feedback before the Electron message loop, including argv and handoff."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != "nt", reason="Native launcher is Windows only")
def test_after_pack_waits_for_runtime_resource_editing(tmp_path):
    node = shutil.which("node")
    compiler = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    if not node or not compiler.exists():
        pytest.skip("Windows compiler or Node.js unavailable")
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = process.argv[1];
const output = process.argv[2];
const config = require(path.join(root, 'packaging/electron-builder.config.cjs'));
const entry = path.join(output, 'SugarAgent.exe');
const runtime = path.join(output, 'SugarAgentRuntime.exe');
for (const relative of ['resources/runtime/python/python.exe', 'resources/runtime/app/main.py']) {
  const file = path.join(output, relative); fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, '');
}
fs.writeFileSync(entry, 'unbranded-runtime');
let release, edited = false, finished = false;
const gate = new Promise(resolve => { release = resolve });
const context = { appOutDir: output, outDir: output, arch: 1,
  packager: { appInfo: { productFilename: 'SugarAgent' }, platformSpecificBuildOptions: {},
    async signAndEditResources(file, arch, outDir, internalName) {
      assert.equal(file, runtime); assert.equal(internalName, 'SugarAgentRuntime');
      await gate; edited = true;
    } } };
(async () => {
  const pending = config.afterPack(context).then(() => { finished = true });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(finished, false, 'the hook must not return while branding is pending');
  assert.equal(fs.existsSync(entry), false, 'launcher compilation must wait for branding');
  release(); await pending;
  assert.equal(edited, true); assert.equal(fs.existsSync(entry), true);
  assert.equal(fs.readFileSync(runtime, 'utf8'), 'unbranded-runtime');
})().catch(error => { console.error(error.stack); process.exitCode = 1 });
'''
    result = subprocess.run([node, "-e", script, str(ROOT), str(tmp_path)], cwd=ROOT,
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stdout + result.stderr

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

    # A notification invocation must take the quiet path even when the OS
    # protocol still points at the launcher shipped by an older installer.
    protocol_report = tmp_path / "protocol-launcher.json"
    probe_report.unlink()
    protocol = 'sugaragent-desktop://open-ui?session=abc-123'
    result = subprocess.run([str(tmp_path / "launcher.exe"), f"--launcher-report={protocol_report}",
                             f"--probe-report={probe_report}", protocol, '中文 参数'],
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
    assert result.returncode == 0
    deadline = time.monotonic() + 5
    while not probe_report.exists() and time.monotonic() < deadline:
        time.sleep(.05)
    quiet = json.loads(protocol_report.read_text(encoding="utf-8-sig"))
    probe = json.loads(probe_report.read_text(encoding="utf-8-sig"))
    assert quiet["nativeSplashShown"] is False
    assert quiet["protocolForwarded"] is True
    assert quiet["startupFlags"] == 0 and probe["startupFlags"] & 0x40 == 0
    assert probe["args"] == [f"--probe-report={probe_report}", protocol, '中文 参数']
    assert not Path(str(protocol_report).replace('.json', '.png')).exists()
