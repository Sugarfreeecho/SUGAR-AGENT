import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from runtime_v2.execution_journal import (ExecutionJournal, close_unfinished_calls,
    merge_continuation, register_output_continuation, execution_progress_note)
from runtime_v2.event_log import SessionEventLog
from runtime_v2.ui_projection import RuntimeUiProjection
from runtime_v2.projector import RuntimeProjector
from agent_messages import AssistantMessage, ToolMessage, UserMessage


@pytest.fixture
def journal(tmp_path):
    store = ExecutionJournal(tmp_path)
    store.log.append("s", "user_turn_committed", {"content": "work"}, run_id="r")
    return store


def emit(store, kind, **fields):
    return store.record("s", {"type": kind, "run_id": "r", "stream_seq": 1, "react_iter": 1, **fields})


def test_draft_promotes_to_same_execution_and_survives_cache_loss(journal):
    first = emit(journal, "tool_call_delta", index=0, id="call", name_delta="run_shell", arguments_delta='{"command":')
    pending = emit(journal, "tool_pending", tool_call_id="call", tool_call_index=0,
                   tool="run_shell", args={"command": "test"})
    assert first["execution_id"] == pending["execution_id"]
    ExecutionJournal._cache.clear()
    record = journal.read("s")["execution_records"][0]
    assert record["arguments_raw"] == '{"command":'
    assert record["status"] == "waiting_execution"
    assert record["process_group_id"] == "turn:1"


def test_updates_are_not_ui_history_or_model_messages(journal):
    emit(journal, "tool_call_delta", index=0, name_delta="write_file", arguments_delta='{"content":"draft')
    assert len(RuntimeUiProjection(journal.log.root).read_ui_events("s")) == 1
    snapshot = RuntimeProjector().project(journal.log.read_all("s"))
    assert snapshot["executions"]
    assert not any(message.get("tool_calls") for message in snapshot["raw_model_messages"])


def test_incremental_replay_includes_journal_updates_with_runtime_cursor(journal):
    event = emit(journal, "llm_response_delta", delta="received", delta_seq=1)
    page = RuntimeUiProjection(journal.log.root).read_ui_after_runtime_seq("s", after_runtime_seq=1)
    assert page["events"][0]["type"] == "execution_update"
    assert page["events"][0]["ephemeral"] is True
    assert page["last_runtime_seq"] == event["execution_runtime_seq"]


def test_duplicate_delta_is_idempotent(journal):
    first = emit(journal, "llm_response_delta", delta="one", delta_seq=1)
    duplicate = emit(journal, "llm_response_delta", delta="one", delta_seq=1)
    assert first["execution_runtime_seq"] == duplicate["execution_runtime_seq"]
    assert journal.read("s")["execution_records"][0]["content"] == "one"


def test_late_pending_cannot_clear_started_state(journal):
    emit(journal, "tool_pending", tool_call_id="call", tool="write_file", args={"path": "out.txt"})
    emit(journal, "tool_execution_state", tool_call_id="call", executed=True, status="unknown")
    emit(journal, "tool_pending", tool_call_id="call", tool="write_file", args={"path": "out.txt"})
    row = journal.read("s")["execution_records"][0]
    assert row["executed"] and row["status"] == "unknown"
    assert journal.uncertain_execution("s", "write_file", {"path": "out.txt"})


def test_reasoning_commit_keeps_received_whitespace(journal):
    emit(journal, "llm_reasoning_delta", delta="\n received reasoning \n", delta_seq=1)
    emit(journal, "llm_reasoning", content="received reasoning")
    assert journal.read("s")["execution_records"][0]["content"] == "\n received reasoning \n"


def test_parent_does_not_persist_child_forward(journal):
    emit(journal, "tool_call_delta", _subagent_forward=True, agent_id="child", arguments_delta="child")
    assert journal.read("s")["execution_records"] == []


def test_steer_and_replacement_run_reuse_group_but_final_splits(journal):
    first = emit(journal, "llm_response_delta", delta="first")
    journal.log.append("s", "user_turn_committed", {"content": "steer", "ui_type": "user_steer"}, run_id="r2")
    next_event = journal.record("s", {"type": "llm_response_delta", "run_id": "r2", "delta": "next"})
    assert first["process_group_id"] == next_event["process_group_id"]
    journal.log.append("s", "assistant_final_committed", {"content": "done"}, run_id="r2")
    after = journal.record("s", {"type": "llm_response_delta", "run_id": "r3", "delta": "later"})
    assert after["process_group_id"] != first["process_group_id"]


