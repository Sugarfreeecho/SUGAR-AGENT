import sys
from pathlib import Path
from queue import Queue
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _client_with_create(create, *, multimodal=True, mark_failed=None):
    completions = SimpleNamespace(create=create)
    return SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
        completions=completions,
        _myagent_multimodal_input=multimodal,
        _myagent_mark_multimodal_failed=mark_failed,
    )


def _message_with_role(messages, role):
    return next(message for message in messages if message.get("role") == role)


def test_media_error_detection_accepts_common_provider_wording():
    import agent_openai

    accepted = [
        "This model does not support image input",
        "Model doesn't support image inputs",
        "Model does not support images",
        "Invalid content: image_url is not supported by this model",
        "This endpoint cannot process video_url content",
        "Multimodal input is unsupported",
        "当前模型不支持图片输入",
        {"error": {"code": "unsupported_value", "message": "input_audio is unavailable"}},
    ]

    for value in accepted:
        exc = ValueError(str(value))
        if isinstance(value, dict):
            exc.body = value
        assert agent_openai._is_media_input_error(exc), value

    assert not agent_openai._is_media_input_error(
        ValueError("messages.0.content: expected string")
    )
    assert not agent_openai._is_media_input_error(
        ValueError("unsupported image file format")
    )
    assert agent_openai._media_error_modalities(
        ValueError("image_url is not supported"), {"image", "audio"}
    ) == {"image"}


def test_text_only_fallback_preserves_original_local_media_path(tmp_path):
    import agent_openai
    from agent_messages import UserMessage

    image_path = tmp_path / "screen shot.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    prompt = f'请分析 "{image_path}"'
    messages = [UserMessage(content=prompt)]

    expanded = agent_openai.messages_to_openai_params(messages)
    assert isinstance(expanded[0]["content"], list)
    assert any(part.get("type") == "image_url" for part in expanded[0]["content"])

    fallback = agent_openai._messages_to_text_only_params(messages)
    assert fallback[-1] == {"role": "user", "content": prompt}
    assert fallback[0]["role"] == "system"
    assert "task 工具" in fallback[0]["content"]
    assert "subagent" in fallback[0]["content"]
    assert "图片" in fallback[0]["content"]
    assert "model_profile_id" in fallback[0]["content"]
    assert "双引号" in fallback[0]["content"]


def test_fallback_instruction_does_not_create_trailing_system_turn():
    import agent_openai

    original = [
        {"role": "system", "content": "基础系统提示"},
        {"role": "user", "content": "分析图片路径"},
    ]

    fallback = agent_openai._inject_multimodal_fallback_instruction(original)

    assert [message["role"] for message in fallback] == ["system", "user"]
    assert "基础系统提示" in fallback[0]["content"]
    assert "task 工具" in fallback[0]["content"]
    assert fallback[-1] == original[-1]


def test_structured_media_without_local_path_uses_placeholder():
    import agent_openai
    from agent_messages import UserMessage

    messages = [
        UserMessage(
            content=[
                {"type": "text", "text": "请分析"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,AAA"},
                },
            ]
        )
    ]

    fallback = agent_openai._messages_to_text_only_params(messages)

    user_message = _message_with_role(fallback, "user")
    system_message = _message_with_role(fallback, "system")
    assert "请分析" in user_message["content"]
    assert "当前模型不支持" in user_message["content"]
    assert "data:image/png" not in user_message["content"]
    assert "task 工具" in system_message["content"]


def test_nonstream_media_fallback_has_its_own_retry_and_preserves_path(
    monkeypatch,
    tmp_path,
):
    import agent_openai
    from agent_messages import UserMessage

    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    prompt = f'分析 "{image_path}"'
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if isinstance(kwargs["messages"][0]["content"], list):
            raise ValueError("This model does not support image input")
        return SimpleNamespace(usage=None, choices=[])

    monkeypatch.setattr(agent_openai, "OPENAI_MAX_RETRIES", 1)

    agent_openai.chat_completion(
        _client_with_create(create),
        "text-model",
        [UserMessage(content=prompt)],
        temperature=0,
        max_tokens=8,
    )

    assert len(calls) == 2
    assert _message_with_role(calls[1]["messages"], "user")["content"] == prompt
    assert "task 工具" in _message_with_role(
        calls[1]["messages"], "system"
    )["content"]


def test_text_only_profile_skips_media_request_and_keeps_path(tmp_path):
    import agent_openai
    from agent_messages import UserMessage

    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    prompt = f'分析 "{image_path}"'
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(usage=None, choices=[])

    agent_openai.chat_completion(
        _client_with_create(create, multimodal=False),
        "text-model",
        [UserMessage(content=prompt)],
        temperature=0,
        max_tokens=8,
    )

    assert len(calls) == 1
    assert _message_with_role(calls[0]["messages"], "user")["content"] == prompt
    assert "task 工具" in _message_with_role(
        calls[0]["messages"], "system"
    )["content"]
    assert not agent_openai._api_messages_have_media(calls[0]["messages"])


