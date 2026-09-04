import sys
import json
from pathlib import Path

import httpx


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import model_profiles


def test_profile_store_defaults_to_project_root(tmp_path):
    assert model_profiles.profile_store_path(tmp_path) == tmp_path / "model_profiles.json"


def test_models_table_is_bundled_inside_app():
    root = Path(__file__).resolve().parents[1]
    expected = root / "app" / "data" / "models_table.md"

    assert model_profiles.MODEL_LIMITS_TABLE_PATH == expected
    assert expected.is_file()


def test_normalized_custom_model_name_selects_latest_table_match():
    metadata = model_profiles.model_table_metadata_for_model("deepseekv4")
    limits = model_profiles.infer_model_limits("deepseekv4")
    capabilities = model_profiles.infer_model_task_capabilities("deepseekv4")

    assert metadata is not None
    assert metadata["model_id"] == "deepseek/deepseek-v4-pro"
    assert metadata["intel_score"] == 44.3
    assert metadata["coding_score"] == 59.4
    assert metadata["agentic_score"] == 36.4
    assert metadata["input_price_per_m"] == 0.435
    assert metadata["output_price_per_m"] == 0.87
    assert limits["context_window"] == 1048576
    assert limits["context_source"] == "table"
    assert capabilities["matched_model_id"] == "deepseek/deepseek-v4-pro"
    assert capabilities["capability_source"] == "automatic:models-table"
    assert capabilities["model_prices"] == {
        "input_per_m": 0.435,
        "output_per_m": 0.87,
    }
    assert capabilities["capability_description"] == (
        "适合：低成本/多并发、高难度、调查调研、代码、Agent；"
        "多模态输入：不支持（仅文本）"
    )


