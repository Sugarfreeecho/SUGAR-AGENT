"""Qwen-style leading single-system-message request adaptation."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import model_profiles  # noqa: E402
from agent_messages import SystemMessage, UserMessage  # noqa: E402
from agent_openai import (  # noqa: E402
    _merge_system_prompt_for_single_system_model,
    _messages_to_params_for_client,
)


def test_leading_system_messages_merge_and_late_system_keeps_position_as_user():
    original = [
        {"role": "system", "content": "identity"},
        {"role": "system", "content": "tools"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
        {"role": "system", "content": "tail reminder"},
    ]

    projected = _merge_system_prompt_for_single_system_model(original)

    assert projected == [
        {"role": "system", "content": "identity\n\ntools"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "tail reminder"},
    ]
    assert original[0]["content"] == "identity"
    assert _merge_system_prompt_for_single_system_model(projected) == projected


def test_empty_system_messages_are_removed():
    projected = _merge_system_prompt_for_single_system_model([
        {"role": "system", "content": "  "},
        {"role": "system", "content": "identity"},
        {"role": "user", "content": "question"},
        {"role": "system", "content": ""},
    ])

    assert projected == [
        {"role": "system", "content": "identity"},
        {"role": "user", "content": "question"},
    ]


def test_late_system_without_a_leading_slot_folds_into_user():
    projected = _merge_system_prompt_for_single_system_model([
        {"role": "user", "content": "question"},
        {"role": "system", "content": "runtime context"},
    ])

    assert projected == [
        {"role": "user", "content": "question"},
        {"role": "user", "content": "runtime context"},
    ]


def test_system_inside_tool_transaction_folds_into_leading_prompt():
    projected = _merge_system_prompt_for_single_system_model([
        {"role": "system", "content": "identity"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "function": {"name": "one", "arguments": "{}"}},
                {"id": "call_2", "function": {"name": "two", "arguments": "{}"}},
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "one"},
        {"role": "system", "content": "do not split tools"},
        {"role": "tool", "tool_call_id": "call_2", "content": "two"},
        {"role": "system", "content": "tail"},
    ])

    assert projected[0] == {
        "role": "system",
        "content": "identity\n\ndo not split tools",
    }
    assert [message["role"] for message in projected] == [
        "system", "assistant", "tool", "tool", "user"
    ]
    assert projected[-1]["content"] == "tail"


def test_client_mode_gates_projection_without_changing_other_clients():
    messages = [SystemMessage("one"), SystemMessage("two"), UserMessage("hello")]
    merge_client = SimpleNamespace(
        _myagent_input_modalities=["text"],
        _myagent_system_prompt_mode="merge",
    )
    preserve_client = SimpleNamespace(_myagent_input_modalities=["text"])

    assert _messages_to_params_for_client(merge_client, messages) == [
        {"role": "system", "content": "one\n\ntwo"},
        {"role": "user", "content": "hello"},
    ]
    assert _messages_to_params_for_client(preserve_client, messages) == [
        {"role": "system", "content": "one"},
        {"role": "system", "content": "two"},
        {"role": "user", "content": "hello"},
    ]


def test_non_transport_fallback_facade_projects_selected_qwen_candidate():
    import agent_harness

    calls = []

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return "ok"

    raw_client = SimpleNamespace(
        chat=SimpleNamespace(completions=_Completions())
    )
    facade = agent_harness.FallbackOpenAIClient([{
        "client": raw_client,
        "model": "qwen-plus",
        "max_output_tokens": 1024,
        "system_prompt_mode": "merge",
    }])

    assert facade._myagent_transport_enabled is False
    result = facade.chat.completions.create(
        model="ignored",
        messages=[
            {"role": "system", "content": "one"},
            {"role": "system", "content": "two"},
            {"role": "user", "content": "hello"},
            {"role": "system", "content": "tail"},
        ],
    )

    assert result == "ok"
    assert calls[0]["messages"] == [
        {"role": "system", "content": "one\n\ntwo"},
        {"role": "user", "content": "hello"},
        {"role": "user", "content": "tail"},
    ]


@pytest.mark.parametrize("model", ["qwen-plus", "Qwen/Qwen3-32B", "qwen3-vl-plus"])
def test_auto_mode_detects_qwen_chat_profiles(model):
    assert model_profiles.profile_system_prompt_mode({
        "model": model,
        "llm_type": "openai-compatible",
        "system_prompt_mode": "auto",
    }) == "merge"


def test_explicit_profile_mode_wins_and_non_chat_protocols_are_untouched():
    assert model_profiles.profile_system_prompt_mode({
        "model": "qwen-plus",
        "llm_type": "openai-compatible",
        "system_prompt_mode": "preserve",
    }) == "preserve"
    assert model_profiles.profile_system_prompt_mode({
        "model": "custom-model",
        "llm_type": "openai-compatible",
        "system_prompt_mode": "merge",
    }) == "merge"
    assert model_profiles.profile_system_prompt_mode({
        "model": "qwen-plus",
        "llm_type": "openai-responses",
        "system_prompt_mode": "merge",
    }) == "preserve"


def test_profile_persists_mode_and_rejects_unknown_values(tmp_path):
    saved = model_profiles.upsert_profile(tmp_path, {
        "model": "qwen-plus",
        "base_url": "https://example.com/v1",
        "llm_type": "openai-compatible",
        "system_prompt_mode": "merge",
    })
    assert saved["system_prompt_mode"] == "merge"
    assert model_profiles.public_profile(saved)["system_prompt_mode"] == "merge"
    assert model_profiles.public_profile(saved)["effective_system_prompt_mode"] == "merge"

    with pytest.raises(ValueError, match="system_prompt_mode"):
        model_profiles.upsert_profile(tmp_path, {
            "model": "qwen-plus",
            "base_url": "https://example.com/v1",
            "llm_type": "openai-compatible",
            "system_prompt_mode": "invalid",
        })


def test_legacy_public_profile_exposes_auto_and_effective_modes():
    public = model_profiles.public_profile({
        "model": "qwen-plus",
        "llm_type": "openai-compatible",
    })

    assert public["system_prompt_mode"] == "auto"
    assert public["effective_system_prompt_mode"] == "merge"
