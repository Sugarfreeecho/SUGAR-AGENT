from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from llm.provider_registry import ProviderRegistry


def test_provider_registry_builds_and_exposes_immutable_diagnostics():
    registry = ProviderRegistry()
    registry.register(
        "demo.transport",
        lambda profile, **services: {"profile": profile, "clock": services["clock"]},
        source="test",
        dialect="demo.standard",
        tokenizer=lambda _text: 3,
        discover=lambda: ["demo-model"],
        probe=lambda **kwargs: {"ok": kwargs["ready"]},
        capabilities={"responses": True, "compact": False},
    )

    assert registry.build("DEMO.TRANSPORT", {"model": "x"}, clock="utc") == {
        "profile": {"model": "x"},
        "clock": "utc",
    }
    assert asyncio.run(registry.run_diagnostic("demo.transport", "discover")) == [
        "demo-model"
    ]
    assert asyncio.run(
        registry.run_diagnostic("demo.transport", "probe", ready=True)
    ) == {"ok": True}
    snapshot = registry.snapshot()
    assert snapshot["demo.transport"]["dialect"] == "demo.standard"
    assert snapshot["demo.transport"]["has_tokenizer"] is True
    assert snapshot["demo.transport"]["capabilities"] == {
        "responses": True,
        "compact": False,
    }
    with pytest.raises(TypeError):
        snapshot["demo.transport"]["source"] = "spoofed"


def test_provider_registry_rejects_invalid_version_callbacks_and_duplicates():
    registry = ProviderRegistry()
    factory = lambda _profile, **_services: object()
    registry.register("demo", factory, source="test")
    with pytest.raises(ValueError, match="already registered"):
        registry.register("demo", factory, source="other")
    with pytest.raises(ValueError, match="API version"):
        registry.register("future", factory, source="test", api_version=2)
    with pytest.raises(ValueError, match="dotted identifier"):
        registry.register("../../escape", factory, source="test")
    with pytest.raises(TypeError, match="probe"):
        registry.register("bad.probe", factory, source="test", probe="not-callable")


def test_provider_registry_requires_declared_diagnostic_operation():
    registry = ProviderRegistry()
    registry.register("demo", lambda _profile: None, source="test")
    with pytest.raises(ValueError, match="does not support discover"):
        asyncio.run(registry.run_diagnostic("demo", "discover"))
    with pytest.raises(ValueError, match="unsupported provider diagnostic"):
        asyncio.run(registry.run_diagnostic("demo", "delete"))
