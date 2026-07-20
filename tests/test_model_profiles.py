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
        "deepseek-v4-flash": {"low_cost_parallel", "research", "coding_agent"},
        "MiniMax-M3": {"low_cost_parallel", "hard_reasoning", "multimodal_candidate"},
        "gpt-5.4": {"hard_reasoning", "multimodal_candidate", "coding_agent"},
        "claude-opus-4.8": {"hard_reasoning", "multimodal_candidate", "coding_agent"},
        "glm-5.2": {"hard_reasoning", "coding_agent"},
        "gemini-3.1-pro": {"hard_reasoning", "research", "multimodal_candidate"},
        "grok-4.5": {"hard_reasoning", "research", "multimodal_candidate"},
        "mimo-v2.5-pro": {"hard_reasoning", "multimodal_candidate", "coding_agent"},
        "qwen3.7-plus": {"multimodal_candidate", "coding_agent"},
        "kimi-k2.6": {"hard_reasoning", "multimodal_candidate", "coding_agent"},
        "sonar-deep-research": {"research"},
        "pixtral-large": {"multimodal_candidate"},
    }

    for model, expected in cases.items():
        inferred = model_profiles.infer_model_task_capabilities(model, context_window=256_000)
        assert expected <= set(inferred["capability_tags"]), model

    deepseek = model_profiles.infer_model_task_capabilities("deepseek-v4-flash")
    assert "低成本/多并发" in deepseek["capability_description"]
    assert "批量总结" in deepseek["capability_description"]


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