def test_normalized_multiple_matches_prefer_latest_release_over_scores(tmp_path, monkeypatch):
    table_path = tmp_path / "models_table.md"
    table_path.write_text(
        "| Provider | Model ID | Name | Context | Modality | Input | Output | Input $/M | Output $/M | Intel | Coding | Agentic | Reasoning | Created |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| vendor | vendor/family-v4-pro | Old Strong | 1,000,000 | text->text | text | text | - | - | 99 | 99 | 99 | Optional | 2025-01-01 |\n"
        "| vendor | vendor/family-v4-flash | New Weak | 128,000 | text->text | text | text | - | - | 1 | 1 | 1 | Optional | 2026-01-01 |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(model_profiles, "MODEL_LIMITS_TABLE_PATH", table_path)

    metadata = model_profiles.model_table_metadata_for_model("familyv4")

    assert metadata is not None
    assert metadata["model_id"] == "vendor/family-v4-flash"
    assert metadata["created"] == "2026-01-01"


def test_table_multimodal_metadata_drives_capability_description():
    capabilities = model_profiles.infer_model_task_capabilities("google/gemini-2.5-flash")

    assert "multimodal_candidate" in capabilities["capability_tags"]
    assert {"image", "audio", "video", "file"} <= set(capabilities["input_modalities"])
    assert "多模态输入：图片、音频、视频、文件" in capabilities["capability_description"]


def test_model_task_capabilities_come_only_from_table_metadata():
    cases = {
        "deepseek-v4-flash": {"low_cost_concurrency", "hard_reasoning", "research", "coding", "agent", "long_context"},
        "MiniMax-M3": {"hard_reasoning", "research", "multimodal_candidate", "coding", "agent"},
        "gpt-5.4": {"hard_reasoning", "research", "multimodal_candidate", "coding", "agent"},
        "claude-opus-4.8": {"hard_reasoning", "research", "multimodal_candidate", "coding", "agent"},
        "glm-5.2": {"hard_reasoning", "research", "coding", "agent"},
        "gemini-3.1-pro": {"multimodal_candidate", "long_context"},
        "grok-4.5": {"hard_reasoning", "research", "multimodal_candidate", "coding", "agent"},
        "mimo-v2.5-pro": {"hard_reasoning", "research", "coding", "agent"},
        "qwen3.7-plus": {"multimodal_candidate", "coding", "agent"},
        "kimi-k2.6": {"hard_reasoning", "research", "multimodal_candidate", "coding", "agent"},
        "sonar-deep-research": {"long_context"},
    }

    for model, expected in cases.items():
        inferred = model_profiles.infer_model_task_capabilities(model, context_window=256_000)
        assert expected <= set(inferred["capability_tags"]), model

    deepseek = model_profiles.infer_model_task_capabilities("deepseek-v4-flash")
    assert "适合：低成本/多并发、高难度、调查调研、代码、Agent" in deepseek["capability_description"]
    assert "Best for: low-cost/high-concurrency, complex tasks, research, coding, agent workflows" in deepseek["capability_description_en"]
    assert "hard_reasoning" in model_profiles.infer_model_task_capabilities("MiniMax-M3")["capability_tags"]

    unmatched = model_profiles.infer_model_task_capabilities("pixtral-large")
    assert unmatched == {
        "capability_tags": [],
        "capability_description": "",
        "capability_description_en": "",
        "capability_source": "unavailable",
    }
    assert model_profiles.infer_multimodal_input("pixtral-large") is False


def test_long_context_uses_actual_configured_context_not_table_maximum():
    normal = model_profiles.infer_model_task_capabilities(
        "deepseek-v4-pro", context_window=119_808
    )
    long = model_profiles.infer_model_task_capabilities(
        "deepseek-v4-pro", context_window=256_000
    )

    assert "long_context" not in normal["capability_tags"]
    assert "长上下文" not in normal["capability_description"]
    assert "long_context" in long["capability_tags"]
    assert "长上下文（实际配置 256,000 tokens）" in long["capability_description"]
    assert "long-context (256,000 tokens configured)" in long["capability_description_en"]


def test_negative_router_prices_are_not_treated_as_low_cost():
    inferred = model_profiles.infer_model_task_capabilities(
        "openrouter/auto", context_window=512_000
    )

    assert inferred["model_prices"] == {"input_per_m": None, "output_per_m": None}
    assert "low_cost_concurrency" not in inferred["capability_tags"]


def test_public_profile_adds_automatic_capability_description():
    public = model_profiles.public_profile({
        "name": "Research model",
        "model": "gemini-3.1-pro",
        "context_window": 1_000_000,
        "api_key": "secret",
    })

    assert public["capability_source"] == "automatic:models-table"
    assert {"multimodal_candidate", "long_context"} <= set(public["capability_tags"])
    assert "长上下文（实际配置 1,000,000 tokens）" in public["capability_description"]
    assert "多模态输入：图片、音频、视频、文件" in public["capability_description"]
    assert "long-context (1,000,000 tokens configured)" in public["capability_description_en"]
    assert "Multimodal input: image, audio, video, file" in public["capability_description_en"]


def test_model_profile_persists_editable_capability_description(tmp_path):
    saved = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "minimax-m3",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capability_description": "代码：常规修改；Agent：低复杂度工具任务",
        },
    )

    public = model_profiles.public_profile(saved)
    assert public["capability_source"] == "manual"
    assert public["capability_description"] == "代码：常规修改；Agent：低复杂度工具任务"

    cleared = model_profiles.upsert_profile(
        tmp_path,
        {
            **saved,
            "capability_description": "",
        },
    )
    automatic = model_profiles.public_profile(cleared)
    assert automatic["capability_source"] == "automatic:models-table"
    assert "hard_reasoning" in automatic["capability_tags"]


def test_model_profile_multimodal_mode_controls_effective_capability(tmp_path):
    automatic = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "gpt-5.4",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 128000,
            "max_output_tokens": 8192,
        },
    )

    public = model_profiles.public_profile(automatic)
    assert public["multimodal_mode"] == "auto"
    assert public["multimodal_input"] is True
    assert public["multimodal_source"] == "automatic:models-table"
    assert "multimodal" in public["capability_tags"]

    disabled = model_profiles.upsert_profile(
        tmp_path,
        {
            **automatic,
            "multimodal_mode": "disabled",
        },
    )
    public_disabled = model_profiles.public_profile(disabled)
    assert public_disabled["multimodal_input"] is False
    assert public_disabled["multimodal_source"] == "manual"
    assert "multimodal" not in public_disabled["capability_tags"]
    assert "multimodal_candidate" not in public_disabled["capability_tags"]


