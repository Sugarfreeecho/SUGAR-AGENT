"""Keyless ACP peer used by real subprocess transport tests."""
import asyncio
import os
import sys
from pathlib import Path

import acp
from acp import schema as s


class FakeAgent(acp.Agent):
    def on_connect(self, connection):
        self.connection = connection
        self.cancelled = asyncio.Event()

    async def initialize(self, protocol_version, **kwargs):
        return s.InitializeResponse(protocol_version=1, agent_capabilities=s.AgentCapabilities(), auth_methods=[])

    async def new_session(self, cwd, mcp_servers=None, **kwargs):
        return s.NewSessionResponse(session_id="fake-session")

    async def prompt(self, session_id, prompt, **kwargs):
        mode = sys.argv[1] if len(sys.argv) > 1 else "echo"
        if mode == "wait":
            if len(sys.argv) > 2:
                Path(sys.argv[2] + ".ready").write_text("ready", encoding="utf-8")
            await self.cancelled.wait()
            return s.PromptResponse(stop_reason="cancelled")
        if mode == "permission":
            result = await self.connection.request_permission(session_id=session_id,
                tool_call=s.ToolCallUpdate(tool_call_id="call-1"),
                options=[s.PermissionOption(option_id="always", kind="allow_always", name="Always"),
                         s.PermissionOption(option_id="once", kind="allow_once", name="Once")])
            text = result.outcome.option_id if isinstance(result.outcome, s.AllowedOutcome) else "denied"
        elif mode == "environment":
            text = str(os.getenv("ACP_TEST_SECRET")) + "/" + str(os.getenv("ACP_UNFORWARDED_TOKEN"))
        elif mode == "error":
            raise acp.RequestError(-32603, "REMOTE_SECRET must not appear in a tool result")
        else:
            text = "echo:" + "".join(block.text for block in prompt if block.type == "text")
        await self.connection.session_update(session_id, acp.update_agent_thought_text("private reasoning"))
        await self.connection.session_update(session_id, acp.update_agent_message_text(text))
        return s.PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id, **kwargs):
        self.cancelled.set()
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text("cancelled", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(str(os.getpid()), encoding="ascii")
    asyncio.run(acp.run_agent(FakeAgent()))
