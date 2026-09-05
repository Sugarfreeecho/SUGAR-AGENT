#!/usr/bin/env python3
"""Guard frontend source/dist consistency before committing or pushing.

This wrapper is intentionally small: it runs the reproducible dist check and,
when invoked inside a Git worktree, warns about suspicious staged changes such
as dist-only edits or source-only edits.

Frontend-related files trigger the check; pure backend commits skip it so the
reproducible Vite build is not run on every commit.

Use --pushed when running from a pre-push hook: the check then inspects the
files touched by HEAD instead of the index, because nothing is staged at push
time. Set SKIP_FRONTEND_CHECK=1 to bypass the whole check (CI/emergency).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FRONTEND_PREFIXES = ("frontend/", "app/templates/dist/")


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def _changed_paths(pushed: bool) -> list[str]:
    if pushed:
        # Nothing is staged at push time; inspect the commit being pushed.
        proc = _run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"])
    else:
        proc = _run(["git", "diff", "--cached", "--name-only"])
    if proc.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def _is_frontend_related(paths: list[str]) -> bool:
    return any(p.startswith(FRONTEND_PREFIXES) for p in paths)


def _warn_staged_shape(paths: list[str]) -> int:
    if not paths:
        return 0
    src_changed = any(p.startswith("frontend/src/") or p.startswith("frontend/index.html") for p in paths)
    dist_changed = any(p.startswith("app/templates/dist/") for p in paths)
    if src_changed and not dist_changed:
        print("Frontend source changed but app/templates/dist is not staged.", file=sys.stderr)
        print("Run `npm run build` from frontend/ and stage the generated dist.", file=sys.stderr)
        return 1
    if dist_changed and not src_changed:
        print("Frontend dist changed without matching frontend source changes.", file=sys.stderr)
        print("Do not hand-edit dist; make the source change under frontend/src and rebuild.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pushed", action="store_true", help="inspect HEAD instead of the index (pre-push)")
    args = parser.parse_args()

    if os.environ.get("SKIP_FRONTEND_CHECK") == "1":
        return 0

    paths = _changed_paths(args.pushed)
    if not _is_frontend_related(paths):
        return 0

    # The staged-shape warning only makes sense for the index (pre-commit).
    shape_rc = 0 if args.pushed else _warn_staged_shape(paths)
    dist_rc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_frontend_dist_sync.py")],
        cwd=ROOT,
    ).returncode
    return shape_rc or dist_rc


if __name__ == "__main__":
    raise SystemExit(main())