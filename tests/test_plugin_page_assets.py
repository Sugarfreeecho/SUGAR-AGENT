"""Shared console resources must be reachable through the real ASGI router."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["plugin-page-bridge.js", "plugin-page.css", "workflow-console.js", "workflow-console.css"])
def test_shared_asset_real_route_mime_and_cache_policy(name):
    import webui
    client = TestClient(webui.fastapi_app, raise_server_exceptions=True)
    try:
        response = client.get("/static/" + name)
    finally:
        client.close()
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css" if name.endswith(".css") else "application/javascript")
    assert response.headers["cache-control"] == "no-cache"
    assert response.content == (ROOT / "app/templates/static" / name).read_bytes()


def test_hot_install_replaces_cached_asset_route_and_is_idempotent(tmp_path, monkeypatch):
    from plugin_page_assets import install_plugin_page_assets, ASSET_ROUTE
    import plugin_web_gateway
    asset = tmp_path / "app.js"
    asset.write_text("export const ready = true;", encoding="utf-8")
    monkeypatch.setattr(plugin_web_gateway, "plugin_asset", lambda *_: asset)
    app = FastAPI()
    @app.get(ASSET_ROUTE)
    async def stale(plugin_id: str, asset_path: str): return {"stale": True}
    install_plugin_page_assets(app)
    install_plugin_page_assets(app)
    assert sum(getattr(route, "path", "") == ASSET_ROUTE for route in app.routes) == 1
    with TestClient(app) as client:
        response = client.get("/plugin-assets/agent-goal/app.js")
        assert response.text == asset.read_text()
        assert response.headers["cache-control"] == "no-cache"
        assert client.get("/static/unknown.txt").status_code == 404
        assert client.get("/static/settings/secret.env").status_code == 404
