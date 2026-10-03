#!/usr/bin/env python
"""巡检 `app/` 与 `plugins/` 里的子进程派生点是否声明了 `creationflags`。

背景：后端可能在无控制台的形态下运行（pythonw / DETACHED_PROCESS）。此时任何
未加 `CREATE_NO_WINDOW` 的控制台子系统子进程都会弹出可见控制台窗口（"黑框一闪"）。
统一走 `app/proc_flags.py`；本脚本用来防止以后新增调用点时再漏掉。

用法：
    python scripts/audit_subprocess_flags.py            # 报告（发现未覆盖点返回 1）
    python scripts/audit_subprocess_flags.py --strict   # 同上，且把"已知豁免"也列为失败
退出码：0 = 没有未覆盖的调用点；1 = 存在未覆盖调用点。
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 允许缺省 creationflags 的调用点：`文件 -> {所在函数名, ...}`。
#: 逐条说明原因；`*` 表示整文件豁免。
ALLOWED: dict[str, set[str]] = {
    # 平台专用实现（Windows 上不可达：platform_tray 显式 raise）。
    "app/platform_tray.py": {"*"},
    "app/platform_install.py": {"*"},  # systemd / launchd 安装器
    "app/native/sugaragent-egress-helper.py": {"*"},  # 仅 Linux/macOS 落地子进程
    # 非 Windows 分支的图形/终端启动器（macOS/Linux 没有控制台窗口概念）。
    "app/desktop_notify.py": {"_notify_macos", "_notify_linux"},
    "app/webui.py": {"_open_detached", "_reveal_detached"},
    "app/path_picker_util.py": {"_pick_zenity", "_pick_kdialog", "_pick_macos"},
    # 命令行入口：调用方自带可见控制台（agentctl / 更新程序），或明确要新开控制台。
    "app/agentctl.py": {"*"},
    "app/agent_updater.py": {"launch_agent", "main"},
    "app/platform_lifecycle.py": {"logs", "update"},  # 日志查看器 / 更新进度要给人看
    "app/tray_launcher.py": {"*"},  # 其余点用 CREATE_NEW_CONSOLE/DETACHED_PROCESS
}

SPAWN_ATTRS = {"run", "Popen", "call", "check_output", "check_call"}
ASYNC_SPAWN = {"create_subprocess_exec", "create_subprocess_shell"}


def _enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Map every statement line to the name of the function that contains it."""
    owners: dict[int, str] = {}

    def walk(node: ast.AST, current: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = current
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
            if isinstance(child, ast.stmt):
                owners[child.lineno] = name
            walk(child, name)

    walk(tree, "<module>")
    return owners


def scan(path: Path) -> list[tuple[int, str, str, bool]]:
    """Return (line, label, enclosing function, has_kwargs_expansion)."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    owners = _enclosing_functions(tree)
    findings: list[tuple[int, str, str, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            continue
        if func.value.id == "subprocess" and func.attr in SPAWN_ATTRS:
            label = f"subprocess.{func.attr}"
        elif func.value.id == "asyncio" and func.attr in ASYNC_SPAWN:
            label = f"asyncio.{func.attr}"
        else:
            continue
        if any(keyword.arg == "creationflags" for keyword in node.keywords):
            continue
        star_kwargs = any(keyword.arg is None for keyword in node.keywords)
        findings.append((node.lineno, label, owners.get(node.lineno, "<module>"), star_kwargs))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="把已知豁免也当作失败")
    args = parser.parse_args(argv)

    pending: list[str] = []
    exempt: list[str] = []
    for subtree in ("app", "plugins"):
        for path in sorted((ROOT / subtree).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            allowed = ALLOWED.get(rel, set())
            for lineno, label, function, star_kwargs in scan(path):
                entry = f"{rel}:{lineno} {label} in {function}()"
                if star_kwargs:
                    exempt.append(f"{entry}  [kwargs 展开，由构造处决定]")
                elif "*" in allowed or function in allowed:
                    exempt.append(f"{entry}  [已知豁免]")
                else:
                    pending.append(entry)

    print(f"未覆盖的派生点：{len(pending)}")
    for entry in pending:
        print(f"  ! {entry}")
    print(f"\n已知豁免 / 间接处理：{len(exempt)}")
    for entry in exempt:
        print(f"  - {entry}")

    if pending:
        print("\n请改用 app/proc_flags.py 的 hidden_flags() / NO_WINDOW，或在 ALLOWED 里说明原因。")
        return 1
    if args.strict and exempt:
        print("\n--strict：存在已知豁免条目。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