def test_approval_and_question_keep_tool_identity(journal):
    pending = emit(journal, "tool_pending", tool_call_id="call", tool="ask_user", args={})
    card = emit(journal, "interaction_requested", tool_call_id="call", interaction_id="question")
    assert pending["execution_id"] == card["execution_id"]
    assert journal.read("s")["execution_records"][0]["status"] == "waiting_input"


def test_abort_keeps_partial_output_and_marks_interrupted(journal):
    emit(journal, "tool_pending", tool_call_id="call", tool="run_shell", args={})
    emit(journal, "tool_command_delta", tool_call_id="call", delta="10 files done\n")
    event = emit(journal, "llm_stream_aborted", reason="user_steer")
    record = journal.read("s")["execution_records"][0]
    assert record["output"] == "10 files done\n"
    assert record["status"] == "interrupted"
    assert event["preserve_execution_records"] is True


def test_output_truncation_does_not_cancel_complete_running_call(journal):
    emit(journal, "tool_pending", tool_call_id="call", tool="run_shell", args={})
    emit(journal, "tool_execution_state", tool_call_id="call", status="running", executed=True)
    emit(journal, "tool_call_delta", id="call", arguments_delta=" ", delta_seq=9)
    emit(journal, "tool_call_delta", index=1, id="draft", arguments_delta='{"content":')
    emit(journal, "llm_stream_aborted", reason="truncated_after_closed_tool_call")
    records = journal.read("s")["execution_records"]
    assert records[0]["status"] == "running"
    assert records[1]["status"] == "interrupted"


def test_closing_mixed_calls_retains_real_result_and_progress():
    assistant = AssistantMessage(tool_calls=[{"id": "done", "name": "read_file", "args": {}},
                                              {"id": "interrupted", "name": "run_shell", "args": {}}])
    real = ToolMessage("real result", "done")
    rows, added = close_unfinished_calls([assistant, real, UserMessage("followup")],
        [{"tool_call_id": "interrupted", "executed": True, "output": "10 files"}])
    assert rows[1] is real
    assert rows[2].tool_call_id == "interrupted"
    assert "10 files" in rows[2].content and "尚未确认" in rows[2].content
    assert isinstance(rows[3], UserMessage)
    assert len(added) == 1
    assert close_unfinished_calls(rows, [])[1] == []


@pytest.mark.parametrize("prefix,suffix,expected", [
    ("hello ", "world", "hello world"),
    ("hello world", "world!", "hello world!"),
    ("hello", "hello world", "hello world"),
])
def test_continuation_merges_exact_overlap(prefix, suffix, expected):
    assert merge_continuation(prefix, suffix) == expected


def test_history_delete_does_not_resurrect_execution(journal):
    first = emit(journal, "tool_call", tool_call_id="call", tool="read_file", result="done")
    visible = journal.log.append("s", "tool_finished", first)
    journal.read("s")
    journal.log.append("s", "message_deleted", {"target_seq": visible.seq})
    assert not journal.read("s")["execution_records"]


def test_shell_timeout_keeps_stdout_and_stderr(tmp_path):
    import agent_tools
    script = tmp_path / "timeout_fixture.py"
    script.write_text("import sys,time\nprint('progress',flush=True)\nprint('diagnostic',file=sys.stderr,flush=True)\ntime.sleep(10)\n", encoding="utf-8")
    result = asyncio.run(agent_tools.run_shell(f'python "{script}"', timeout_ms=2000))
    assert "timed out" in result
    assert "progress" in result
    assert "diagnostic" in result


def test_cancelled_pipe_reader_retains_received_bytes():
    import agent_tools
    async def scenario():
        pipe = asyncio.StreamReader()
        pipe.feed_data(b"already received")
        publisher = agent_tools._RunShellProgressPublisher(None)
        task = asyncio.create_task(agent_tools._read_run_shell_pipe(pipe, "stdout", publisher))
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return publisher.output_bytes["stdout"]
    assert asyncio.run(scenario()) == b"already received"


