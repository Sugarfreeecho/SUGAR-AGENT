import asyncio
import threading
from types import SimpleNamespace

import pytest


def test_batch_publishes_only_after_all_durable_commits(tmp_path, monkeypatch):
    import agent_loop as agent
    import runtime_v2
    entered, release = threading.Event(), threading.Event()
    public = []
    def commit(sid, events, *, cancel_event):
        entered.set()
        assert release.wait(3)
        return [{**event, "_runtime_v2_committed": True} for event in events]
    monkeypatch.setattr(agent, "session_manager", SimpleNamespace(commit_execution_ui_events=commit))
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)
    async def publish(sid, event):
        public.append(event)
    monkeypatch.setattr(agent, "publish_session_event", publish)
    async def scenario():
        async def emit(event):
            pytest.fail("used single commit path")
        queue = asyncio.Queue()
        agent._attach_tool_batch_emitter(emit, {}, "s", "r", SimpleNamespace(allows_stream_event=lambda _: True), queue, lambda: True)
        task = asyncio.create_task(emit.tool_batch([{"type": "tool_call", "tool_call_id": "a"},
                                                  {"type": "tool_call", "tool_call_id": "b"}]))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert public == [] and queue.empty()
        finally:
            release.set()
        await task
        assert [event["tool_call_id"] for event in public] == ["a", "b"]
        assert all("_runtime_v2_committed" not in event for event in public)
        assert queue.qsize() == 2
    asyncio.run(scenario())


def test_cancelled_batch_cannot_publish_after_worker_returns(monkeypatch):
    import agent_loop as agent
    import runtime_v2
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    public = []
    def commit(sid, events, *, cancel_event):
        entered.set()
        try:
            assert release.wait(3)
            assert cancel_event.is_set()
            raise asyncio.CancelledError()
        finally:
            done.set()
    monkeypatch.setattr(agent, "session_manager", SimpleNamespace(commit_execution_ui_events=commit))
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)
    async def publish(sid, event):
        public.append(event)
    monkeypatch.setattr(agent, "publish_session_event", publish)
    async def scenario():
        async def emit(event):
            pass
        agent._attach_tool_batch_emitter(emit, {}, "s", "r", SimpleNamespace(allows_stream_event=lambda _: True), asyncio.Queue(), lambda: True)
        task = asyncio.create_task(emit.tool_batch([{"type": "tool_call"}]))
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        assert await asyncio.to_thread(done.wait, 2)
        assert public == []
    asyncio.run(scenario())


def test_non_strict_or_forwarded_events_keep_existing_emit_path(monkeypatch):
    import agent_loop as agent
    import runtime_v2
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: False)
    monkeypatch.setattr(agent, "session_manager", SimpleNamespace(commit_execution_ui_events=lambda *a, **k: pytest.fail("non-strict batch commit")))
    async def scenario():
        seen = []
        async def emit(event):
            seen.append(event)
        agent._attach_tool_batch_emitter(emit, {}, "s", "r", SimpleNamespace(allows_stream_event=lambda _: True), asyncio.Queue(), lambda: True)
        events = [{"type": "tool_call"}, {"type": "tool_call", "_subagent_forward": True}]
        await emit.tool_batch(events)
        assert seen == events
    asyncio.run(scenario())


def test_plain_tool_text_is_not_scanned_as_an_attachment_block_sequence():
    import agent_loop as agent
    class Text(str):
        def __iter__(self):
            raise AssertionError("iterated text as blocks")
    event = agent._tool_result_sse_event({"tool_name": "read_file", "tool_args": {},
                                         "tool_detail_ui": Text("x" * 10000)}, 1)
    assert event["attachments"] == []
    assert event["result"] == "x" * 10000
