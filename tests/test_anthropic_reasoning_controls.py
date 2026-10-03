import json

import httpx
import pytest

from llm.transport import AnthropicMessagesTransport


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
def test_anthropic_wire_uses_adaptive_thinking_and_native_effort(stream, effort):
    captured = []
    def handle(request):
        captured.append(json.loads(request.content))
        if stream:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text='data: {"type":"message_stop"}\n\n')
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"})
    client = httpx.Client(transport=httpx.MockTransport(handle))
    transport = AnthropicMessagesTransport(api_key="fixture", base_url="https://fixture.invalid", http_client=client)
    request = {"model": "claude-opus-5", "messages": [{"role": "user", "content": "Example"}], "max_tokens": 8192, "temperature": 0.7,
               "reasoning_effort": effort, "extra_body": {"thinking": {"type": "enabled"}, "metadata": {"user_id": "fixture"}, "output_config": {"fixture": True}}}
    if stream:
        list(transport.stream_completion(**request))
    else:
        assert transport.complete_text(**request)["text"] == "ok"
    body = captured[0]
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"fixture": True, "effort": effort}
    assert body["metadata"] == {"user_id": "fixture"}
    assert "temperature" not in body
    assert request["extra_body"]["thinking"] == {"type": "enabled"}, "request translation must not mutate the profile"


@pytest.mark.parametrize("effort,budget", [("low", 1024), ("medium", 4096), ("max", 5999)])
def test_older_anthropic_models_receive_bounded_thinking_budget(effort, budget):
    captured = []
    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"content": [], "stop_reason": "end_turn"})
    transport = AnthropicMessagesTransport(api_key="fixture", base_url="https://fixture.invalid", http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    transport.complete_text(model="claude-sonnet-4", messages=[], max_tokens=6000,
                            reasoning_effort=effort, extra_body={"thinking": {"type": "enabled"}})
    assert captured[0]["thinking"] == {"type": "enabled", "budget_tokens": budget}
    assert "output_config" not in captured[0]
