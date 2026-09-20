import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_full_input_token_cache_key_changes_when_early_message_changes():
    import agent_tokenizer
    from agent_harness import AssistantMessage, UserMessage

    before = [
        UserMessage(content="old " * 200),
        AssistantMessage(content="answer"),
        UserMessage(content="tail"),
        AssistantMessage(content="tail answer"),
    ]
    after = [
        UserMessage(content="short"),
        AssistantMessage(content="answer"),
        UserMessage(content="tail"),
        AssistantMessage(content="tail answer"),
    ]

    assert agent_tokenizer._full_input_token_cache_key("s1", before, "") != (
        agent_tokenizer._full_input_token_cache_key("s1", after, "")
    )


def test_full_input_token_cache_key_changes_when_tools_change():
    import agent_tokenizer
    from agent_harness import UserMessage

    messages = [UserMessage(content="hello")]
    first = [{"type": "function", "function": {"name": "first", "parameters": {"type": "object"}}}]
    second = [{"type": "function", "function": {"name": "second", "parameters": {"type": "object"}}}]

    assert agent_tokenizer._full_input_token_cache_key("s1", messages, "", first) != (
        agent_tokenizer._full_input_token_cache_key("s1", messages, "", second)
    )


def test_warm_tokenizer_loads_and_runs_tiny_encode(monkeypatch):
    import agent_tokenizer

    seen = []

    class FakeTokenizer:
        def encode(self, text):
            seen.append(text)

    monkeypatch.setattr(agent_tokenizer, "_get_tokenizer", lambda: FakeTokenizer())

    assert agent_tokenizer.warm_tokenizer() is True
    assert seen == ["MyAgent tokenizer warmup"]