def test_multimodal_send_failure_persists_text_only_profile_state(tmp_path):
    saved = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "vision-model",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "multimodal_mode": "enabled",
        },
    )

    failed = model_profiles.mark_profile_multimodal_failed(tmp_path, saved["id"])
    public = model_profiles.public_profile(failed)

    assert failed["multimodal_mode"] == "disabled"
    assert failed["multimodal_source"] == "failure"
    assert failed["multimodal_failure_reason"] == "provider_rejected_multimodal_input"
    assert public["multimodal_input"] is False
    assert model_profiles.load_store(tmp_path)["profiles"][0]["multimodal_mode"] == "disabled"


def test_specific_modality_failure_preserves_other_media_capabilities(tmp_path):
    saved = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "vision-model",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 128000,
            "max_output_tokens": 8192,
            "multimodal_mode": "enabled",
            "input_modalities": ["text", "image", "audio"],
        },
    )

    failed = model_profiles.mark_profile_modalities_failed(
        tmp_path, saved["id"], ["image"], "provider rejected image_url"
    )
    public = model_profiles.public_profile(failed)

    assert failed["multimodal_mode"] == "enabled"
    assert public["effective_input_modalities"] == ["text", "audio"]
    assert public["multimodal_input"] is True
    assert public["multimodal_source"] == "partial_failure"
    assert public["failed_modalities"]["image"]["reason"] == "provider rejected image_url"


def test_load_store_reads_legacy_app_location_when_default_missing(tmp_path):
    legacy_dir = tmp_path / "app"
    legacy_dir.mkdir()
    (legacy_dir / "model_profiles.json").write_text(
        json.dumps({"profiles": [{"id": "legacy"}], "env_profile": {}}),
        encoding="utf-8",
    )

    assert model_profiles.load_store(tmp_path)["profiles"][0]["id"] == "legacy"


def test_extract_context_window_from_error_message():
    assert model_profiles.extract_context_window_from_error("maximum context length is 128000 tokens") == 128000
    assert (
        model_profiles.extract_context_window_from_error(
            {"error": {"message": "This model's maximum context length is 128,000 tokens."}}
        )
        == 128000
    )


def test_recommended_unknown_model_windows_use_128k_default():
    assert model_profiles.recommended_model_windows(0) == {
        "model_context_window": 128000,
        "max_output_tokens": 8192,
        "context_window": 119808,
    }
    assert model_profiles.recommended_model_windows(128000) == {
        "model_context_window": 128000,
        "max_output_tokens": 8192,
        "context_window": 119808,
    }


