import json
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import agent_openai
from agent_request_timing import RequestPreparationTrace, request_timing_scope


def test_fast_encoding_preserves_json_values_and_input():
    payload = {"messages": [{"role": "user", "content": "中文\n emoji 🐈 / \""}],
               "tools": [{"type": "function", "function": {"name": "example", "parameters": {"type": "object"}}}],
               "numbers": [0, -0.0, 1e-200, 1.2345678901234567, -(1 << 63), (1 << 64) - 1],
               "nested": [None, True, False, {}, []]}
    if agent_openai._wire_orjson is None:
        pytest.skip("Optional fast JSON encoder unavailable")
    before = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    encoded = agent_openai._fast_wire_json(payload)
    assert isinstance(encoded, bytes)
    assert json.loads(encoded) == json.loads(before)
    assert json.dumps(payload, ensure_ascii=False, allow_nan=False) == before


@pytest.mark.parametrize("payload", [float("nan"), float("inf"), float("-inf"), 1 << 80,
                                     {1: "integer key"}, {"tuple": (1, 2)}, {"object": object()}])
def test_uncommon_values_use_original_encoder(payload):
    assert agent_openai._fast_wire_json(payload) is None


@pytest.mark.parametrize("fast", [False, True])
def test_real_httpx_send_preserves_body_headers_and_timing(monkeypatch, fast):
    if fast and agent_openai._wire_orjson is None:
        pytest.skip("Optional fast JSON encoder unavailable")
    if not fast:
        monkeypatch.setattr(agent_openai, "_wire_orjson", None)
    captured = []
    def endpoint(request):
        captured.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=b'data: {"choices": [{"delta": {"content": "OK"}}]}\n\ndata: [DONE]\n\n')
    payload = {"messages": [{"role": "user", "content": "中文"}], "stream": True}
    trace = RequestPreparationTrace("s", "r", 1)
    with httpx.Client(transport=httpx.MockTransport(endpoint)) as http:
        with request_timing_scope(trace):
            chunks = list(agent_openai._http_stream_chat_completion(
                SimpleNamespace(_client=http), url="https://benchmark.invalid/chat/completions",
                payload=payload, headers={"X-Benchmark": "yes"}, timeout=1))
    assert chunks[0].choices[0].delta.content == "OK"
    assert len(captured) == 1
    assert json.loads(captured[0].content) == payload
    assert captured[0].headers["content-type"] == "application/json"
    assert captured[0].headers["x-benchmark"] == "yes"
    assert int(captured[0].headers["content-length"]) == len(captured[0].content)
    assert ("wire_json_encode_ms" in trace.snapshot()) == fast


def test_custom_content_type_is_preserved_and_nonfinite_is_not_sent():
    captured = []
    def endpoint(request):
        captured.append(request)
        return httpx.Response(200, content=b"data: [DONE]\n\n")
    with httpx.Client(transport=httpx.MockTransport(endpoint)) as http:
        client = SimpleNamespace(_client=http)
        list(agent_openai._http_stream_chat_completion(
            client, url="https://benchmark.invalid/chat/completions", payload={"n": 1},
            headers={"content-type": "application/custom+json"}, timeout=1))
        with pytest.raises(agent_openai.HttpStreamTransportError):
            list(agent_openai._http_stream_chat_completion(
                client, url="https://benchmark.invalid/chat/completions", payload={"n": float("nan")},
                headers={}, timeout=1))
    assert len(captured) == 1
    assert captured[0].headers["content-type"] == "application/custom+json"
