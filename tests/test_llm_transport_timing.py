import sys
from pathlib import Path
from queue import Queue
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _Observer:
    def __init__(self):
        self.started = False
        self.finished = False

    def start_transport_trace(self):
        self.started = True

    def snapshot_transport_trace(self):
        return {
            "elapsed_ms": 20,
            "events": [
                {"event": "connection.connect_tcp.started", "at_ms": 1},
                {"event": "connection.connect_tcp.complete", "at_ms": 6},
                {"event": "http11.send_request_body.started", "at_ms": 7},
                {"event": "http11.send_request_body.complete", "at_ms": 9},
                {"event": "http11.receive_response_headers.started", "at_ms": 9},
                {"event": "http11.receive_response_headers.complete", "at_ms": 19},
            ],
        }

    def finish_transport_trace(self):
        self.finished = True


def test_stream_worker_reports_transport_breakdown_at_first_delta():
    from agent_messages import UserMessage
    from agent_openai import run_chat_completion_stream_worker

    delta = SimpleNamespace(content="ok", reasoning_content=None, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason=None, stop_reason=None)
    chunk = SimpleNamespace(choices=[choice], usage=None, model="test-model")
    completions = SimpleNamespace(create=lambda **_kwargs: iter([chunk]))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    observer = _Observer()
    q = Queue()

    run_chat_completion_stream_worker(
        q,
        client,
        "test-model",
        [UserMessage(content="hello")],
        temperature=0,
        max_tokens=32,
        transport_observer=observer,
    )

    rows = []
    while not q.empty():
        rows.append(q.get())
    timing_payloads = [row[1] for row in rows if row and row[0] == "stream_timing"]
    breakdown = next(row for row in timing_payloads if row.get("step") == "transport_breakdown")

    assert observer.started is True
    assert observer.finished is True
    assert breakdown["connection_connect_tcp_ms"] == 5
    assert breakdown["http11_send_request_body_ms"] == 2
    assert breakdown["http11_receive_response_headers_ms"] == 10


def test_stream_worker_usage_includes_requested_tps_denominator_phases():
    from agent_messages import UserMessage
    from agent_openai import run_chat_completion_stream_worker

    delta = SimpleNamespace(content="ok", reasoning_content=None, tool_calls=None)
    content_chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=delta, finish_reason=None, stop_reason=None)],
        usage=None,
        model="test-model",
    )
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    usage_chunk = SimpleNamespace(choices=[], usage=usage, model="test-model")
    completions = SimpleNamespace(create=lambda **_kwargs: iter([content_chunk, usage_chunk]))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    q = Queue()

    run_chat_completion_stream_worker(
        q, client, "test-model", [UserMessage(content="hello")],
        temperature=0, max_tokens=32,
    )

    rows = []
    while not q.empty():
        rows.append(q.get())
    usage_payload = next(row[1] for row in rows if row and row[0] == "usage")
    timing = usage_payload["_timing"]
    assert set(timing) == {
        "first_token_wait_ms", "token_generation_ms", "usage_return_ms", "measured_total_ms"
    }
    assert timing["measured_total_ms"] == (
        timing["first_token_wait_ms"]
        + timing["token_generation_ms"]
        + timing["usage_return_ms"]
    )
