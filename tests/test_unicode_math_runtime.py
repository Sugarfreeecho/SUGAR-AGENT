import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_final_card_math_renders_as_unicode_math():
    """The Final card has no TeX engine, so LaTeX math is rewritten into Unicode
    math text before Markdown parsing. Code spans / fences and currency amounts
    must stay literal, and the raw Markdown used by copy / export stays TeX."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests" / "js" / "unicode_math_runtime.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unicode math runtime checks passed" in result.stdout