def test_arguments_and_output_use_independent_delta_counters(journal):
    emit(journal, "tool_call_delta", id="call", arguments_delta='{"command":', delta_seq=5)
    emit(journal, "tool_pending", tool_call_id="call", tool="run_shell", args={"command": "test"})
    emit(journal, "tool_command_delta", tool_call_id="call", stream="stderr", delta="diagnostic", delta_seq=1)
    row = journal.read("s")["execution_records"][0]
    assert row["output"] == "diagnostic" and row["stderr"] == "diagnostic"


def test_late_delta_retains_output_without_reopening_terminal(journal):
    emit(journal, "tool_pending", tool_call_id="call", tool="run_shell", args={})
    emit(journal, "llm_stream_aborted", reason="user_steer")
    emit(journal, "tool_command_delta", tool_call_id="call", delta="late confirmed output", delta_seq=1)
    row = journal.read("s")["execution_records"][0]
    assert row["status"] == "interrupted" and row["output"] == "late confirmed output"
    emit(journal, "tool_call", tool_call_id="call", tool="run_shell", result="real result")
    assert journal.read("s")["execution_records"][0]["status"] == "completed"


def test_unknown_operation_cannot_be_repeated_until_confirmed_stopped(journal):
    args = {"command":"write command"}
    emit(journal, "tool_pending", tool_call_id="call", tool="run_shell", args=args)
    emit(journal, "tool_execution_state", tool_call_id="call", status="running", executed=True)
    emit(journal, "run_failed", reason="crash")
    assert journal.uncertain_execution("s", "run_shell", args)
    assert not journal.uncertain_execution("s", "run_shell", {"command":"query state"})
    emit(journal, "tool_execution_state", tool_call_id="call", status="interrupted", executed=True, process_state="stopped")
    assert not journal.uncertain_execution("s", "run_shell", args)


def test_duplicate_terminal_is_not_appended(journal):
    first = emit(journal, "tool_call", tool_call_id="call", tool="read_file", args={}, result="real")
    second = emit(journal, "tool_call", tool_call_id="call", tool="read_file", args={}, result="real")
    assert first["execution_runtime_seq"] == second["execution_runtime_seq"]


def test_late_tool_result_keeps_original_request_identity(journal):
    import agent_loop
    first = emit(journal, "tool_pending", tool_call_id="call", tool="read_file", args={})
    replacement = emit(journal, "tool_pending", stream_seq=2, tool_call_id="call", tool="read_file", args={})
    async def publish(event):
        event.setdefault("run_id", "r")
        event.setdefault("stream_seq", 2)
        journal.record("s", event)
    result = {"type": "tool", "tool_name": "read_file", "tool_args": {}, "tool_id": "call",
              "result": "old result", "execution_stream_seq": 1, "execution_react_iter": 1}
    asyncio.run(agent_loop._emit_tool_call_sse(publish, result, react_iter=2))
    rows = {row["execution_id"]: row for row in journal.read("s")["execution_records"]}
    assert rows[first["execution_id"]]["result"] == "old result"
    assert rows[replacement["execution_id"]]["status"] == "waiting_execution"


def test_complete_calls_without_indexes_do_not_overwrite_each_other(journal):
    first = emit(journal, "tool_pending", tool_call_id="first", tool="read_file", args={"path":"one"})
    second = emit(journal, "tool_pending", tool_call_id="second", tool="read_file", args={"path":"two"})
    assert first["execution_id"] != second["execution_id"]
    emit(journal, "tool_call", tool_call_id="first", tool="read_file", result="one")
    emit(journal, "tool_call", tool_call_id="second", tool="read_file", result="two")
    records = journal.read("s")["execution_records"]
    assert [row["tool_call_id"] for row in records] == ["first", "second"]
    assert [row["result"] for row in records] == ["one", "two"]


def test_reused_provider_call_id_in_new_attempt_has_distinct_execution(journal):
    first = emit(journal, "tool_pending", tool_call_id="call_0", tool="read_file", args={"path":"one"})
    second = emit(journal, "tool_pending", tool_call_id="call_0", tool="read_file", args={"path":"two"}, stream_seq=2)
    assert first["execution_id"] != second["execution_id"]
    assert len(journal.read("s")["execution_records"]) == 2


