"""Project committed native events into standard ACP semantic updates."""
from __future__ import annotations

import acp


class EventProjector:
    def __init__(self):
        self.tools = set()
        self.last_response = ""

    def updates(self, event):
        kind = event.get("type")
        content = str(event.get("content") or "")
        if kind == "llm_reasoning" and content:
            return [acp.update_agent_thought_text(content)]
        if kind == "llm_response" and content:
            self.last_response = content
            return [acp.update_agent_message_text(content)]
        if kind == "final" and content and content != self.last_response:
            self.last_response = content
            return [acp.update_agent_message_text(content)]
        if kind in {"tool_pending", "tool_call"}:
            identifier = str(event.get("tool_call_id") or "")
            if not identifier:
                return []
            out = []
            if identifier not in self.tools:
                self.tools.add(identifier)
                out.append(acp.start_tool_call(identifier, str(event.get("tool") or "tool"),
                                              kind="other", status="in_progress", raw_input=event.get("args")))
            if kind == "tool_call":
                failed = event.get("execution_status") in {"failed", "denied", "error"}
                out.append(acp.update_tool_call(identifier, status="failed" if failed else "completed",
                           content=[acp.tool_content(acp.text_block(str(event.get("result") or "")[:16000]))]))
            return out
        return []
