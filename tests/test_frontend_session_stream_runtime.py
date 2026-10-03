import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", [
    "frontend_session_stream_runtime.cjs",
    "stream_recovery_runtime.cjs",
    "ui_performance_runtime.cjs",
    "session_store_runtime.cjs",
    "new_session_lifecycle_runtime.cjs",
    "new_session_legacy_options_runtime.cjs",
    "runtime_status_takeover.cjs",
    "restart_recovery_order_runtime.cjs",
    "tool_pending_history_recovery_runtime.cjs",
    "model_profile_bound_refresh_runtime.cjs",
    "model_profile_refresh_races_runtime.cjs",
    "model_profile_refresh_requests_runtime.cjs",
    "model_reasoning_effort_runtime.cjs",
])
def test_frontend_session_stream_runtime(script):
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "js" / script)], cwd=ROOT,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
