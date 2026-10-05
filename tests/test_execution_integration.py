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


def test_terminal_classification_follows_live_directory(tmp_path, monkeypatch):
    from execution_services.terminals import terminal_manager
    from security.runtime import classify_tool
    workspace, outside = tmp_path / "workspace", tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    service = ExecutionService()
    tm = terminal_manager(service)
    monkeypatch.setattr(jobs, "_SERVICE", service)

    async def run():
        try:
            opened = await service.call(tm.open, "owner", cwd=str(workspace))
            identifier = opened["id"]
            path = str(outside).replace("'", "''" if os.name == "nt" else "'\"'\"'")
            command = f"Set-Location -LiteralPath '{path}'" if os.name == "nt" else f"cd '{path}'"
            await service.call(tm.send, "owner", identifier, command)
            terminal = tm.sessions[identifier]
            observed = terminal.working_directory()
            assert observed is not None
            assert Path(observed).resolve() == outside.resolve()
            text = "Set-Content -LiteralPath './result.txt' -Value ok" if os.name == "nt" else "echo ok > ./result.txt"
            request = classify_tool("terminal_send", {"sessionId": identifier, "text": text}, workspace)
            assert request.metadata["external_workspace"]
            assert Path(request.metadata["effective_workdir"]).resolve() == outside.resolve()
            assert not request.metadata.get("terminal_cwd_unknown")

            # Once input is admitted, its last prompt no longer establishes
            # where a still-running shell/REPL will interpret the next input.
            terminal.cwd_ready = False
            request = classify_tool("terminal_send", {"sessionId": identifier, "text": text}, workspace)
            assert request.metadata["terminal_cwd_unknown"]
            assert request.metadata["external_workspace"]
            assert not request.metadata["workspace_delete"]
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_create_session_permission_downgrade_stops_existing_jobs(monkeypatch):
    import webui
    import security
    service = ExecutionService()
    monkeypatch.setattr(jobs, "_SERVICE", service)
    mode = {"value": "full_access"}
    manager = SimpleNamespace(
        get_or_create_session=lambda *a, **kw: ("new", [], [], [], "", {}),
        list_sessions=lambda **kw: [{"id": "existing"}, {"id": "new"}],
    )
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "_invalidate_sessions_state_cache", lambda: 1)
    monkeypatch.setattr(security, "set_session_permission_mode", lambda sid, value: mode.update(value=value))
    monkeypatch.setattr(security, "security_status_for_session", lambda sid: {"mode": mode["value"]})
    events = []

    async def publish(sid, event):
        events.append((sid, event))

    async def body():
        return {"permission_mode": "ask_for_approval"}

    monkeypatch.setattr(webui, "publish_session_event", publish)

    async def run():
        try:
            job = await service.call(service.admit, "existing", "process", "test", permission_mode="full_access")

            async def cancel():
                await service.settle(job, "killed")

            job.cancel = cancel
            response = await webui.create_session(SimpleNamespace(json=body))
            assert response.status_code == 200
            assert mode["value"] == "ask_for_approval"
            assert job.status == "killed"
            assert not await service.call(service.notices, "existing")
            assert {sid for sid, _ in events} == {"existing", "new"}
        finally:
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.parametrize("old_mode,new_mode,tightened", [
    ("full_access", "ask_for_approval", True),
    ("full_access", "approve_for_me", True),
    ("ask_for_approval", "full_access", False),
    ("approve_for_me", "full_access", False),
    ("ask_for_approval", "approve_for_me", False),
    ("approve_for_me", "ask_for_approval", False),
    ("full_access", "full_access", False),
])
def test_permission_changes_only_cancel_when_execution_boundary_tightens(old_mode, new_mode, tightened, monkeypatch):
    from execution_services.integration import permissions_changed
    service = ExecutionService()
    monkeypatch.setattr(jobs, "_SERVICE", service)
    closed = []
    model = SimpleNamespace(id="model", owner="owner", actor="model", status="running", permission_mode=old_mode)
    user = SimpleNamespace(id="user", owner="owner", actor="user", status="running", permission_mode="")

    async def close(owner, identifier):
        closed.append(identifier)
        model.status = "closed"

    async def stop_owner(owner, *, close=False):
        pass

    service.terminals = SimpleNamespace(sessions={"model": model, "user": user}, close=close, stop_owner=stop_owner)

    async def run():
        try:
            job = await service.call(service.admit, "owner", "process", "test", permission_mode=old_mode)

            async def cancel():
                await service.settle(job, "killed")

            job.cancel = cancel
            await permissions_changed(new_mode)
            assert closed == (["model"] if tightened else [])
            assert job.status == ("killed" if tightened else "running")
            assert user.status == "running"
            if not tightened:
                assert model.permission_mode == new_mode
                # Background PTY sends reuse this stamp in their admission.
                assert model.status == "running"
        finally:
            service.terminals = None
            await service.shutdown()
    asyncio.run(run())


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
