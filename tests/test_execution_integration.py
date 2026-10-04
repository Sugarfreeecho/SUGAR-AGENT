from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from execution_services.jobs import ExecutionService
from execution_services import jobs


class FakeManager:
    def __init__(self, root):
        self.repository = SimpleNamespace(sessions_dir=root)
    def _resolve_session_path(self, owner):
        return self.repository.sessions_dir / owner
    def is_interrupt_requested(self, owner, run_id=""):
        return False


def test_restart_preserves_job_record_and_never_replays_command(tmp_path):
    (tmp_path / "owner").mkdir()
    manager = FakeManager(tmp_path)
    async def run():
        first = ExecutionService(manager)
        job = await first.call(first.admit, "owner", "process", "must not replay")
        await first.call(first.append, job, b"retained output")
        # Simulate a stale runtime record, without creating a live process.
        second = ExecutionService(manager)
        try:
            rows = await second.call(second.list_jobs, "owner")
            assert rows[0]["id"] == job.id
            assert rows[0]["status"] == "failed"
            assert "host_restarted" in rows[0]["detail"]
            assert rows[0]["pid"] is None
            result = await second.call(second.output, "owner", job.id)
            assert result["text"] == "retained output"
            assert await second.call(second.notices, "owner") == []
        finally:
            await first.shutdown()
            await second.shutdown()
    asyncio.run(run())


def test_busy_to_idle_wakeup_uses_single_writer_and_system_notice(tmp_path, monkeypatch):
    import agent_loop
    from execution_services.notifications import _continue
    from execution_services.integration import consume_notices
    service = ExecutionService()
    service.manager = SimpleNamespace(is_interrupt_requested=lambda *args: False)
    monkeypatch.setattr(jobs, "_SERVICE", service)
    calls = []
    reservation = {"busy": True}
    fake_webui = SimpleNamespace(
        _reserve_session_chat_start=lambda *args: None if reservation["busy"] else "token",
        _release_session_chat_start=lambda *args: calls.append("released"),
        _session_pending_human_count=lambda owner: 0)
    monkeypatch.setitem(sys.modules, "webui", fake_webui)
    state = {"session_id": "owner", "llm_history": [], "work_messages": []}
    async def continuation(owner, **kwargs):
        calls.append(kwargs["continuation_source"])
        assert kwargs["require_pending_subagents"] is False
        assert await consume_notices(state, lambda *args: None)
        yield {"type": "final"}
    monkeypatch.setattr(agent_loop, "astream_events_continuation", continuation)
    async def run():
        # In-memory unit test, not a production persistence binding.
        service.manager = None
        job = await service.call(service.admit, "owner", "process", "done")
        await service.call(service.settle, job)
        service.manager = SimpleNamespace(is_interrupt_requested=lambda *args: False)
        async def no_persist(*args):
            pass
        monkeypatch.setattr(service, "persist", no_persist)
        await _continue(service, "owner")
        assert await service.call(service.notices, "owner")
        reservation["busy"] = False
        await _continue(service, "owner")
        assert calls.count("tool-jobs") == 1
        assert not await service.call(service.notices, "owner")
        assert all(isinstance(message, agent_loop.SystemMessage) for message in state["llm_history"])
        await _continue(service, "owner")
        assert calls.count("tool-jobs") == 1
        await service.shutdown()
    asyncio.run(run())


