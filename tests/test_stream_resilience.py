import asyncio
import inspect
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_live_tool_delta_replay_is_compacted_without_losing_prefix():
    import session_event_bus as bus

    async def scenario():
        sid = "stream-replay-tool"
        await bus.close_session_stream(sid)
        for index in range(600):
            await bus.publish_session_event(
                sid,
                {
                    "type": "tool_call_delta",
                    "ephemeral": True,
                    "react_iter": 2,
                    "stream_seq": 3,
                    "delta_seq": index + 1,
                    "index": 0,
                    "id": "call-1" if index == 0 else "",
                    "name_delta": "task" if index == 0 else "",
                    "arguments_delta": str(index % 10),
                },
            )
        subscription = bus.subscribe_session_events(sid, replay_recent=True)
        replay = await asyncio.wait_for(subscription.__anext__(), timeout=1)
        await subscription.aclose()
        await bus.close_session_stream(sid)
        return replay

    replay = asyncio.run(scenario())
    assert replay["type"] == "tool_call_delta"
    assert replay["name_delta"] == "task"
    assert replay["arguments_delta"] == "".join(str(i % 10) for i in range(600))
    assert replay["replayed_snapshot"] is True
    assert replay["seq_scope"] == "event_bus"


def test_completed_tool_prunes_live_delta_snapshot():
    import session_event_bus as bus

    async def scenario():
        sid = "stream-replay-prune"
        await bus.close_session_stream(sid)
        await bus.publish_session_event(
            sid,
            {
                "type": "tool_call_delta",
                "ephemeral": True,
                "react_iter": 1,
                "stream_seq": 1,
                "delta_seq": 1,
                "index": 0,
                "id": "call-prune",
                "name_delta": "task",
                "arguments_delta": "{}",
            },
        )
        await bus.publish_session_event(
            sid,
            {
                "type": "tool_call",
                "react_iter": 1,
                "tool_call_id": "call-prune",
                "tool": "task",
            },
        )
        assert not bus._live_delta_snapshots.get(sid)
        assert not [
            event
            for event in bus._recent_ephemeral.get(sid, ())
            if event.get("type") == "tool_call_delta"
        ]
        await bus.close_session_stream(sid)

    asyncio.run(scenario())


def test_session_event_bus_wakes_subscriber_on_a_different_event_loop():
    import session_event_bus as bus

    sid = "cross-loop-event-bus"
    ready = threading.Event()
    received = []

    def subscriber_worker():
        async def receive_one():
            subscription = bus.subscribe_session_events(sid, replay_recent=False)
            pending = asyncio.create_task(subscription.__anext__())
            await asyncio.sleep(0)
            ready.set()
            received.append(await asyncio.wait_for(pending, timeout=1))
            await subscription.aclose()

        asyncio.run(receive_one())

    asyncio.run(bus.close_session_stream(sid))
    thread = threading.Thread(target=subscriber_worker, daemon=True)
    thread.start()
    assert ready.wait(timeout=1)
    asyncio.run(bus.publish_session_event(sid, {"type": "status", "content": "awake"}))
    thread.join(timeout=1)
    asyncio.run(bus.close_session_stream(sid))

    assert not thread.is_alive()
    assert received and received[0]["content"] == "awake"


def test_run_task_cancellation_is_thread_safe_across_event_loops():
    import session_lifecycle

    sid = "cross-loop-cancel"
    ready = threading.Event()
    cancelled = threading.Event()

    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_forever():
            try:
                ready.set()
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        task = loop.create_task(run_forever())
        session_lifecycle.register_run_task(sid, task)
        try:
            loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert ready.wait(timeout=1)
    asyncio.run(session_lifecycle.cancel_run_tasks([sid]))
    thread.join(timeout=1)

    assert cancelled.is_set()
    assert not thread.is_alive()
    assert not session_lifecycle.is_run_active(sid)


def test_stream_detach_does_not_request_user_interrupt():
    import agent_loop

    chat_source = inspect.getsource(agent_loop.astream_events)
    continuation_source = inspect.getsource(agent_loop.astream_events_continuation)
    for source in (chat_source, continuation_source):
        assert 'reason="disconnect"' not in source
        assert "task.add_done_callback(_discard_task_result)" in source

    react_source = inspect.getsource(agent_loop._react_node_once)
    assert "READ_ONLY_TOOLS | COOPERATIVE_STEER_TOOLS" in react_source


def test_frontend_uses_independent_sse_sequence_scopes_and_fast_reattach():
    store_source = (ROOT / "frontend/src/app/state/session-store.js").read_text(encoding="utf-8")
    sse_source = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    webui_source = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "sid + '::' + seqScope" in store_source
    assert "parsed.seq_scope || 'legacy'" in sse_source
    assert "scheduleActiveSessionReconnect(runSessionId, { delayMs: 120 })" in sse_source
    assert 'payload["seq_scope"] = "ui_projection"' in webui_source
    assert "subscription.__anext__()" in webui_source
