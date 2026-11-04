from ui_process_timing import UiProcessTiming


class Clock:
    wall = 1000.0
    tick = 20.0

    def advance(self, seconds):
        self.wall += seconds
        self.tick += seconds

    def timing(self):
        return UiProcessTiming(clock=lambda: self.wall, monotonic=lambda: self.tick)


def test_reasoning_ends_at_response_not_later_commit_and_survives_history(tmp_path):
    from runtime_v2.mirror import RuntimeMirror
    from runtime_v2.ui_projection import RuntimeUiProjection
    clock = Clock()
    timing = clock.timing()
    base = {"run_id": "r", "react_iter": 2, "stream_seq": 8}
    first = {**base, "type": "llm_reasoning_delta", "delta": "检查"}
    timing.annotate(first)
    clock.advance(1.25)
    timing.annotate({**base, "type": "llm_response_delta", "delta": "说明"})
    clock.advance(3)
    final = {**base, "type": "llm_reasoning", "content": "检查"}
    timing.annotate(final)
    assert final["duration_ms"] == 1250
    assert final["started_at"] == 1000
    assert final["finished_at"] == 1001.25
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s", final)
    restored = RuntimeUiProjection(tmp_path).read_ui_events("s")[0]
    assert restored["duration_ms"] == 1250
    clock.advance(2)
    duplicate = {**base, "type": "llm_reasoning", "content": "检查"}
    timing.annotate(duplicate)
    assert duplicate["duration_ms"] == 1250


def test_reasoning_spans_are_scoped_by_run_iteration_and_stream():
    clock = Clock()
    timing = clock.timing()
    one = {"run_id":"r", "react_iter":1, "stream_seq":1}
    two = {"run_id":"r", "react_iter":2, "stream_seq":2}
    timing.annotate({**one,"type":"llm_reasoning_delta"})
    clock.advance(1)
    timing.annotate({**two,"type":"llm_reasoning_delta"})
    clock.advance(2)
    first = {**one,"type":"llm_reasoning"}
    timing.annotate(first)
    clock.advance(1)
    second = {**two,"type":"llm_reasoning"}
    timing.annotate(second)
    assert first["duration_ms"] == second["duration_ms"] == 3000
    unknown = {**one,"run_id":"other","type":"llm_reasoning"}
    timing.annotate(unknown)
    assert "duration_ms" not in unknown


def test_actual_tool_measurement_overrides_admission_wait_and_allows_zero():
    clock = Clock()
    timing = clock.timing()
    base = {"run_id":"r","react_iter":1,"tool_call_id":"tool"}
    timing.annotate({**base,"type":"tool_pending"})
    clock.advance(10)
    running = {**base,"type":"tool_execution_state","status":"running"}
    timing.annotate(running)
    assert running["started_at"] == 1010
    clock.advance(2)
    result = {**base,"type":"tool_call","result":"ok","status":{"ok":True,"duration_ms":1250}}
    timing.annotate(result)
    assert result["duration_ms"] == 1250
    assert result["finished_at"] - result["started_at"] == 1.25
    zero = {**base,"tool_call_id":"zero","type":"tool_call","status":{"ok":True,"duration_ms":0}}
    timing.annotate(zero)
    assert zero["duration_ms"] == 0


def test_clock_adjustment_does_not_change_measured_duration_or_forwarded_events():
    clock = Clock()
    timing = clock.timing()
    base = {"run_id":"r","react_iter":1}
    timing.annotate({**base,"type":"llm_reasoning_delta"})
    clock.wall -= 100
    clock.tick += 2
    result = {**base,"type":"llm_reasoning"}
    timing.annotate(result)
    assert result["duration_ms"] == 2000
    forwarded = {**base,"type":"llm_reasoning_delta","_subagent_forward":True}
    timing.annotate(forwarded)
    assert "started_at" not in forwarded


