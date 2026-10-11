"""Regression tests for the PowerShell UTF-8 prelude used by run_shell (2026-10-11).

背景：Agent 的 PowerShell 会话（gb2312/936）写出中文与处理原生命令管道时会产生
“���ٻع飨…”/“�?”类误码；修复为在 -EncodedCommand 脚本前统一前置 UTF-8 I/O 配置。
"""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import agent_tools  # noqa: E402


def test_ps_utf8_prelude_prepended_by_default(monkeypatch):
    monkeypatch.delenv("RUN_SHELL_PS_UTF8", raising=False)
    script = agent_tools._powershell_script_with_utf8_prelude("Write-Output 1")
    assert script.endswith("Write-Output 1")
    assert "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" in script
    assert "$OutputEncoding=[Text.Encoding]::UTF8;" in script
    assert "$ProgressPreference='SilentlyContinue';" in script


def test_ps_utf8_prelude_can_be_disabled(monkeypatch):
    monkeypatch.setenv("RUN_SHELL_PS_UTF8", "0")
    assert agent_tools._powershell_script_with_utf8_prelude("Write-Output 1") == "Write-Output 1"
