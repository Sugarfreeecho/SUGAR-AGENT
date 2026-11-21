"""CLI 启动器：`python cli.py status --json`（插件根目录下执行）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sugar_assistant.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
