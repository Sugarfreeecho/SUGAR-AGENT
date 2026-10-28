#!/usr/bin/env python3
"""Control an existing SugarAgent backend. Run --help for commands."""
from pathlib import Path
import sys

for stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
from session_control.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
