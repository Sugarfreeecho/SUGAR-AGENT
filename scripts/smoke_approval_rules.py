"""Smoke test: does the deployed code contain the red-approval fixes?

Run from the project root:

    python scripts/smoke_approval_rules.py

Exits non-zero when any check fails, so it can gate a deploy. It only reads
code; no session data is touched and the Agent does not need a restart.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from agent_tools import dangerous_matches  # noqa: E402
from security.runtime import classify_tool  # noqa: E402

# A throwaway root: every case below uses relative targets, so the real
# workspace's contents cannot change the outcome.
WORKSPACE = ROOT

CASES = [
    (
        "搜索词不是删除",
        r"git show HEAD:x | Select-String -Pattern 'RMDir|rm -rf'",
        "no-danger",
    ),
    (
        "here-string 里的字符串不是删除",
        "cd \"D:\\x\"; @'\nimport json\n"
        "defs = {\"delete_file\": \"Shell rm -rf / rmdir are blocked.\"}\n"
        "'@ | python -",
        "no-danger",
    ),
    (
        "server.shutdown() 不是关机命令",
        'python -c "import http.server as h; s=h.HTTPServer(); s.shutdown()"',
        "no-danger",
    ),
    (
        "块内的删除识别为工作区内删除",
        "if(Test-Path $p){ Remove-Item -Recurse -Force $p }",
        "ws-delete",
    ),
    (
        "换行分隔的删除识别为工作区内删除",
        "Set-Location .\\sub\nRemove-Item -Recurse -Force cache",
        "ws-delete",
    ),
    (
        "git rm 识别为删除",
        "git rm -r --quiet plugins/x",
        "deletion",
    ),
    (
        "bash -c 里的删除不能漏检",
        'bash -c "rm -rf /"',
        "danger",
    ),
    (
        "危险模式带中文标签",
        "Remove-Item -Recurse -Force $p",
        "labeled",
    ),
]


def check(command: str, expected: str) -> tuple[bool, str]:
    meta = dict(classify_tool("run_shell", {"command": command}, WORKSPACE).metadata or {})
    hits = dangerous_matches(command)
    kinds = [hit["kind"] for hit in hits]
    if expected == "no-danger":
        ok = not meta.get("destructive") and not hits
        return ok, f"destructive={meta.get('destructive')} hits={kinds}"
    if expected == "ws-delete":
        ok = bool(meta.get("deletion")) and bool(meta.get("workspace_delete"))
        return ok, f"deletion={meta.get('deletion')} workspace_delete={meta.get('workspace_delete')}"
    if expected == "deletion":
        ok = bool(meta.get("deletion"))
        return ok, f"deletion={meta.get('deletion')} workspace_delete={meta.get('workspace_delete')}"
    if expected == "labeled":
        ok = bool(meta.get("destructive")) and bool(meta.get("destructive_summary"))
        return ok, f"labels={meta.get('destructive_labels')} rule={meta.get('destructive_kinds')}"
    ok = bool(meta.get("destructive"))
    return ok, f"destructive={meta.get('destructive')} labels={meta.get('destructive_labels')}"


def main() -> int:
    failures: list[str] = []
    for name, command, expected in CASES:
        ok, detail = check(command, expected)
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        print(f"      {detail}")
        if not ok:
            failures.append(name)
    print()
    if failures:
        print(f"{len(failures)} 项未通过：当前代码不包含本次修复，或修复未生效")
        return 1
    print(f"ALL PASSED ({len(CASES)} checks) — 本次修复已生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
