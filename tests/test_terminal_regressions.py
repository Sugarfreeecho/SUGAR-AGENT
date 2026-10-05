"""Regressions from the background/PTY feedback session, including real interruption."""
import asyncio
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from execution_services.jobs import ExecutionService
from execution_services.terminals import TerminalSession, terminal_manager


@pytest.mark.parametrize("failure", [None, OSError("broken transport")])
def test_no_data_read_does_not_close_live_shell(tmp_path, failure, monkeypatch):
    import pyte
    backend = SimpleNamespace(pid=0, alive=True, closed=[], exitstatus=0)
    values = iter(["", "", "still alive\r\n"])
    def read(size):
        try:
            return next(values)
        except StopIteration:
            if failure:
                raise failure
            backend.alive = False
            raise EOFError()
    backend.read = read
    backend.isalive = lambda: backend.alive
    backend.close = lambda force: backend.closed.append(force)
    cleanup = []
    monkeypatch.setattr("execution_services.terminals.terminate_process", lambda process, created: cleanup.append(process))
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        screen = pyte.HistoryScreen(160, 40)
        session = TerminalSession("fake", "owner", "shell", str(tmp_path), "model",
            backend, "pwsh", screen, pyte.Stream(screen))
        await tm._pump(session)
        assert "still alive" in tm.viewport(session)
        assert session.status == "closed"
        assert session.detail == "shell exited" if failure is None else "terminal read failed" in session.detail
        assert backend.closed == [True]
        assert cleanup == ([] if failure is None else [backend])
    asyncio.run(run())


@pytest.mark.parametrize("actor", ["model", "user"])
def test_model_uses_dsh_plain_environment_user_keeps_color(tmp_path, monkeypatch, actor):
    backend_module = pytest.importorskip("winpty" if os.name == "nt" else "ptyprocess")
    captured = {}
    def spawn(argv, **kw):
        captured.update(argv=argv, **kw)
        def eof(size):
            raise EOFError()
        return SimpleNamespace(pid=0, read=eof, close=lambda force: None,
            isalive=lambda: False, exitstatus=0)
    monkeypatch.setattr(backend_module.PtyProcess if os.name == "nt" else backend_module.PtyProcessUnicode, "spawn", spawn)
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        try:
            await service.call(tm.open, "owner", cwd=str(tmp_path), actor=actor)
            env = captured["env"]
            assert env["TERM"] == ("dumb" if actor == "model" else "xterm-256color")
            if actor == "model":
                assert env["NO_COLOR"] == "1" and env["PAGER"] == "cat" and env["GIT_PAGER"] == "cat"
                assert "COLORTERM" not in env
        finally:
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.parametrize("drop_ctrl_c", [False, True])
def test_sigint_interrupts_external_command_and_retains_same_shell(tmp_path, monkeypatch, drop_ctrl_c):
    if drop_ctrl_c and os.name != "nt":
        pytest.skip("Windows forced fallback")
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        child_file = tmp_path / "child.py"
        child_file.write_text("import time\nprint('external-'+'began', flush=True)\ntime.sleep(20)\nprint('external-'+'finished', flush=True)\n")
        try:
            opened = await service.call(tm.open, "owner", cwd=str(tmp_path))
            tid = opened["id"]
            with pytest.raises(ValueError, match="not found"):
                await service.call(tm.signal, "other-owner", tid, "SIGINT")
            if os.name == "nt":
                original_created = tm.sessions[tid].process_created
                tm.sessions[tid].process_created += 1
                try:
                    with pytest.raises(RuntimeError, match="identity changed"):
                        await service.call(tm.signal, "owner", tid, "SIGINT")
                finally:
                    tm.sessions[tid].process_created = original_created
            child = "& '" + sys.executable.replace("'", "''") + "' '" + str(child_file).replace("'", "''") + "'" if os.name == "nt" else f"'{sys.executable}' '{child_file}'"
            started = await service.call(tm.send, "owner", tid, child, background=True)
            for _ in range(100):
                read = await service.call(tm.read, "owner", tid)
                if "external-began" in read["text"]:
                    break
                await asyncio.sleep(.05)
            assert "external-began" in read["text"]
            if drop_ctrl_c:
                backend = tm.sessions[tid].backend
                write = backend.write
                monkeypatch.setattr(backend, "write", lambda value: None if value == "\x03" else write(value))
            began = time.monotonic()
            receipt = await service.call(tm.signal, "owner", tid, "SIGINT")
            assert receipt["delivered"] and receipt["interruptVerified"], receipt
            if os.name == "nt":
                assert receipt["method"] in {"pty_ctrl_c", "pty_ctrl_c_then_terminate_owned_children"}
                if receipt["method"].endswith("terminate_owned_children"):
                    assert receipt["forced"] and receipt["fallback"]["shellPreserved"]
                if drop_ctrl_c:
                    assert receipt["method"] == "pty_ctrl_c_then_terminate_owned_children" and receipt["forced"]
            collected = await service.call(service.output, "owner", started["jobId"], True, 5000)
            assert collected["result"]["waitReason"] == "stdin_read", collected
            command = "Write-Output ('reused-'+'shell')" if os.name == "nt" else "printf 'reused-%s\\n' shell"
            after = await service.call(tm.send, "owner", tid, command)
            assert after["waitReason"] == "stdin_read" and "reused-shell" in after["viewport"]
            assert "external-finished" not in after["viewport"]
            assert tm.sessions[tid].pid == opened["pid"] and tm.sessions[tid].status == "running"
            assert time.monotonic() - began < 8
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_background_output_renders_repaint_once(tmp_path, monkeypatch):
    import pyte
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        screen = pyte.HistoryScreen(160, 40)
        session = TerminalSession("terminal", "owner", "shell", str(tmp_path), "model",
            SimpleNamespace(), "pwsh", screen, pyte.Stream(screen))
        tm.sessions[session.id] = session
        async def send(session, text, submit):
            # ConPTY/PSReadLine paints the same line several times. Raw draw
            # callbacks used to concatenate all of these into SStStart-Sleep.
            session.output.append(b"S\rSt\rStart-Sleep\r\nfinal output\r\n")
            return {"waitReason": "stdin_read", "command_state": "shell_ready"}
        monkeypatch.setattr(tm, "_send", send)
        try:
            started = await service.call(tm.send, "owner", session.id, "unused", background=True)
            result = await service.call(service.output, "owner", started["jobId"], True, 2000)
            assert result["text"] == "Start-Sleep\nfinal output\n"
        finally:
            session.status = "closed"
            await service.shutdown()
    asyncio.run(run())


