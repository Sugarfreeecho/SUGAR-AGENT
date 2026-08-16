#!/usr/bin/env python3
"""Install local Git hooks for General Agent development."""

from __future__ import annotations

import os
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".git" / "hooks"

PRE_COMMIT_BODY = """#!/bin/sh
python scripts/update_frontend_version.py
git add frontend/index.html frontend/src/shell-body.html app/templates/dist/index.html 2>/dev/null || true
python scripts/check_frontend_commit_policy.py
"""

PRE_PUSH_BODY = """#!/bin/sh
python scripts/check_frontend_commit_policy.py
"""


def main() -> int:
    if not (ROOT / ".git").exists():
        print("Not inside the General Agent Git worktree.")
        return 2
    HOOKS.mkdir(parents=True, exist_ok=True)
    (HOOKS / "pre-commit").write_text(PRE_COMMIT_BODY, encoding="utf-8")
    (HOOKS / "pre-push").write_text(PRE_PUSH_BODY, encoding="utf-8")
    for name in ("pre-commit", "pre-push"):
        path = HOOKS / name
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"Installed {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
