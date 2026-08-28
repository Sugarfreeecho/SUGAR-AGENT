import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture(autouse=True)
def _trust_extensions(monkeypatch):
    monkeypatch.setattr(
        "security.extensions.descriptor_is_trusted",
        lambda _descriptor: True,
    )


def _make_web_plugin(discovery: Path, *, api: bool = True) -> Path:
    root = discovery / "web-demo"
    manifest_path = root / ".myagent-plugin" / "plugin.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "web.demo",
                "name": "Web Demo",
                "version": "1.0.0",
                "runtime": {
                    "type": "python",
                    "entrypoint": "./plugin.py",
                    "api_version": "1",
                    "timeout_seconds": 5,
                },
                "capabilities": {
                    "web": {
                        "entry": "web/index.html",
                        "assets": "web/assets",
                        "api": api,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "web" / "assets").mkdir(parents=True)
    (root / "web" / "index.html").write_text("<h1>plugin page</h1>", encoding="utf-8")
    (root / "web" / "assets" / "app.js").write_text("export default 1;", encoding="utf-8")
    (root / "plugin.py").write_text(
        """
from myagent_plugin_sdk import Plugin, current_tool_context

plugin = Plugin()

@plugin.on_http_request
def http(request, context):
    call = current_tool_context()
    return {
        "status": 201,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
            "set-cookie": "must-be-filtered=1",
        },
        "json": {
            "method": request.get("method"),
            "path": request.get("path"),
            "query": request.get("query"),
            "json": request.get("json"),
            "plugin_id": call.plugin_id,
            "plugin_data_dir": call.plugin_data_dir,
            "authorization_forwarded": "authorization" in (request.get("headers") or {}),
        },
    }
""".lstrip(),
        encoding="utf-8",
    )
    return root


def _configure(tmp_path, monkeypatch, *, api: bool = True):
    import agent_extensions
    from plugins import PluginManager

    discovery = tmp_path / "plugins"
    root = _make_web_plugin(discovery, api=api)
    manager = PluginManager([discovery], tmp_path / "plugin-state.json")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: manager)
    monkeypatch.setenv("PLUGINS_ENABLED", "1")
    agent_extensions.invalidate_extension_caches()
    return root


def test_static_page_and_assets_stay_inside_declared_plugin_paths(tmp_path, monkeypatch):
    from plugin_web_gateway import PluginWebError, plugin_asset, plugin_page

    root = _configure(tmp_path, monkeypatch)

    assert plugin_page("web.demo") == (root / "web" / "index.html").resolve()
    assert plugin_asset("web.demo", "app.js") == (
        root / "web" / "assets" / "app.js"
    ).resolve()
    with pytest.raises(PluginWebError, match="not found"):
        plugin_asset("web.demo", "../index.html")


def test_legacy_top_level_plugin_page_redirects_to_canonical_url(
    tmp_path,
    monkeypatch,
):
    import asyncio
    import webui

    _configure(tmp_path, monkeypatch)

    response = asyncio.run(webui.legacy_plugin_web_page("web.demo"))

    assert response.status_code == 307
    assert response.headers["location"] == "/plugins/web.demo"
    assert response.headers["cache-control"] == "no-store"


def test_legacy_top_level_plugin_page_keeps_unknown_plugins_missing(
    tmp_path,
    monkeypatch,
):
    import asyncio
    import webui

    _configure(tmp_path, monkeypatch)

    response = asyncio.run(webui.legacy_plugin_web_page("missing-plugin"))

    assert response.status_code == 404
    assert json.loads(response.body)["error"] == "plugin_not_found"


def test_plugin_http_receives_sanitized_request_and_host_storage_context(
    tmp_path,
    monkeypatch,
):
    from plugin_web_gateway import invoke_plugin_http

    _configure(tmp_path, monkeypatch)
    response = invoke_plugin_http(
        "web.demo",
        method="POST",
        path="/echo",
        query={"one": "1", "many": ["a", "b"]},
        headers={
            "content-type": "application/json",
            "authorization": "Bearer secret",
        },
        body=json.dumps({"hello": "world"}).encode("utf-8"),
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status == 201
    assert response.headers == {
        "content-type": "application/json",
        "cache-control": "no-store",
    }
    assert payload["method"] == "POST"
    assert payload["path"] == "/echo"
    assert payload["query"] == {"one": "1", "many": ["a", "b"]}
    assert payload["json"] == {"hello": "world"}
    assert payload["plugin_id"] == "web.demo"
    assert payload["plugin_data_dir"]
    assert payload["authorization_forwarded"] is False


def test_plugin_http_requires_manifest_api_declaration(tmp_path, monkeypatch):
    from plugin_web_gateway import PluginWebError, invoke_plugin_http

    _configure(tmp_path, monkeypatch, api=False)

    with pytest.raises(PluginWebError, match="did not declare"):
        invoke_plugin_http(
            "web.demo",
            method="GET",
            path="/echo",
            query={},
            headers={},
            body=b"",
        )


def test_plugin_write_origin_rejects_cross_site_browser_requests():
    from plugin_web_gateway import PluginWebError, validate_plugin_write_origin

    validate_plugin_write_origin(
        "POST",
        origin="http://localhost:8000",
        scheme="http",
        host="localhost:8000",
        fetch_site="same-origin",
    )
    with pytest.raises(PluginWebError) as exc_info:
        validate_plugin_write_origin(
            "POST",
            origin="https://evil.example",
            scheme="http",
            host="localhost:8000",
            fetch_site="cross-site",
        )

    assert exc_info.value.status == 403
    assert exc_info.value.code == "cross_origin_denied"

    with pytest.raises(PluginWebError) as missing_origin:
        validate_plugin_write_origin(
            "POST",
            origin="",
            scheme="http",
            host="localhost:8000",
            require_origin=True,
        )
    assert missing_origin.value.code == "origin_required"


def test_plugin_http_consumes_session_grant_only_for_run_many_actions(
    tmp_path, monkeypatch
):
    import plugin_web_gateway as gateway

    _configure(tmp_path, monkeypatch)
    plugin = gateway._enabled_plugin("web.demo")
    captured = {}
    monkeypatch.setattr(
        gateway.get_plugin_runtime_registry(),
        "handle_http",
        lambda *_args, **_kwargs: {
            "status": 202,
            "json": {"ok": True},
            "_host_actions": [{"service": "sessions.run_many", "sessions": []}],
        },
    )
    monkeypatch.setattr(
        gateway,
        "consume_session_run_grant",
        lambda owner, token: (
            captured.update({"owner": owner.plugin_id, "token": token})
            or frozenset({"s1", "s2"})
        ),
    )
    monkeypatch.setattr(
        gateway,
        "execute_host_actions",
        lambda owner, actions, **kwargs: captured.update(
            {"actions": actions, "trusted": kwargs.get("trusted_session_ids")}
        ),
    )

    response = gateway.invoke_plugin_http(
        plugin.plugin_id,
        method="POST",
        path="/run",
        query={},
        headers={"content-type": "application/json"},
        body=b"{}",
        session_run_grant="grant-token",
    )

    assert response.status == 202
    assert captured["owner"] == "web.demo"
    assert captured["token"] == "grant-token"
    assert set(captured["trusted"]) == {"s1", "s2"}
