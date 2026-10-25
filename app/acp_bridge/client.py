"""One isolated ACP subprocess per delegated task, using the official SDK."""
from __future__ import annotations

import asyncio
import json
import math
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

import acp
from acp import schema as s


@dataclass(frozen=True)
class AgentTarget:
    name: str
    command: str
    args: tuple = ()
    env_refs: tuple = ()
    permission: str = "reject"
    timeout: float = 600

    def environment(self):
        from security.extensions import minimal_extension_environment

        explicit = {}
        for name in self.env_refs:
            if name not in os.environ:
                raise ValueError("a configured ACP environment reference is unavailable")
            explicit[name] = os.environ[name]
        return minimal_extension_environment(explicit=explicit)


def parse_targets(raw):
    value = json.loads(raw or "{}")
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("agents_json must be an object with at most 32 targets")
    targets = {}
    for name, config in value.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(config, dict):
            raise ValueError("invalid ACP target")
        if set(config) - {"command", "args", "env_refs", "permission", "timeout"}:
            raise ValueError("unknown ACP target field")
        command, args, refs = config.get("command"), config.get("args", []), config.get("env_refs", [])
        timeout = config.get("timeout", 600)
        permission = config.get("permission", "reject")
        if (not isinstance(command, str) or not command.strip() or "\0" in command
                or not isinstance(args, list) or any(not isinstance(arg, str) or "\0" in arg for arg in args)
                or not isinstance(refs, list) or any(not isinstance(ref, str) or not ref or "=" in ref or "\0" in ref for ref in refs)
                or isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or not 1 <= timeout <= 86400
                or permission not in {"reject", "allow"}):
            raise ValueError("invalid ACP target configuration")
        targets[name] = AgentTarget(name, command, tuple(args), tuple(refs), permission, float(timeout))
    return targets


class DelegationClient(acp.Client):
    def __init__(self, permission="reject"):
        self.permission = permission
        self.chunks = []
        self.characters = 0
        self.truncated = False
        self.permission_requested = False

    async def session_update(self, session_id, update, **kwargs):
        if update.session_update != "agent_message_chunk" or update.content.type != "text":
            return
        remaining = 32000 - self.characters
        text = update.content.text
        if len(text) > remaining:
            self.truncated = True
        if remaining > 0:
            self.chunks.append(text[:remaining])
            self.characters += min(len(text), remaining)

    async def request_permission(self, session_id, tool_call, options, **kwargs):
        self.permission_requested = True
        if self.permission == "allow":
            once = next((option for option in options if option.kind == "allow_once"), None)
            if once is not None:
                return s.RequestPermissionResponse(outcome=s.AllowedOutcome(outcome="selected", option_id=once.option_id))
        return s.RequestPermissionResponse(outcome=s.DeniedOutcome(outcome="cancelled"))

    def on_connect(self, conn):
        pass

    async def ext_method(self, method, params):
        raise acp.RequestError.method_not_found(method)

    async def ext_notification(self, method, params):
        pass

    async def _unsupported(self, **kwargs):
        raise acp.RequestError.method_not_found("unadvertised client capability")

    read_text_file = write_text_file = create_terminal = terminal_output = _unsupported
    release_terminal = wait_for_terminal_exit = kill_terminal = create_elicitation = _unsupported


def _descendants(pid):
    import psutil
    try:
        return psutil.Process(pid).children(recursive=True)
    except psutil.NoSuchProcess:
        return []


async def _reap(process, children):
    """EOF first, then terminate the owned range; observe the direct child's exit."""
    import psutil

    if process.stdin:
        process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), 3)
    except asyncio.TimeoutError:
        children = list({child.pid: child for child in [*children, *_descendants(process.pid)]}.values())
        try:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        except ProcessLookupError:
            pass
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = await asyncio.to_thread(psutil.wait_procs, children, timeout=2)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.returncode is None:
        try:
            await asyncio.wait_for(process.wait(), 2)
        except asyncio.TimeoutError:
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            await asyncio.wait_for(process.wait(), 3)


async def run_target(target: AgentTarget, prompt: str, cwd: str):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 200000:
        raise ValueError("ACP task must contain between 1 and 200000 characters")
    path = Path(cwd)
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("ACP task cwd must be an existing absolute directory")
    client = DelegationClient(target.permission)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    process = await asyncio.create_subprocess_exec(target.command, *target.args,
        cwd=str(path.resolve()), env=target.environment(), stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=8 * 1024 * 1024, **options)
    connection = None
    operation = None
    session_id = None
    children = []
    try:
        connection = acp.connect_to_agent(client, process.stdin, process.stdout, use_unstable_protocol=True)

        async def execute():
            nonlocal session_id
            initialized = await connection.initialize(protocol_version=acp.PROTOCOL_VERSION,
                client_capabilities=s.ClientCapabilities(),
                client_info=s.Implementation(name="sugaragent-acp-client", version="1.0.0"))
            if initialized.protocol_version != acp.PROTOCOL_VERSION:
                raise ValueError("ACP protocol version mismatch")
            session = await connection.new_session(cwd=str(path.resolve()), mcp_servers=[])
            session_id = session.session_id
            response = await connection.prompt(session_id=session_id, prompt=[acp.text_block(prompt)])
            return {"agent": target.name, "session_id": session_id, "stop_reason": response.stop_reason,
                    "output": "".join(client.chunks), "truncated": client.truncated,
                    "permission_requested": client.permission_requested}

        operation = asyncio.create_task(execute())
        try:
            return await asyncio.wait_for(asyncio.shield(operation), target.timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if session_id:
                try:
                    await asyncio.wait_for(connection.cancel(session_id=session_id), 2)
                    await asyncio.wait_for(asyncio.shield(operation), 3)
                except Exception:
                    pass  # Cleanup below reaps the process if cooperative cancellation failed.
            raise
    finally:
        children = _descendants(process.pid)
        if operation is not None and not operation.done():
            operation.cancel()
        if operation is not None:
            await asyncio.gather(operation, return_exceptions=True)
        try:
            if connection is not None:
                await connection.close()
        finally:
            await _reap(process, children)
