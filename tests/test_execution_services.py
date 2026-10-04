from __future__ import annotations

import asyncio
import concurrent.futures
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from execution_services.jobs import ExecutionService, OutputBuffer
from execution_services.terminals import terminal_manager


def test_output_consumption_and_ui_cursor_are_independent():
    output = OutputBuffer(5)
    output.append(b"abcdef")
    assert output.read_at(0) == (b"bcdef", 6, True)
    assert output.cursor == 0
    assert output.read() == (b"bcdef", True)
    output.append(b"gh")
    assert output.read() == (b"gh", False)


def test_jobs_survive_caller_loop_and_enforce_owner(tmp_path):
    service = ExecutionService()
    spec = {"argv": [sys.executable, "-c", "import time;print('first',flush=True);time.sleep(.4);print('last')"],
            "cwd": str(tmp_path), "env": dict(os.environ), "spawn_kw": {}, "label": "test process"}
    identifier = asyncio.run(service.call(service.spawn_process, "owner", spec, visible=True))
    async def verify():
        with pytest.raises(ValueError, match="not found"):
            await service.call(service.output, "other-owner", identifier)
        result = await service.call(service.output, "owner", identifier, True, 5000, offset=0)
        assert result["job"]["status"] == "completed"
        assert result["job"]["exit_code"] == 0
        assert "first" in result["text"] and "last" in result["text"]
        consumed = await service.call(service.output, "owner", identifier)
        assert "first" in consumed["text"]
        assert (await service.call(service.output, "owner", identifier))["text"] == ""
        await service.shutdown()
    asyncio.run(verify())


def test_wait_timeout_does_not_kill_and_stop_suppresses_wake(tmp_path):
    async def verify():
        service = ExecutionService(max_concurrent=1)
        spec = {"argv": [sys.executable, "-c", "import time;time.sleep(20)"],
                "cwd": str(tmp_path), "env": dict(os.environ), "label": "sleeper"}
        try:
            identifier = await service.call(service.spawn_process, "owner", spec, visible=True)
            result = await service.call(service.output, "owner", identifier, True, 10)
            assert result["job"]["status"] == "running"
            with pytest.raises(RuntimeError, match="limit"):
                await service.call(service.spawn_process, "owner", spec, visible=True)
            await service.call(service.stop_owner, "owner")
            result = await service.call(service.output, "owner", identifier, True, 5000)
            assert result["job"]["status"] == "killed"
            assert not await service.call(service.notices, "owner")
            with pytest.raises(RuntimeError, match="stopped"):
                await service.call(service.admit, "owner", "process", "after stop")
            await service.call(service.resume_owner, "owner")
        finally:
            await service.shutdown()
    asyncio.run(verify())


