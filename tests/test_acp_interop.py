"""Real stdio entry point over isolated authenticated session control HTTP."""
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
def runtime_url(tmp_path, monkeypatch):
    rows = {}
    operations = {}
    resolved = threading.Event()
    monkeypatch.setenv("MYAGENT_CONTROL_TOKEN", "isolated-acp-test-credential")

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
            if self.path.startswith("/api/control/v1/operations/"):
                assert self.headers.get("Authorization") == "Bearer isolated-acp-test-credential"
                operation = operations[self.path.split("/")[5]]
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                def event(value):
                    self.wfile.write((json.dumps(value) + "\n").encode())
                    self.wfile.flush()
                if operation["message"] == "permission":
                    event({"type": "approval_requested", "approval_id": "approval-1", "tool_call_id": "tool-1"})
                    assert resolved.wait(10), "ACP permission response was not forwarded"
                event({"type": "llm_response", "content": "answer"})
                event({"type": "final", "content": "answer"})
                event({"type": "operation.completed", "operation": {"status": "succeeded", "content": "answer"}})
                return
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
            if self.path == "/api/control/v1/rpc":
                assert self.headers.get("Authorization") == "Bearer isolated-acp-test-credential"
                request = json.loads(raw)
                method, params = request["method"], request["params"]
                if method == "session.create":
                    sid = "session-" + str(len(rows) + 1)
                    rows[sid] = {"id": sid, "name": sid, "work_dir": params["work_dir"], "model_profile_id": "model-a", "reasoning_effort": "", "config": {}, "revision": 0}
                    result = {"session_id": sid}
                elif method == "session.list":
                    result = {"sessions": list(rows.values())}
                elif method == "session.get":
                    result = {"session": rows[params["session_id"]]}
                elif method == "session.delete":
                    rows.pop(params["session_id"], None)
                    result = {"ok": True}
                elif method == "session.config.get":
                    row = rows[params["session_id"]]
                    result = {"config": row["config"], "revision": row["revision"]}
                elif method == "session.config.update":
                    row = rows[params["session_id"]]
                    assert params["expected_revision"] == row["revision"]
                    row.update(params["config"])
                    row["config"], row["revision"] = params["config"], row["revision"] + 1
                    result = {"ok": True}
                elif method == "session.send":
                    oid = "op-" + str(len(operations) + 1)
                    operations[oid] = params
                    result = {"operation_id": oid, "run_id": "run-" + oid}
                elif method == "approval.resolve":
                    assert params["approve"] is True
                    resolved.set()
                    result = {"ok": True}
                elif method == "operation.cancel":
                    result = {"ok": True}
                else:
                    raise AssertionError(method)
                return self.reply({"schema_version": 1, "ok": True, "data": result, "error": None})
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
                        (str(ROOT / "app/acp_stdio.py"), "--server-url", runtime_url), env_refs=("MYAGENT_CONTROL_TOKEN",))
    result = asyncio.run(run_target(target, "hello", str(tmp_path)))
    assert result["output"] == "answer"
    assert result["stop_reason"] == "end_turn"


def test_terminal_caller_returns_completed_result_and_resumes_same_session(runtime_url, tmp_path):
    receipt = tmp_path / "result.json"
    base = [sys.executable, str(ROOT / "app/acp_call.py"), "--server-url", runtime_url,
            "--cwd", str(tmp_path), "--prompt", "hello", "--result-file", str(receipt)]
    first = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", timeout=30, cwd=tmp_path)
    assert first.returncode == 0, first.stderr + first.stdout
    rows = [json.loads(line) for line in first.stdout.splitlines()]
    assert [row["event"] for row in rows] == ["started", "progress", "completed"]
    assert rows[-1]["status"] == "succeeded" and rows[-1]["output"] == "answer"
    assert rows[-1]["connected"] is False
    assert json.loads(receipt.read_text(encoding="utf-8")) == {key: value for key, value in rows[-1].items() if key != "event"}
    sid = rows[-1]["session_id"]
    saved = json.loads(receipt.read_text(encoding="utf-8"))
    assert saved["session_id"] == sid and saved["output"] == "answer"
    second = subprocess.run([*base, "--session-id", sid], capture_output=True, text=True,
                            encoding="utf-8", timeout=30, cwd=tmp_path)
    assert second.returncode == 0, second.stderr + second.stdout
    result = json.loads(second.stdout.splitlines()[-1])
    assert result["session_id"] == sid and result["session_action"] == "resume"
    assert result["output"] == "answer"


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
