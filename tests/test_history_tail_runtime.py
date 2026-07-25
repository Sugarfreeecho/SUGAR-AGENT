from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_history_tail_runtime_contract() -> None:
    result = subprocess.run(
        ["node", str(ROOT / "tests/js/history_tail_runtime.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "history tail runtime checks passed" in result.stdout
