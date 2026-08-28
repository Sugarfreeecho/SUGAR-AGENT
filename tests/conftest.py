"""Shared pytest safety defaults."""

import os


# Tests may construct the real FastAPI application and exercise page-presence
# endpoints. Never emit desktop notifications from those test processes unless
# a developer explicitly opts into the native-notification path.
if os.getenv("MYAGENT_TEST_DESKTOP_NOTIFY", "").strip() != "1":
    os.environ["MYAGENT_UI_CLOSED_NOTIFY"] = "0"

# Most Runtime tests tear down TemporaryDirectory immediately after an event.
# Keep a wider Windows file-handle grace in tests; dedicated async-checkpoint
# tests override this to zero and exercise the production non-blocking path.
os.environ.setdefault("RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS", "50")
