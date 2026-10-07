import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

SID = "00000000-0000-4000-8000-000000000041"


def test_model_headers_preserve_clear_validate_and_empty_extra_keeps_thinking(tmp_path):
    import model_profiles
    import agent_harness
    saved = model_profiles.upsert_profile(tmp_path, {"model": "fixture", "base_url": "https://fixture.test/v1", "api_key": "test",
        "headers": {"X-Fixture": "value"}, "extra_body_json": "{}"})
    assert saved["thinking_mode"] == "enabled"
    assert saved["extra_body_json"] == ""
    assert agent_harness._profile_extra_body(saved) == {"thinking": {"type": "enabled"}}
    edit = {"id": saved["id"], "model": saved["model"], "base_url": saved["base_url"]}
    updated = model_profiles.upsert_profile(tmp_path, {**edit, "name": "Renamed"})
    assert updated["headers"] == {"X-Fixture": "value"}
    before = model_profiles.profile_store_path(tmp_path).read_bytes()
    for headers in (["bad"], {"bad header": "value"}, {"X-Fixture": "a\r\nb"}, {"X-Fixture": 123}):
        with pytest.raises(ValueError):
            model_profiles.upsert_profile(tmp_path, {**edit, "headers": headers})
    for extra in ("[1]", "null", "invalid"):
        with pytest.raises(ValueError):
            model_profiles.upsert_profile(tmp_path, {**edit, "extra_body_json": extra})
    assert model_profiles.profile_store_path(tmp_path).read_bytes() == before
    cleared = model_profiles.upsert_profile(tmp_path, {**edit, "headers": {}})
    assert not cleared.get("headers")


def test_capability_preview_is_generated_without_persisting_profiles(tmp_path, monkeypatch):
    import webui
    monkeypatch.setattr(webui, "PROJECT_ROOT", tmp_path)
    response = TestClient(webui.fastapi_app).post("/api/model_profiles/capabilities", json={"model": "deepseekv4"})
    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    assert capabilities["capability_source"] == "automatic:models-table"
    assert capabilities["capability_description"]
    assert not (tmp_path / ".sugaragent" / "model_profiles.json").exists()


@pytest.fixture
def session_effort_client(tmp_path, monkeypatch):
    import agent_harness
    import webui
    root = tmp_path / "sessions"
    (root / SID).mkdir(parents=True)
    (root / SID / "metadata.json").write_text(json.dumps({"id": SID, "name": "Example", "model_profile_id": "p1"}))
    manager = agent_harness.SessionManager(root, tmp_path / "index.json")
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "_invalidate_executor_config_cache", lambda sid: None)
    monkeypatch.setattr(webui, "reset_executor_failure_state_for_session", lambda sid: None)
    return TestClient(webui.fastapi_app), manager


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max", ""])
def test_session_effort_persists_without_overwriting_model_binding(session_effort_client, effort):
    client, manager = session_effort_client
    response = client.post(f"/sessions/{SID}/reasoning_effort", json={"reasoning_effort": effort})
    assert response.status_code == 200
    metadata = manager._load_metadata(SID)
    assert metadata["model_profile_id"] == "p1"
    assert metadata.get("reasoning_effort", "") == effort


@pytest.mark.parametrize("payload", [{"reasoning_effort": "ultra"}, {"reasoning_effort": None}, {"reasoning_effort": 3}, {}, []])
def test_invalid_session_effort_does_not_mutate_metadata(session_effort_client, payload):
    client, manager = session_effort_client
    before = manager._load_metadata(SID)
    assert client.post(f"/sessions/{SID}/reasoning_effort", json=payload).status_code == 400
    assert manager._load_metadata(SID) == before


@pytest.mark.parametrize("provider", ["openai-responses", "openai-compatible", "anthropic"])
def test_session_effort_applies_after_frozen_snapshot_and_to_fallbacks(monkeypatch, provider):
    import agent_harness
    profiles = {pid: {"id": pid, "model": "fixture", "base_url": "https://fixture.test/v1", "llm_type": provider,
                      "api_key": "test", "reasoning_effort": "low", "extra_body_json": '{"fixture":true}'} for pid in ("p1", "p2")}
    original = json.dumps(profiles)
    monkeypatch.setattr(agent_harness, "_executor_profile_catalog", lambda: (profiles, ["p1", "p2"], "p1"))
    monkeypatch.setattr(agent_harness, "session_manager", SimpleNamespace(_load_metadata=lambda sid: {
        "model_profile_id": "p2", "reasoning_effort": "max", "fork_model_runtime": {"reasoning_effort": "medium", "extra_body": {"fixture": True}}}))
    candidates = agent_harness.resolve_executor_candidates_for_session("fixture")
    assert [item["profile_id"] for item in candidates] == ["p2", "p1"]
    assert all(item["reasoning_effort"] == "max" for item in candidates)
    assert json.dumps(profiles) == original
    if provider != "openai-responses":
        assert all(item["extra_body"]["thinking"]["type"] == "enabled" for item in candidates)
    else:
        assert all("thinking" not in (item.get("extra_body") or {}) for item in candidates)
    client, _, _, _ = agent_harness._build_executor_config_for_session("fixture")
    assert client.candidates[0]["reasoning_effort"] == "max", "fork snapshots must not overwrite the session's newer choice"
