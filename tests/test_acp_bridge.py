import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import acp
from acp import schema as s
from acp_bridge.server import SugarACPAgent
from acp_bridge.events import EventProjector
from acp_bridge.client import AgentTarget, DelegationClient, parse_targets, run_target
from acp_bridge.mcp import resolve_servers


class Backend:
    def __init__(self, cwd):
        self.cwd = str(cwd)
        self.rows = {}
        self.calls = []
        self.attached = set()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.block = False
        self.failed = False

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/api/model_profiles":
            return {"profiles": [{"id": "model-a", "name": "A"}, {"id": "model-b", "name": "B"}]}
        if path == "/sessions" and method == "POST":
            sid = "session-" + str(len(self.rows) + 1)
            self.rows[sid] = {"id": sid, "work_dir": kwargs["json"]["work_dir"], "name": sid, "profile_id": "model-a"}
            return {"session_id": sid}
        if path == "/sessions":
            return list(self.rows.values())
        sid = path.split("/")[2]
        if path.endswith("/model_profile") and method == "GET":
            return {"profile_id": self.rows[sid].get("profile_id", "model-a"), "reasoning_effort": ""}
        if path.endswith("/model_profile"):
            self.rows[sid]["profile_id"] = kwargs["json"]["profile_id"]
            return {"ok": True}
        if path.endswith("/reasoning_effort"):
            return {"ok": True}
        if method == "DELETE":
            del self.rows[sid]
            return {"ok": True}
        return self.rows[sid]

    async def attach(self, sid, servers):
        self.attached.add(sid)

    async def detach(self, sid):
        self.attached.discard(sid)

    async def interrupt(self, sid, run_id):
        self.release.set()

    async def resolve(self, sid, approval_id, allow):
        self.calls.append(("approval", approval_id, allow))

    async def events(self, sid, run_id, message):
        self.started.set()
        if self.block:
            await self.release.wait()
        if self.failed:
            yield {"type": "error", "content": "private internal detail"}
            return
        yield {"type": "llm_reasoning", "content": "reason"}
        yield {"type": "tool_pending", "tool_call_id": "tool-1", "tool": "read_file", "args": {}}
        yield {"type": "tool_call", "tool_call_id": "tool-1", "tool": "read_file", "result": "result"}
        yield {"type": "llm_response", "content": "answer"}
        yield {"type": "final", "content": "answer"}
        yield {"type": "run_finished"}


class Connection:
    def __init__(self):
        self.updates = []
        self.permissions = []

    async def session_update(self, sid, update):
        self.updates.append(update)

    async def request_permission(self, **kwargs):
        self.permissions.append(kwargs)
        return s.RequestPermissionResponse(outcome=s.AllowedOutcome(outcome="selected", option_id="allow-once"))


def test_dsh_capabilities_and_persistent_resume_without_replay(tmp_path):
    async def scenario():
        backend, connection = Backend(tmp_path), Connection()
        agent = SugarACPAgent(backend)
        agent.on_connect(connection)
        init = await agent.initialize(1)
        wire = init.model_dump(by_alias=True, exclude_none=True)
        assert wire["protocolVersion"] == 1
        assert set(wire["agentCapabilities"]["sessionCapabilities"]) >= {"list", "resume", "close"}
        assert wire["agentCapabilities"]["mcpCapabilities"]["http"] is True
        assert wire["agentCapabilities"]["loadSession"] is False
        created = await agent.new_session(str(tmp_path))
        assert {o.id for o in created.config_options} == {"model", "reasoning_effort"}
        sid = created.session_id
        await agent.close_session(sid)
        assert sid in backend.rows and sid not in backend.attached
        await agent.resume_session(sid, str(tmp_path))
        assert connection.updates == []
        listed = await agent.list_sessions(cwd=str(tmp_path))
        assert listed.sessions[0].session_id == sid
        with pytest.raises(KeyError):
            await agent.resume_session("missing", str(tmp_path))
        assert len(backend.rows) == 1
        await agent.shutdown()
    asyncio.run(scenario())


