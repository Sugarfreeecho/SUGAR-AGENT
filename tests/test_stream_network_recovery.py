"""Recover a half-open model socket without losing progress or repeating tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))


def test_idle_watchdog_starts_with_model_chunks_and_resets_on_progress(monkeypatch):
    import agent_loop

    clock = [100.0]
    monkeypatch.setattr(agent_loop.time, "monotonic", lambda: clock[0])
    watchdog = agent_loop._StreamActivityWatchdog(60)
    clock[0] += 600
    assert watchdog.stalled_error() is None  # First-token policy owns this wait.
    watchdog.touch()
    clock[0] += 59
    assert watchdog.stalled_error() is None
    watchdog.touch()
    clock[0] += 60
    error = watchdog.stalled_error()
    assert isinstance(error, TimeoutError)
    assert agent_loop._classify_api_error(error)["code"] == "NET"


@pytest.mark.parametrize("error_kind", ["empty_read", "protocol", "raw", "localized"])
def test_midstream_transport_failures_enter_network_recovery(error_kind):
    import agent_harness
    import agent_loop
    import httpx
    from agent_openai import HttpStreamTransportError

    error = {
        "empty_read": httpx.ReadError(""),
        "protocol": httpx.RemoteProtocolError("peer closed"),
        "raw": HttpStreamTransportError("raw httpx stream failed: "),
        "localized": HttpStreamTransportError("[WinError 10054] 远程主机强迫关闭了一个现有的连接。"),
    }[error_kind]
    assert agent_harness._is_network_connectivity_error(error)
    assert agent_loop._classify_api_error(error)["code"] == "NET"


@pytest.mark.parametrize("mode", ["partial", "facade", "closed_tool", "buffered", "exhausted"])
def test_agent_recovers_a_half_open_http_stream(tmp_path, mode):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), str(tmp_path), mode],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    (tmp_path / "scenario.log").write_text(result.stdout, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3500:]
    assert "half-open stream recovery passed" in result.stdout


def _run_http_scenario(scratch: Path, mode: str) -> None:
    import asyncio
    from contextlib import ExitStack
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import logging
    import threading
    from unittest.mock import patch

    os.environ.update({
        "MYAGENT_DOTENV_OVERRIDE": "0", "WORK_DIR": str(scratch),
        "MYAGENT_SECURITY_HOME": str(scratch / "security"), "MCP_ENABLED": "false",
        "MYAGENT_UI_CLOSED_NOTIFY": "0", "MYAGENT_TOOL_SEARCH": "off",
        "STREAM_WORKER_IDLE_TIMEOUT_SEC": "1", "STREAM_WORKER_ABORT_TIMEOUT_SEC": "0.1",
        "NETWORK_RECONNECT_MAX_ATTEMPTS": "1",
    })
    import agent_loop as agent
    import agent_harness as harness
    from openai import OpenAI
    from runtime_v2 import RuntimeHistoryOps

    logging.basicConfig(level=logging.WARNING)
    release_old_socket = threading.Event()
    old_socket_finished = threading.Event()
    requests = []
    tool_path = scratch / "written-once.txt"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(payload)
            first = len(requests) == 1
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            def send(delta, finish=None):
                frame = ("data: " + json.dumps({"id": "local-stream", "object": "chat.completion.chunk",
                    "created": 1, "model": "local-model", "choices": [
                        {"index": 0, "delta": delta, "finish_reason": finish}]}) + "\n\n").encode()
                self.wfile.write(f"{len(frame):x}\r\n".encode() + frame + b"\r\n")
                self.wfile.flush()

            try:
                if first or mode == "exhausted":
                    if mode == "closed_tool":
                        send({"tool_calls": [{"index": 0, "id": "write-once", "type": "function",
                            "function": {"name": "write_file", "arguments": json.dumps({
                                "path": str(tool_path), "content": "one write"})}}]})
                    else:
                        send({"content": "First half. "})
                    # Keep HTTP open without raising any transport exception.
                    assert release_old_socket.wait(20)
                    send({"content": "STALE OUTPUT MUST BE IGNORED"})
                elif mode == "buffered":
                    # Total generation exceeds the idle threshold, but each
                    # chunk is timely even when no UI deltas are emitted.
                    for text in ("Second ", "half ", "complete."):
                        threading.Event().wait(0.6)
                        send({"content": text})
                else:
                    send({"content": "Second half complete."})
                send({}, "stop")
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                if first:
                    old_socket_finished.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    http = harness.RequestResponseLogger(trust_env=False, timeout=30)
    client = OpenAI(api_key="local-test", base_url=f"http://127.0.0.1:{server.server_port}/v1",
                    http_client=http, max_retries=0)
    model_client = client
    if mode == "facade":
        from llm import OpenAICompatibleTransport
        model_client = harness.ExecutorLLMClient([{
            "client": client, "transport": OpenAICompatibleTransport(client),
            "provider": "openai-compatible", "model": "local-model",
            "max_output_tokens": 1024, "temperature": 0,
        }])
    sid, *_ = harness.session_manager.get_or_create_session(work_dir=str(scratch))
    events = []
    model_config = lambda _sid: (model_client, "local-model", 1024, 1_000_000)

    async def collect():
        async for event in agent.astream_events("Finish the task.", session_id=sid):
            events.append(event)

    async def scenario():
        await asyncio.wait_for(collect(), 12)
        # Release the obsolete connection only after the replacement completed.
        # Its late chunks and cleanup must not publish into the new iteration.
        release_old_socket.set()
        assert await asyncio.to_thread(old_socket_finished.wait, 3)
        await asyncio.sleep(0.1)

    try:
        with ExitStack() as patches:
            for module in (agent, harness):
                patches.enter_context(patch.object(module, "resolve_executor_config_for_session", model_config))
                patches.enter_context(patch.object(module, "executor_http_client", http))
            patches.enter_context(patch.object(harness, "warm_llm_connections_if_stale", lambda: False))
            patches.enter_context(patch.object(agent, "setup_logging", lambda *a, **k: None))
            patches.enter_context(patch.object(agent, "schedule_session_title_generation", lambda *a: False))
            patches.enter_context(patch.object(agent, "machine_network_available", lambda: True))
            if mode == "buffered":
                original_policy = agent._llm_runtime_policy
                patches.enter_context(patch.object(agent, "_llm_runtime_policy", lambda emit: {
                    **original_policy(emit), "use_stream": True, "emit_deltas": False,
                }))
            asyncio.run(scenario())
        assert len(requests) == 2, len(requests)
        if mode == "exhausted":
            assert any(event["type"] == "run_failed" for event in events), events[-10:]
            assert any(event["type"] == "error" and '"c": "NET"' in event["content"]
                       for event in events), events[-10:]
            print("half-open stream recovery passed")
            return
        assert not any(event["type"] in {"error", "run_failed"} for event in events), events
        assert any(event["type"] == "run_finished" for event in events), events[-10:]
        final = next(event["content"] for event in events if event["type"] == "final")
        assert "Second half complete." in final, final
        assert "STALE OUTPUT" not in json.dumps(events), events[-10:]
        if mode == "closed_tool":
            assert tool_path.read_text(encoding="utf-8") == "one write"
            assert sum(event["type"] == "tool_call" for event in events) == 1
            assert any(message.get("role") == "tool" for message in requests[1]["messages"])
        elif mode in {"partial", "facade"}:
            assert "First half." in final, final
            assert "First half." in json.dumps(requests[1]["messages"])
            ops = RuntimeHistoryOps(harness.session_manager.sessions_dir,
                path_resolver=harness.session_manager._resolve_session_path)
            assert "First half." in json.dumps([event.payload for event in ops.event_log.read_all(sid)])
        print("half-open stream recovery passed")
    finally:
        release_old_socket.set()
        server.shutdown()
        client.close()


if __name__ == "__main__":
    _run_http_scenario(Path(sys.argv[1]), sys.argv[2])
