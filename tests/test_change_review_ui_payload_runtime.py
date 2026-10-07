import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_change_review_ui_payload_survives_the_execution_record_path():
    """Regression: the 10-04 execution-record renderer dropped `ui.changes`, which
    silently blanked the chat-side change review. The payload must reach the tool
    row event for both the replayed projection and the live execution record."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests" / "js" / "change_review_ui_payload_runtime.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "change review ui payload runtime checks passed" in result.stdout
