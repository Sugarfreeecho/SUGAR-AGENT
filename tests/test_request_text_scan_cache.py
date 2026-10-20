from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_unchanged_plain_user_text_is_probed_once_and_replacement_is_reprobed(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage
    import attachments.admission as admission

    probe = Mock(wraps=admission.text_requires_admission)
    monkeypatch.setattr(admission, "text_requires_admission", probe)
    message = UserMessage("ordinary plain text " * 100)
    client = SimpleNamespace()
    first = agent_openai._messages_to_params_for_client(client, [message])
    assert agent_openai._messages_to_params_for_client(client, [message]) == first
    assert probe.call_count == 1
    message.content = "different plain text"
    changed = agent_openai._messages_to_params_for_client(client, [message])
    assert changed[0]["content"] == "different plain text"
    assert probe.call_count == 2


def test_possible_attachment_is_never_skipped_and_scan_switch_invalidates_negative_cache(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage

    calls = []
    monkeypatch.setattr(agent_openai, "durable_content", lambda content, **kwargs: calls.append(content) or content)
    message = UserMessage('"C:/example/image.png"')
    client = SimpleNamespace()
    monkeypatch.setenv("MULTIMODAL_TEXT_PATH_SCAN", "off")
    agent_openai._messages_to_params_for_client(client, [message])
    assert calls == []
    monkeypatch.setenv("MULTIMODAL_TEXT_PATH_SCAN", "on")
    agent_openai._messages_to_params_for_client(client, [message])
    agent_openai._messages_to_params_for_client(client, [message])
    assert calls == [message.content, message.content]


def test_mutable_content_blocks_keep_live_admission(monkeypatch):
    import agent_openai
    from agent_messages import UserMessage

    calls = []
    monkeypatch.setattr(agent_openai, "durable_content", lambda content, **kwargs: calls.append(content) or content)
    message = UserMessage([{"type": "text", "text": "before"}])
    agent_openai._messages_to_params_for_client(SimpleNamespace(), [message])
    message.content[0]["text"] = "after"
    result = agent_openai._messages_to_params_for_client(SimpleNamespace(), [message])
    assert len(calls) == 2
    assert "after" in str(result)
