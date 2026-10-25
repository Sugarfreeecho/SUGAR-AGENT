"""Real MCP HTTP discovery/calls; all Bilibili traffic uses isolated fakes."""
import asyncio
from contextlib import asynccontextmanager
import json
import socket
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import agent_mcp
import mcp_host_context as tickets
from tests.test_sugar_bili_scroll_workflows import runtime, BV1, BV2
from tests.test_sugar_bili_scroll_tasks import host, PLUGIN_ROOT


@asynccontextmanager
async def endpoint(rt, monkeypatch):
    import plugins.host
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda pid: True)
    app = FastAPI()
    adapter = rt.h._load_sibling("mcp_server")
    adapter.install(app, rt.h)
    await adapter.start(rt.h)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async def wait_started():
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(.01)
        await asyncio.wait_for(wait_started(), timeout=10)
        yield f"http://127.0.0.1:{port}{adapter.PATH}/", adapter, app
    finally:
        server.should_exit = True
        await task
        await adapter.stop(rt.h)
        sock.close()


def test_manifest_discovers_mcp_and_single_bundled_skill():
    from plugins.loader import load_plugin, skill_resources
    plugin = load_plugin(PLUGIN_ROOT)
    assert list(plugin.mcp_servers) == ["sugar-bili-scroll/bili"]
    cfg = plugin.mcp_servers["sugar-bili-scroll/bili"]
    assert cfg["host_context"] and cfg["transport"] == "streamable-http"
    assert cfg["tool_contracts"]["bili_favorite_add"]["effect"] == "external_write"
    # Resource discovery must expose the actual bundled Skill, not just its directory.
    assert len(plugin.skills) == 1
    assert skill_resources(plugin)[0].qualified_name == "sugar-bili-scroll:bili-scroll"


def test_host_url_tracks_port_and_rejects_nonlocal_paths(monkeypatch):
    monkeypatch.setenv("MYAGENT_SERVER_PORT", "8234")
    assert agent_mcp._streamable_url({"host_path": "/api/bili/mcp/"}) == "http://127.0.0.1:8234/api/bili/mcp/"
    for path in ["https://example.com/api/", "//example.com/api/", "/api/../x", "/api/x?secret=1"]:
        with pytest.raises(ValueError):
            agent_mcp._streamable_url({"host_path": path})


def test_context_tickets_bind_identity_tool_args_expiry_and_cannot_replay(monkeypatch):
    args = {"bvid": BV1}
    meta = tickets.issue("bili", "info", args, session_id="s", run_id="bili-r", tool_call_id="c")
    assert tickets.consume(meta, "bili", "info", args) == {"session_id": "s", "run_id": "bili-r", "tool_call_id": "c"}
    with pytest.raises(ValueError):
        tickets.consume(meta, "bili", "info", args)
    for alias, name, changed in [("other", "info", args), ("bili", "write", args), ("bili", "info", {"bvid": BV2})]:
        meta = tickets.issue("bili", "info", args, session_id="s")
        with pytest.raises(ValueError):
            tickets.consume(meta, alias, name, changed)
    meta = tickets.issue("bili", "info", args, session_id="s")
    monkeypatch.setattr(tickets.time, "monotonic", lambda: float("inf"))
    with pytest.raises(ValueError):
        tickets.consume(meta, "bili", "info", args)


def test_real_mcp_catalog_and_context_permissions(runtime, monkeypatch):
    rt = runtime
    async def search(keyword, num, order):
        return {"videos": [{"bvid": BV1, "title": keyword}]}
    rt.h.bili_client.search_videos = search

    async def run():
        async with endpoint(rt, monkeypatch) as (url, adapter, app):
            async with streamable_http_client(url) as (read, write, _):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    catalog = (await client.list_tools()).tools
                    assert len(catalog) == 14
                    assert next(t for t in catalog if t.name == "bili_favorite_add").annotations.readOnlyHint is False
                    args = {"keyword": "MCP"}
                    assert (await client.call_tool("bili_search", args)).isError
                    forged = await client.call_tool("bili_search", args, meta={"session_id": "s", "run_id": "manual"})
                    assert forged.isError
                    meta = tickets.issue(adapter.ALIAS, "bili_search", args, session_id="s", run_id="manual")
                    result = await client.call_tool("bili_search", args, meta=meta)
                    assert not result.isError
                    assert json.loads(result.content[0].text)["videos"][0]["title"] == "MCP"
                    assert (await client.call_tool("bili_search", args, meta=meta)).isError
                    rt.flow.store.start_run("bili-stranger", "s", {"mode": "dm", "uid": "200"})
                    meta = tickets.issue(adapter.ALIAS, "bili_search", args, session_id="s", run_id="bili-stranger")
                    assert (await client.call_tool("bili_search", args, meta=meta)).isError
                    rt.flow.store.start_run("bili-public", "s", {"mode": "reply", "uid": "100",
                        "target": {"bvid": BV1, "root": 10, "rpid": 11}})
                    bad = {"bvid": BV2, "text": "wrong"}
                    meta = tickets.issue(adapter.ALIAS, "bili_reply", bad, session_id="s", run_id="bili-public")
                    assert (await client.call_tool("bili_reply", bad, meta=meta)).isError
                    assert rt.calls == []
                    good = {"bvid": BV1, "text": "right"}
                    meta = tickets.issue(adapter.ALIAS, "bili_reply", good, session_id="s", run_id="bili-public")
                    assert not (await client.call_tool("bili_reply", good, meta=meta)).isError
                    assert rt.calls[0][3:5] == (11, 10)
                    # Revoking whitelist after discovery still prevents a call.
                    rt.cfg["inbound_whitelist"] = ""
                    meta = tickets.issue(adapter.ALIAS, "bili_search", args, session_id="s", run_id="bili-public")
                    assert (await client.call_tool("bili_search", args, meta=meta)).isError
            # Stop, disable and re-enable create a fresh manager, with one mount.
            await adapter.stop(rt.h)
            async with httpx.AsyncClient() as client:
                assert (await client.post(url, json={})).status_code == 503
            adapter.install(app, rt.h)
            await adapter.start(rt.h)
            assert sum(getattr(route, "path", "") == adapter.PATH for route in app.routes) == 1
            async with streamable_http_client(url) as (read, write, _):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    assert len((await client.list_tools()).tools) == 14
    asyncio.run(run())


