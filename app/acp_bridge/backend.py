"""ACP protocol adaptation over authenticated session control RPC."""
from __future__ import annotations

import json
import asyncio
import logging
import os
import uuid
from urllib.parse import quote, unquote, urlsplit

import httpx

from session_control.client import ControlClient
from session_control.errors import ControlError


def session_path(session_id: str) -> str:
    return "/sessions/" + quote(session_id, safe="")


class RuntimeBackend:
    def __init__(self, url: str, *, client=None, token=None):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("ACP backend must be a loopback HTTP origin")
        if token is None:
            credentials = ControlClient(url)
            try:
                token = credentials.token
            finally:
                credentials.close()
        self.token = token
        self.operations = {}
        self.cancelled = set()
        self.connection_id = uuid.uuid4().hex
        self.monitor_available = False
        self.monitor_payload = None
        self.monitor_task = None
        self.busy_sessions = set()
        self.client = client or httpx.AsyncClient(
            base_url=url.rstrip("/"), timeout=httpx.Timeout(30, read=None),
            trust_env=False, follow_redirects=False,
            headers={"Origin": url.rstrip("/"), "X-MyAgent-ACP": "1",
                     "X-MyAgent-ACP-Connection": self.connection_id},
        )
        self.client.headers.update({"Origin": url.rstrip("/"), "X-MyAgent-ACP": "1",
                                    "X-MyAgent-ACP-Connection": self.connection_id})

    async def register_connection(self, client_info, protocol_version):
        if not self.monitor_available:
            return
        client = client_info.model_dump(exclude_none=True) if hasattr(client_info, "model_dump") else client_info
        self.monitor_payload = {"client": client or {}, "protocol_version": 1, "adapter_pid": os.getpid()}
        await self.request("POST", "/api/acp/connections", json=self.monitor_payload)
        if self.monitor_task is None:
            self.monitor_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat(self, activity=None):
        if self.monitor_payload is None:
            return
        payload = {"busy_session_ids": sorted(self.busy_sessions)}
        if activity:
            payload["activity"] = activity
        try:
            await self.request("POST", "/api/acp/connections/heartbeat", json=payload, timeout=5)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            await self.request("POST", "/api/acp/connections", json=self.monitor_payload, timeout=5)
            await self.request("POST", "/api/acp/connections/heartbeat", json=payload, timeout=5)

    async def _activity(self, activity):
        try:
            await self._heartbeat(activity)
        except Exception as exc:
            logging.getLogger(__name__).warning("ACP connection telemetry unavailable (%s)", type(exc).__name__)

    async def _heartbeat_loop(self):
        from .connections import HEARTBEAT_SECONDS
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await self._activity(None)

    def headers(self):
        if not self.token:
            raise ControlError("unauthorized", "ACP requires a host-issued identity or auth login", status=401)
        return {"Authorization": "Bearer " + self.token}

    async def rpc(self, method, params=None, *, key=None):
        response = await self.client.post("/api/control/v1/rpc", headers=self.headers(),
            json={"method": method, "params": params or {}, "idempotency_key": key or str(uuid.uuid4())})
        return ControlClient.decode(response)["data"]

    async def request(self, method, path, **kwargs):
        if path == "/sessions":
            if method == "POST":
                return await self.rpc("session.create", kwargs.get("json", {}))
            rows = (await self.rpc("session.list"))["sessions"]
            # ACP requires a concrete cwd, including sessions using the default root.
            return [(await self.rpc("session.get", {"session_id": row["id"], "include_runtime": True}))["session"] for row in rows]
        if path.startswith("/sessions/"):
            parts = path.split("/")
            sid = unquote(parts[2])
            if len(parts) == 3:
                if method == "DELETE":
                    return await self.rpc("session.delete", {"session_id": sid})
                return await self.rpc("session.get", {"session_id": sid, "include_runtime": True})
            if parts[3] in {"model_profile", "reasoning_effort"}:
                current = (await self.rpc("session.get", {"session_id": sid, "include_runtime": True}))["session"]
                if method == "GET":
                    return {"profile_id": current.get("model_profile_id", ""), "reasoning_effort": current.get("reasoning_effort", "")}
                config = await self.rpc("session.config.get", {"session_id": sid})
                update = kwargs.get("json", {})
                values = {"model_profile_id": update["profile_id"]} if parts[3] == "model_profile" else {"reasoning_effort": update["reasoning_effort"]}
                result = await self.rpc("session.config.update", {"session_id": sid, "expected_revision": config["revision"],
                    "config": {**config["config"], **values}})
                await self._activity("configured")
                return result
        kwargs.setdefault("timeout", 30)
        kwargs["headers"] = {**kwargs.get("headers", {}), **self.headers()}
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        data = response.json()
        if path == "/api/acp/status":
            self.monitor_available = data.get("connection_monitoring") is True
        return data

    async def attach(self, session_id, servers):
        await self.request("POST", "/api/acp/mcp/" + quote(session_id, safe=""), json={"servers": servers})

    async def detach(self, session_id):
        await self.request("DELETE", "/api/acp/mcp/" + quote(session_id, safe=""))

    async def interrupt(self, session_id, run_id):
        self.cancelled.add(run_id)
        operation_id = self.operations.get(run_id)
        if operation_id:
            await self.rpc("operation.cancel", {"id": operation_id}, key="acp-cancel:" + run_id)

    async def resolve(self, session_id, approval_id, allow):
        await self.rpc("approval.resolve", {"session_id": session_id, "approval_id": approval_id, "approve": bool(allow)})

    async def events(self, session_id, run_id, message):
        self.busy_sessions.add(session_id)
        try:
            await self._activity("prompt")
            async for event in self._operation_events(session_id, run_id, message):
                yield event
        finally:
            self.busy_sessions.discard(session_id)
            self.operations.pop(run_id, None)
            self.cancelled.discard(run_id)
            await self._activity("completed")

    async def _operation_events(self, session_id, run_id, message):
        receipt = await self.rpc("session.send", {"session_id": session_id, "message": message, "mode": "queue"}, key="acp:" + run_id)
        operation_id = self.operations[run_id] = receipt["operation_id"]
        if run_id in self.cancelled:
            await self.interrupt(session_id, run_id)
        endpoint = "/api/control/v1/operations/" + operation_id + "/events"
        cursor = 0
        final_content = None
        # Reattach to the accepted operation, never submit the prompt again.
        # Operation events are durable and their cursor survives HTTP reconnects.
        for attempt in range(4):
            try:
                async with self.client.stream("GET", endpoint, headers=self.headers(),
                                              params={"cursor": cursor},
                                              timeout=httpx.Timeout(30, read=30)) as response:
                    if response.status_code != 200:
                        await response.aread()
                        if response.status_code in {502, 503, 504}:
                            response.raise_for_status()
                        ControlClient.decode(response)
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        event = json.loads(line)
                        if event.get("type") == "operation.completed":
                            operation = event["operation"]
                            if operation["status"] == "succeeded":
                                content = operation.get("content")
                                if content is not None and content != final_content:
                                    yield {"type": "final", "content": content}
                                yield {"type": "run_finished"}
                            elif operation["status"] in {"stopped", "interrupted", "cancelled"}:
                                yield {"type": "run_interrupted"}
                            else:
                                yield {"type": "error", "content": (operation.get("error") or {}).get("message") or operation["status"]}
                            return
                        if event.get("type") == "operation.status":
                            continue
                        position = event.get("cursor")
                        if position is not None:
                            if not isinstance(position, int) or isinstance(position, bool) or position < 1:
                                raise ValueError("invalid operation event cursor")
                            if position <= cursor:
                                continue
                            cursor = position
                        if event.get("type") == "tool_approval_required":
                            event["type"] = "approval_requested"
                        if event.get("type") == "final":
                            final_content = event.get("content")
                        yield event
                raise httpx.RemoteProtocolError("operation stream ended before its execution receipt")
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {502, 503, 504}:
                    raise
                if attempt == 3:
                    raise
                await asyncio.sleep(.25 * 2 ** attempt)

    async def close(self):
        if self.monitor_task:
            self.monitor_task.cancel()
            await asyncio.gather(self.monitor_task, return_exceptions=True)
            self.monitor_task = None
        try:
            if self.monitor_payload is not None:
                await self.request("DELETE", "/api/acp/connections", timeout=5)
        except Exception as exc:
            logging.getLogger(__name__).warning("ACP disconnect telemetry unavailable (%s)", type(exc).__name__)
        finally:
            await self.client.aclose()