def test_continuation_limit_counts_mixed_and_draft_requests():
    state = {}
    assert register_output_continuation(state, "hello ", tool_drafts=False) == (1, True)
    assert register_output_continuation(state, "partial tool", tool_drafts=True) == (2, True)
    assert register_output_continuation(state, "world", tool_drafts=False) == (3, False)
    assert state["_output_continuation"] == "hello world"


def test_short_matching_character_is_not_removed():
    assert merge_continuation("data", "analysis") == "dataanalysis"


def test_progress_note_never_makes_argument_drafts_formal_calls():
    rows = [{"kind": "reasoning", "status": "interrupted", "content": "checked ten files"},
            {"kind": "tool", "tool": "write_file", "arguments_raw": '{"content":"half'}]
    note = execution_progress_note(rows, reason="steer")
    assert "checked ten files" in note and "草稿" in note and "未执行" in note
    assert not execution_progress_note([{"kind":"tool", "tool":"read_file", "args":{},
        "arguments_raw":"{}", "executed":True, "status":"completed"}], reason="steer")


def test_non_streaming_truncation_keeps_raw_incomplete_arguments(journal):
    from runtime_v2.execution_journal import response_tool_drafts
    response = {"choices":[{"message":{"tool_calls":[{"id":"call", "function":{
        "name":"write_file", "arguments":'{"content":"not finished'}}]}}]}
    for draft in response_tool_drafts(response):
        journal.record("s", {**draft, "run_id":"r", "react_iter":1, "stream_seq":1})
    emit(journal, "llm_stream_aborted", reason="output_length")
    record = journal.read("s")["execution_records"][0]
    assert record["arguments_raw"] == '{"content":"not finished'
    assert record["status"] == "interrupted" and not record.get("executed")


def test_transport_error_with_only_argument_draft_informs_next_request(journal, monkeypatch):
    import agent_loop
    from agent_harness import strip_reasoning_for_api_request
    emit(journal, "tool_call_delta", id="unfinished", name_delta="write_file",
         arguments_delta='{"path":"output.txt","content":"unfinished')
    emit(journal, "llm_stream_aborted", reason="transport_error")
    monkeypatch.setattr(agent_loop, "_execution_recovery_snapshot", lambda sid: journal.read("s"))
    monkeypatch.setattr(agent_loop, "_persist_state_with_model_append", lambda *args: None)
    state = {"session_id": "s", "_runtime_v2_run_id": "r", "_active_stream_seq": 1,
             "llm_history": [UserMessage("work")], "work_messages": [UserMessage("work")]}
    agent_loop._append_execution_progress_note(state, "模型流连接中断")
    outgoing = strip_reasoning_for_api_request(state["llm_history"])
    assert "output.txt" in outgoing[-1].content and "参数草稿未执行" in outgoing[-1].content
    assert not any(getattr(message, "tool_calls", None) for message in outgoing)


def test_human_requests_restore_execution_anchor_and_verify_digest(journal, monkeypatch):
    from human_interaction.service import HumanInteractionService, HumanInteractionConflict
    service = HumanInteractionService(journal.log.root, path_resolver=lambda sid: journal.log.session_dir(sid))
    pending = emit(journal, "tool_pending", tool_call_id="call", tool="run_shell", args={"command": "test"})
    approval = service.create_approval("s", approval_id="approval", run_id="r", tool_call_id="call",
                                       metadata={"command_preview": "test"})
    assert approval["execution_id"] == pending["execution_id"]
    assert approval["process_group_id"] == pending["process_group_id"]
    assert journal.read("s")["execution_records"][0]["status"] == "waiting_approval"
    ExecutionJournal._cache.clear()
    restored = HumanInteractionService(journal.log.root, path_resolver=lambda sid: journal.log.session_dir(sid))
    assert restored.get("s", "approval", kind="approval")["execution_id"] == pending["execution_id"]
    with pytest.raises(HumanInteractionConflict, match="digest"):
        restored.create_approval("s", approval_id="approval", run_id="r", tool_call_id="call",
                                 metadata={"command_preview": "changed command"})
    emit(journal, "tool_pending", tool_call_id="ask", tool="ask_user", args={})
    question = restored.create_question("s", {"questions":[{"header":"choice", "question":"Pick?",
        "options":[{"label":"one", "description":"first"}, {"label":"two", "description":"second"}]}]},
        run_id="r", tool_call_id="ask", interaction_id="question")
    assert question["process_group_id"] == pending["process_group_id"]
    ExecutionJournal._cache.clear()
    assert journal.read("s")["execution_records"][-1]["status"] == "waiting_input"


