import sys
import threading
import time
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


def _content_chunk(text):
    delta = SimpleNamespace(content=text, reasoning_content=None, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason=None, stop_reason=None)
    return SimpleNamespace(choices=[choice], usage=None, model="test-model")


class _GateStream:
    def __init__(self, gate, text):
        self.gate = gate
        self.text = text
        self.closed = False
        self.sent = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.sent:
            raise StopIteration
        self.gate.wait(timeout=2)
        if self.closed:
            raise StopIteration
        self.sent = True
        return _content_chunk(self.text)

    def close(self):
        self.closed = True
        self.gate.set()


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


def test_stream_worker_hedges_slow_first_token_and_uses_retry_winner(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage

    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC", 0.01)
    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_MAX_RETRIES", 1)
    blocked_gate = threading.Event()
    primary = _GateStream(blocked_gate, "slow")
    hedge = iter([_content_chunk("fast")])
    streams = [primary, hedge]
    create_lock = threading.Lock()

    def create(**_kwargs):
        with create_lock:
            return streams.pop(0)

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    q = Queue()

    agent_openai.run_chat_completion_stream_worker(
        q,
        client,
        "test-model",
        [UserMessage(content="hello")],
        temperature=0,
        max_tokens=32,
    )

    rows = []
    while not q.empty():
        rows.append(q.get())
    turn = next(row[1] for row in rows if row and row[0] == "turn")
    timings = [row[1] for row in rows if row and row[0] == "stream_timing"]

    assert turn.content == "fast"
    assert primary.closed is True
    assert any(row.get("step") == "first_token_hedge_started" for row in timings)
    assert any(
        row.get("step") == "first_token_hedge_winner" and row.get("winner") == "hedge_1"
        for row in timings
    )


def test_stream_worker_keeps_primary_and_closes_slower_retry(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage

    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC", 0.01)
    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_MAX_RETRIES", 1)
    primary_gate = threading.Event()
    hedge_gate = threading.Event()
    primary = _GateStream(primary_gate, "primary")
    hedge = _GateStream(hedge_gate, "retry")
    streams = [primary, hedge]
    create_lock = threading.Lock()

    def create(**_kwargs):
        with create_lock:
            return streams.pop(0)

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    q = Queue()
    release_primary = threading.Timer(0.04, primary_gate.set)
    release_primary.start()
    try:
        agent_openai.run_chat_completion_stream_worker(
            q,
            client,
            "test-model",
            [UserMessage(content="hello")],
            temperature=0,
            max_tokens=32,
        )
    finally:
        release_primary.cancel()

    rows = []
    while not q.empty():
        rows.append(q.get())
    turn = next(row[1] for row in rows if row and row[0] == "turn")
    timings = [row[1] for row in rows if row and row[0] == "stream_timing"]

    assert turn.content == "primary"
    assert hedge.closed is True
    assert any(
        row.get("step") == "first_token_hedge_winner" and row.get("winner") == "primary"
        for row in timings
    )


def test_stream_worker_can_start_two_hedged_retries(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage

    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC", 0.01)
    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_MAX_RETRIES", 2)
    primary = _GateStream(threading.Event(), "primary")
    first_retry = _GateStream(threading.Event(), "retry-one")
    second_retry = iter([_content_chunk("retry-two")])
    streams = [primary, first_retry, second_retry]
    create_lock = threading.Lock()
    calls = []

    def create(**_kwargs):
        with create_lock:
            calls.append(1)
            return streams.pop(0)

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    q = Queue()

    agent_openai.run_chat_completion_stream_worker(
        q,
        client,
        "test-model",
        [UserMessage(content="hello")],
        temperature=0,
        max_tokens=32,
    )

    rows = []
    while not q.empty():
        rows.append(q.get())
    turn = next(row[1] for row in rows if row and row[0] == "turn")
    timings = [row[1] for row in rows if row and row[0] == "stream_timing"]

    assert len(calls) == 3
    assert turn.content == "retry-two"
    assert primary.closed is True
    assert first_retry.closed is True
    assert [
        row.get("hedge_index")
        for row in timings
        if row.get("step") == "first_token_hedge_started"
    ] == [1, 2]
    assert any(
        row.get("step") == "first_token_hedge_winner"
        and row.get("winner") == "hedge_2"
        and row.get("hedges_started") == 2
        for row in timings
    )


def test_stream_worker_does_not_duplicate_fast_request(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage

    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC", 0.2)
    calls = []

    def create(**_kwargs):
        calls.append(1)
        return iter([_content_chunk("ok")])

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    q = Queue()

    started = time.monotonic()
    agent_openai.run_chat_completion_stream_worker(
        q,
        client,
        "test-model",
        [UserMessage(content="hello")],
        temperature=0,
        max_tokens=32,
    )

    assert calls == [1]
    assert time.monotonic() - started < 0.2