def test_model_limits_map_exact_and_providerless_ids_from_markdown_table(tmp_path, monkeypatch):
    table_path = tmp_path / "models_table.md"
    table_path.write_text(
        "# Models\n\n"
        "| Provider | Model ID | Name | Context |\n"
        "|---|---|---|---|\n"
        "| xiaomi | xiaomi/mimo-v2.5 | MiMo | 1,050,000 |\n"
        "| deepseek | deepseek/deepseek-chat | DeepSeek | 163,840 |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(model_profiles, "MODEL_LIMITS_TABLE_PATH", table_path)

    exact = model_profiles.infer_model_limits("xiaomi/mimo-v2.5")
    providerless = model_profiles.infer_model_limits("mimo-v2.5")

    assert exact["context_window"] == 1050000
    assert exact["max_output_tokens"] == 50000
    assert exact["context_source"] == "table"
    assert providerless["context_window"] == 1050000
    assert providerless["context_source"] == "table"


def test_huawei_domain_precedes_table_but_not_api_limits(tmp_path, monkeypatch):
    table_path = tmp_path / "models_table.md"
    table_path.write_text(
        "| Provider | Model ID | Name | Context |\n"
        "|---|---|---|---|\n"
        "| xiaomi | xiaomi/mimo-v2.5 | MiMo | 1,050,000 |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(model_profiles, "MODEL_LIMITS_TABLE_PATH", table_path)
    huawei_url = "https://maas-api.cn-north-4.myhuaweicloud.com/v1"

    huawei = model_profiles.infer_model_limits("mimo-v2.5", base_url=huawei_url)
    api = model_profiles.infer_model_limits(
        "mimo-v2.5",
        {"context_window": 256000, "max_output_tokens": 12000},
        base_url=huawei_url,
    )

    assert model_profiles.is_huawei_api_domain("https://api.huawei.com/v1") is True
    assert model_profiles.is_huawei_api_domain(huawei_url) is True
    assert (
        model_profiles.is_huawei_api_domain(
            "http://ai.threecloud.huawei.com/models/tools/deepseekv4f/v1"
        )
        is True
    )
    assert model_profiles.is_huawei_api_domain("https://example.com/v1/huawei") is False
    assert huawei == {
        "context_window": 128000,
        "max_output_tokens": 8192,
        "context_source": "huawei",
        "output_source": "recommended",
    }
    assert api == {
        "context_window": 256000,
        "max_output_tokens": 12000,
        "context_source": "api",
        "output_source": "api",
    }


def test_unknown_model_falls_back_to_128k_model_window(tmp_path, monkeypatch):
    monkeypatch.setattr(model_profiles, "MODEL_LIMITS_TABLE_PATH", tmp_path / "missing.md")

    limits = model_profiles.infer_model_limits("not-in-model-table")

    assert limits == {
        "context_window": 128000,
        "max_output_tokens": 8192,
        "context_source": "default",
        "output_source": "recommended",
    }


def test_upsert_without_limits_saves_unknown_model_recommendation(tmp_path, monkeypatch):
    monkeypatch.setattr(model_profiles, "MODEL_LIMITS_TABLE_PATH", tmp_path / "missing.md")

    saved = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "not-in-model-table",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
        },
    )

    assert saved["model_context_window"] == 128000
    assert saved["max_output_tokens"] == 8192
    assert saved["context_window"] == 119808


def test_huawei_upsert_fills_only_missing_limits_and_preserves_manual_values(tmp_path):
    base = "https://maas-api.cn-north-4.myhuaweicloud.com/v1"
    automatic = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "mimo-v2.5",
            "base_url": base,
            "api_key": "test-key",
        },
    )
    manual = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "mimo-v2.5",
            "base_url": base,
            "api_key": "test-key",
            "model_context_window": 300000,
            "max_output_tokens": 24000,
            "context_window": 200000,
        },
    )

    assert automatic["model_context_window"] == 128000
    assert automatic["max_output_tokens"] == 8192
    assert automatic["context_window"] == 119808
    assert manual["model_context_window"] == 300000
    assert manual["max_output_tokens"] == 24000
    assert manual["context_window"] == 200000


