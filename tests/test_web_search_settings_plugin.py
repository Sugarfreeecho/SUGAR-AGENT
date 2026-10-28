"""The bundled web-search plugin owns an embedded settings page and local API."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from plugins import load_plugin, plugin_ui_contributions
import plugins.host as host


def _module():
    return host._module(load_plugin(ROOT / "plugins" / "web-search-providers"))


def test_manifest_exposes_embedded_settings_page():
    plugin = load_plugin(ROOT / "plugins" / "web-search-providers")
    rows = [row for row in plugin_ui_contributions(plugin) if row["slot"] == "settings.section"]

    assert plugin.version == "1.1.0"
    assert rows == [
        {
            "id": "search",
            "plugin_id": "web-search-providers",
            "slot": "settings.section",
            "title": "联网搜索",
            "label": "Open",
            "description": "选择搜索引擎、配置 API 密钥并测试 web_search 工具",
            "order": 30,
            "target": "plugin-page",
            "href": "/plugins/web-search-providers",
            "embedded": True,
        }
    ]
    assert (plugin.root / "web" / "index.html").is_file()


def test_settings_status_masks_keys_and_reports_readiness(monkeypatch):
    module = _module()
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("WEB_SEARCH_MAX_RESULTS", "9")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-secret-abcd")

    payload = module._public_settings()

    assert payload["provider"] == "brave"
    assert payload["max_results"] == 9
    assert payload["ready"] is True
    assert payload["keys"]["BRAVE_API_KEY"] == {"configured": True, "hint": "••••abcd"}


def test_searxng_url_is_normalized_and_restricted(monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "_public_endpoint", lambda _url: (True, ""))

    assert module._normalize_searxng_url("https://search.example.com/search/") == "https://search.example.com"
    assert module._normalize_searxng_url("https://search.example.com/searxng") == "https://search.example.com/searxng"
    for value in ("ftp://search.example.com", "https://user:pass@search.example.com", "https://search.example.com/?q=1"):
        try:
            module._normalize_searxng_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe SearXNG URL was accepted: {value}")


def test_missing_provider_key_is_reported(monkeypatch):
    module = _module()
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "jina")
    monkeypatch.delenv("JINA_API_KEY", raising=False)

    payload = module._public_settings()

    assert payload["provider"] == "jina"
    assert payload["ready"] is False
    assert "Jina" in payload["ready_reason"]


def test_settings_api_validates_and_persists(monkeypatch):
    module = _module()
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setenv("WEB_SEARCH_MAX_RESULTS", "20")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)
    monkeypatch.setattr(host, "bundled_host_plugin_enabled", lambda _plugin_id: True)
    writes = []
    monkeypatch.setattr(module, "_persist_env", lambda updates, remove_keys=(): writes.append((dict(updates), tuple(remove_keys))))

    app = FastAPI()
    module.install(app, {}, None)
    headers = {"Origin": "http://127.0.0.1", "Sec-Fetch-Site": "same-origin"}

    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50123)) as client:
        response = client.get("/api/web-search-providers/status")
        assert response.status_code == 200
        assert response.json()["provider"] == "duckduckgo"

        response = client.post(
            "/api/web-search-providers/settings",
            json={"provider": "brave", "max_results": 7},
            headers=headers,
        )
        assert response.status_code == 200
        assert writes[-1] == ({"WEB_SEARCH_PROVIDER": "brave", "WEB_SEARCH_MAX_RESULTS": "7"}, ())

        response = client.post(
            "/api/web-search-providers/credentials",
            json={"name": "BRAVE_API_KEY", "value": "brave-secret-abcd"},
            headers=headers,
        )
        assert response.status_code == 200
        assert writes[-1] == ({"BRAVE_API_KEY": "brave-secret-abcd"}, ())

        response = client.post(
            "/api/web-search-providers/credentials",
            json={"name": "BRAVE_API_KEY", "remove": True},
            headers=headers,
        )
        assert response.status_code == 200
        assert writes[-1] == ({}, ("BRAVE_API_KEY",))

        response = client.post(
            "/api/web-search-providers/settings",
            json={"provider": "unknown", "max_results": 7},
            headers=headers,
        )
        assert response.status_code == 422

        response = client.post(
            "/api/web-search-providers/settings",
            json={"provider": "brave", "max_results": 0},
            headers=headers,
        )
        assert response.status_code == 422

        response = client.post(
            "/api/web-search-providers/searxng",
            json={"base_url": "http://127.0.0.1:8080"},
            headers=headers,
        )
        assert response.status_code == 422


def test_settings_api_rejects_external_clients(monkeypatch):
    module = _module()
    monkeypatch.setattr(host, "bundled_host_plugin_enabled", lambda _plugin_id: True)
    app = FastAPI()
    module.install(app, {}, None)

    with TestClient(app, base_url="http://localhost", client=("203.0.113.10", 50123)) as client:
        response = client.get("/api/web-search-providers/status")
        assert response.status_code == 403
