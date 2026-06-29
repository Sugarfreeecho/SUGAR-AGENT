import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_resolve_executor_config_uses_session_cache(monkeypatch):
    import agent_harness

    agent_harness._invalidate_executor_config_cache()
    calls = {"metadata": 0}

    def load_metadata(_sid):
        calls["metadata"] += 1
        return {}

    monkeypatch.setattr(agent_harness.session_manager, "_load_metadata", load_metadata)
    monkeypatch.setattr(agent_harness.model_profiles, "top_profile_id_with_env", lambda _root: "")

    first = agent_harness.resolve_executor_config_for_session("s1")
    second = agent_harness.resolve_executor_config_for_session("s1")

    assert first == second
    assert calls["metadata"] == 1


def test_metadata_sidecar_updates_do_not_invalidate_executor_config_cache(monkeypatch, tmp_path):
    import agent_harness

    agent_harness._invalidate_executor_config_cache()
    calls = {"metadata": 0}
    sid = str(uuid.uuid4())

    def load_metadata(_sid):
        calls["metadata"] += 1
        return {}

    monkeypatch.setattr(agent_harness.session_manager, "_load_metadata", load_metadata)
    monkeypatch.setattr(agent_harness.model_profiles, "top_profile_id_with_env", lambda _root: "")

    first = agent_harness.resolve_executor_config_for_session(sid)
    manager = agent_harness.SessionManager(tmp_path / "sessions", tmp_path / "sessions.json")
    manager._save_metadata(
        sid,
        {"ui_event_count": 10, "updated_at": "2026-06-29T19:20:00"},
    )
    second = agent_harness.resolve_executor_config_for_session(sid)

    assert first == second
    assert calls["metadata"] == 1


def test_interrupt_check_uses_memory_cache(tmp_path):
    import agent_harness

    sid = str(uuid.uuid4())
    manager = agent_harness.SessionManager(tmp_path / "sessions", tmp_path / "sessions.json")
    manager._save_metadata(
        sid,
        {
            "interrupt_requested": True,
            "interrupt_reason": "followup",
            "interrupt_run_id": "run-1",
        },
    )

    assert manager.is_interrupt_requested(sid, "run-1") is True
    manager.repository.load_metadata = lambda _sid: (_ for _ in ()).throw(
        AssertionError("interrupt cache should avoid metadata reload")
    )

    assert manager.is_interrupt_requested(sid, "run-1") is True
    assert manager.is_interrupt_requested(sid, "run-2") is False
    assert manager.get_interrupt_reason(sid) == "followup"


def test_full_input_token_estimate_reuses_cache(monkeypatch):
    import agent_tokenizer
    from agent_messages import UserMessage

    agent_tokenizer._FULL_INPUT_TOKEN_CACHE.clear()
    calls = {"estimate": 0}

    def estimate_tokens(_messages):
        calls["estimate"] += 1
        return 123

    import agent_harness
    import agent_tools

    monkeypatch.setattr(agent_tools, "get_skills_catalog", lambda: "")
    monkeypatch.setattr(agent_harness, "estimate_tokens", estimate_tokens)
    monkeypatch.setattr(agent_harness, "key_context_body_for_system_prompt", lambda text: text)
    monkeypatch.setattr(agent_harness, "strip_reasoning_for_api_request", lambda messages: messages)
    monkeypatch.setattr(agent_harness, "load_prompt_template", lambda _name: "{skills_catalog}" if _name == "system_skills_intro" else "")

    messages = [UserMessage(content="hello")]
    assert agent_tokenizer.estimate_full_input_tokens_for_llm_history("s1", messages, "") == 123
    assert agent_tokenizer.estimate_full_input_tokens_for_llm_history("s1", messages, "") == 123
    assert calls["estimate"] == 1


def test_prebuilt_token_estimate_uses_exact_provider_usage(monkeypatch):
    import agent_tokenizer
    from agent_messages import SystemMessage, UserMessage

    agent_tokenizer._PROMPT_USAGE_BASELINE_CACHE.clear()
    agent_tokenizer._PROMPT_USAGE_EXACT_CACHE.clear()

    import agent_harness

    monkeypatch.setattr(
        agent_harness,
        "estimate_tokens",
        lambda _messages: (_ for _ in ()).throw(
            AssertionError("exact provider usage should avoid local token estimate")
        ),
    )
    monkeypatch.setattr(agent_harness, "strip_reasoning_for_api_request", lambda messages: messages)

    messages = [SystemMessage(content="sys"), UserMessage(content="hello")]
    agent_tokenizer.record_prompt_tokens_for_messages("s1", messages, 88)

    assert agent_tokenizer.estimate_full_input_tokens_for_messages("s1", messages) == 88


def test_prebuilt_token_estimate_uses_provider_prefix_baseline(monkeypatch):
    import agent_tokenizer
    from agent_messages import AssistantMessage, SystemMessage, UserMessage

    agent_tokenizer._PROMPT_USAGE_BASELINE_CACHE.clear()
    agent_tokenizer._PROMPT_USAGE_EXACT_CACHE.clear()
    calls = {"estimate": 0, "sizes": []}

    def estimate_tokens(messages):
        calls["estimate"] += 1
        calls["sizes"].append(len(messages))
        return 12

    import agent_harness

    monkeypatch.setattr(agent_harness, "estimate_tokens", estimate_tokens)
    monkeypatch.setattr(agent_harness, "strip_reasoning_for_api_request", lambda messages: messages)

    first = [SystemMessage(content="sys"), UserMessage(content="hello")]
    second = [*first, AssistantMessage(content="answer")]
    agent_tokenizer.record_prompt_tokens_for_messages("s1", first, 88)

    estimated = agent_tokenizer.estimate_full_input_tokens_for_messages("s1", second)

    assert estimated == 108
    assert calls == {"estimate": 1, "sizes": [1]}
