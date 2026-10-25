"""Real production stdio entry point over an isolated keyless HTTP runtime."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from acp_bridge.client import AgentTarget, run_target


@pytest.fixture
def runtime_url(tmp_path):
    rows = {}
    resolved = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/api/acp/status":
                return self.reply({"protocol": "acp", "version": 1})
            if self.path == "/api/model_profiles":
                return self.reply({"profiles": [{"id": "model-a", "name": "A"}, {"id": "model-b", "name": "B"}]})
            if self.path == "/sessions":
                return self.reply(list(rows.values()))
            sid = self.path.split("/")[2]
            if self.path.endswith("/model_profile"):
                return self.reply({"profile_id": rows[sid].get("profile_id", "model-a"), "reasoning_effort": ""})
            return self.reply(rows[sid])

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/chat":
                from urllib.parse import parse_qs
                form = parse_qs(raw.decode())
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                def event(value):
                    self.wfile.write(("data: " + json.dumps(value) + "\n\n").encode())
                    self.wfile.flush()
                if form["message"] == ["permission"]:
                    event({"type": "approval_requested", "approval_id": "approval-1", "tool_call_id": "tool-1"})
                    assert resolved.wait(10), "ACP permission response was not forwarded"
                event({"type": "llm_reasoning_delta", "delta": "ephemeral reasoning must stay off wire"})
                event({"type": "llm_response", "content": "answer"})
                event({"type": "final", "content": "answer"})
                event({"type": "run_finished"})
                self.wfile.write(b"data: [DONE]\n\n")
                return
            data = json.loads(raw or "{}")
            if self.path == "/sessions":
                sid = "session-" + str(len(rows) + 1)
                rows[sid] = {"id": sid, "name": sid, "work_dir": data["work_dir"]}
                return self.reply({"session_id": sid})
            if self.path.endswith("/model_profile"):
                rows[self.path.split("/")[2]]["profile_id"] = data["profile_id"]
            if self.path.endswith("/resolve"):
                assert data["decision"] == "allow_once"
                resolved.set()
            return self.reply({"ok": True})

        def do_DELETE(self):
            self.reply({"ok": True})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_production_stdio_entry_works_with_official_python_client(runtime_url, tmp_path):
    target = AgentTarget("sugaragent", sys.executable,
                        (str(ROOT / "app/acp_stdio.py"), "--server-url", runtime_url))
    result = asyncio.run(run_target(target, "hello", str(tmp_path)))
    assert result["output"] == "answer"
    assert result["stop_reason"] == "end_turn"


@pytest.mark.skipif(not os.environ.get("ACP_TYPESCRIPT_SDK"), reason="set ACP_TYPESCRIPT_SDK to DSH's installed SDK dist/acp.js")
def test_dsh_typescript_sdk_conformance(runtime_url, tmp_path):
    completed = subprocess.run(["node", str(ROOT / "tests/fixtures/acp_conformance.mjs"),
        os.environ["ACP_TYPESCRIPT_SDK"], sys.executable, str(ROOT / "app/acp_stdio.py"),
        runtime_url, str(tmp_path)], capture_output=True, text=True, timeout=35)
    assert completed.returncode == 0, completed.stderr
    assert "resume-without-replay" in completed.stdout


@pytest.mark.skipif(not os.environ.get("ACP_TYPESCRIPT_SDK"), reason="set ACP_TYPESCRIPT_SDK to DSH's installed SDK dist/acp.js")
def test_outbound_client_with_dsh_typescript_sdk_agent(tmp_path):
    target = AgentTarget("typescript", shutil.which("node"),
        (str(ROOT / "tests/fixtures/acp_typescript_agent.mjs"), os.environ["ACP_TYPESCRIPT_SDK"]),
        permission="allow", timeout=20)
    result = asyncio.run(run_target(target, "task", str(tmp_path)))
    assert result["output"] == "allowed"
    assert result["permission_requested"] is True
