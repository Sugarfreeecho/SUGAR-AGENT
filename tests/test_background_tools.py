import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture(autouse=True)
def _clean_registry():
    import background_tools

    background_tools.configure_committer(None)
    yield
    background_tools.configure_committer(None)
    background_tools._running.clear()


def test_execution_scope_forwards_then_isolates_state_and_emit():
    import background_tools

    emitted = []

    async def emit(event):
        emitted.append(event)

    live = {"session_id": "s", "stream_events": [], "llm_history": ["h"]}
    scope = background_tools.execution_scope(
        live, emit, tool_call={"name": "web_fetch", "id": "c1", "args": {}})
    state = scope.state
    state["scratch_only"] = 1
    assert live["scratch_only"] == 1, "attached scope must behave like the live state"

    scope.detach()

    state["scratch_only"] = 2
    state["stream_events"].append({"type": "status"})
    state.pop("_pending_human_request", None)
    assert live["scratch_only"] == 1
    assert live["stream_events"] == []
    assert state.get("_background_tool") is True
    assert asyncio.run(scope.emit({"type": "status"})) is None
    assert emitted == []


def test_scoped_state_keeps_history_lists_independent():
    import background_tools

    live = {"session_id": "s", "llm_history": [1], "work_messages": [2], "stream_events": []}
    scope = background_tools.execution_scope(live, None, tool_call={"name": "t", "id": "c"})
    scope.detach()
    scope.state["llm_history"].append(3)
    scope.state["work_messages"].append(4)
    assert live["llm_history"] == [1]
    assert live["work_messages"] == [2]


def test_note_lines_report_status_and_truncate():
    import background_tools

    rows = [
        {"tool": "web_fetch", "args": {"url": "https://example.com"}, "status": "completed",
         "result": "ok"},
        {"tool": "grep", "args": {}, "status": "failed",
         "result": "x" * (background_tools.NOTE_RESULT_LIMIT + 10)},
    ]
    lines = background_tools.note_lines(rows)
    assert "web_fetch" in lines[0] and "已完成" in lines[0]
    assert lines[0].endswith("\nok")
    assert "失败" in lines[1]
    assert lines[1].endswith("完整结果见工具记录）")


def test_claim_notes_is_one_shot_and_restorable(tmp_path):
    import background_tools

    session_dir = tmp_path / "sess"
    session_dir.mkdir()
    background_tools._write_pending_note(session_dir, {"tool": "t", "status": "completed", "result": "r"})
    rows = background_tools.claim_notes("sess", session_dir)
    assert len(rows) == 1
    assert background_tools.claim_notes("sess", session_dir) == []
    background_tools.restore_notes(session_dir, rows)
    assert len(background_tools.claim_notes("sess", session_dir)) == 1


def test_claim_notes_keeps_a_running_call_registered(tmp_path):
    import background_tools

    session_dir = tmp_path / "sess-live"
    session_dir.mkdir()
    committed = []

    async def committer(session_id, event):
        committed.append(event)

    background_tools.configure_committer(committer)

    async def scenario():
        loop = asyncio.get_running_loop()
        task = loop.create_future()
        scope = background_tools.execution_scope(
            {}, None, tool_call={"name": "grep", "id": "c-live"})
        assert background_tools.register(
            session_id="sess-live", run_id="r", session_dir=session_dir,
            scope=scope, task=task)
        # The next round runs while the tool is still going: claiming must not
        # discard the ownership that produces the eventual result.
        assert background_tools.claim_notes("sess-live", session_dir) == []
        assert background_tools.is_backgrounded("sess-live", "c-live")
        task.set_result({"type": "tool", "tool_name": "grep", "tool_args": {},
                         "tool_id": "c-live", "result": "hit",
                         "tool_detail_llm": "hit", "tool_detail_ui": "hit"})
        for _ in range(50):
            await asyncio.sleep(0.01)
            if committed:
                break

    asyncio.run(scenario())
    assert committed and committed[0]["tool_call_id"] == "c-live"


def test_close_unfinished_calls_uses_background_text():
    from runtime_v2.execution_journal import close_unfinished_calls
    from agent_messages import AssistantMessage

    message = AssistantMessage(
        content="",
        tool_calls=[{"id": "a", "name": "web_fetch", "args": {}},
                    {"id": "b", "name": "run_shell", "args": {}}],
    )
    _out, added = close_unfinished_calls([message], [], background_ids={"a"})
    texts = {row.tool_call_id: str(row.content) for row in added}
    assert "转入后台继续执行" in texts["a"]
    assert "用户追问打断" in texts["b"]


