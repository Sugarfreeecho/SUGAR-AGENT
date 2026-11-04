"""Result delivery survives HTTP loss and terminal calls wait for completion."""
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from acp_bridge.backend import RuntimeBackend
from acp_bridge.client import AgentTarget
from acp_bridge import call as caller


def ndjson(*events):
    return ("\n".join(json.dumps(event) for event in events) + "\n").encode()


@pytest.mark.parametrize("broken", ["eof", "read_error"])
def test_operation_stream_reattaches_without_resubmitting_or_duplicate_text(broken):
    async def scenario():
        posts, cursors = [], []
        class BrokenStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield ndjson({"type": "llm_response", "cursor": 1, "content": "progress"})
                if broken == "read_error":
                    raise httpx.ReadError("private transport detail")
        def handler(request):
            if request.method == "POST":
                posts.append(json.loads(request.content))
                return httpx.Response(200, json={"schema_version": 1, "ok": True, "data": {"operation_id": "op"}})
            cursors.append(request.url.params["cursor"])
            if len(cursors) == 1:
                return httpx.Response(200, stream=BrokenStream())
            return httpx.Response(200, content=ndjson(
                {"type": "llm_response", "cursor": 1, "content": "progress"},
                {"type": "final", "cursor": 2, "content": "answer"},
                {"type": "operation.completed", "cursor": 2, "operation": {"status": "succeeded", "content": "answer"}}))
        client = httpx.AsyncClient(base_url="http://127.0.0.1", transport=httpx.MockTransport(handler))
        backend = RuntimeBackend("http://127.0.0.1", client=client, token="private-token")
        try:
            rows = [row async for row in backend.events("sid", "run", "do once")]
            assert [row["type"] for row in rows] == ["llm_response", "final", "run_finished"]
            assert cursors == ["0", "1"]
            assert len(posts) == 1 and posts[0]["method"] == "session.send"
            assert not backend.operations
        finally:
            await backend.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["empty_final", "receipt_only", "exhausted", "revoked"])
def test_stream_receipt_fallback_and_bounded_failures(case):
    async def scenario():
        gets = []
        def handler(request):
            if request.method == "POST":
                return httpx.Response(200, json={"schema_version": 1, "ok": True, "data": {"operation_id": "op"}})
            gets.append(request)
            if case == "exhausted":
                return httpx.Response(200, content=b"")
            if case == "revoked":
                return httpx.Response(403, json={"schema_version": 1, "ok": False,
                    "error": {"code": "forbidden", "message": "revoked"}})
            events = [{"type": "final", "cursor": 1, "content": ""}] if case == "empty_final" else []
            return httpx.Response(200, content=ndjson(*events,
                {"type": "operation.completed", "operation": {"status": "succeeded", "content": "durable answer"}}))
        client = httpx.AsyncClient(base_url="http://127.0.0.1", transport=httpx.MockTransport(handler))
        backend = RuntimeBackend("http://127.0.0.1", client=client, token="private-token")
        try:
            if case in {"exhausted", "revoked"}:
                with pytest.raises(Exception):
                    _ = [row async for row in backend.events("sid", "run", "once")]
                assert len(gets) == (4 if case == "exhausted" else 1)
            else:
                rows = [row async for row in backend.events("sid", "run", "once")]
                assert rows[-2:] == [{"type": "final", "content": "durable answer"}, {"type": "run_finished"}]
        finally:
            await backend.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("outcome", ["success", "timeout", "error", "close_error", "cancelled"])
def test_caller_waits_preserves_partial_and_writes_terminal_receipt(tmp_path, monkeypatch, outcome):
    received, lifecycle = [], []
    class Peer:
        async def new_session(self):
            return "owned-session"
        async def resume(self, sid):
            assert sid == "owned-session"
            lifecycle.append("resume")
            return "resume"
        async def prompt(self, sid, prompt, callback):
            await callback({"type": "message", "text": "中间回复", "truncated": False})
            if outcome == "timeout":
                await asyncio.Event().wait()
            if outcome == "error":
                raise RuntimeError("PRIVATE_TOKEN must not leak")
            if outcome == "cancelled":
                raise asyncio.CancelledError()
            await asyncio.sleep(.01)
            await callback({"type": "message", "text": "最终结果", "truncated": False})
            return {"stop_reason": "end_turn", "output": "中间回复最终结果", "truncated": False,
                    "permission_requested": False}
        async def close_session(self, sid):
            lifecycle.append("close_session")
            if outcome == "close_error":
                raise ConnectionError("PRIVATE cleanup detail")
    @asynccontextmanager
    async def transport(*args):
        try:
            yield Peer()
        finally:
            lifecycle.append("transport_closed")
    monkeypatch.setattr(caller, "peer_transport", transport)
    path = tmp_path / "result.json"
    async def scenario():
        task = caller.call(AgentTarget("sugaragent", "unused", timeout=.05), "hello", str(tmp_path),
            session_id="owned-session", emit=received.append, result_file=path)
        if outcome == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await task
            return json.loads(path.read_text(encoding="utf-8"))
        return await task
    result = asyncio.run(scenario())
    assert received[0]["event"] == "started" and received[-1]["event"] == "completed"
    assert result["connected"] is False and lifecycle[-1] == "transport_closed"
    assert "PRIVATE" not in json.dumps(result)
    assert json.loads(path.read_text(encoding="utf-8")) == result
    assert result["status"] == {"timeout": "timed_out", "error": "failed", "cancelled": "cancelled"}.get(outcome, "succeeded")
    assert result["output"] == ("中间回复" if outcome in {"timeout", "error", "cancelled"} else "中间回复最终结果")
    assert result["session_action"] == "resume"
