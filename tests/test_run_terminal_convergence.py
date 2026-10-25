import asyncio
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["run_terminal_convergence_runtime.cjs", "session_changes_runtime.cjs"])
def test_frontend_terminal_state_cannot_be_reopened_by_old_responses(script):
    result = subprocess.run(
        ["node", str(ROOT / "tests/js" / script)],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_terminal_signal_retains_bounded_deltas_and_consistent_cursor():
    from session_state_signal import SessionStateSignal

    signal = SessionStateSignal()
    for revision in range(1, 301):
        signal.publish(revision, {"type": "run_finished", "run_id": str(revision)})
    assert len(signal.terminal_events) == 256
    assert signal.changes_since(300) == {"state_revision": 300}
    delta = signal.changes_since(298)
    assert delta["state_revision"] == 300
    assert [event["run_id"] for event in delta["terminal_events"]] == ["299", "300"]
    delta["terminal_events"][0]["run_id"] = "changed"
    assert signal.changes_since(298)["terminal_events"][0]["run_id"] == "299"


def test_committed_terminal_reaches_all_tabs_without_a_new_request_type(monkeypatch):
    import webui
    from session_state_signal import SessionStateSignal

    base = webui._sessions_state_cache_generation
    signal = SessionStateSignal(base)
    monkeypatch.setattr(webui, "_sessions_state_signal", signal)

    async def scenario():
        waiting = [asyncio.create_task(signal.wait(base, timeout=2)) for _ in range(2)]
        await asyncio.sleep(0)
        await asyncio.to_thread(webui._on_session_lifecycle_event_invalidate_state, "s", {
            "type": "run_finished", "run_id": "r", "result_status": "success",
            "content": "a large answer must not be copied into the signal",
        })
        revisions = await asyncio.gather(*waiting)
        assert revisions[0] == revisions[1] > base
        response = await webui.sessions_changes(after_revision=base)
        payload = json.loads(response.body)
        assert payload["terminal_events"] == [{
            "type": "run_finished", "run_id": "r", "session_id": "s",
            "result_status": "success", "ephemeral": True,
            "state_revision": revisions[0],
        }]
        assert response.headers["cache-control"] == "no-store"

    asyncio.run(scenario())


def test_forwarded_child_terminal_does_not_close_the_parent(monkeypatch):
    import webui
    from session_state_signal import SessionStateSignal

    signal = SessionStateSignal(webui._sessions_state_cache_generation)
    monkeypatch.setattr(webui, "_sessions_state_signal", signal)
    webui._on_session_lifecycle_event_invalidate_state("parent", {
        "type": "run_finished", "run_id": "child-run", "_subagent_forward": True,
    })
    assert not signal.terminal_events