def test_signal_delivery_without_readiness_is_not_confirmed(tmp_path, monkeypatch):
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        session = TerminalSession("terminal", "owner", "shell", str(tmp_path), "model",
            SimpleNamespace(write=lambda value: None), "pwsh", None, None,
            pid=123, process_created=1)
        tm.sessions[session.id] = session
        if os.name == "nt":
            monkeypatch.setattr(tm, "_windows_shell", lambda session: SimpleNamespace(children=lambda **kw: []))
        monkeypatch.setattr(tm, "_foreground_ready", lambda session: True)
        try:
            receipt = await service.call(tm.signal, "owner", session.id, "SIGINT")
            assert receipt["delivered"] is True
            assert receipt["interruptVerified"] is False and receipt["verification"] == "not_observed"
            if os.name == "nt":
                assert receipt["reason"] == "no_owned_child_processes" and receipt["shellPreserved"]
        finally:
            session.status = "closed"
            await service.shutdown()
    asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows in-process command boundary")
def test_inprocess_sigint_does_not_claim_success_or_kill_shell(tmp_path):
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        try:
            opened = await service.call(tm.open, "owner", cwd=str(tmp_path))
            tid = opened["id"]
            await service.call(tm.send, "owner", tid,
                "Write-Output ('inprocess-'+'began'); Start-Sleep -Seconds 10; Write-Output ('inprocess-'+'finished')", background=True)
            for _ in range(100):
                read = await service.call(tm.read, "owner", tid)
                if "inprocess-began" in read["text"]:
                    break
                await asyncio.sleep(.05)
            assert "inprocess-began" in read["text"]
            receipt = await service.call(tm.signal, "owner", tid, "SIGINT")
            assert tm.sessions[tid].pid == opened["pid"] and tm.sessions[tid].status == "running"
            if not receipt["interruptVerified"]:
                assert receipt["reason"] == "no_owned_child_processes" and receipt["shellPreserved"]
                assert "terminal_close" in receipt["next_action"]
                assert "inprocess-finished" not in (await service.call(tm.read, "owner", tid))["text"]
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_background_observation_is_not_command_exit_and_late_output_is_readable(tmp_path):
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        try:
            opened = await service.call(tm.open, "owner", cwd=str(tmp_path))
            tid = opened["id"]
            command = "Start-Sleep -Seconds 5; Write-Output ('late-'+'output')" if os.name == "nt" else "sleep 5; printf 'late-%s\\n' output"
            started = await service.call(tm.send, "owner", tid, command, background=True)
            collected = await service.call(service.output, "owner", started["jobId"], True, 4500, offset=0)
            assert collected["job"]["status"] == "completed", collected
            assert collected["job"]["completion_scope"] == "terminal_send"
            assert collected["job"]["command_state"] == "unknown" and collected["job"]["wait_reason"] == "inferred_idle"
            assert collected["job"]["terminal_id"] == tid
            assert "late-output" not in collected["text"]
            notices = await service.call(service.notices, "owner")
            assert "does not establish command success or exit" in notices[0]["text"]
            for _ in range(100):
                read = await service.call(tm.read, "owner", tid)
                if "late-output" in read["text"]:
                    break
                await asyncio.sleep(.05)
            assert "late-output" in read["text"]
            consumed = await service.call(service.output, "owner", started["jobId"])
            again = await service.call(service.output, "owner", started["jobId"])
            assert consumed["result"] and again["result"] is None
            assert again["job"]["command_state"] == "unknown"
        finally:
            await service.shutdown()
    asyncio.run(run())
