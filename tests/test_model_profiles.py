import sys
from pathlib import Path

import httpx


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import model_profiles


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


def test_env_profile_participates_in_model_order(tmp_path):
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
    env = model_profiles.env_profile_from_env(
        tmp_path,
        {
            "EXECUTOR_LLM": "env-model",
            "OPENAI_BASE_URL": "https://api.example.com/v1",
            "OPENAI_API_KEY": "env-key",
        },
    )

    assert [p["id"] for p in model_profiles.sorted_profiles_with_env(tmp_path, env)] == [saved["id"], "__env__"]

    model_profiles.reorder_profiles(tmp_path, ["__env__", saved["id"]])
    env = model_profiles.env_profile_from_env(
        tmp_path,
        {
            "EXECUTOR_LLM": "env-model",
            "OPENAI_BASE_URL": "https://api.example.com/v1",
            "OPENAI_API_KEY": "env-key",
        },
    )

    assert [p["id"] for p in model_profiles.sorted_profiles_with_env(tmp_path, env)] == ["__env__", saved["id"]]
    assert model_profiles.top_profile_id_with_env(tmp_path) == "__env__"
