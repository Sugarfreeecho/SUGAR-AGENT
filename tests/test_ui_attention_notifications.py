import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

def test_worker_session_event_reaches_initialized_server_loop(monkeypatch):
    import webui

    async def scenario():
        scheduled = []
        monkeypatch.setattr(webui, "_UI_ATTENTION_MAIN_LOOP", None)
        monkeypatch.setattr(
            webui,
            "_schedule_ui_attention_notify",
            lambda session_id, reason: scheduled.append((session_id, reason)),
        )

        webui.initialize_ui_attention_notifications()
        await asyncio.to_thread(
            webui._on_session_event_for_attention_notify,
            "session-1",
            {"type": "run_finished"},
        )
        await asyncio.sleep(0)

        assert webui._UI_ATTENTION_MAIN_LOOP is asyncio.get_running_loop()
        assert scheduled == [("session-1", "completed")]

    asyncio.run(scenario())


def test_attention_listener_ignores_unrelated_and_forwarded_events(monkeypatch):
    import webui

    async def scenario():
        scheduled = []
        monkeypatch.setattr(webui, "_UI_ATTENTION_MAIN_LOOP", asyncio.get_running_loop())
        monkeypatch.setattr(
            webui,
            "_schedule_ui_attention_notify",
            lambda session_id, reason: scheduled.append((session_id, reason)),
        )

        webui._on_session_event_for_attention_notify("session-1", {"type": "status"})
        webui._on_session_event_for_attention_notify(
            "session-1",
            {"type": "run_finished", "_subagent_forward": True},
        )
        await asyncio.sleep(0)

        assert scheduled == []

    asyncio.run(scenario())
