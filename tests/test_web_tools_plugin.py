"""The bundled web-search plugin owns web_fetch / web_download as well."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from plugins import load_plugin
import plugins.host as host
from host_tool_registry import host_tool_invokers
import agent_tools


def _plugin():
    return load_plugin(ROOT / "plugins" / "web-search-providers")


def _module():
    return host._module(_plugin())


def _web_tools(module):
    module.tool_definitions({"is_enabled": lambda _plugin_id: True}, _plugin())
    return module.web_tools


class _Response:
    status_code = 200
    headers = {"content-type": "text/html; charset=utf-8"}
    url = "https://example.com/page"
    text = (
        "<html><head><title>Example Docs</title></head><body>"
        "<script>bad()</script><h1>Hello</h1><p>Body text</p></body></html>"
    )

    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True}


class _Client:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, _url):
        return _Response()


def test_plugin_exposes_all_three_web_tools():
    plugin = _plugin()
    module = _module()
    definitions = module.tool_definitions({"is_enabled": lambda _plugin_id: True}, plugin)

    assert [row["function"]["name"] for row in definitions] == [
        "web_search",
        "web_fetch",
        "web_download",
    ]
    for name in ("web_search", "web_fetch", "web_download"):
        assert host_tool_invokers.has(name)
        assert host_tool_invokers.owner(name) == "web-search-providers"
        assert host_tool_invokers.is_enabled(name) is True


def test_core_no_longer_ships_the_web_tools():
    names = {row["function"]["name"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS}

    assert not ({"web_search", "web_fetch", "web_download"} & names)
    assert "web_fetch" not in agent_tools.tools
    assert "web_download" not in agent_tools.tools


def test_fetch_is_read_only_and_download_is_a_serial_write():
    fetch = host_tool_invokers.policy("web_fetch")
    download = host_tool_invokers.policy("web_download")

    assert fetch.effect == "read" and fetch.parallel_safe is True
    assert download.effect == "write" and download.parallel_safe is False


def test_disabling_the_plugin_disables_every_web_tool():
    plugin = _plugin()
    module = _module()
    try:
        module.tool_definitions({"is_enabled": lambda _plugin_id: False}, plugin)
        assert host_tool_invokers.is_enabled("web_fetch") is False
        assert host_tool_invokers.is_enabled("web_download") is False
    finally:
        module.tool_definitions({"is_enabled": lambda _plugin_id: True}, plugin)
    assert host_tool_invokers.is_enabled("web_fetch") is True


def test_url_guard_blocks_non_public_and_non_http_targets():
    web_tools = _web_tools(_module())

    for url in (
        "http://127.0.0.1/admin",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data",
        "http://192.168.1.1/",
        "http://[::1]/",
        "file:///C:/Windows/win.ini",
    ):
        ok, reason = web_tools._url_safe_for_fetch(url)
        assert ok is False, url
        assert reason


def test_fetch_strips_tags_and_marks_content_untrusted(monkeypatch):
    module = _module()
    web_tools = _web_tools(module)
    monkeypatch.setattr(web_tools, "_url_safe_for_fetch", lambda _url: (True, ""))
    monkeypatch.setattr(web_tools.httpx, "AsyncClient", _Client)

    payload = json.loads(
        __import__("asyncio").run(web_tools.web_fetch("https://example.com/page"))
    )

    assert payload["untrusted"] is True
    assert payload["finalUrl"] == "https://example.com/page"
    assert "Example Docs" in payload["text"]
    assert "Hello" in payload["text"]
    assert "bad()" not in payload["text"]
    assert web_tools._UNTRUSTED_WEB_BANNER in payload["text"]


def test_fetch_clamps_and_reports_truncation(monkeypatch):
    module = _module()
    web_tools = _web_tools(module)
    long_html = (
        "<html><head><title>Long</title></head><body>"
        + ("word " * 4000)
        + "</body></html>"
    )
    monkeypatch.setattr(web_tools, "_url_safe_for_fetch", lambda _url: (True, ""))
    monkeypatch.setattr(web_tools.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(_Response, "text", long_html)

    payload = json.loads(
        __import__("asyncio").run(
            web_tools.web_fetch("https://example.com/page", max_chars=500)
        )
    )

    assert payload["truncated"] is True
    assert 500 <= len(payload["text"]) <= 570


def test_download_writes_bytes_under_the_work_root(monkeypatch, tmp_path):
    module = _module()
    web_tools = _web_tools(module)
    target = tmp_path / "file.bin"

    class StreamResponse:
        status_code = 200
        headers = {"content-type": "application/octet-stream", "content-length": "5"}
        url = "https://example.com/file.bin"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"hello"

    class StreamClient(_Client):
        def stream(self, _method, _url):
            return StreamResponse()

    monkeypatch.setattr(web_tools, "_url_safe_for_fetch", lambda _url: (True, ""))
    monkeypatch.setattr(web_tools.httpx, "AsyncClient", StreamClient)
    monkeypatch.setattr(web_tools, "safe_work_path", lambda _raw: target)
    monkeypatch.setattr(web_tools, "enforce_leaf", lambda _action, _target: None)
    monkeypatch.setattr(web_tools, "_path_is_sensitive_tool_resource", lambda _path: False)
    monkeypatch.setattr(web_tools, "_format_path_for_tool_output", lambda path: str(path))

    payload = json.loads(
        __import__("asyncio").run(
            web_tools.web_download("https://example.com/file.bin", path="file.bin")
        )
    )

    assert payload["bytes"] == 5
    assert target.read_bytes() == b"hello"
    assert not (tmp_path / "file.bin.download_part").exists()


def test_download_rejects_oversized_content_length(monkeypatch, tmp_path):
    module = _module()
    web_tools = _web_tools(module)
    target = tmp_path / "big.bin"

    class StreamResponse:
        status_code = 200
        headers = {"content-type": "application/octet-stream", "content-length": "99999999"}
        url = "https://example.com/big.bin"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"never"

    class StreamClient(_Client):
        def stream(self, _method, _url):
            return StreamResponse()

    monkeypatch.setattr(web_tools, "_url_safe_for_fetch", lambda _url: (True, ""))
    monkeypatch.setattr(web_tools.httpx, "AsyncClient", StreamClient)
    monkeypatch.setattr(web_tools, "safe_work_path", lambda _raw: target)
    monkeypatch.setattr(web_tools, "enforce_leaf", lambda _action, _target: None)
    monkeypatch.setattr(web_tools, "_path_is_sensitive_tool_resource", lambda _path: False)

    payload = json.loads(
        __import__("asyncio").run(
            web_tools.web_download(
                "https://example.com/big.bin", path="big.bin", max_bytes=1024
            )
        )
    )

    assert "exceeds max_bytes" in payload["error"]
    assert not target.exists()
