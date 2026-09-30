import asyncio
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from stream_event_bridge import StreamEventBridge


def test_blocked_ui_does_not_block_deltas_but_completed_tool_is_a_barrier():
    async def scenario():
        release = asyncio.Event()
        produced = threading.Event()
        tool_acknowledged = threading.Event()
        seen = []

        async def emit(event):
            await release.wait()
            seen.append(event)

        bridge = StreamEventBridge(asyncio.get_running_loop(), emit)

        async def produce():
            for index in range(1000):
                event = {
                    "type": "llm_reasoning_delta", "ephemeral": True,
                    "react_iter": 1, "stream_seq": 1, "delta_seq": index + 1,
                    "delta": str(index % 10),
                }
                await bridge.send(event)
                event["delta"] = "mutated"
            produced.set()
            await bridge.send({"type": "tool_call", "tool_call_id": "call-1"})
            tool_acknowledged.set()
            await bridge.flush()

        task = asyncio.create_task(asyncio.to_thread(lambda: asyncio.run(produce())))
        assert await asyncio.to_thread(produced.wait, 2)
        assert not tool_acknowledged.is_set()
        assert seen == []
        release.set()
        await asyncio.wait_for(task, 2)
        deltas = [event for event in seen if event["type"] == "llm_reasoning_delta"]
        assert "".join(event["delta"] for event in deltas) == "".join(str(i % 10) for i in range(1000))
        assert len(deltas) <= 2
        assert seen[-1]["type"] == "tool_call"
        assert tool_acknowledged.is_set()

    asyncio.run(scenario())


def test_tool_and_round_identities_are_not_merged_and_all_events_keep_order():
    async def scenario():
        seen = []
        bridge = StreamEventBridge(asyncio.get_running_loop(), lambda event: seen.append(event))
        events = [
            {"type": "tool_call_delta", "ephemeral": True, "react_iter": 1, "index": 0, "id": "a", "name_delta": "read", "arguments_delta": "{"},
            {"type": "tool_call_delta", "ephemeral": True, "react_iter": 1, "index": 0, "id": "a", "name_delta": "_file", "arguments_delta": "}"},
            {"type": "tool_call_delta", "ephemeral": True, "react_iter": 1, "index": 1, "id": "b", "name_delta": "grep", "arguments_delta": "{}"},
            {"type": "tool_call_delta", "ephemeral": True, "react_iter": 2, "index": 1, "id": "b", "name_delta": "grep", "arguments_delta": "{}"},
            {"type": "llm_response_delta", "ephemeral": True, "react_iter": 2, "delta": "done"},
            {"type": "run_finished"},
        ]
        for event in events:
            await bridge.send(event)
        await bridge.flush()
        assert len(seen) == 5
        assert seen[0]["name_delta"] == "read_file"
        assert seen[0]["arguments_delta"] == "{}"
        assert [event.get("react_iter") for event in seen] == [1, 1, 2, 2, None]
        assert seen[-1]["type"] == "run_finished"

    asyncio.run(scenario())


def test_non_ephemeral_delta_and_delivery_failure_are_acknowledged():
    async def scenario():
        seen = []

        async def emit(event):
            seen.append(event["type"])
            if event["type"] in {"tool_call", "llm_response_delta"}:
                raise ValueError("delivery failed")

        bridge = StreamEventBridge(asyncio.get_running_loop(), emit)
        # A queued ephemeral failure must not kill the drain or its barriers.
        await bridge.send({"type": "llm_response_delta", "ephemeral": True, "delta": "x"})
        with pytest.raises(ValueError, match="delivery failed"):
            await bridge.send({"type": "tool_call"})
        with pytest.raises(ValueError, match="delivery failed"):
            await bridge.send({"type": "llm_response_delta", "delta": "durable"})
        await bridge.send({"type": "run_finished"})
        await bridge.flush()
        assert seen == ["llm_response_delta", "tool_call", "llm_response_delta", "run_finished"]

    asyncio.run(scenario())


def test_worker_exit_flushes_deltas_and_pruning_cannot_leave_a_late_draft(monkeypatch):
    import agent_loop
    import session_event_bus as bus

    sid = "bridge-prune-order"

    async def react(state, emit):
        for _ in range(100):
            await emit({"type": "llm_reasoning_delta", "ephemeral": True, "react_iter": 1, "delta": "x"})
        await agent_loop._prune_stream_ephemeral(emit, sid, types={"llm_reasoning_delta"})
        assert not bus._live_delta_snapshots.get(sid)
        await emit({"type": "llm_response_delta", "ephemeral": True, "delta": "final"})
        return state

    monkeypatch.setattr(agent_loop, "react_node", react)

    async def scenario():
        await bus.close_session_stream(sid)

        async def emit(event):
            await asyncio.sleep(0)
            await bus.publish_session_event(sid, event)

        await agent_loop._run_react_node_off_loop({}, emit)
        snapshots = list(bus._live_delta_snapshots[sid].values())
        assert len(snapshots) == 1
        assert snapshots[0]["type"] == "llm_response_delta"
        assert snapshots[0]["_delta_parts"]["delta"] == ["final"]
        await bus.close_session_stream(sid)

    asyncio.run(scenario())


def test_worker_exception_flushes_already_queued_deltas(monkeypatch):
    import agent_loop

    seen = []

    async def react(state, emit):
        await emit({"type": "llm_response_delta", "ephemeral": True, "delta": "before error"})
        raise RuntimeError("react failed")

    monkeypatch.setattr(agent_loop, "react_node", react)

    async def scenario():
        async def emit(event):
            await asyncio.sleep(0)
            seen.append(event)

        with pytest.raises(RuntimeError, match="react failed"):
            await agent_loop._run_react_node_off_loop({}, emit)
        assert seen[0]["delta"] == "before error"

    asyncio.run(scenario())