def test_abort_preserves_background_tool_status(tmp_path):
    from runtime_v2.execution_journal import ExecutionJournal

    journal = ExecutionJournal(tmp_path)
    journal.log.append("s", "user_turn_committed", {"content": "work"}, run_id="r")

    def emit(kind, **fields):
        return journal.record("s", {"type": kind, "run_id": "r", "stream_seq": 1,
                                    "react_iter": 1, **fields})

    def record_for(tool_id):
        return next(row for row in journal.read("s")["execution_records"]
                    if row.get("tool_call_id") == tool_id)

    emit("tool_pending", tool_call_id="bg", tool_call_index=0, tool="web_fetch", args={})
    emit("tool_execution_state", tool_call_id="bg", tool_call_index=0,
         status="running", executed=True)
    emit("llm_stream_aborted", reason="user_steer", preserve_tool_call_ids=["bg"])
    assert record_for("bg")["status"] == "background"

    emit("tool_pending", tool_call_id="fg", tool_call_index=1, tool="web_fetch", args={})
    emit("tool_execution_state", tool_call_id="fg", tool_call_index=1,
         status="running", executed=True)
    emit("llm_stream_aborted", reason="user_steer")
    assert record_for("fg")["status"] == "interrupted"


def test_background_state_ignores_steer_and_stop(monkeypatch):
    import agent_loop

    def _boom(*args, **kwargs):
        raise AssertionError("background state must not poll the foreground run")

    monkeypatch.setattr(agent_loop.session_manager, "is_interrupt_requested", _boom)
    state = {"session_id": "s", "_runtime_v2_run_id": "r", "_background_tool": True}
    assert agent_loop._steer_requested(state) is False
    assert agent_loop._state_interrupt_requested(state) is False


def test_await_steerable_moves_started_tool_to_background(monkeypatch, tmp_path):
    import agent_loop
    import background_tools

    session_dir = tmp_path / "sess-bg"
    session_dir.mkdir()
    monkeypatch.setattr(agent_loop, "_active_session_path", lambda sid: session_dir)
    committed = []

    async def committer(session_id, event):
        committed.append((session_id, event))

    background_tools.configure_committer(committer)

    state = {"session_id": "sess-bg", "_runtime_v2_run_id": "run-bg",
             "stream_events": [], "_active_stream_seq": 4}
    emitted = []

    async def emit(event):
        emitted.append(event)

    tool_call = {"name": "web_fetch", "id": "call-bg", "args": {"url": "u"}, "index": 0}
    scope = background_tools.execution_scope(
        state, emit, tool_call=tool_call, react_iter=2, stream_seq=4)

    steer = {"on": False}
    monkeypatch.setattr(agent_loop, "_steer_requested", lambda _state: steer["on"])

    gate = asyncio.Event()
    started = asyncio.Event()

    async def work():
        scope.marker["executing"] = True
        started.set()
        await gate.wait()
        return {"type": "tool", "tool_name": "web_fetch", "tool_args": {"url": "u"},
                "tool_id": "call-bg", "result": "page", "tool_detail_llm": "page",
                "tool_detail_ui": "page"}

    async def scenario():
        task = asyncio.create_task(
            agent_loop._await_steerable(state, work(), emit, "tool", background=scope))
        await started.wait()
        steer["on"] = True
        with pytest.raises(agent_loop._SteerRestartRequested):
            await task
        assert scope.detached is True
        assert background_tools.is_backgrounded("sess-bg", "call-bg")
        gate.set()
        for _ in range(50):
            await asyncio.sleep(0.01)
            if committed:
                break

    asyncio.run(scenario())

    assert committed, "the finished background tool must be committed"
    session_id, event = committed[0]
    assert session_id == "sess-bg"
    assert event["tool_call_id"] == "call-bg"
    assert event["execution_status"] == "completed"
    assert event["background_execution"] is True
    rows = json.loads((session_dir / background_tools.RESULTS_FILENAME).read_text(encoding="utf-8"))
    assert rows[0]["tool"] == "web_fetch" and rows[0]["status"] == "completed"


def test_await_steerable_cancels_call_that_never_started(monkeypatch, tmp_path):
    import agent_loop
    import background_tools

    monkeypatch.setattr(agent_loop, "_active_session_path", lambda sid: tmp_path / "sess")
    state = {"session_id": "sess-cancel", "_runtime_v2_run_id": "run",
             "stream_events": []}
    scope = background_tools.execution_scope(
        state, None, tool_call={"name": "web_fetch", "id": "call-x", "args": {}, "index": 0})

    steer = {"on": False}
    monkeypatch.setattr(agent_loop, "_steer_requested", lambda _state: steer["on"])
    cancelled = []

    async def work():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    async def scenario():
        task = asyncio.create_task(
            agent_loop._await_steerable(state, work(), None, "tool", background=scope))
        await asyncio.sleep(0.12)
        steer["on"] = True
        with pytest.raises(agent_loop._SteerRestartRequested):
            await task
        await asyncio.sleep(0.1)

    asyncio.run(scenario())

    assert cancelled == [True]
    assert scope.detached is False
    assert background_tools.is_backgrounded("sess-cancel", "call-x") is False
