from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from search_provider_registry import SearchProviderRegistry


def test_search_provider_registry_dispatches_async_and_is_immutable():
    registry = SearchProviderRegistry()

    async def search(query: str, count: int) -> str:
        return f"{query}:{count}"

    registry.register("demo.search", search, source="test")
    assert asyncio.run(registry.search("DEMO.SEARCH", "query", 2)) == "query:2"
    snapshot = registry.snapshot()
    assert snapshot["demo.search"]["source"] == "test"
    with pytest.raises(TypeError):
        snapshot["demo.search"]["source"] = "spoofed"


def test_search_provider_registry_rejects_invalid_and_clears():
    registry = SearchProviderRegistry()
    registry.register("demo", lambda _query, _count: "ok", source="test")
    with pytest.raises(ValueError, match="already registered"):
        registry.register("demo", lambda _query, _count: "other", source="other")
    with pytest.raises(ValueError, match="dotted identifier"):
        registry.register("../escape", lambda _query, _count: "bad", source="test")
    registry.clear()
    with pytest.raises(ValueError, match="unregistered"):
        asyncio.run(registry.search("demo", "query", 1))


def test_bundled_search_plugin_registers_all_transports():
    from agent_extensions import activate_bundled_search_provider_extensions

    registry = SearchProviderRegistry()
    activate_bundled_search_provider_extensions(registry)
    assert set(registry.snapshot()) >= {
        "default",
        "duckduckgo",
        "brave",
        "tavily",
        "searxng",
        "jina",
    }
