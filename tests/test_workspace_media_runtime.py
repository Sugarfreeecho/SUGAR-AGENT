import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script, expected", [
    ("workspace_media_runtime.cjs", "workspace media runtime checks passed"),
    ("image_preview_runtime.cjs", "image preview runtime checks passed"),
])
def test_workspace_media_frontend_runtime(script, expected):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is required for frontend runtime checks")
    result = subprocess.run(
        [node, str(ROOT / "tests/js" / script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert expected in result.stdout
