from pathlib import Path
import sys
from unittest.mock import Mock

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_unchanged_system_prefix_keeps_identity_and_rebuilds_after_content_change():
    import agent_loop
    state = {}
    before = agent_loop._request_system_messages(state, ["system", "context"])
    after = agent_loop._request_system_messages(state, ["system", "context"])
    assert after is not before
    assert all(left is right for left, right in zip(before, after))
    after[0].content = "externally changed"
    repaired = agent_loop._request_system_messages(state, ["system", "context"])
    assert repaired[0].content == "system"
    assert repaired[0] is not after[0]
    changed = agent_loop._request_system_messages(state, ["system", "new context"])
    assert changed[1].content == "new context"


def test_reassembled_request_hashes_only_new_tail(monkeypatch):
    import agent_loop
    import agent_harness
    import agent_tokenizer
    from agent_messages import UserMessage, AssistantMessage

    agent_harness._clear_strip_reasoning_cache()
    agent_tokenizer._MESSAGE_TOKEN_LIST_CACHE.clear()
    hash_message = Mock(wraps=agent_tokenizer._message_token_cache_hash)
    monkeypatch.setattr(agent_tokenizer, "_message_token_cache_hash", hash_message)
    state = {}
    turns = [UserMessage("question"), AssistantMessage("answer")]
    first = agent_loop._request_system_messages(state, ["system"]) + turns
    agent_tokenizer._messages_token_hashes(agent_harness.strip_reasoning_for_api_request(first))
    assert hash_message.call_count == 3
    second = agent_loop._request_system_messages(state, ["system"]) + turns + [UserMessage("next")]
    agent_tokenizer._messages_token_hashes(agent_harness.strip_reasoning_for_api_request(second))
    assert hash_message.call_count == 4