def test_probe_context_window_from_http_400_error():
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(
            400,
            json={"error": {"message": "This model's maximum context length is 128000 tokens."}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        value = model_profiles.probe_context_window_from_error(
            client,
            "https://api.example.com/v1",
            {"Authorization": "Bearer test"},
            "demo-model",
        )

    assert value == 128000
    assert seen_urls == ["https://api.example.com/v1/chat/completions"]


def test_discover_models_only_fetches_model_list(monkeypatch):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "demo-model"}]})
        return httpx.Response(
            400,
            json={"error": {"message": "This model's maximum context length is 128000 tokens."}},
        )

    class MockClient(httpx.Client):
        def __init__(self, *args, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(model_profiles.httpx, "Client", MockClient)

    models = model_profiles.discover_models("https://api.example.com/v1", "test-key")

    assert seen_paths == ["/v1/models"]
    assert models[0]["context_window"] == model_profiles.DEFAULT_UNKNOWN_MODEL_CONTEXT_WINDOW
    assert models[0]["model_context_window"] == model_profiles.DEFAULT_UNKNOWN_MODEL_CONTEXT_WINDOW
    assert models[0]["max_output_tokens"] == model_profiles.DEFAULT_UNKNOWN_OUTPUT_TOKENS
    assert models[0]["limit_source"] == "default"


def test_probe_model_context_uses_context_probe_for_one_selected_model(monkeypatch):
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(
            400,
            json={"error": {"message": "This model's maximum context length is 128000 tokens."}},
        )

    class MockClient(httpx.Client):
        def __init__(self, *args, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(model_profiles.httpx, "Client", MockClient)

    model = model_profiles.probe_model_context(
        "https://api.example.com/v1",
        "test-key",
        "demo-model",
        {"max_output_tokens": 8192},
    )

    assert seen_paths == ["/v1/chat/completions"]
    assert model["context_window"] == 128000
    assert model["model_context_window"] == 128000
    assert model["max_output_tokens"] == 8192
    assert model["limit_source"] == "probe"
    assert model["probe_succeeded"] is True


def test_probe_model_context_uses_responses_protocol(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            400,
            json={"error": {"message": "maximum context length is 200000 tokens"}},
        )

    class MockClient(httpx.Client):
        def __init__(self, *args, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(model_profiles.httpx, "Client", MockClient)
    model = model_profiles.probe_model_context(
        "https://api.openai.com/v1",
        "test-key",
        "gpt-test",
        {"llm_type": "openai-responses"},
    )

    assert seen["path"] == "/v1/responses"
    assert "input" in seen["body"]
    assert "messages" not in seen["body"]
    assert seen["body"]["max_output_tokens"] == 1
    assert model["context_window"] == 200000


def test_probe_model_context_uses_anthropic_messages_protocol(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            400,
            json={"error": {"message": "context window limit is 180000 tokens"}},
        )

    class MockClient(httpx.Client):
        def __init__(self, *args, **kwargs):
            super().__init__(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(model_profiles.httpx, "Client", MockClient)
    model = model_profiles.probe_model_context(
        "https://api.anthropic.com",
        "test-key",
        "claude-test",
        {"llm_type": "anthropic"},
    )

    assert seen["path"] == "/v1/messages"
    assert seen["headers"]["x-api-key"] == "test-key"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert "messages" in seen["body"]
    assert "input" not in seen["body"]
    assert seen["body"]["max_tokens"] == 1
    assert model["context_window"] == 180000


def test_model_order_contains_only_saved_profiles(tmp_path):
    saved = model_profiles.upsert_profile(
        tmp_path,
        {
            "name": "saved",
            "model": "saved-model",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 128000,
            "max_output_tokens": 8192,
        },
    )
    assert [p["id"] for p in model_profiles.sorted_profiles(tmp_path)] == [saved["id"]]
    assert model_profiles.top_profile(tmp_path)["id"] == saved["id"]


def test_legacy_env_profile_metadata_is_discarded_on_save(tmp_path):
    path = model_profiles.profile_store_path(tmp_path)
    path.write_text(
        json.dumps({"env_profile": {"priority": 1}, "profiles": []}),
        encoding="utf-8",
    )

    assert model_profiles.load_store(tmp_path) == {"profiles": []}
    model_profiles.save_store(tmp_path, model_profiles.load_store(tmp_path))
    assert "env_profile" not in json.loads(path.read_text(encoding="utf-8"))


def test_local_profile_is_usable_without_api_key(tmp_path):
    profile = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "qwen3",
            "llm_type": "local",
            "base_url": "http://localhost:11434/v1",
            "context_window": 32768,
            "max_output_tokens": 4096,
        },
    )

    assert model_profiles.is_usable_profile(profile) is True


def test_legacy_dotenv_model_config_is_registered_once(tmp_path):
    env = {
        "EXECUTOR_LLM": "legacy-model",
        "EXECUTOR_LLM_TYPE": "openai",
        "OPENAI_BASE_URL": "https://api.example.com/v1",
        "OPENAI_API_KEY": "legacy-key",
        "CONTEXT_WINDOW": "128000",
        "MAX_OUTPUT_TOKENS": "8192",
        "EXECUTOR_TEMPERATURE": "0.2",
        "LLM_THINKING_MODE": "disabled",
    }

    first = model_profiles.register_legacy_env_model_profile(tmp_path, env)
    second = model_profiles.register_legacy_env_model_profile(
        tmp_path,
        {**env, "EXECUTOR_LLM": "changed-after-import"},
    )

    assert first["action"] == "created"
    assert second["action"] == "already_imported"
    profiles = model_profiles.sorted_profiles(tmp_path)
    assert len(profiles) == 1
    assert profiles[0]["model"] == "legacy-model"
    assert profiles[0]["name"] == "legacy-model"
    assert profiles[0]["api_key"] == "legacy-key"
    assert profiles[0]["llm_type"] == "auto"
    assert profiles[0]["temperature"] == "0.2"
    assert profiles[0][model_profiles.LEGACY_ENV_IMPORT_MARKER] is True
    assert model_profiles.is_usable_profile(profiles[0]) is True


def test_legacy_dotenv_import_matches_existing_profile_without_duplicate(tmp_path):
    existing = model_profiles.upsert_profile(
        tmp_path,
        {
            "name": "already saved",
            "model": "same-model",
            "base_url": "https://api.example.com/v1",
            "api_key": "same-key",
            "context_window": 64000,
            "max_output_tokens": 4096,
        },
    )

    result = model_profiles.register_legacy_env_model_profile(
        tmp_path,
        {
            "EXECUTOR_LLM": "same-model",
            "OPENAI_BASE_URL": "https://api.example.com/v1/",
            "OPENAI_API_KEY": "same-key",
            "CONTEXT_WINDOW": "64000",
            "MAX_OUTPUT_TOKENS": "4096",
        },
    )

    assert result["action"] == "matched_existing"
    assert result["profile"]["id"] == existing["id"]
    assert len(model_profiles.sorted_profiles(tmp_path)) == 1


def test_incomplete_legacy_dotenv_model_config_is_not_registered(tmp_path):
    result = model_profiles.register_legacy_env_model_profile(
        tmp_path,
        {"EXECUTOR_LLM": "missing-connection-settings"},
    )

    assert result == {"ok": True, "action": "skipped_incomplete", "profile": None}
    assert model_profiles.sorted_profiles(tmp_path) == []


def test_local_legacy_dotenv_model_config_uses_local_fields(tmp_path):
    result = model_profiles.register_legacy_env_model_profile(
        tmp_path,
        {
            "EXECUTOR_LLM_TYPE": "local",
            "LOCAL_LLM": "qwen3:8b",
            "LOCAL_LLM_HOST": "http://localhost:11434",
            "CONTEXT_WINDOW": "32768",
            "MAX_OUTPUT_TOKENS": "4096",
        },
    )

    assert result["action"] == "created"
    assert result["profile"]["model"] == "qwen3:8b"
    assert result["profile"]["base_url"] == "http://localhost:11434/v1"
    assert result["profile"].get("api_key", "") == ""
    assert model_profiles.is_usable_profile(result["profile"]) is True


def test_agent_harness_imports_model_fields_from_dotenv_file(tmp_path, monkeypatch):
    import agent_harness

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\ufeffEXECUTOR_LLM=file-model\n"
        "EXECUTOR_LLM_TYPE=openai\n"
        "OPENAI_BASE_URL=https://api.example.com/v1\n"
        "OPENAI_API_KEY=file-key\n"
        "CONTEXT_WINDOW=96000\n"
        "MAX_OUTPUT_TOKENS=6000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(agent_harness, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(agent_harness, "dotenv_file_path", lambda: env_path)

    result = agent_harness._register_legacy_dotenv_model_profile()

    assert result["action"] == "created"
    profile = model_profiles.top_profile(tmp_path)
    assert profile is not None
    assert profile["model"] == "file-model"
    assert profile["context_window"] == 96000


def test_model_profile_can_be_disabled_and_reenabled_without_deleting_config(tmp_path):
    primary = model_profiles.upsert_profile(
        tmp_path,
        {
            "name": "primary",
            "model": "model-a",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 128000,
            "max_output_tokens": 8192,
        },
    )
    backup = model_profiles.upsert_profile(
        tmp_path,
        {
            "name": "backup",
            "model": "model-b",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 64000,
            "max_output_tokens": 4096,
        },
    )

    disabled = model_profiles.set_profile_enabled(tmp_path, primary["id"], False)

    assert disabled is not None
    assert disabled["enabled"] is False
    assert model_profiles.is_usable_profile(disabled) is False
    assert model_profiles.public_profile(disabled)["enabled"] is False
    assert model_profiles.top_profile(tmp_path)["id"] == backup["id"]
    assert [item["id"] for item in model_profiles.fallback_chain(tmp_path, primary["id"])] == [backup["id"]]
    assert model_profiles.get_profile(tmp_path, primary["id"])["model"] == "model-a"

    restored = model_profiles.set_profile_enabled(tmp_path, primary["id"], True)

    assert restored is not None
    assert model_profiles.is_usable_profile(restored) is True
    assert model_profiles.top_profile(tmp_path)["id"] == primary["id"]


def test_editing_model_profile_preserves_disabled_state(tmp_path):
    profile = model_profiles.upsert_profile(
        tmp_path,
        {
            "model": "model-a",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "context_window": 128000,
            "max_output_tokens": 8192,
        },
    )
    model_profiles.set_profile_enabled(tmp_path, profile["id"], False)

    edited = model_profiles.upsert_profile(
        tmp_path,
        {
            "id": profile["id"],
            "name": "renamed",
            "model": "model-a",
            "base_url": "https://api.example.com/v1",
            "context_window": 128000,
            "max_output_tokens": 8192,
        },
    )

    assert edited["enabled"] is False
    assert edited["api_key"] == "test-key"


def test_advanced_model_profile_list_wires_drag_drop_reordering():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app" / "templates" / "advance_config.html").read_text(encoding="utf-8")
    i18n = (root / "app" / "templates" / "static" / "setup_i18n.js").read_text(encoding="utf-8")

    assert "class='profile-row" in html
    assert "draggable='true'" in html
    assert "profile-drag-handle" in html
    assert 'handles[i].addEventListener("dragstart",onProfileDragStart)' in html
    assert 'rows[i].addEventListener("dragstart",onProfileDragStart)' not in html
    assert 'addEventListener("dragover",onProfileDragOver)' in html
    assert 'addEventListener("drop",onProfileDrop)' in html
    assert "data-act='up'" not in html
    assert "data-act='down'" not in html
    assert "animateProfileRowShift" in html
    assert "profile-drop-settle" in html
    drag_over = html.split("function onProfileDragOver", 1)[1].split("function onProfileDrop", 1)[0]
    assert drag_over.index("ev.preventDefault()") < drag_over.index("target===dragged")
    assert 'modelEls.configured.addEventListener("dragover",onProfileDragOver)' in html
    assert 'modelEls.configured.addEventListener("drop",onProfileDrop)' in html
    assert 'fetch("/api/model_profiles/reorder"' in html
    assert "ordered_ids:ids" in html
    assert '"ArrowUp"' in html and '"ArrowDown"' in html
    assert "'拖动排序':'Drag to reorder'" in i18n
    assert 'id="model-capability-description"' in html
    assert "capability_description:capabilityFieldValue()" in html
    assert "data-auto-value" in html
    assert 'id="model-multimodal-mode"' in html
    assert 'value="auto">按 models_table.md 自动识别' in html
    assert 'id="model-input-modalities"' in html
    assert "input_modalities:selectedInputModalities()" in html
    assert "multimodal_mode:fieldValue(modelEls.multimodal)" in html
    assert "p.multimodal_source===\"failure\"" in html


def test_reorder_profiles_persists_dragged_priority(tmp_path):
    first = model_profiles.upsert_profile(
        tmp_path,
        {
            "name": "first",
            "model": "model-a",
            "base_url": "https://api.example.com/v1",
            "api_key": "key-a",
            "context_window": 64000,
            "max_output_tokens": 4096,
        },
    )
    second = model_profiles.upsert_profile(
        tmp_path,
        {
            "name": "second",
            "model": "model-b",
            "base_url": "https://api.example.com/v1",
            "api_key": "key-b",
            "context_window": 64000,
            "max_output_tokens": 4096,
        },
    )

    reordered = model_profiles.reorder_profiles(tmp_path, [second["id"], first["id"]])
    reloaded = model_profiles.sorted_profiles(tmp_path)

    assert [item["id"] for item in reordered] == [second["id"], first["id"]]
    assert [item["id"] for item in reloaded] == [second["id"], first["id"]]
    assert [item["priority"] for item in reloaded] == [1, 2]
