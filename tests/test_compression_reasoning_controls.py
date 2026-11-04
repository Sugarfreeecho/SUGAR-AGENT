"""Compression controls apply to every attempt without changing session settings."""
import copy

import pytest


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("provider,model,expected_effort", [
    ("openai", "gpt-reasoning", "low"),
    ("openai-compatible", "compatible-reasoning", "low"),
    ("anthropic", "claude-sonnet-4", "low"),
    ("openai-compatible", "deepseek-v4.1-flash", None),
])
def test_compression_controls_cover_fallback_and_preserve_main_settings(
    monkeypatch, streaming, provider, model, expected_effort,
):
    import agent_harness as harness
    from llm import LLMRequestContext, LLMRequestPurpose, TransportEvent

    calls = []

    class Transport:
        def __init__(self, name):
            self.name = name

        def complete_text(self, **kwargs):
            calls.append((self.name, kwargs))
            if self.name == "primary":
                raise RuntimeError("primary unavailable")
            return {"text": "summary"}

        def stream_completion(self, **kwargs):
            calls.append((self.name, kwargs))
            if self.name == "primary":
                raise RuntimeError("primary unavailable")
            yield TransportEvent("content_delta", text="summary")
            yield TransportEvent("finish", finish_reason="stop")

    monkeypatch.setattr(harness, "_candidate_retry_policy", lambda: (0, 0))
    candidates = [
        {
            "provider": provider,
            "model": model,
            "transport": Transport(name),
            "reasoning_effort": effort,
            "extra_body": {
                "thinking": {"type": "enabled", "budget_tokens": 16000},
                "reasoning_effort": effort,
                "reasoning": {"effort": effort, "summary": "auto"},
                "metadata": {"tag": name},
            },
        }
        for name, effort in (("primary", "high"), ("backup", "max"))
    ]
    original_controls = [copy.deepcopy(candidate["extra_body"]) for candidate in candidates]
    client = harness.ExecutorLLMClient(candidates)

    def complete(purpose):
        kwargs = {
            "messages": [],
            "request_context": LLMRequestContext(purpose=purpose),
        }
        if streaming:
            return "".join(event.text for event in client.stream_completion(**kwargs)
                           if event.kind == "content_delta")
        return client.complete_text(**kwargs)["text"]

    assert complete(LLMRequestPurpose.SUMMARY) == "summary"
    assert [name for name, _kwargs in calls] == ["primary", "backup"]
    for name, kwargs in calls:
        assert kwargs.get("reasoning_effort") == expected_effort
        extra = kwargs["extra_body"]
        assert extra["metadata"] == {"tag": name}
        assert "budget_tokens" not in extra["thinking"]
        if expected_effort is None:
            assert extra["thinking"] == {"type": "disabled"}
            assert "reasoning_effort" not in extra
        else:
            assert extra["reasoning_effort"] == "low"
            assert extra["reasoning"] == {"effort": "low", "summary": "auto"}

    assert [candidate["extra_body"] for candidate in candidates] == original_controls
    calls.clear()
    assert complete(LLMRequestPurpose.MAIN) == "summary"
    assert [kwargs["reasoning_effort"] for _name, kwargs in calls] == ["high", "max"]
    assert [kwargs["extra_body"] for _name, kwargs in calls] == original_controls


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("extra_body", [None, {"thinking": {"type": "disabled"}}])
def test_compression_does_not_enable_effort_for_non_thinking_chat(streaming, extra_body):
    import agent_harness as harness
    from llm import LLMRequestContext, LLMRequestPurpose, TransportEvent

    calls = []

    class Transport:
        def complete_text(self, **kwargs):
            calls.append(kwargs)
            return {"text": "summary"}

        def stream_completion(self, **kwargs):
            calls.append(kwargs)
            yield TransportEvent("content_delta", text="summary")

    client = harness.ExecutorLLMClient([{
        "provider": "openai-compatible", "model": "plain-chat",
        "transport": Transport(), "extra_body": extra_body,
    }])
    kwargs = {
        "messages": [],
        "request_context": LLMRequestContext(purpose=LLMRequestPurpose.SUMMARY),
    }
    if streaming:
        list(client.stream_completion(**kwargs))
    else:
        client.complete_text(**kwargs)
    assert len(calls) == 1
    assert "reasoning_effort" not in calls[0]
    assert calls[0].get("extra_body") == extra_body
