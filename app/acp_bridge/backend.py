"""Local HTTP facade over the existing session, run and approval owners."""
from __future__ import annotations

import json
import uuid
from urllib.parse import quote, urlsplit

import httpx


def session_path(session_id: str) -> str:
    return "/sessions/" + quote(session_id, safe="")


class RuntimeBackend:
    def __init__(self, url: str, *, client=None):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("ACP backend must be a loopback HTTP origin")
        self.client = client or httpx.AsyncClient(
            base_url=url.rstrip("/"), timeout=httpx.Timeout(30, read=None),
            trust_env=False, follow_redirects=False,
            headers={"Origin": url.rstrip("/"), "X-MyAgent-ACP": "1",
                     "X-MyAgent-ACP-Connection": uuid.uuid4().hex},
        )

    async def request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", 30)
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def attach(self, session_id, servers):
        await self.request("POST", "/api/acp/mcp/" + quote(session_id, safe=""), json={"servers": servers})

    async def detach(self, session_id):
        await self.request("DELETE", "/api/acp/mcp/" + quote(session_id, safe=""))

    async def interrupt(self, session_id, run_id):
        await self.request("POST", session_path(session_id) + "/interrupt",
                           json={"run_id": run_id, "reason": "acp_cancel"})

    async def resolve(self, session_id, approval_id, allow):
        await self.request("POST", session_path(session_id) + "/approvals/" + quote(approval_id, safe="") + "/resolve",
                           json={"decision": "allow_once" if allow else "deny",
                                 "rejection_reason": "" if allow else "ACP client denied this operation"})

    async def events(self, session_id, run_id, message):
        data = {"session_id": session_id, "client_run_id": run_id,
                "message": message, "stream_protocol": "legacy"}
        async with self.client.stream("POST", "/chat", data=data) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    return
                if payload:
                    event = json.loads(payload)
                    if not isinstance(event, dict):
                        raise ValueError("runtime event must be an object")
                    yield event
        raise RuntimeError("runtime event stream ended before [DONE]")

    async def close(self):
        await self.client.aclose()
