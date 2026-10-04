from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from plugins import load_plugin
from plugins.host import _module
from execution_services import jobs
from execution_services.jobs import ExecutionService
from execution_services.terminals import terminal_manager
from tests.test_execution_integration import FakeManager

ROOT = Path(__file__).resolve().parents[1]


def test_user_api_ownership_origin_control_and_closed_stream(tmp_path, monkeypatch):
    import plugins.host
    for owner in ("owner", "other"):
        (tmp_path / owner).mkdir()
    manager = FakeManager(tmp_path)
    manager._load_metadata_unlocked = lambda owner: {}
    service = ExecutionService(manager)
    monkeypatch.setattr(jobs, "_SERVICE", service)
    monkeypatch.setattr(plugins.host, "bundled_host_plugin_enabled", lambda name: True)
    plugin = load_plugin(ROOT / "plugins" / "execution-tools")
    app = FastAPI()
    _module(plugin).install(app, {"session_manager": manager}, plugin)
    tm = terminal_manager(service)
    try:
        with TestClient(app) as client:
            base = "/sessions/owner/terminals"
            assert client.post(base, json={}).status_code == 403
            headers = {"Origin": "http://testserver"}
            assert client.post(base, json={}, headers={"Origin": "https://evil.example"}).status_code == 403
            response = client.post(base, json={"cwd": str(tmp_path)}, headers=headers)
            assert response.status_code == 200, response.text
            identifier = response.json()["id"]
            assert response.json()["actor"] == "user"
            assert client.get(base).json()["model"] == []
            asyncio.run(service.call(tm.stream, "owner", identifier, 0, "active", claim=True))
            action = base + "/" + identifier
            assert client.post(action + "/input", json={"text": "x", "connection": "stale"}, headers=headers).status_code == 409
            command = "Write-Output 'ui-output'\r" if os.name == "nt" else "printf 'ui-output\\n'\r"
            assert client.post(action + "/input", json={"text": command, "connection": "active"}, headers=headers).status_code == 200
            async def wait_output():
                for _ in range(100):
                    if "ui-output" in (await service.call(tm.read, "owner", identifier, actor="user"))["text"]:
                        return
                    await asyncio.sleep(.05)
                raise AssertionError("terminal output did not arrive")
            asyncio.run(wait_output())
            assert client.post(action + "/resize", json={"rows": 30, "cols": 100, "connection": "active"}, headers=headers).status_code == 200
            assert client.get("/sessions/other/terminals/" + identifier + "/history").status_code == 404
            assert client.post(action + "/close", json={}, headers=headers).status_code == 200
            stream = client.get(action + "/events?connection=active")
            assert stream.status_code == 200
            assert '"status": "closed"' in stream.text
            assert client.get(action + "/history").status_code == 200
    finally:
        asyncio.run(service.shutdown())
