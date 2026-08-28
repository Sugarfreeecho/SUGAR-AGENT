from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_executor_choices_prefer_manual_description_and_effective_modalities(
    monkeypatch,
):
    import agent_harness

    profile = {
        "id": "manual-text-profile",
        "name": "Manual text profile",
        "model": "unknown-vision-looking-model",
        "llm_type": "openai-compatible",
        "context_window": 128_000,
        "max_output_tokens": 8_192,
        "capability_description": "高难度：复杂推理和疑难调试",
        "multimodal_mode": "disabled",
        "input_modalities": ["text", "image"],
    }
    monkeypatch.setattr(
        agent_harness,
        "_executor_profile_catalog",
        lambda: ({profile["id"]: profile}, [profile["id"]], profile["id"]),
    )
    monkeypatch.setattr(
        agent_harness.model_profiles,
        "infer_model_task_capabilities",
        lambda *_args: {
            "capability_description": "自动推断：视觉模型",
            "capability_description_en": "Automatically inferred vision model",
            "capability_source": "automatic:models-table",
            "capability_tags": ["multimodal_candidate"],
            "input_modalities": ["text", "image"],
        },
    )

    choice = agent_harness.list_executor_model_profile_choices()[0]

    assert choice["capability_description"] == "高难度：复杂推理和疑难调试"
    assert choice["capability_description_en"] == "高难度：复杂推理和疑难调试"
    assert choice["capability_source"] == "manual"
    assert choice["table_input_modalities"] == ["text", "image"]
    assert choice["input_modalities"] == ["text"]
    assert choice["multimodal_input"] is False
    assert choice["multimodal_mode"] == "disabled"
    assert "multimodal_candidate" not in choice["capability_tags"]