def test_restart_context_includes_result_executed_before_model_checkpoint(journal, monkeypatch):
    import agent_loop
    emit(journal, "tool_call", tool_call_id="write", tool="write_file", args={"path":"created.txt"}, result="created")
    emit(journal, "llm_reasoning", content="checked progress", execution_status="interrupted")
    monkeypatch.setattr(agent_loop, "_execution_recovery_snapshot", lambda sid: journal.read("s"))
    monkeypatch.setattr(agent_loop, "_persist_state_with_model_replace", lambda *args: None)
    state = {"session_id":"s", "_runtime_v2_run_id":"replacement",
             "llm_history":[UserMessage("work")], "work_messages":[UserMessage("work")]}
    agent_loop._restore_execution_context(state)
    from agent_harness import strip_reasoning_for_api_request
    outgoing = strip_reasoning_for_api_request(state["llm_history"])
    assert "created.txt" in outgoing[-1].content and "created" in outgoing[-1].content
    assert "checked progress" in outgoing[-1].content
    assert "不要重复" in outgoing[-1].content
    assert not any(getattr(message, "tool_calls", None) for message in outgoing)


@pytest.mark.parametrize("decision", ["allow_once", "deny"])
def test_restart_approval_resumes_once_without_replaying_operation(journal, monkeypatch, decision):
    import json
    import human_interaction
    import security
    import webui
    from human_interaction.service import HumanInteractionService

    service = HumanInteractionService(journal.log.root, path_resolver=lambda sid: journal.log.session_dir(sid))
    emit(journal, "tool_pending", tool_call_id="approved-call", tool="write_file", args={"path": "out.txt"})
    service.create_approval("s", approval_id="recover", run_id="r", tool_call_id="approved-call",
        metadata={"security_request_digest": "sha256:original"})
    monkeypatch.setattr(human_interaction, "get_human_interaction_service", lambda: service)
    monkeypatch.setattr(webui, "_has_local_worker_activity", lambda sid: False)
    monkeypatch.setattr(webui.session_manager.repository, "sessions_dir", journal.log.root)
    monkeypatch.setattr(webui.session_manager, "_resolve_session_path", lambda sid: journal.log.session_dir(sid))
    grants, scheduled = [], []
    monkeypatch.setattr(security, "add_approval_grant", lambda *args: grants.append(args))
    monkeypatch.setattr(webui, "_schedule_human_interaction_recovery", lambda sid: scheduled.append(sid) or True)
    async def publish(*args):
        pass
    monkeypatch.setattr(webui, "publish_session_event", publish)
    class Request:
        headers = {}
        async def json(self):
            return {"decision": decision, "rejection_reason": "use another path" if decision == "deny" else ""}

    first = json.loads(asyncio.run(webui.resolve_session_approval("s", "recover", Request())).body)
    second = json.loads(asyncio.run(webui.resolve_session_approval("s", "recover", Request())).body)
    assert first["ok"] and first["recovered"] and first["recovery_scheduled"]
    assert second["ok"] and not second["recovery_scheduled"]
    assert scheduled == ["s"]
    assert len(grants) == (1 if decision == "allow_once" else 0)
    row = journal.read("s")["execution_records"][0]
    assert row["status"] == "interrupted" and not row["executed"]
    assert row["process_group_id"] == "turn:1"
    notices = [event.payload for event in journal.log.read_all("s")
               if event.payload.get("operation_id") == "approval-recovery:recover"]
    assert len(notices) == 1 and notices[0]["role"] == "system"
    assert "out.txt" in notices[0]["content"]


def test_recovered_approval_rejects_changed_summary(journal):
    from human_interaction.service import HumanInteractionService, HumanInteractionConflict
    service = HumanInteractionService(journal.log.root, path_resolver=lambda sid: journal.log.session_dir(sid))
    service.create_approval("s", approval_id="original", metadata={"message": "original operation"})
    record = service.verified_approval_request("s", "original")
    record["message"] = "changed operation"
    with pytest.raises(HumanInteractionConflict, match="摘要"):
        service._verify_approval_record(record)


