"""The real one-shot Agent path must send HTTP and persist its tool result."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_nonstream_agent_reaches_http_and_continues_after_a_durable_tool(tmp_path):
    root = Path(__file__).resolve().parents[1]
    report = tmp_path / "nonstream.json"
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(root/"scripts/benchmark_agent_interround.py"),
         "--non-stream", "--steps", "1", "--tools-per-round", "1",
         "--only-case", "light_short", "--stress-workers", "0", "--output", str(report)],
        cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stdout[-6000:]
    data = json.loads(report.read_text(encoding="utf-8"))
    case = data["cases"][0]
    assert data["stream"]["enabled"] is False
    assert case["successful_tools"] == 1 and case["http_requests"] == 2
    assert case["tool_to_http_send"]["samples"] == 1
    assert all(request["status"] == "completed" and request["output_mode"] == "non_stream"
               for request in case["requests"])
    assert all(trace["http_send_observed"] and "worker_executor_queue_ms" in trace
               for trace in case["traces"])
    followup = case["traces"][1]["anchors"]
    assert followup["tool_returned"] <= followup["tool_result_committed"] <= followup["http_send_entered"]