def test_media_failure_disables_client_for_later_requests(tmp_path):
    import agent_openai
    from agent_messages import UserMessage

    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    prompt = f'分析 "{image_path}"'
    calls = []
    failures = []

    def create(**kwargs):
        calls.append(kwargs)
        if agent_openai._api_messages_have_media(kwargs["messages"]):
            raise ValueError("This model does not support image input")
        return SimpleNamespace(usage=None, choices=[])

    client = _client_with_create(
        create,
        multimodal=True,
        mark_failed=failures.append,
    )
    messages = [UserMessage(content=prompt)]

    agent_openai.chat_completion(
        client,
        "text-model",
        messages,
        temperature=0,
        max_tokens=8,
    )
    agent_openai.chat_completion(
        client,
        "text-model",
        messages,
        temperature=0,
        max_tokens=8,
    )

    assert len(calls) == 3
    assert agent_openai._api_messages_have_media(calls[0]["messages"])
    assert not agent_openai._api_messages_have_media(calls[1]["messages"])
    assert not agent_openai._api_messages_have_media(calls[2]["messages"])
    assert client._myagent_multimodal_input is True
    assert "image" not in client._myagent_input_modalities
    assert {"audio", "video", "file"} <= set(client._myagent_input_modalities)
    assert len(failures) == 1


def test_remote_image_url_is_expanded_only_for_image_capable_client():
    import agent_openai
    from agent_messages import UserMessage

    prompt = "分析 ![dashboard](https://cdn.example.com/dashboard.png?size=large)"
    messages = [UserMessage(content=prompt)]
    image_calls = []
    text_calls = []

    image_client = _client_with_create(lambda **kwargs: image_calls.append(kwargs) or SimpleNamespace(usage=None, choices=[]))
    image_client._myagent_input_modalities = ["text", "image"]
    text_client = _client_with_create(
        lambda **kwargs: text_calls.append(kwargs) or SimpleNamespace(usage=None, choices=[]),
        multimodal=False,
    )
    text_client._myagent_input_modalities = ["text"]

    agent_openai.chat_completion(image_client, "vision", messages, temperature=0, max_tokens=8)
    agent_openai.chat_completion(text_client, "text", messages, temperature=0, max_tokens=8)

    image_content = _message_with_role(image_calls[0]["messages"], "user")["content"]
    assert any(
        part.get("type") == "image_url"
        and part["image_url"]["url"] == "https://cdn.example.com/dashboard.png?size=large"
        for part in image_content
    )
    assert not agent_openai._api_messages_have_media(text_calls[0]["messages"])
    assert prompt in _message_with_role(text_calls[0]["messages"], "user")["content"]


def test_structured_local_attachment_expands_and_survives_history_roundtrip(tmp_path):
    import agent_harness
    import agent_openai
    from agent_messages import UserMessage

    image_path = tmp_path / "attached.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    original = UserMessage(content=[
        {"type": "text", "text": "分析附件"},
        {"type": "local_file", "local_file": {"path": str(image_path)}},
    ])

    serialized = agent_harness._message_to_dict(original)
    restored = agent_harness._dict_to_message(serialized)
    api_messages = agent_openai.messages_to_openai_params([restored])

    assert isinstance(restored.content, list)
    assert agent_openai._api_messages_required_modalities(api_messages) == {"image"}
    assert any(
        part.get("type") == "image_url"
        and part["image_url"]["url"].startswith("data:image/png;base64,")
        for part in api_messages[0]["content"]
    )


def test_stream_media_fallback_handles_lazy_error_without_duplicate_request(
    monkeypatch,
    tmp_path,
):
    import agent_openai
    from agent_messages import UserMessage

    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    prompt = f'分析 "{image_path}"'
    calls = []

    class LazyMediaError:
        def __iter__(self):
            return self

        def __next__(self):
            raise ValueError("Model does not support image inputs")

        def close(self):
            pass

    def create(**kwargs):
        calls.append(kwargs)
        if isinstance(kwargs["messages"][0]["content"], list):
            return LazyMediaError()
        return iter(())

    monkeypatch.setattr(agent_openai, "OPENAI_MAX_RETRIES", 1)
    queue = Queue()

    agent_openai.run_chat_completion_stream_worker(
        queue,
        _client_with_create(create),
        "text-model",
        [UserMessage(content=prompt)],
        temperature=0,
        max_tokens=8,
    )

    events = []
    while not queue.empty():
        events.append(queue.get())

    assert len(calls) == 2
    assert _message_with_role(calls[1]["messages"], "user")["content"] == prompt
    assert "task 工具" in _message_with_role(
        calls[1]["messages"], "system"
    )["content"]
    assert any(
        event is not None
        and event[0] == "status"
        and "已保留文件路径" in event[1]
        for event in events
    )
    assert any(event is not None and event[0] == "turn" for event in events)
    assert not any(event is not None and event[0] == "err" for event in events)


def test_stream_options_fallback_only_retries_parameter_errors(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage

    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if "stream_options" in kwargs:
            raise ValueError("Unknown stream_options field")
        return iter(())

    monkeypatch.setattr(agent_openai, "OPENAI_MAX_RETRIES", 1)
    queue = Queue()

    agent_openai.run_chat_completion_stream_worker(
        queue,
        _client_with_create(create),
        "text-model",
        [UserMessage(content="hello")],
        temperature=0,
        max_tokens=8,
    )

    assert len(calls) == 2
    assert "stream_options" in calls[0]
    assert "stream_options" not in calls[1]
