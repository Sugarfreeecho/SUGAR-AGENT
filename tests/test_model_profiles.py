import sys
import json
from pathlib import Path

import httpx


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import model_profiles


def test_profile_store_defaults_to_project_root(tmp_path):
    assert model_profiles.profile_store_path(tmp_path) == tmp_path / "model_profiles.json"


def test_model_task_capabilities_cover_routing_families():
    cases = {
        "deepseek-v4-flash": {"low_cost_parallel", "research", "coding", "agent"},
        "MiniMax-M3": {"low_cost_parallel", "multimodal_candidate", "coding", "agent"},
        "gpt-5.4": {"hard_reasoning", "multimodal_candidate", "coding", "agent"},
        "claude-opus-4.8": {"hard_reasoning", "multimodal_candidate", "coding", "agent"},
        "glm-5.2": {"hard_reasoning", "coding", "agent"},
        "gemini-3.1-pro": {"hard_reasoning", "research", "multimodal_candidate"},
        "grok-4.5": {"hard_reasoning", "research", "multimodal_candidate"},
        "mimo-v2.5-pro": {"hard_reasoning", "multimodal_candidate", "coding", "agent"},
        "qwen3.7-plus": {"multimodal_candidate", "coding", "agent"},
        "kimi-k2.6": {"hard_reasoning", "multimodal_candidate", "coding", "agent"},
        "sonar-deep-research": {"research"},
        "pixtral-large": {"multimodal_candidate"},
    }

    for model, expected in cases.items():
        inferred = model_profiles.infer_model_task_capabilities(model, context_window=256_000)
        assert expected <= set(inferred["capability_tags"]), model

    deepseek = model_profiles.infer_model_task_capabilities("deepseek-v4-flash")
    assert "低成本/多并发" in deepseek["capability_description"]
    assert "批量总结" in deepseek["capability_description"]
    assert "代码：" in deepseek["capability_description"]
    assert "Agent：" in deepseek["capability_description"]
    assert "hard_reasoning" not in model_profiles.infer_model_task_capabilities("MiniMax-M3")["capability_tags"]


def test_public_profile_adds_automatic_capability_description():
    public = model_profiles.public_profile({
        "name": "Research model",
        "model": "gemini-3.1-pro",
        "context_window": 1_000_000,
        "api_key": "secret",
    })

    assert public["capability_source"] == "automatic:model-family-heuristic"
    assert {"research", "multimodal_candidate", "long_context"} <= set(public["capability_tags"])
    assert "调查调研" in public["capability_description"]


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
    assert automatic["capability_source"] == "automatic:model-family-heuristic"
    assert "hard_reasoning" not in automatic["capability_tags"]


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
    assert public["multimodal_source"] == "automatic:model-family-heuristic"
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
    assert models[0]["context_window"] == model_profiles.DEFAULT_UNKNOWN_CONTEXT_WINDOW
    assert models[0]["model_context_window"] == model_profiles.DEFAULT_UNKNOWN_CONTEXT_WINDOW
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
    assert "capability_description:fieldValue(modelEls.capability)" in html
    assert 'id="model-multimodal-mode"' in html
    assert 'value="auto">自动识别' in html
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