def test_restart_approval_cannot_repeat_an_operation_that_started(journal, monkeypatch):
    import json
    import human_interaction
    import webui
    from human_interaction.service import HumanInteractionService
    service = HumanInteractionService(journal.log.root, path_resolver=lambda sid: journal.log.session_dir(sid))
    emit(journal, "tool_pending", tool_call_id="call", tool="write_file", args={"path": "out.txt"})
    service.create_approval("s", approval_id="unsafe", run_id="r", tool_call_id="call",
        metadata={"security_request_digest": "sha256:original"})
    emit(journal, "tool_execution_state", tool_call_id="call", executed=True, status="unknown")
    monkeypatch.setattr(human_interaction, "get_human_interaction_service", lambda: service)
    monkeypatch.setattr(webui, "_has_local_worker_activity", lambda sid: False)
    class Request:
        headers = {}
        async def json(self):
            return {"decision": "allow_once"}
    response = asyncio.run(webui.resolve_session_approval("s", "unsafe", Request()))
    assert response.status_code == 409
    assert "状态" in json.loads(response.body)["error"]
    assert service.get("s", "unsafe", kind="approval")["status"] == "pending"


def test_shell_cancellation_reports_output_and_confirmed_stop(tmp_path):
    import agent_tools
    script = tmp_path / "cancel_fixture.py"
    script.write_text("import time\nprint('before cancel',flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    async def scenario():
        rows, received = [], asyncio.Event()
        async def output(stream, text):
            if "before cancel" in text:
                received.set()
        with agent_tools.run_shell_runtime_context(output_sink=output, state_sink=rows.append):
            task = asyncio.create_task(agent_tools.run_shell(f'python "{script}"', timeout_ms=20000))
            await asyncio.wait_for(received.wait(), timeout=10)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return rows
    row = asyncio.run(scenario())[-1]
    assert row["status"] == "interrupted" and row["process_state"] == "stopped"
    assert "before cancel" in row["stdout"] and "before cancel" in row["result"]
    assert row["exit_code"] is not None and row["duration_ms"] > 0


def test_shell_reader_failure_keeps_received_output(tmp_path, monkeypatch):
    import agent_tools
    script = tmp_path / "reader_error_fixture.py"
    script.write_text("import time\nprint('received before error',flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    async def failing_reader(process, publisher):
        raw = await process.stdout.readline()
        publisher.output_bytes["stdout"].extend(raw)
        raise OSError("controlled pipe error")
    monkeypatch.setattr(agent_tools, "_communicate_run_shell_process", failing_reader)
    result = asyncio.run(agent_tools.run_shell(f'python "{script}"', timeout_ms=10000))
    assert "received before error" in result and "controlled pipe error" in result
    assert "Exit code:" in result


def test_continuation_checkpoint_survives_restart(journal, monkeypatch):
    import agent_loop
    state = {}
    register_output_continuation(state, "prefix", tool_drafts=False)
    register_output_continuation(state, "", tool_drafts=True)
    journal.checkpoint_continuation("s", "r", state)
    ExecutionJournal._cache.clear()
    monkeypatch.setattr(agent_loop, "_execution_recovery_snapshot", lambda sid: journal.read("s"))
    monkeypatch.setattr(agent_loop, "_persist_state_with_model_replace", lambda *args: None)
    restarted = {"session_id":"s", "_runtime_v2_run_id":"replacement", "llm_history":[], "work_messages":[]}
    agent_loop._restore_execution_context(restarted)
    assert restarted["_output_length_retries"] == 2
    assert restarted["_output_continuation"] == "prefix"
    assert register_output_continuation(restarted, "tail", tool_drafts=False) == (3, False)


def test_projection_updates_do_not_mutate_published_execution(journal):
    emit(journal, "llm_response_delta", delta="before", delta_seq=1)
    projector = RuntimeProjector()
    before = projector.project(journal.log.read_all("s"))
    emit(journal, "llm_response_delta", delta=" after", delta_seq=2)
    after = projector.project_incremental(before, journal.log.read_all("s")[-1])
    assert list(before["executions"].values())[0]["content"] == "before"
    assert list(after["executions"].values())[0]["content"] == "before after"


def test_compacted_log_recovers_execution_records(journal):
    from runtime_v2.log_compaction import RuntimeV2LogCompactionService
    emit(journal, "llm_response_delta", delta="saved partial", delta_seq=1)
    for index in range(40):
        journal.log.append("s", "model_history_replaced", {"messages":[], "reason":"test " + str(index)})
    journal.read("s")
    result = RuntimeV2LogCompactionService(journal.log.root).compact("s", keep_backup=False)
    assert result["compacted"]
    # The same cached seq now points to a rewritten compacted log.
    assert journal.read("s")["execution_records"][0]["content"] == "saved partial"
    ExecutionJournal._cache.clear()
    assert journal.read("s")["process_group_id"] == "turn:1"


def test_history_truncation_discards_drafts_and_restores_boundary(journal):
    emit(journal, "llm_response_delta", delta="keep")
    end = journal.log.next_seq("s") - 1
    journal.log.append("s", "assistant_final_committed", {"content":"answer"})
    emit(journal, "tool_call_delta", id="later", arguments_delta="discard")
    journal.log.append("s", "visible_range_changed", {"to_seq":end})
    recovery = journal.read("s")
    assert recovery["process_group_id"] == "turn:1" and recovery["last_final_seq"] == 0
    assert len(recovery["execution_records"]) == 1


def test_history_snapshot_acknowledges_non_ui_revision(monkeypatch, journal):
    import json
    import webui
    import runtime_v2
    from types import SimpleNamespace
    journal.log.append("s", "message_rewritten", {"target_seq":1, "content":"edited"})
    manager = SimpleNamespace(repository=SimpleNamespace(sessions_dir=journal.log.root),
                              _resolve_session_path=lambda sid: journal.log.session_dir(sid))
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(runtime_v2, "runtime_v2_primary", lambda: True)
    monkeypatch.setattr(webui, "_runtime_v2_legacy_only_migration_pending", lambda sid: {})
    monkeypatch.setattr(webui, "_session_run_state_fields_light", lambda sid: {"run_active":False})
    response = asyncio.run(webui.get_session_history_snapshot("s", limit=200, turns=5,
                         before_index=None, after_index=None, include_aux=False))
    payload = json.loads(response.body)
    assert payload["ok"]
    assert payload["last_runtime_seq"] >= payload["projection_revision"] > 1
    replay = RuntimeUiProjection(journal.log.root).read_ui_after_runtime_seq("s", after_runtime_seq=payload["last_runtime_seq"])
    assert not replay["requires_reprojection"]


def test_tool_result_record_keeps_change_review_ui_payload(journal):
    """Plugin-owned change-review rows must ride on the execution record.

    The chat-side change review reads ``ui.changes`` from the rendered tool row,
    and that row is built from the execution record (live ``execution_update``
    and replayed history). Dropping the payload here blanks the review pane
    while the details column keeps listing the same changes from history.
    """
    import json
    change = {"path": "workspace/demo.txt", "operation": "create", "snapshot_id": "snap-1",
              "revision": 1, "turn_id": "turn-id", "added": 1, "removed": 0,
              "diff": "--- a/workspace/demo.txt\n+++ b/workspace/demo.txt\n+secret-ui-only\n",
              "effective": True}
    event = emit(journal, "tool_call", tool_call_id="call", tool="write_file",
                 args={"path": "workspace/demo.txt"}, result="ok",
                 execution_status="completed", ui={"changes": [change]})
    record = next(row for row in journal.read("s")["execution_records"]
                  if row.get("execution_id") == event["execution_id"])
    assert record["ui"]["changes"][0]["snapshot_id"] == "snap-1"
    snapshot = RuntimeProjector().project(journal.log.read_all("s"))
    assert "secret-ui-only" not in json.dumps(snapshot["raw_model_messages"], ensure_ascii=False)
    page = RuntimeUiProjection(journal.log.root).read_ui_after_runtime_seq(
        "s", after_runtime_seq=int(event["execution_runtime_seq"]) - 1)
    updates = [item for item in page["events"] if item.get("type") == "execution_update"]
    assert any(item["update"].get("ui", {}).get("changes", [{}])[0].get("snapshot_id") == "snap-1"
               for item in updates)