def test_argument_generation_ends_reasoning_and_recovery_uses_actual_execution_start(tmp_path):
    from runtime_v2.execution_journal import ExecutionJournal
    clock = Clock()
    timing, journal = clock.timing(), ExecutionJournal(tmp_path)
    base = {"run_id": "r", "react_iter": 1, "stream_seq": 8}
    timing.annotate({**base, "type": "llm_reasoning_delta"})
    clock.advance(1)
    draft = {**base, "type": "tool_call_delta", "id": "a", "index": 0,
             "name_delta": "run_shell", "arguments_delta": '{"command":"test"}'}
    timing.annotate(draft)
    journal.record("s", draft)
    clock.advance(3)
    reason = {**base, "type": "llm_reasoning", "content": "plan"}
    timing.annotate(reason)
    assert reason["duration_ms"] == 1000
    pending = {**base, "type": "tool_pending", "tool_call_id": "a", "tool_call_index": 0, "tool": "run_shell", "args": {"command": "test"}}
    timing.annotate(pending)
    journal.record("s", pending)
    clock.advance(5)
    running = {**base, "type": "tool_execution_state", "tool_call_id": "a", "tool_call_index": 0, "status": "running"}
    timing.annotate(running)
    journal.record("s", running)
    journal.record("s", {**base, "type": "tool_command_delta", "tool_call_id": "a", "delta_seq": 1, "delta": "live", "raw_delta": "live"})
    row = journal.read("s")["execution_records"][0]
    assert row["execution_started_at"] == 1009
    assert row["output"] == "live"


