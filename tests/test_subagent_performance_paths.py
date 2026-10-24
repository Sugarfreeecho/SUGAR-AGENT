"""Child delivery must keep durable barriers while sharing the optimized paths."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest


@pytest.fixture
def child_runtime(tmp_path, monkeypatch):
    import agent_loop
    import agent_subagent as child
    import execution_metrics as metrics
    import runtime_observability as obs
    import runtime_v2
    import session_event_bus
    from agent_harness import SessionManager
    from runtime_v2 import RuntimeMirror, SessionEventLog, SnapshotStore

    root = tmp_path / "sessions"
    published, parent_events = [], []

    class Manager:
        sessions_dir = root
        commit_execution_ui_event = SessionManager.commit_execution_ui_event
        commit_execution_ui_events = SessionManager.commit_execution_ui_events

        def __init__(self):
            self.ui = []
            self.metadata = []

        def _resolve_session_path(self, sid):
            return root / sid

        def clear_interrupt(self, sid):
            pass

        def request_interrupt(self, sid, *args, **kwargs):
            pass

        def append_ui_event(self, sid, event, *, require_commit=False):
            self.ui.append(dict(event))
            if runtime_v2.runtime_v2_primary():
                RuntimeMirror(root).mirror_ui_event(sid, event)

        def upsert_subagent_task(self, *args):
            pass

        def patch_subagent_metadata(self, sid, patch):
            self.metadata.append(dict(patch))

        def append_pending_subagent_result(self, *args):
            pass

        def write_subagent_output(self, *args):
            return str(tmp_path / "output.md")

        def _load_metadata(self, sid):
            return {}

    manager = Manager()
    metrics.flush()
    obs.flush()
    old_obs = (obs._sessions_root, obs._path_resolver)
    for name, value in {"_root": root, "_path_resolver": None, "_sessions": {},
                        "_flush_deadlines": {}, "_flush_failed_sessions": set(),
                        "_heartbeat_controls": set()}.items():
        monkeypatch.setattr(metrics, name, value)
    obs.configure(root)
    monkeypatch.setattr(child, "session_manager", manager)
    monkeypatch.setattr(child, "subagent_registry", child.SubagentTaskRegistry())
    monkeypatch.setattr(child, "_load_subagent_run_histories", lambda _: ([], [], ""))
    monkeypatch.setattr(child, "_commit_subagent_initial_turn", lambda *args: None)
    monkeypatch.setattr(child, "_persist_subagent_run_state", lambda *args: None)
    monkeypatch.setattr(child.todo_manager, "sync_session_from_key_context", lambda *args: None)
    monkeypatch.setattr(child, "cleanup_git_worktree_for_session", lambda *args: None)
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: True)

    async def publish(sid, event):
        published.append(dict(event))

    async def parent_emit(event):
        parent_events.append(dict(event))

    monkeypatch.setattr(session_event_bus, "publish_session_event", publish)

    async def execute(react):
        monkeypatch.setattr(agent_loop, "react_node", react)
        return await child._execute_subagent_run(
            child_id="child", parent_session_id="parent", user_text="task",
            description="test", subagent_type="generalPurpose", resumed=False,
            parent_emit=parent_emit,
        )

    yield child, manager, metrics, published, parent_events, execute
    metrics.flush()
    obs.flush()
    assert not metrics._heartbeat_controls
    assert SnapshotStore(root).wait_for_checkpoint("child", 5)
    if old_obs[0] is not None:
        obs.configure(old_obs[0], path_resolver=old_obs[1])


def tool_rows(count=4):
    return [{"type": "tool_call", "tool_name": "read_file", "tool_args": {},
             "tool_call_id": f"call-{i}", "tool_call_index": i, "result": f"ok-{i}",
             "react_iter": 1} for i in range(count)]


def done(state):
    state["final_response"] = "done"
    return state


def test_resumed_child_runs_have_distinct_request_traces_and_terminal_metrics(child_runtime):
    from agent_request_timing import new_request_trace
    child, manager, metrics, published, parent, execute = child_runtime
    identities = []

    async def react(state, emit):
        rid = state["_runtime_v2_run_id"]
        assert rid == state["_subagent_run_id"] == child.subagent_registry.running_runs()["child"]
        identities.append(rid)
        trace = new_request_trace(state, 1, 1)
        trace.mark("http_send_entered", 2)
        metrics.record_request("child", rid, 1, local_request_timing=trace.snapshot())
        return done(state)

    async def run():
        await execute(react)
        await execute(react)

    asyncio.run(run())
    runs = metrics._load("child")["runs"]
    assert len(set(identities)) == len(runs) == 2
    assert all(r["status"] == "finished" and r["finished_at"] and len(r["requests"]) == 1 for r in runs)
    assert all(r["requests"][0]["local_request_timing"]["run_id"] == r["run_id"] for r in runs)
    assert all("subagent_finalize_before_metrics_ms" in r for r in runs)


def test_single_result_uses_combined_commit_once_off_the_child_loop(child_runtime, monkeypatch):
    child, manager, metrics, published, parent, execute = child_runtime
    threads = []
    original = manager.commit_execution_ui_event

    def commit(*args, **kwargs):
        threads.append(threading.get_ident())
        assert not published
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, "commit_execution_ui_event", commit)

    async def react(state, emit):
        loop_thread = threading.get_ident()
        await emit(tool_rows(1)[0])
        assert threads == [threads[0]] and threads[0] != loop_thread
        assert len([e for e in manager.ui if e["type"] == "tool_call"]) == 1
        return done(state)

    asyncio.run(execute(react))
    assert len(published) == 1
    assert "_runtime_v2_committed" not in published[0]
    assert all("_runtime_v2_committed" not in e for e in parent)


def test_batch_waits_for_all_durable_rows_before_any_publication(child_runtime, monkeypatch):
    child, manager, metrics, published, parent, execute = child_runtime
    entered, release = threading.Event(), threading.Event()
    calls = []
    original = manager.commit_execution_ui_events

    def commit(*args, **kwargs):
        calls.append(args)
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, "commit_execution_ui_events", commit)

    async def react(state, emit):
        task = asyncio.create_task(emit.tool_batch(tool_rows()))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            assert not published and not any(e["type"] == "tool_call" for e in parent)
        finally:
            release.set()
        await task
        return done(state)

    asyncio.run(execute(react))
    assert len(calls) == 1
    assert [e["tool_call_id"] for e in published] == [f"call-{i}" for i in range(4)]
    assert all("_runtime_v2_committed" not in e for e in [*published, *parent])
    from runtime_v2 import SessionEventLog
    facts = SessionEventLog(manager.sessions_dir).read_all("child")
    assert sum(e.type == "execution_recorded" for e in facts) == 4


def test_partial_ui_failure_does_not_publish_the_batch_as_success(child_runtime, monkeypatch):
    child, manager, metrics, published, parent, execute = child_runtime
    original = manager.append_ui_event

    def append(sid, event, **kwargs):
        if event.get("tool_call_id") == "call-1":
            raise OSError("UI failed")
        return original(sid, event, **kwargs)

    monkeypatch.setattr(manager, "append_ui_event", append)

    async def react(state, emit):
        await emit.tool_batch(tool_rows())
        return done(state)

    asyncio.run(execute(react))
    assert not published
    assert metrics._load("child")["runs"][-1]["status"] == "failed"
    assert not any(e["type"] == "subagent_finish" and e.get("ok") for e in parent)


def test_cancelled_batch_sets_worker_cancel_guard_and_releases_registry(child_runtime, monkeypatch):
    child, manager, metrics, published, parent, execute = child_runtime
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    guards = []
    original = manager.commit_execution_ui_events

    def commit(*args, **kwargs):
        guards.append(kwargs["cancel_event"])
        entered.set()
        assert release.wait(5)
        try:
            return original(*args, **kwargs)
        finally:
            settled.set()

    monkeypatch.setattr(manager, "commit_execution_ui_events", commit)

    async def react(state, emit):
        await emit.tool_batch(tool_rows())
        return done(state)

    async def run():
        task = asyncio.create_task(execute(react))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            cancel = asyncio.create_task(child.subagent_registry.cancel("child"))
            while not guards[0].is_set():
                await asyncio.sleep(0)
            release.set()
            await cancel
            await task
            assert await asyncio.to_thread(settled.wait, 3)
        finally:
            release.set()

    asyncio.run(asyncio.wait_for(run(), 8))
    assert not published and not child.subagent_registry.is_running("child")
    assert metrics._load("child")["runs"][-1]["status"] == "interrupted"


@pytest.mark.parametrize("primary,strict", [(False, False), (True, False)])
def test_legacy_and_permissive_modes_keep_individual_delivery(child_runtime, monkeypatch, primary, strict):
    import runtime_v2
    child, manager, metrics, published, parent, execute = child_runtime
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: primary)
    monkeypatch.setattr(runtime_v2, "runtime_v2_strict", lambda: strict)
    monkeypatch.setattr(manager, "commit_execution_ui_events", lambda *a, **k: pytest.fail("unexpected batch"))

    async def react(state, emit):
        await emit.tool_batch(tool_rows())
        return done(state)

    asyncio.run(execute(react))
    assert len(published) == 4


def test_heartbeat_file_io_yields_the_child_event_loop(child_runtime, monkeypatch):
    child, manager, metrics, published, parent, execute = child_runtime
    entered, release = threading.Event(), threading.Event()
    original = manager.patch_subagent_metadata

    def patch(sid, fields):
        if set(fields) == {"subagent_run_heartbeat_at", "subagent_run_status"}:
            entered.set()
            assert release.wait(5)
        return original(sid, fields)

    monkeypatch.setattr(manager, "patch_subagent_metadata", patch)

    async def react(state, emit):
        task = asyncio.create_task(emit({"type": "status", "content": "working"}))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            progress = asyncio.Event()
            asyncio.get_running_loop().call_soon(progress.set)
            await progress.wait()
        finally:
            release.set()
        await task
        return done(state)

    result = asyncio.run(asyncio.wait_for(execute(react), 8))
    assert "done" in result
    assert any(e["type"] == "status" for e in published)


def test_partially_failed_metrics_start_still_finishes_and_clears_heartbeat(child_runtime, monkeypatch):
    child, manager, metrics, published, parent, execute = child_runtime
    original = metrics.start_run

    def start(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("metrics start failed after registration")

    monkeypatch.setattr(metrics, "start_run", start)

    async def react(state, emit):
        return done(state)

    asyncio.run(execute(react))
    assert metrics._load("child")["runs"][-1]["status"] == "finished"


@pytest.mark.parametrize("write", ["heartbeat", "ui"])
def test_cancel_waits_for_started_write_before_terminalizing(child_runtime, monkeypatch, write):
    child, manager, metrics, published, parent, execute = child_runtime
    entered, release = threading.Event(), threading.Event()
    target = "patch_subagent_metadata" if write == "heartbeat" else "append_ui_event"
    original = getattr(manager, target)

    def blocked(sid, event, **kwargs):
        eligible = (set(event) == {"subagent_run_heartbeat_at", "subagent_run_status"} if write == "heartbeat"
                    else event.get("type") == "status")
        if eligible:
            entered.set()
            assert release.wait(5)
        return original(sid, event, **kwargs)

    monkeypatch.setattr(manager, target, blocked)

    async def react(state, emit):
        await emit({"type": "status", "content": "working"})
        return done(state)

    async def run():
        task = asyncio.create_task(execute(react))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            cancel = asyncio.create_task(child.subagent_registry.cancel("child"))
            await asyncio.sleep(.02)
            assert not cancel.done()
            assert not any(e["type"] == "final" for e in manager.ui)
            release.set()
            await cancel
            await task
        finally:
            release.set()

    asyncio.run(asyncio.wait_for(run(), 8))
    assert metrics._load("child")["runs"][-1]["status"] == "interrupted"
    if write == "heartbeat":
        statuses = [m["subagent_run_status"] for m in manager.metadata if "subagent_run_status" in m]
        assert statuses[-1] == "interrupted"
    else:
        assert [e["type"] for e in manager.ui].index("status") < [e["type"] for e in manager.ui].index("final")


def test_react_run_error_is_not_reported_as_a_successful_subagent(child_runtime):
    child, manager, metrics, published, parent, execute = child_runtime

    async def react(state, emit):
        state["_run_error"] = "model request failed"
        return done(state)

    asyncio.run(execute(react))
    assert metrics._load("child")["runs"][-1]["status"] == "failed"
    assert any(e["type"] == "subagent_finish" and e.get("ok") is False for e in parent)


def test_cancel_during_metrics_start_cannot_leave_a_late_heartbeat_registration(child_runtime, monkeypatch):
    child, manager, metrics, published, parent, execute = child_runtime
    entered, release = threading.Event(), threading.Event()
    original = metrics.start_run

    def start(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(metrics, "start_run", start)

    async def react(state, emit):
        pytest.fail("cancelled child must not enter ReAct")

    async def run():
        task = asyncio.create_task(execute(react))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            cancel = asyncio.create_task(child.subagent_registry.cancel("child"))
            await asyncio.sleep(.02)
            assert not cancel.done()
            release.set()
            await cancel
            await task
        finally:
            release.set()

    asyncio.run(asyncio.wait_for(run(), 8))
    assert not metrics._heartbeat_controls
    assert metrics._load("child")["runs"][-1]["status"] == "interrupted"


@pytest.mark.parametrize("background", [False, True])
def test_real_subagent_loop_reaches_http_with_nonempty_finished_run(tmp_path, background):
    root = Path(__file__).resolve().parents[1]
    report = tmp_path / "subagent.json"
    command = [sys.executable, "-X", "utf8", str(root/"scripts/benchmark_agent_interround.py"),
               "--subagent", "--steps", "1", "--tools-per-round", "4", "--non-stream",
               "--only-case", "light_short", "--stress-workers", "0", "--output", str(report)]
    if background:
        command.append("--subagent-background")
    result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf8", timeout=60,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == 0, result.stdout[-5000:]
    data = json.loads(report.read_text(encoding="utf8"))
    case = data["cases"][0]
    assert case["run_id"] and case["parent_session_id"] != case["session_id"]
    assert case["successful_tools"] == 4 and case["http_requests"] == 2
    assert case["durable_model_tools"] == 4
    assert case["recovery_checkpoint_validated"] is True
    assert case["tool_to_http_send"]["samples"] == 1
    assert all(t["run_id"] == case["run_id"] for t in case["traces"])
    for request in case['requests']:
        assert set(request['pre_api_tail_events']) == {
            'timing_log', 'metrics_prepare', 'thinking_status_emit', 'strip_reasoning',
            'runtime_policy', 'pressure_emit_and_metrics', 'request_scope_and_setup'}
        assert sum(request['pre_api_tail_events'].values()) <= request['pre_api_tail_ms']
