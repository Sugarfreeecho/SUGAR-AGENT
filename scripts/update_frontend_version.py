#!/usr/bin/env python3
"""Refresh the sidebar runtime version stamp to today's date.

The version token looks like ``v4.20260814`` (``v<major>.<YYYYMMDD>``) and is
embedded in the frontend shell and the built dist. On every commit this script
rewrites the date part to the current local date, keeping the major prefix.

Exits 0 always (idempotent); prints the effective version.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "frontend" / "index.html",
    ROOT / "frontend" / "src" / "shell-body.html",
    ROOT / "app" / "templates" / "dist" / "index.html",
]
TOKEN_RE = re.compile(r"v\d+\.\d{8}")


def main() -> int:
    stamp = f"v4.{date.today():%Y%m%d}"
    changed = False
    for path in TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_text, n = TOKEN_RE.subn(stamp, text)
        if n and new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"[version] {path.relative_to(ROOT)} -> {stamp}")
            changed = True
        elif n:
            print(f"[version] {path.relative_to(ROOT)} already {stamp}")
    if not changed:
        print(f"[version] no change (stamp {stamp})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
