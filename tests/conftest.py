"""Shared pytest safety defaults."""

import os
import sys
from pathlib import Path

import pytest


# Tests may construct the real FastAPI application and exercise page-presence
# endpoints. Never emit desktop notifications from those test processes unless
# a developer explicitly opts into the native-notification path.
if os.getenv("MYAGENT_TEST_DESKTOP_NOTIFY", "").strip() != "1":
    os.environ["MYAGENT_UI_CLOSED_NOTIFY"] = "0"

# Most Runtime tests tear down TemporaryDirectory immediately after an event.
# Keep a wider Windows file-handle grace in tests; dedicated async-checkpoint
# tests override this to zero and exercise the production non-blocking path.
os.environ.setdefault("RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS", "50")


@pytest.fixture(autouse=True)
def isolated_tool_disclosure_config(monkeypatch, tmp_path):
    """Tests must not inherit or overwrite the user's live disclosure setting."""
    app_dir = str(Path(__file__).resolve().parents[1] / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import tool_search
    monkeypatch.setattr(tool_search, "CONFIG_PATH", tmp_path / "tool_search.json")
    monkeypatch.setattr(tool_search, "_config_cache", None)
    monkeypatch.delenv("MYAGENT_TOOL_SEARCH", raising=False)
