"""Run isolated regressions without creating sessions or sending Bilibili messages."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest",
    "tests/test_sugar_bili_scroll_tasks.py", "tests/test_sugar_bili_scroll_workflows.py",
    "tests/test_sugar_bili_scroll_accounts.py",
    "tests/test_sugar_bili_scroll_favorite_tool.py",
    "tests/test_sugar_bili_scroll_mcp.py", "tests/test_sugar_bili_scroll_skill.py",
    "tests/test_run_tool_scope.py", "-q"], cwd=root))
