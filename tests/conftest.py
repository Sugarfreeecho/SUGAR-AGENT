"""Shared pytest safety defaults."""

import os


# Tests may construct the real FastAPI application and exercise page-presence
# endpoints. Never emit desktop notifications from those test processes unless
# a developer explicitly opts into the native-notification path.
if os.getenv("MYAGENT_TEST_DESKTOP_NOTIFY", "").strip() != "1":
    os.environ["MYAGENT_UI_CLOSED_NOTIFY"] = "0"