def test_persistent_pty_and_user_terminal_isolation(tmp_path):
    pytest.importorskip("pyte")
    pytest.importorskip("winpty" if os.name == "nt" else "ptyprocess")
    async def verify():
        service = ExecutionService()
        terminals = terminal_manager(service)
        try:
            opened = await service.call(terminals.open, "owner", cwd=str(tmp_path))
            identifier = opened["id"]
            command = "$env:DSH_TEST='kept'" if os.name == "nt" else "export DSH_TEST=kept"
            await service.call(terminals.send, "owner", identifier, command)
            command = "Write-Output $env:DSH_TEST" if os.name == "nt" else "printf '%s\\n' \"$DSH_TEST\""
            result = await service.call(terminals.send, "owner", identifier, command)
            assert "kept" in result["viewport"]
            # Prompt detection races with ConPTY echo timing; both settlement
            # reasons are legitimate under the send-wait contract.
            assert result["waitReason"] in ("stdin_read", "inferred_idle")
            command = "Write-Output ('background-' + 'start'); Start-Sleep -Seconds 20" if os.name == "nt" else "printf 'background-%s\\n' start; sleep 20"
            started = await service.call(terminals.send, "owner", identifier, command, background=True)
            for _ in range(100):
                output = await service.call(service.output, "owner", started["jobId"], offset=0)
                if "background-start" in output["text"]:
                    break
                await asyncio.sleep(.05)
            assert "background-start" in output["text"], output
            assert output["job"]["status"] == "running"
            await service.call(service.kill, "owner", started["jobId"])
            killed = await service.call(service.output, "owner", started["jobId"], True, 5000)
            assert killed["job"]["status"] == "killed"
            assert terminals.sessions[identifier].status == "running"
            command = "Write-Output 'after-cancel'" if os.name == "nt" else "printf 'after-cancel\\n'"
            finished = await service.call(terminals.send, "owner", identifier, command, background=True)
            collected = await service.call(service.output, "owner", finished["jobId"], True, 5000)
            assert collected["result"]["waitReason"] in ("stdin_read", "inferred_idle")
            # winpty can deliver the cancellation Ctrl+C late (or queue it after
            # the interrupted command), and the stream / viewport / screen feed
            # settle on different edges; poll the terminal read until the
            # command output shows up in any of them.
            payload = (collected.get("text") or "") + "\n" + ((collected.get("result") or {}).get("viewport") or "")
            for _ in range(140):
                if "after-cancel" in payload:
                    break
                await asyncio.sleep(.25)
                readback = await service.call(terminals.read, "owner", identifier)
                payload += "\n" + (readback.get("text") or "")
            assert "after-cancel" in payload, payload[-400:]
            assert (await service.call(service.output, "owner", finished["jobId"]))["result"] is None
            with pytest.raises(ValueError, match="not found"):
                await service.call(terminals.read, "other", identifier)
            user = await service.call(terminals.open, "owner", cwd=str(tmp_path), actor="user")
            with pytest.raises(ValueError, match="not found"):
                await service.call(terminals.send, "owner", user["id"], "echo forbidden")
            await service.call(terminals.stream, "owner", user["id"], 0, "connection-1", claim=True)
            await service.call(terminals.stream, "owner", user["id"], 0, "connection-2", claim=True)
            with pytest.raises(PermissionError, match="control"):
                await service.call(terminals.input, "owner", user["id"], "x", "connection-1")
            await service.call(service.stop_owner, "owner")
            assert terminals.sessions[user["id"]].status == "running"
        finally:
            await service.shutdown()
    asyncio.run(verify())


def test_blocking_job_readers_leave_management_workers_available(tmp_path):
    async def run():
        service = ExecutionService()
        async def constrain_pool():
            asyncio.get_running_loop().set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=1))
        try:
            await service.call(constrain_pool)
            identifier = await service.call(service.spawn_process, "owner", {
                "argv": [sys.executable, "-c", "import time;time.sleep(20)"],
                "cwd": str(tmp_path), "env": dict(os.environ), "label": "sleeper"}, visible=True)
            await asyncio.sleep(.1)
            await asyncio.wait_for(service.call(service.kill, "owner", identifier), 5)
            result = await service.call(service.output, "owner", identifier, True, 5000)
            assert result["job"]["status"] == "killed"
        finally:
            await service.shutdown()
    asyncio.run(run())


def test_deletion_during_pty_startup_waits_for_partial_resource_cleanup(tmp_path, monkeypatch):
    backend_module = pytest.importorskip("winpty" if os.name == "nt" else "ptyprocess")
    creating, release = threading.Event(), threading.Event()
    closed = []
    backend = SimpleNamespace(close=lambda force: closed.append(force))
    def spawn(*args, **kwargs):
        creating.set()
        assert release.wait(5)
        return backend
    monkeypatch.setattr(backend_module.PtyProcess if os.name == "nt" else backend_module.PtyProcessUnicode, "spawn", spawn)
    async def run():
        service = ExecutionService()
        tm = terminal_manager(service)
        try:
            opening = asyncio.create_task(service.call(tm.open, "owner", cwd=str(tmp_path), actor="user"))
            assert await asyncio.to_thread(creating.wait, 3)
            stopping = asyncio.create_task(service.call(service.stop_owner, "owner", close_terminals=True))
            await asyncio.sleep(.1)
            assert not stopping.done()
            release.set()
            await asyncio.wait_for(stopping, 5)
            with pytest.raises(asyncio.CancelledError):
                await opening
            assert closed == [True] and tm.sessions == {}
            with pytest.raises(RuntimeError, match="closing"):
                await service.call(tm.open, "owner", cwd=str(tmp_path), actor="user")
        finally:
            release.set()
            await service.shutdown()
    asyncio.run(run())
