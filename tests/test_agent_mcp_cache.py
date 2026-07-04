import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_mcp_config_signature_uses_short_cache(monkeypatch):
    import agent_mcp

    calls = {"signature": 0}
    now = {"value": 100.0}

    def compute():
        calls["signature"] += 1
        return f"sig-{calls['signature']}"

    monkeypatch.setattr(agent_mcp, "_signature_cache", None)
    monkeypatch.setattr(agent_mcp, "_compute_config_signature", compute)
    monkeypatch.setattr(agent_mcp.time, "monotonic", lambda: now["value"])

    assert agent_mcp._compute_config_signature_cached() == "sig-1"
    assert agent_mcp._compute_config_signature_cached() == "sig-1"
    assert calls["signature"] == 1

    now["value"] += agent_mcp._SIGNATURE_CACHE_TTL_SEC + 0.01
    assert agent_mcp._compute_config_signature_cached() == "sig-2"
    assert calls["signature"] == 2


def test_mcp_force_reload_clears_signature_cache(monkeypatch):
    import agent_mcp

    monkeypatch.setattr(agent_mcp, "_signature_cache", (100.0, "stale"))

    async def noop_shutdown():
        return None

    monkeypatch.setattr(agent_mcp, "_shutdown_servers_unlocked", noop_shutdown)

    asyncio.run(agent_mcp.force_reload())

    assert agent_mcp._signature_cache is None
    assert agent_mcp._loaded_signature is None
