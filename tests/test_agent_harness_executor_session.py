import pytest


def test_executor_chat_complete_uses_session_model(monkeypatch):
    import agent_harness

    calls = []

    class Message:
        content = "ok"
        tool_calls = None

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    def fake_resolve(session_id):
        calls.append(("resolve", session_id))
        return "client-for-session", "model-for-session", 123, 456

    def fake_chat_completion(client, model, messages, **kwargs):
        calls.append((client, model, kwargs.get("max_tokens")))
        return Response()

    monkeypatch.setattr(agent_harness, "resolve_executor_config_for_session", fake_resolve)
    monkeypatch.setattr(agent_harness, "chat_completion", fake_chat_completion)

    assert agent_harness.executor_chat_complete([], session_id="s1") == "ok"
    assert calls == [
        ("resolve", "s1"),
        ("client-for-session", "model-for-session", 123),
    ]


def test_executor_text_complete_uses_session_model(monkeypatch):
    import agent_harness

    calls = []

    def fake_resolve(session_id):
        calls.append(("resolve", session_id))
        return "client-for-session", "model-for-session", 321, 654

    def fake_single_turn(client, model, prompt, **kwargs):
        calls.append((client, model, prompt, kwargs.get("max_tokens")))
        return "edited", None

    monkeypatch.setattr(agent_harness, "resolve_executor_config_for_session", fake_resolve)
    monkeypatch.setattr(agent_harness, "single_turn_text_completion", fake_single_turn)

    assert agent_harness.executor_text_complete("prompt", session_id="s1") == "edited"
    assert calls == [
        ("resolve", "s1"),
        ("client-for-session", "model-for-session", "prompt", 321),
    ]


def test_fallback_client_switches_after_api_error_and_preserves_request_cap():
    import agent_harness

    calls = []

    class _Completions:
        def __init__(self, name, error=None):
            self.name = name
            self.error = error

        def create(self, **kwargs):
            calls.append((self.name, kwargs["model"], kwargs["max_tokens"]))
            if self.error:
                raise self.error
            return "ok"

    class _Client:
        def __init__(self, completions):
            self.chat = type("Chat", (), {"completions": completions})()

    candidates = [
        {
            "client": _Client(_Completions("primary", RuntimeError("bad api"))),
            "model": "primary-model",
            "max_output_tokens": 4096,
        },
        {
            "client": _Client(_Completions("backup")),
            "model": "backup-model",
            "max_output_tokens": 1024,
        },
    ]
    switched = []
    client = agent_harness.FallbackOpenAIClient(candidates)
    client.set_status_callback(switched.append)

    result = client.chat.completions.create(model="ignored", max_tokens=256)

    assert result == "ok"
    assert calls == [
        ("primary", "primary-model", 256),
        ("backup", "backup-model", 256),
    ]
    assert switched[0]["from_model"] == "primary-model"
    assert switched[0]["to_model"] == "backup-model"


def test_fallback_client_marks_media_failure_and_routes_to_next_profile():
    import agent_harness

    calls = []
    marked = []
    statuses = []

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            content = kwargs["messages"][0]["content"]
            if isinstance(content, list):
                raise ValueError("This model does not support image input")
            return "ok"

    class _Client:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": _Completions()})()

    candidates = [
        {
            "client": _Client(),
            "model": "primary-model",
            "max_output_tokens": 4096,
            "multimodal_input": True,
            "mark_multimodal_failed": marked.append,
        },
        {
            "client": _Client(),
            "model": "backup-model",
            "max_output_tokens": 4096,
            "multimodal_input": False,
        },
    ]
    client = agent_harness.FallbackOpenAIClient(candidates)
    client.set_status_callback(statuses.append)

    result = client.chat.completions.create(
        model="ignored",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": '分析 "D:\\screen.png"'},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAA"},
                    },
                ],
            }
        ],
    )

    assert result == "ok"
    assert len(calls) == 2
    assert candidates[0]["multimodal_input"] is False
    assert len(marked) == 1
    assert isinstance(calls[0]["messages"][0]["content"], list)
    retry_user = next(
        message for message in calls[1]["messages"] if message["role"] == "user"
    )
    retry_system = next(
        message for message in calls[1]["messages"] if message["role"] == "system"
    )
    assert 'D:\\screen.png' in retry_user["content"]
    assert "task 工具" in retry_system["content"]
    assert calls[1]["messages"][-1]["role"] == "user"
    assert statuses[0]["multimodal_fallback"] is True


