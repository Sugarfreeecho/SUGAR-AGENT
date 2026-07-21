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
                "type": "tool_pending",
                "ephemeral": True,
                "react_iter": 1,
                "tool_call_id": "call-prune",
                "tool": "task",
                "args": {},
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
        assert not bus._live_state_snapshots.get(sid)
        await bus.close_session_stream(sid)

    asyncio.run(scenario())


def test_refresh_replay_keeps_running_tool_after_many_stream_chunks():
    import session_event_bus as bus

    async def scenario():
        sid = "stream-replay-running-tool"
        await bus.close_session_stream(sid)
        await bus.publish_session_event(
            sid,
            {
                "type": "tool_pending",
                "ephemeral": True,
                "react_iter": 3,
                "tool_call_index": 0,
                "tool_call_id": "call-running",
                "tool": "run_shell",
                "args": {"command": "long-running"},
            },
        )
        for index in range(800):
            await bus.publish_session_event(
                sid,
                {
                    "type": "tool_command_delta",
                    "ephemeral": True,
                    "react_iter": 3,
                    "tool_call_id": "call-running",
                    "stream_seq": 1,
                    "delta_seq": index + 1,
                    "delta": str(index % 10),
                },
            )
        subscription = bus.subscribe_session_events(sid, replay_recent=True)
        first = await asyncio.wait_for(subscription.__anext__(), timeout=1)
        second = await asyncio.wait_for(subscription.__anext__(), timeout=1)
        await subscription.aclose()
        await bus.close_session_stream(sid)
        return [first, second]

    replay = asyncio.run(scenario())
    assert [event["type"] for event in replay] == ["tool_pending", "tool_command_delta"]
    assert replay[0]["tool_call_id"] == "call-running"
    assert replay[1]["delta"] == "".join(str(i % 10) for i in range(800))


def test_refresh_replay_compacts_thinking_status_and_clears_it_on_delta():
    import session_event_bus as bus

    async def replay_all(sid, count):
        subscription = bus.subscribe_session_events(sid, replay_recent=True)
        rows = []
        for _ in range(count):
            rows.append(await asyncio.wait_for(subscription.__anext__(), timeout=1))
        await subscription.aclose()
        return rows

    async def scenario():
        sid = "stream-replay-thinking-status"
        await bus.close_session_stream(sid)
        for index in range(30):
            await bus.publish_session_event(
                sid,
                {
                    "type": "status",
                    "content": "正在思考中...",
                    "ephemeral": True,
                    "heartbeat": index,
                },
            )
        compacted = await replay_all(sid, 1)
        await bus.publish_session_event(
            sid,
            {
                "type": "llm_reasoning_delta",
                "delta": "reasoning",
                "ephemeral": True,
                "react_iter": 1,
                "stream_seq": 1,
                "delta_seq": 1,
            },
        )
        after_delta = await replay_all(sid, 1)
        await bus.close_session_stream(sid)
        return compacted, after_delta

    compacted, after_delta = asyncio.run(scenario())
    assert [event["type"] for event in compacted] == ["status"]
    assert compacted[0]["heartbeat"] == 29
    assert [event["type"] for event in after_delta] == ["llm_reasoning_delta"]


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
    assert "not _can_execute_closed_stream_tool" in react_source
    assert "recovered_closed_tool_calls" in react_source


def test_all_closed_external_tools_can_start_before_finish_reason():
    import agent_loop

    for tool_name in ("read_file", "task", "write_file", "apply_patch", "run_shell", "mcp_remote"):
        assert agent_loop._can_execute_closed_stream_tool(tool_name) is True
    # This is an internal history-replacement control operation, not an external
    # command; it must run after the current assistant turn has been assembled.
    assert agent_loop._can_execute_closed_stream_tool("context_manage") is False


def test_frontend_uses_independent_sse_sequence_scopes_and_fast_reattach():
    store_source = (ROOT / "frontend/src/app/state/session-store.js").read_text(encoding="utf-8")
    sse_source = (ROOT / "frontend/src/app/modules/sse-handling.js").read_text(encoding="utf-8")
    webui_source = (ROOT / "app/webui.py").read_text(encoding="utf-8")

    assert "sid + '::' + seqScope" in store_source
    assert "parsed.seq_scope || 'legacy'" in sse_source
    assert "scheduleActiveSessionReconnect(runSessionId, { delayMs: 120 })" in sse_source
    assert 'payload["seq_scope"] = "ui_projection"' in webui_source
    assert "subscription.__anext__()" in webui_source