def test_prompt_order_deduplication_and_failure(tmp_path):
    async def scenario():
        backend, connection = Backend(tmp_path), Connection()
        agent = SugarACPAgent(backend)
        agent.on_connect(connection)
        sid = (await agent.new_session(str(tmp_path))).session_id
        response = await agent.prompt(sid, [acp.text_block("hello")])
        assert response.stop_reason == "end_turn"
        assert [u.session_update for u in connection.updates] == [
            "agent_thought_chunk", "tool_call", "tool_call_update", "agent_message_chunk"]
        backend.failed = True
        with pytest.raises(acp.RequestError) as error:
            await agent.prompt(sid, [acp.text_block("again")])
        assert "private" not in str(error.value)
        await agent.shutdown()
    asyncio.run(scenario())


def test_same_session_prompt_slot_cancel_and_next_turn_config(tmp_path):
    async def scenario():
        backend = Backend(tmp_path)
        backend.block = True
        agent = SugarACPAgent(backend)
        agent.on_connect(Connection())
        sid = (await agent.new_session(str(tmp_path))).session_id
        running = asyncio.create_task(agent.prompt(sid, [acp.text_block("one")]))
        await backend.started.wait()
        with pytest.raises(acp.RequestError):
            await agent.prompt(sid, [acp.text_block("two")])
        response = await agent.set_config_option(sid, "model", "model-b")
        assert next(option for option in response.config_options if option.id == "model").current_value == "model-b"
        assert backend.rows[sid]["profile_id"] == "model-a"
        await agent.cancel(sid)
        assert (await running).stop_reason == "cancelled"
        assert backend.rows[sid]["profile_id"] == "model-b"
        await agent.close_session(sid)
        assert not backend.attached
    asyncio.run(scenario())


def test_permission_only_one_shot_and_unknown_option_rejected(tmp_path):
    async def scenario():
        backend, connection = Backend(tmp_path), Connection()
        agent = SugarACPAgent(backend)
        agent.on_connect(connection)
        sid = (await agent.new_session(str(tmp_path))).session_id
        await agent._permission(sid, agent.sessions[sid], {"approval_id": "approval-1"})
        assert [option.kind for option in connection.permissions[0]["options"]] == ["allow_once", "reject_once"]
        assert ("approval", "approval-1", True) in backend.calls
        with pytest.raises(acp.RequestError):
            await agent.set_config_option(sid, "anything", "accepted?")
        await agent.shutdown()
    asyncio.run(scenario())


def test_failed_new_session_rolls_back(tmp_path):
    async def scenario():
        backend = Backend(tmp_path)
        async def fail(*args):
            raise RuntimeError("MCP unavailable")
        backend.attach = fail
        agent = SugarACPAgent(backend)
        with pytest.raises(RuntimeError):
            await agent.new_session(str(tmp_path))
        assert not backend.rows and not agent.sessions
    asyncio.run(scenario())


def test_cancellation_releases_unanswered_permission(tmp_path):
    async def scenario():
        backend = Backend(tmp_path)
        requested = asyncio.Event()
        class Unanswered(Connection):
            async def request_permission(self, **kwargs):
                requested.set()
                await asyncio.Event().wait()
        agent = SugarACPAgent(backend)
        agent.on_connect(Unanswered())
        sid = (await agent.new_session(str(tmp_path))).session_id
        record = agent.sessions[sid]
        record.task = asyncio.current_task()
        permission = asyncio.create_task(agent._permission(sid, record, {"approval_id": "pending"}))
        await requested.wait()
        await agent.cancel(sid)
        await asyncio.wait_for(permission, 1)
        assert not any(row[0] == "approval" for row in backend.calls)
        record.task = None
        await agent.shutdown()
    asyncio.run(scenario())