def test_fallback_client_keeps_text_profile_and_injects_task_delegation():
    import agent_harness

    calls = []
    statuses = []

    class _Completions:
        def __init__(self, name):
            self.name = name

        def create(self, **kwargs):
            calls.append((self.name, kwargs))
            return "ok"

    class _Client:
        def __init__(self, name):
            self.chat = type("Chat", (), {"completions": _Completions(name)})()

    candidates = [
        {
            "client": _Client("text"),
            "model": "text-model",
            "max_output_tokens": 4096,
            "input_modalities": ["text", "audio"],
        },
        {
            "client": _Client("vision"),
            "model": "vision-model",
            "max_output_tokens": 4096,
            "input_modalities": ["text", "image"],
        },
    ]
    client = agent_harness.FallbackOpenAIClient(candidates)
    client.set_status_callback(statuses.append)

    result = client.chat.completions.create(
        model="ignored",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [{
                "type": "image_url",
                "image_url": {"url": "https://example.com/image.png"},
            }],
        }],
    )

    assert result == "ok"
    assert [name for name, _kwargs in calls] == ["text"]
    text_messages = calls[0][1]["messages"]
    assert not any(
        isinstance(part, dict) and part.get("type") == "image_url"
        for message in text_messages
        for part in (message.get("content") if isinstance(message.get("content"), list) else [])
    )
    system_message = next(message for message in text_messages if message["role"] == "system")
    user_message = next(message for message in text_messages if message["role"] == "user")
    assert "task 工具" in system_message["content"]
    assert "model_profile_id" in system_message["content"]
    assert "https://example.com/image.png" in user_message["content"]
    assert statuses == []


def test_chat_completion_does_not_replace_preferred_text_profile_for_image():
    import agent_harness
    import agent_openai
    from agent_messages import UserMessage

    calls = []

    class _Completions:
        def __init__(self, name):
            self.name = name

        def create(self, **kwargs):
            calls.append((self.name, kwargs))
            return type("Response", (), {"usage": None})()

    class _Client:
        def __init__(self, name):
            self.chat = type("Chat", (), {"completions": _Completions(name)})()

    client = agent_harness.FallbackOpenAIClient([
        {
            "client": _Client("text"),
            "model": "text-model",
            "max_output_tokens": 4096,
            "input_modalities": ["text"],
        },
        {
            "client": _Client("vision"),
            "model": "vision-model",
            "max_output_tokens": 4096,
            "input_modalities": ["text", "image"],
        },
    ])

    prompt = "分析 https://example.com/image.png"
    agent_openai.chat_completion(
        client,
        "text-model",
        [UserMessage(content=prompt)],
        temperature=0,
        max_tokens=256,
    )

    assert [name for name, _kwargs in calls] == ["text"]
    sent = calls[0][1]["messages"]
    assert prompt in next(message for message in sent if message["role"] == "user")["content"]
    system = next(message for message in sent if message["role"] == "system")["content"]
    assert "task 工具" in system
    assert "model_profile_id" in system


def test_fallback_candidates_consume_shared_logical_request_budget(monkeypatch):
    import agent_harness
    import agent_openai
    from agent_messages import UserMessage

    monkeypatch.setattr(agent_openai, "OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC", 0)
    monkeypatch.setattr(agent_openai, "OPENAI_MAX_RETRIES", 1)
    monkeypatch.setattr(agent_openai, "OPENAI_TOTAL_REQUEST_BUDGET", 2)
    calls = []

    class _Completions:
        def __init__(self, name):
            self.name = name

        def create(self, **_kwargs):
            calls.append(self.name)
            raise RuntimeError(f"{self.name} failed")

    class _Client:
        def __init__(self, name):
            self.chat = type("Chat", (), {"completions": _Completions(name)})()

    client = agent_harness.FallbackOpenAIClient([
        {"client": _Client("one"), "model": "one", "max_output_tokens": 128},
        {"client": _Client("two"), "model": "two", "max_output_tokens": 128},
        {"client": _Client("three"), "model": "three", "max_output_tokens": 128},
    ])

    with pytest.raises(RuntimeError, match="budget"):
        agent_openai.chat_completion(
            client,
            "one",
            [UserMessage(content="hello")],
            temperature=0,
            max_tokens=32,
        )

    assert calls == ["one", "two"]