def test_core_mcp_transport_preserves_host_context_and_failure_status(runtime, monkeypatch):
    rt = runtime
    async def run():
        async with endpoint(rt, monkeypatch) as (url, adapter, _):
            srv = agent_mcp._make_streamable_connector(adapter.ALIAS,
                {"url": url, "host_context": True}, register_tools=False)
            await agent_mcp._run_on_mcp_loop(srv.start())
            name = rt.h.mcp_function_name("bili_reply")
            monkeypatch.setattr(agent_mcp, "_servers", {adapter.ALIAS: srv})
            monkeypatch.setattr(agent_mcp, "_fname_to_tool", {name: (adapter.ALIAS, "bili_reply")})
            monkeypatch.setattr(agent_mcp, "_enabled_flag", lambda: True)
            monkeypatch.setattr(agent_mcp, "is_mcp_tool_enabled", lambda _: True)
            monkeypatch.setattr(agent_mcp, "_unapproved_published_servers", lambda: set())
            rt.flow.store.start_run("bili-context", "s", {"mode": "dm", "uid": "100"})
            try:
                outcome = await agent_mcp.invoke_tool_by_fname(name, {"bvid": BV1, "text": "ok"},
                    session_id="s", run_id="bili-context", tool_call_id="t1", return_outcome=True)
                assert outcome.kind.value == "completed"
                assert len(rt.calls) == 1
                ended = await agent_mcp.invoke_tool_by_fname(name, {"bvid": BV1, "text": "expired"},
                    session_id="another-session", run_id="bili-context", return_outcome=True)
                assert ended.kind.value == "failed"
                assert len(rt.calls) == 1
            finally:
                await agent_mcp._run_on_mcp_loop(srv.stop())
    asyncio.run(run())


def test_mcp_keeps_host_asr_and_account_checked_favorite(runtime, monkeypatch):
    rt = runtime
    rt.cfg.update(transcribe=True, fav_folder_id=42)
    seen = []
    async def transcribe(data, source, identity, language):
        assert asyncio.get_running_loop() is rt.h._runtime["loop"]
        seen.append(("speech", source, identity))
        return {"text": "宿主转写结果"}
    speech = SimpleNamespace(settings={}, transcribe=transcribe)
    async def asr(home, bvid, **kwargs):
        result = await asyncio.to_thread(kwargs["speech_call"], b"wav", "mock-video", "zh")
        return {"text": result["text"]}
    rt.h.asr = SimpleNamespace(transcribe=asr, DEFAULT_MODEL="base", MAX_MINUTES=20)
    async def folders(home, uid):
        return {"folders": [{"id": 42}]}
    async def favorite(home, bvid, fid):
        seen.append(("favorite", bvid, fid))
        return {"ok": True, "bvid": bvid, "fid": fid}
    rt.h.bili_client.favorite_folders = folders
    rt.h.bili_client.favorite_add = favorite
    async def run():
        async with endpoint(rt, monkeypatch) as (url, adapter, app):
            app.state.voice_input_service = speech
            rt.h._runtime.update(app=app, loop=asyncio.get_running_loop())
            rt.flow.store.start_run("bili-asr", "s", {"mode": "dm", "uid": "100"})
            async with streamable_http_client(url) as (read, write, _):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    for name, args in [("bili_transcribe", {"bvid": BV1}),
                                       ("bili_favorite_add", {"bvid": BV1})]:
                        meta = tickets.issue(adapter.ALIAS, name, args, session_id="s", run_id="bili-asr")
                        result = await client.call_tool(name, args, meta=meta)
                        assert not result.isError, result
                    assert json.loads(result.content[0].text)["fid"] == 42
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers={"Origin": "http://evil.example"}, json={})
                assert response.status_code == 403
            transport = httpx.ASGITransport(app=app, client=("192.0.2.1", 1234))
            async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
                assert (await client.post(adapter.PATH + "/", json={})).status_code == 403
    asyncio.run(run())
    assert seen == [("speech", "sugar-bili-scroll", "mock-video"), ("favorite", BV1, 42)]
