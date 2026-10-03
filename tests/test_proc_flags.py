"""`app/proc_flags.py`：跨平台子进程控制台标志 + 全局巡检。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app import proc_flags

ROOT = Path(__file__).resolve().parents[1]


def test_flags_match_platform_constants():
    assert proc_flags.NO_WINDOW == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert proc_flags.NEW_PROCESS_GROUP == getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def test_hidden_flags_combine_process_group():
    assert proc_flags.hidden_flags() == proc_flags.NO_WINDOW
    assert proc_flags.hidden_flags(new_process_group=True) == (
        proc_flags.NO_WINDOW | proc_flags.NEW_PROCESS_GROUP
    )


def test_inherit_or_hide_flags_keeps_visible_console_output(monkeypatch):
    """调用方自己有控制台时不该隐藏子进程窗口（否则用户看不到启动/更新进度）。"""

    monkeypatch.setattr(proc_flags, "console_attached", lambda: True)
    assert proc_flags.inherit_or_hide_flags() == 0
    assert proc_flags.inherit_or_hide_flags(new_process_group=True) == proc_flags.NEW_PROCESS_GROUP


def test_inherit_or_hide_flags_hides_without_console(monkeypatch):
    monkeypatch.setattr(proc_flags, "console_attached", lambda: False)
    assert proc_flags.inherit_or_hide_flags() == proc_flags.NO_WINDOW
    assert proc_flags.inherit_or_hide_flags(new_process_group=True) == proc_flags.hidden_flags(
        new_process_group=True
    )


def test_console_attached_returns_boolean_without_raising():
    assert isinstance(proc_flags.console_attached(), bool)


def test_no_uncovered_subprocess_spawn_sites():
    """所有派生点都必须声明 creationflags，或写进巡检脚本的豁免表。"""

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit_subprocess_flags.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=proc_flags.NO_WINDOW,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