def _new_process(root, action):
    """No shared dictionaries, clocks, journal caches or Python process."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    source = r'''
import json, sys
from runtime_v2.execution_journal import ExecutionJournal
from runtime_v2.mirror import RuntimeMirror
from runtime_v2.ui_projection import RuntimeUiProjection
from ui_process_timing import UiProcessTiming
action = json.loads(sys.argv[2])
journal = ExecutionJournal(sys.argv[1])
timer = UiProcessTiming(clock=lambda: action['now'], monotonic=lambda: action['now'])
for event in action['events']:
    timer.annotate(event)
    journal.record('s', event)
    if event['type'] == 'llm_reasoning':
        RuntimeMirror(sys.argv[1]).mirror_ui_event('s', event)
print(json.dumps({'events': action['events'], 'records': journal.read('s')['execution_records'],
                 'ui': RuntimeUiProjection(sys.argv[1]).read_ui_events('s')}))
'''
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "app"), "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, "-c", source, str(root), json.dumps(action)],
                            capture_output=True, text=True, encoding="utf-8", check=True, env=env)
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_reasoning_start_and_end_survive_real_process_restarts(tmp_path):
    base = {"run_id": "r", "react_iter": 3, "stream_seq": 5}
    _new_process(tmp_path, {"now": 1000, "events": [{**base, "type": "llm_reasoning_delta", "delta": "plan"}]})
    boundary = _new_process(tmp_path, {"now": 1002.5, "events": [{**base, "type": "tool_call_delta", "name_delta": "run_shell"}]})
    assert boundary["records"][0]["duration_ms"] == 2500
    restored = _new_process(tmp_path, {"now": 1100, "events": [{**base, "stream_seq": None, "type": "llm_reasoning", "content": "plan"}]})
    for row in (restored["events"][0], restored["records"][0], restored["ui"][0]):
        assert row["started_at"] == 1000
        assert row["finished_at"] == 1002.5
        assert row["duration_ms"] == 2500
        assert not any(key.startswith("_process_") or key == "_reasoning_timing" for key in row)


def test_new_process_partial_timer_cannot_overwrite_durable_start(tmp_path):
    base = {"run_id": "r", "react_iter": 1, "stream_seq": 1}
    _new_process(tmp_path, {"now": 1000, "events": [{**base, "type": "llm_reasoning_delta", "delta": "a"}]})
    result = _new_process(tmp_path, {"now": 1007, "events": [
        {**base, "type": "llm_reasoning_delta", "delta": "b"},
        {**base, "type": "llm_reasoning", "content": "ab"},
    ]})
    assert result["events"][-1]["duration_ms"] == 7000
    assert result["events"][-1]["started_at"] == 1000


def test_abort_freezes_old_span_and_new_run_is_independent(tmp_path):
    base = {"run_id": "old", "react_iter": 1, "stream_seq": 1}
    _new_process(tmp_path, {"now": 1000, "events": [{**base, "type": "llm_reasoning_delta", "delta": "a"}]})
    _new_process(tmp_path, {"now": 1003, "events": [{"run_id": "old", "type": "run_interrupted", "reason": "process_restart"}]})
    result = _new_process(tmp_path, {"now": 1100, "events": [
        {**base, "run_id": "new", "type": "llm_reasoning_delta", "delta": "b"},
        {**base, "run_id": "new", "type": "llm_reasoning", "content": "b"},
    ]})
    old, new = result["records"]
    assert old["status"] == "interrupted"
    assert old["duration_ms"] == 3000
    assert new["duration_ms"] == 0


def test_journal_preserves_monotonic_measurement_and_unknown_history(tmp_path):
    from runtime_v2.execution_journal import ExecutionJournal
    clock = Clock()
    timing, journal = clock.timing(), ExecutionJournal(tmp_path)
    base = {"run_id": "r", "react_iter": 1, "stream_seq": 1}
    def record(event):
        timing.annotate(event)
        return journal.record("s", event)
    record({**base, "type": "llm_reasoning_delta", "delta": "a"})
    clock.wall -= 100
    clock.tick += 2
    record({**base, "type": "llm_response_delta", "delta": "b"})
    clock.advance(20)
    fact = record({**base, "type": "llm_reasoning", "content": "a"})
    assert fact["duration_ms"] == 2000
    unknown = record({**base, "run_id": "history-only", "type": "llm_reasoning", "content": "old"})
    assert "duration_ms" not in unknown
    assert "duration_ms" not in journal.read("s")["execution_records"][-1]


def test_reasoning_end_freezes_durable_span_without_replacing_content(tmp_path):
    base = {"run_id": "r", "react_iter": 1, "stream_seq": 1}
    _new_process(tmp_path, {"now": 1000, "events": [{**base, "type": "llm_reasoning_delta", "delta": "original"}]})
    ended = _new_process(tmp_path, {"now": 1001, "events": [{**base, "type": "llm_reasoning_end"}]})
    assert ended["records"][0]["content"] == "original"
    result = _new_process(tmp_path, {"now": 1100, "events": [{**base, "type": "llm_reasoning", "content": "original"}]})
    assert result["events"][0]["duration_ms"] == 1000


def test_late_boundary_cannot_close_another_phase_or_run(tmp_path):
    from runtime_v2.execution_journal import ExecutionJournal
    clock = Clock()
    timing, journal = clock.timing(), ExecutionJournal(tmp_path)
    def record(kind, *, run="r", phase=1, stream=1):
        event = {"type": kind, "run_id": run, "react_iter": phase, "stream_seq": stream, "delta": "x"}
        timing.annotate(event)
        return journal.record("s", event)
    record("llm_reasoning_delta")
    clock.advance(1)
    record("llm_reasoning_delta", phase=2, stream=2)
    record("llm_reasoning_delta", run="other")
    clock.advance(1)
    record("tool_call_delta")
    rows = journal.read("s")["execution_records"]
    assert rows[0]["duration_ms"] == 2000
    assert "duration_ms" not in rows[1]
    assert "duration_ms" not in rows[2]
    clock.advance(3)
    fact = record("llm_reasoning", phase=2, stream=None)
    assert fact["duration_ms"] == 4000
    assert "duration_ms" not in journal.read("s")["execution_records"][2]


def test_uncommitted_ui_plan_cannot_publish_its_reasoning_index(tmp_path):
    from runtime_v2.execution_journal import ExecutionJournal
    from runtime_v2.execution_ui_batch import _ExecutionPlan
    journal = ExecutionJournal(tmp_path)
    journal.record("s", {"type": "llm_response_delta", "run_id": "r", "react_iter": 1, "stream_seq": 1, "delta": "response only"})
    state = journal._state("s")
    assert state["_reasoning_by_phase"] == {}
    before_seq = state["seq"]
    plan = _ExecutionPlan(journal, state)
    plan.record("s", {"type": "llm_reasoning", "run_id": "r", "react_iter": 1, "stream_seq": 1, "content": "plan only"})
    assert plan._planned["_reasoning_by_phase"]
    assert state["_reasoning_by_phase"] == {}
    assert state["seq"] == before_seq
    assert len(journal.read("s")["execution_records"]) == 1
