"""Reusable standard ACP transports; loaded independently of legacy host imports."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from contextlib import asynccontextmanager

import acp
from acp import schema as s
from .client import AgentTarget, DelegationClient, _reap, _descendants


class ResponseClient(DelegationClient):
    def __init__(self, permission):
        super().__init__(permission)
        self.captures = {}
        self.strict_sessions = True

    async def session_update(self, session_id, update, **kwargs):
        if update.session_update != "agent_message_chunk" or update.content.type != "text":
            return
        capture = self.captures.get(session_id)
        if capture is None:
            if self.strict_sessions:
                return
            capture = self
        remaining = 32000 - capture.characters
        text = update.content.text
        if len(text) > remaining:
            capture.truncated = True
        if remaining > 0:
            accepted = text[:remaining]
            capture.chunks.append(accepted)
            capture.characters += len(accepted)
            callback = getattr(capture, "on_message", None)
            if callback:
                await callback({"type": "message", "session_id": session_id,
                                "phase": "progress", "text": accepted, "truncated": capture.truncated})
        elif getattr(capture, "on_message", None) and capture.truncated:
            await capture.on_message({"type": "message", "session_id": session_id,
                                      "phase": "progress", "text": "", "truncated": True})

    async def request_permission(self, session_id, tool_call, options, **kwargs):
        capture = self.captures.get(session_id)
        if self.strict_sessions and capture is None:
            return s.RequestPermissionResponse(outcome=s.DeniedOutcome(outcome="cancelled"))
        (capture or self).permission_requested = True
        if capture and getattr(capture, "on_message", None):
            await capture.on_message({"type": "permission", "session_id": session_id,
                                      "text": "", "permission_requested": True})
        if self.permission == "allow":
            once = next((option for option in options if option.kind == "allow_once"), None)
            if once is not None:
                return s.RequestPermissionResponse(outcome=s.AllowedOutcome(outcome="selected", option_id=once.option_id))
        return s.RequestPermissionResponse(outcome=s.DeniedOutcome(outcome="cancelled"))



class UnsupportedCapability(ValueError):
    pass


def valid_session_id(value):
    if not isinstance(value, str) or not value or len(value) > 512 or any(ord(ch) < 32 for ch in value):
        raise ValueError("invalid ACP session id")
    return value


class ACPPeer:
    """One authenticated standard ACP transport, with isolated prompt collectors."""
    def __init__(self, target, cwd):
        self.target, self.cwd = target, str(Path(cwd).resolve())
        if not Path(cwd).is_absolute() or not Path(cwd).is_dir():
            raise ValueError("ACP task cwd must be an existing absolute directory")
        self.client = ResponseClient(target.permission)
        self.client.strict_sessions = True
        self.process = self.connection = self.initialized = None
        self.active = set()
        self.busy = set()
        self.closed = False

    async def start(self):
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        self.process = await asyncio.create_subprocess_exec(self.target.command, *self.target.args,
            cwd=self.cwd, env=self.target.environment(), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=8 * 1024 * 1024, **options)
        self.connection = acp.connect_to_agent(self.client, self.process.stdin, self.process.stdout, use_unstable_protocol=True)
        self.initialized = await self.connection.initialize(protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=s.ClientCapabilities(), client_info=s.Implementation(name="sugaragent-acp-client", version="1.1.0"))
        if self.initialized.protocol_version != acp.PROTOCOL_VERSION:
            raise ValueError("ACP protocol version mismatch")
        return self

    def supports(self, name):
        caps = self.initialized.agent_capabilities.session_capabilities
        return caps is not None and getattr(caps, name, None) is not None

    async def new_session(self):
        session = await self.connection.new_session(cwd=self.cwd, mcp_servers=[])
        sid = valid_session_id(session.session_id)
        self.active.add(sid)
        return sid

    async def resume(self, sid):
        valid_session_id(sid)
        if sid in self.active:
            return "existing"
        if not self.supports("resume"):
            raise UnsupportedCapability("peer does not advertise session/resume")
        await self.connection.resume_session(session_id=sid, cwd=self.cwd, mcp_servers=[])
        self.active.add(sid)
        return "resume"

    async def list_sessions(self, cursor=None):
        if not self.supports("list"):
            raise UnsupportedCapability("peer does not advertise session/list")
        result = await self.connection.list_sessions(cwd=self.cwd, cursor=cursor)
        rows = []
        for session in result.sessions:
            # A remote peer's cwd filter is not an authorization boundary.
            if os.path.normcase(str(Path(session.cwd).resolve())) != os.path.normcase(self.cwd):
                continue
            rows.append({"session_id": valid_session_id(session.session_id), "cwd": self.cwd,
                         "title": str(session.title or "")[:200], "updated_at": str(session.updated_at or "")})
        return {"sessions": rows, "next_cursor": result.next_cursor}

    async def close_session(self, sid):
        if sid in self.busy:
            raise ValueError("session has an active prompt")
        if sid in self.active and self.supports("close"):
            await self.connection.close_session(session_id=sid)
        self.active.discard(sid)

    async def prompt(self, sid, text, on_message=None):
        if sid in self.busy:
            raise ValueError("session has an active prompt")
        if not isinstance(text, str) or not text.strip() or len(text) > 200000:
            raise ValueError("ACP task must contain between 1 and 200000 characters")
        capture = DelegationClient(self.target.permission)
        capture.on_message = on_message
        self.client.captures[sid] = capture
        self.busy.add(sid)
        operation = asyncio.create_task(self.connection.prompt(session_id=sid, prompt=[acp.text_block(text)]))
        try:
            response = await asyncio.shield(operation)
            return {"agent": self.target.name, "session_id": sid, "stop_reason": response.stop_reason,
                    "output": "".join(capture.chunks), "truncated": capture.truncated,
                    "permission_requested": capture.permission_requested}
        except BaseException:
            try:
                await asyncio.wait_for(self.connection.cancel(session_id=sid), 2)
                await asyncio.wait_for(asyncio.shield(operation), 3)
            except BaseException:
                # After a failed cancellation the transport cannot safely admit another prompt.
                await self.close()
            raise
        finally:
            if not operation.done():
                operation.cancel()
            await asyncio.gather(operation, return_exceptions=True)
            self.busy.discard(sid)
            self.client.captures.pop(sid, None)

    async def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.connection is not None:
                await self.connection.close()
        finally:
            if self.process is not None:
                await _reap(self.process, _descendants(self.process.pid))
            self.active.clear()


@asynccontextmanager
async def peer_transport(target, cwd):
    peer = ACPPeer(target, cwd)
    try:
        await peer.start()
        yield peer
    finally:
        await peer.close()


