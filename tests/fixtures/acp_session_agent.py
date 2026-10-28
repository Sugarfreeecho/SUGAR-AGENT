"""A persisted keyless ACP v1 peer with real new/list/resume and progress."""
import asyncio
import json
import sys
import uuid
from pathlib import Path

import acp
from acp import schema as s

STATE = Path(sys.argv[1])


class Agent(acp.Agent):
    def on_connect(self, connection):
        self.connection = connection
        self.cancelled = {}

    def rows(self):
        return json.loads(STATE.read_text()) if STATE.exists() else {}

    async def initialize(self, protocol_version, **kwargs):
        return s.InitializeResponse(protocol_version=1, auth_methods=[], agent_capabilities=s.AgentCapabilities(
            session_capabilities=s.SessionCapabilities(list={}, resume={}, close={})))

    async def new_session(self, cwd, mcp_servers=None, **kwargs):
        rows = self.rows()
        sid = str(uuid.uuid4())
        rows[sid] = {"cwd": cwd, "turns": 0}
        STATE.write_text(json.dumps(rows))
        return s.NewSessionResponse(session_id=sid)

    async def resume_session(self, session_id, cwd, **kwargs):
        if session_id not in self.rows() or self.rows()[session_id]["cwd"] != cwd:
            raise acp.RequestError(-32602, "missing session REMOTE_SECRET")
        return s.ResumeSessionResponse()

    async def list_sessions(self, cwd=None, cursor=None, **kwargs):
        rows = self.rows()
        items = [s.SessionInfo(session_id=sid, cwd=row["cwd"], title="Saved session") for sid, row in rows.items()]
        return s.ListSessionsResponse(sessions=items)

    async def close_session(self, session_id, **kwargs):
        return s.CloseSessionResponse()

    async def prompt(self, session_id, prompt, **kwargs):
        text = "".join(block.text for block in prompt if block.type == "text")
        event = self.cancelled[session_id] = asyncio.Event()
        await self.connection.session_update(session_id, acp.update_agent_thought_text("PRIVATE_REASONING"))
        await self.connection.session_update("foreign-session", acp.update_agent_message_text("FOREIGN_TEXT"))
        await self.connection.session_update(session_id, acp.update_agent_message_text("progress:"))
        if text == "wait":
            await event.wait()
            return s.PromptResponse(stop_reason="cancelled")
        if text == "fail":
            raise acp.RequestError(-32603, "REMOTE_SECRET")
        rows = self.rows()
        rows[session_id]["turns"] += 1
        STATE.write_text(json.dumps(rows))
        await asyncio.sleep(.02)
        result = "x" * 33000 if text == "large" else f"done:{text}:{rows[session_id]['turns']}"
        await self.connection.session_update(session_id, acp.update_agent_message_text(result))
        return s.PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id, **kwargs):
        self.cancelled[session_id].set()


asyncio.run(acp.run_agent(Agent(), use_unstable_protocol=True))