def test_authorized_run_shell_promotes_and_preserves_legacy_call(tmp_path, monkeypatch):
    import agent_tools
    from security.runtime import classify_tool, execution_scope
    from security.models import PERMISSION_PRESETS, PermissionMode, SecurityDecision, DecisionOutcome
    from execution_services import shell
    service = ExecutionService()
    monkeypatch.setattr(jobs, "_SERVICE", service)
    monkeypatch.setattr(shell, "jobs_enabled", lambda: True)
    request = classify_tool("run_shell", {"command": "echo test"}, tmp_path)
    context = PERMISSION_PRESETS[PermissionMode.FULL_ACCESS]
    decision = SecurityDecision(DecisionOutcome.ALLOW, "test", "test", "test")
    states = []
    async def run():
        command = "sleep 0.4; echo finished" if agent_tools._windows_bash_executable() else "Start-Sleep -Milliseconds 400; Write-Output finished"
        if os.name != "nt":
            command = "sleep 0.4; echo finished"
        try:
            with agent_tools.run_shell_runtime_context(state_sink=states.append), agent_tools.tool_work_dir_override(tmp_path), execution_scope(session_id="owner",
                context=context, request=request, decision=decision, workspace=tmp_path):
                text = await agent_tools.run_shell(command, timeout_ms=50, login=False)
                assert "promoted to background job" in text
                assert states[-1]["executed"] and states[-1]["process_state"] == "running"
                rows = await service.call(service.list_jobs, "owner")
                result = await service.call(service.output, "owner", rows[0]["id"], True, 5000)
                assert result["job"]["exit_code"] == 0
                assert "finished" in result["text"]
                text = await agent_tools.run_shell("echo managed-complete", login=False)
                assert "managed-complete" in text
                assert states[-1]["executed"] and states[-1]["process_state"] == "stopped"
                assert states[-1]["exit_code"] == 0
            text = await agent_tools.run_shell("echo legacy", workdir=str(tmp_path), login=False)
            assert "legacy" in text and "Exit code: 0" in text
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_terminal_input_retains_destructive_checks_and_fresh_approval(tmp_path):
    from security.runtime import classify_tool
    from security.policy import PolicyEngine
    from security.models import PERMISSION_PRESETS, PermissionMode, DecisionOutcome
    engine = PolicyEngine(tmp_path)
    request = classify_tool("terminal_send", {"sessionId": "unknown", "text": "echo harmless"}, tmp_path)
    decision = engine.decide(request, PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL])
    assert decision.outcome == DecisionOutcome.ASK
    assert decision.constraints.get("one_time_only")
    request = classify_tool("terminal_send", {"sessionId": "unknown", "text": "shutdown /s /t 0"}, tmp_path)
    decision = engine.decide(request, PERMISSION_PRESETS[PermissionMode.FULL_ACCESS])
    assert decision.outcome == DecisionOutcome.ASK


def test_restart_preserves_absolute_output_and_model_cursor_after_log_roll(tmp_path, monkeypatch):
    (tmp_path / "owner").mkdir()
    monkeypatch.setattr(jobs, "LOG_LIMIT", 32)
    async def run():
        first, second = ExecutionService(FakeManager(tmp_path)), ExecutionService(FakeManager(tmp_path))
        try:
            job = await first.call(first.admit, "owner", "process", "rolling")
            await first.call(first.append, job, b"a" * 40)
            consumed = await first.call(first.output, "owner", job.id)
            assert consumed["offset"] == 40
            await first.call(first.append, job, b"tail")
            rows = await second.call(second.list_jobs, "owner")
            assert rows[0]["outputOffset"] == 44
            assert rows[0]["outputBegin"] == 24
            result = await second.call(second.output, "owner", job.id)
            assert result["text"] == "tail" and result["offset"] == 44
            ui = await second.call(second.output, "owner", job.id, offset=0)
            assert ui["truncated"] and ui["text"].endswith("tail")
        finally:
            await first.shutdown()
            await second.shutdown()
    asyncio.run(run())


def test_foreground_quota_falls_back_and_explicit_background_fails(tmp_path, monkeypatch):
    import agent_tools
    from security.runtime import classify_tool, execution_scope
    from security.models import PERMISSION_PRESETS, PermissionMode, SecurityDecision, DecisionOutcome
    from execution_services import shell
    service = ExecutionService(max_concurrent=1)
    monkeypatch.setattr(jobs, "_SERVICE", service)
    monkeypatch.setattr(shell, "jobs_enabled", lambda: True)
    request = classify_tool("run_shell", {"command": "echo fallback"}, tmp_path)
    async def run():
        try:
            await service.call(service.admit, "owner", "process", "occupying quota")
            with agent_tools.tool_work_dir_override(tmp_path), execution_scope(session_id="owner",
                context=PERMISSION_PRESETS[PermissionMode.FULL_ACCESS], request=request,
                decision=SecurityDecision(DecisionOutcome.ALLOW, "test", "test", "test"), workspace=tmp_path):
                result = await agent_tools.run_shell("echo fallback", login=False)
                assert "fallback" in result and "Exit code: 0" in result
                result = await agent_tools.run_shell("echo background", login=False, run_in_background=True)
                assert "limit reached" in result
            assert len(await service.call(service.list_jobs, "owner")) == 1
        finally:
            await service.shutdown()
    asyncio.run(run())
