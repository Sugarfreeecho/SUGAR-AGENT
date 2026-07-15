from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.mark.parametrize("event_type", ["message_user", "user_turn_committed"])
def test_runtime_v2_regular_user_event_skips_second_live_render(event_type: str) -> None:
    import webui
    from runtime_v2.event_schema import RuntimeEvent

    event = RuntimeEvent(
        seq=7,
        type=event_type,
        session_id="toc-session",
        run_id="run-1",
        payload={
            "role": "user",
            "content": "model content",
            "ui_content": "visible question",
            "ui_type": "user",
        },
    )

    payload = webui._runtime_v2_chat_sse_payload("toc-session", event.to_dict())

    assert payload is not None
    assert payload["skip_ui"] is True
    assert "ui_event" not in payload
    assert payload["runtime_event"]["type"] == event_type


def test_frontend_applies_runtime_metadata_for_atomic_user_turn() -> None:
    source = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")

    assert "runtimeEvent.type !== 'message_user'" in source
    assert "runtimeEvent.type !== 'user_turn_committed'" in source