def test_broken_client_delivery_interrupts_owned_native_run(tmp_path):
    async def scenario():
        backend = Backend(tmp_path)
        class Disconnected(Connection):
            async def session_update(self, sid, update):
                raise ConnectionError("transport closed")
        agent = SugarACPAgent(backend)
        agent.on_connect(Disconnected())
        sid = (await agent.new_session(str(tmp_path))).session_id
        with pytest.raises(acp.RequestError):
            await agent.prompt(sid, [acp.text_block("task")])
        assert backend.release.is_set()
        await agent.shutdown()
    asyncio.run(scenario())


def test_mcp_declarations_match_dsh_transports_and_validate_before_connect(tmp_path):
    config = resolve_servers([{"name": "stdio", "command": sys.executable, "args": [], "env": []},
                             {"name": "http", "type": "http", "url": "https://example.com/mcp", "headers": []}], str(tmp_path))
    assert [entry[1]["transport"] for entry in config] == ["stdio", "streamable-http"]
    for servers in ([{"name": "bad", "command": "relative", "args": [], "env": []}],
                    [{"name": "bad", "type": "sse", "url": "https://example.com/sse", "headers": []}],
                    [{"name": "bad", "command": sys.executable, "args": [], "env": [
                        {"name": "TOKEN", "value": "a"}, {"name": "TOKEN", "value": "b"}]}]):
        with pytest.raises(ValueError):
            resolve_servers(servers, str(tmp_path))


def target(mode="echo", *args, timeout=15, permission="reject", refs=()):
    return AgentTarget("test", sys.executable,
                       (str(ROOT / "tests/fixtures/acp_fake_agent.py"), mode, *map(str, args)), refs, permission, timeout)


def test_real_stdio_client_echo_and_permission_scope(tmp_path):
    async def scenario():
        result = await run_target(target(), "hello", str(tmp_path))
        assert result["output"] == "echo:hello"
        assert "private reasoning" not in result["output"]
        assert result["stop_reason"] == "end_turn"
        rejected = await run_target(target("permission"), "task", str(tmp_path))
        assert rejected["output"] == "denied"
        allowed = await run_target(target("permission", permission="allow"), "task", str(tmp_path))
        assert allowed["output"] == "once"
    asyncio.run(scenario())


def test_real_stdio_cancellation_sends_cancel_and_reaps_process(tmp_path):
    import psutil
    pid_file, cancel_file = tmp_path / "pid", tmp_path / "cancel"
    async def scenario():
        task = asyncio.create_task(run_target(target("wait", pid_file, cancel_file, timeout=30), "wait", str(tmp_path)))
        async def ready():
            while not Path(str(pid_file) + ".ready").exists():
                if task.done():
                    await task
                await asyncio.sleep(0.03)
        await asyncio.wait_for(ready(), 15)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert cancel_file.read_text() == "cancelled"
    assert not psutil.pid_exists(int(pid_file.read_text()))


def test_real_stdio_startup_timeout_is_bounded(tmp_path):
    async def scenario():
        with pytest.raises(asyncio.TimeoutError):
            await run_target(target("wait", timeout=0.01), "wait", str(tmp_path))
    asyncio.run(scenario())


def test_real_stdio_environment_credentials_are_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("ACP_TEST_SECRET", "explicit")
    monkeypatch.setenv("ACP_UNFORWARDED_TOKEN", "ambient")
    result = asyncio.run(run_target(target("environment", refs=("ACP_TEST_SECRET",)), "env", str(tmp_path)))
    assert result["output"] == "explicit/None"


def test_model_cannot_supply_arbitrary_target_command():
    assert parse_targets('{"dsh":{"command":"dsh","args":["--profile","acp"]}}')["dsh"].permission == "reject"
    for value in ('[]', '{"a":{"command":"agent","timeout":true}}',
                  '{"a":{"command":"agent","permission":"always"}}', '{"a":{"command":"agent","env":{"KEY":"secret"}}}'):
        with pytest.raises(ValueError):
            parse_targets(value)
