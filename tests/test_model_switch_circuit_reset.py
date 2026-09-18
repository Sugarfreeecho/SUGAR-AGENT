"""Regression tests: manual model switches clear run-scoped model circuits.

During a run, a candidate that failed once is skipped by the run-scoped
circuit ("本轮运行跳过已失败模型"). A manual mid-run switch to that same
profile must therefore reset the circuit at the switch endpoints; otherwise
the request keeps being served by the old model and the fallback takeover
writes the old binding back (the switch is silently reverted).
"""
import asyncio
import json
import sys
import threading
import uuid
from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _JsonRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class _MetadataStore:
    def __init__(self):
        self.meta = {"model_profile_id": "profile-a"}
        self._lock = threading.RLock()

    def _session_metadata_lock(self, _sid):
        lock = self._lock

        class _Ctx:
            def __enter__(self):
                lock.acquire()
                return self

            def __exit__(self, *exc):
                lock.release()
                return False

        return _Ctx()

    def _load_metadata_unlocked(self, _sid):
        return dict(self.meta)

    def _load_metadata(self, sid):
        with self._session_metadata_lock(sid):
            return self._load_metadata_unlocked(sid)

    def _save_metadata_unlocked(self, _sid, meta):
        self.meta = dict(meta)


def test_session_model_switch_endpoint_resets_run_circuit(monkeypatch):
    import webui

    store = _MetadataStore()
    reset_calls = []
    invalidated = []
    monkeypatch.setattr(webui, "session_manager", store)
    monkeypatch.setattr(webui.model_profiles, "is_usable_profile", lambda _profile: True)
    monkeypatch.setattr(webui.model_profiles, "get_profile", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        webui,
        "_invalidate_executor_config_cache",
        lambda sid="": invalidated.append(sid),
    )
    monkeypatch.setattr(
        webui,
        "reset_executor_failure_state_for_session",
        lambda sid: reset_calls.append(sid) or 1,
    )

    response = asyncio.run(
        webui.set_session_model_profile(
            "sess-1",
            _JsonRequest({"profile_id": "profile-b"}),
        )
    )

    assert response.status_code == 200
    assert json.loads(response.body) == {"ok": True, "profile_id": "profile-b"}
    assert store.meta["model_profile_id"] == "profile-b"
    assert store.meta["model_profile_selection_id"]
    assert invalidated == ["sess-1"]
    assert reset_calls == ["sess-1"]


def test_session_model_switch_endpoint_survives_reset_failure(monkeypatch):
    import webui

    store = _MetadataStore()
    monkeypatch.setattr(webui, "session_manager", store)
    monkeypatch.setattr(webui.model_profiles, "is_usable_profile", lambda _profile: True)
    monkeypatch.setattr(webui.model_profiles, "get_profile", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(webui, "_invalidate_executor_config_cache", lambda _sid="": None)

    def boom(_sid):
        raise RuntimeError("circuit reset exploded")

    monkeypatch.setattr(webui, "reset_executor_failure_state_for_session", boom)

    response = asyncio.run(
        webui.set_session_model_profile(
            "sess-1",
            _JsonRequest({"profile_id": "profile-b"}),
        )
    )

    assert response.status_code == 200
    assert store.meta["model_profile_id"] == "profile-b"


def test_in_flight_old_model_cannot_revert_manual_switch(monkeypatch):
    """The old stream can finish after POST returns; its adoption is stale."""
    import agent_harness
    import webui
    from llm import TransportEvent

    store = _MetadataStore()
    monkeypatch.setattr(agent_harness, "session_manager", store)
    monkeypatch.setattr(webui, "session_manager", store)
    monkeypatch.setattr(webui.model_profiles, "is_usable_profile", lambda _profile: True)
    monkeypatch.setattr(webui.model_profiles, "get_profile", lambda *_args: {})
    started = threading.Event()
    release = threading.Event()

    class OldTransport:
        def stream_completion(self, **_kwargs):
            yield TransportEvent("content_delta", text="old output", model="profile-a")
            started.set()
            assert release.wait(5)
            yield TransportEvent("finish", finish_reason="stop", model="profile-a")

    client = agent_harness.ExecutorLLMClient([{
        "profile_id": "profile-a",
        "model": "profile-a",
        "provider": "openai",
        "transport": OldTransport(),
        "max_output_tokens": 128,
    }])
    client.set_request_scope("old-run")
    client.note_scope_session("sess-1")
    errors = []

    def finish_old_request():
        try:
            list(client.stream_completion(model="profile-a", messages=[], max_tokens=32))
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=finish_old_request)
    worker.start()
    try:
        assert started.wait(5)
        response = asyncio.run(webui.set_session_model_profile(
            "sess-1", _JsonRequest({"profile_id": "profile-b"})
        ))
        assert response.status_code == 200
        assert store.meta["model_profile_id"] == "profile-b"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert not errors
    assert store.meta["model_profile_id"] == "profile-b"
    assert store.meta.get("model_switch_history", []) == []


def test_selected_model_can_still_fallback_after_manual_switch(monkeypatch):
    import agent_harness
    import webui
    from llm import TransportEvent

    store = _MetadataStore()
    monkeypatch.setattr(agent_harness, "session_manager", store)
    monkeypatch.setattr(webui, "session_manager", store)
    monkeypatch.setattr(webui.model_profiles, "is_usable_profile", lambda _profile: True)
    monkeypatch.setattr(webui.model_profiles, "get_profile", lambda *_args: {})
    monkeypatch.setattr(agent_harness, "_claim_additional_recovery_request", lambda: True)
    asyncio.run(webui.set_session_model_profile(
        "sess-1", _JsonRequest({"profile_id": "profile-b"})
    ))

    class Transport:
        def __init__(self, name, fail=False):
            self.name, self.fail = name, fail

        def stream_completion(self, **_kwargs):
            if self.fail:
                raise RuntimeError("unavailable")
            yield TransportEvent("content_delta", text="ok", model=self.name)
            yield TransportEvent("finish", finish_reason="stop", model=self.name)

    client = agent_harness.ExecutorLLMClient([
        {"profile_id": "profile-b", "model": "profile-b", "provider": "openai",
         "transport": Transport("profile-b", fail=True), "max_output_tokens": 128},
        {"profile_id": "profile-c", "model": "profile-c", "provider": "openai",
         "transport": Transport("profile-c"), "max_output_tokens": 128},
    ])
    client.set_request_scope("new-run")
    client.note_scope_session("sess-1")
    list(client.stream_completion(model="profile-b", messages=[], max_tokens=32))
    assert store.meta["model_profile_id"] == "profile-c"
    assert store.meta["model_switch_history"][-1]["requested_by"] == "fallback"


def test_reset_preserves_scope_registered_during_reset(monkeypatch):
    import agent_harness

    sid = "reset-race-session"
    old_scope = f"old-run-{uuid.uuid4().hex}"
    new_scope = f"new-run-{uuid.uuid4().hex}"
    failure_lock = agent_harness._executor_failure_lock
    failures = {}
    old = agent_harness.ExecutorLLMClient(
        [], failure_lock=failure_lock, failed_candidates_by_scope=failures
    )
    old.set_request_scope(old_scope)
    old.note_scope_session(sid)
    original_reset_scope = agent_harness._scope_client_registry.reset_scope
    new_clients = []

    def register_while_resetting(scope):
        new = agent_harness.ExecutorLLMClient(
            [], failure_lock=failure_lock, failed_candidates_by_scope=failures
        )
        new.set_request_scope(new_scope)
        new.note_scope_session(sid)
        failures[new_scope]["failed-model"] = "failure"
        new_clients.append(new)
        return original_reset_scope(scope)

    monkeypatch.setattr(
        agent_harness._scope_client_registry, "reset_scope", register_while_resetting
    )
    agent_harness.reset_executor_failure_state_for_session(sid)
    monkeypatch.setattr(
        agent_harness._scope_client_registry, "reset_scope", original_reset_scope
    )
    assert agent_harness._session_run_scopes[sid] == {new_scope}
    assert agent_harness.reset_executor_failure_state_for_session(sid) == 1
    assert new_scope not in failures


def test_in_flight_failure_does_not_repopulate_reset_circuit():
    import agent_harness

    started = threading.Event()
    release = threading.Event()
    failures = {}

    class FailingTransport:
        def stream_completion(self, **_kwargs):
            started.set()
            assert release.wait(5)
            raise RuntimeError("late failure")
            yield  # Make this a streaming transport.

    client = agent_harness.ExecutorLLMClient([{
        "profile_id": "target", "model": "target", "provider": "openai",
        "transport": FailingTransport(), "max_output_tokens": 128,
    }], failure_lock=agent_harness._executor_failure_lock,
       failed_candidates_by_scope=failures)
    client.set_request_scope("late-failure-run")
    client.note_scope_session("late-failure-session")
    errors = []

    def finish_request():
        try:
            list(client.stream_completion(model="target", messages=[], max_tokens=32))
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=finish_request)
    worker.start()
    try:
        assert started.wait(5)
        assert agent_harness.reset_executor_failure_state_for_session(
            "late-failure-session"
        ) == 1
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert len(errors) == 1
    assert "late-failure-run" not in failures


def test_switch_during_config_build_does_not_recache_old_model(monkeypatch):
    import agent_harness

    sid = f"config-race-{uuid.uuid4().hex}"
    store = _MetadataStore()
    monkeypatch.setattr(agent_harness, "session_manager", store)
    agent_harness._invalidate_executor_config_cache(sid)
    resolved = []

    def candidates(_sid, *, profile_id_override):
        resolved.append(profile_id_override)
        if len(resolved) == 1:
            with store._session_metadata_lock(sid):
                store.meta["model_profile_id"] = "profile-b"
                store.meta["model_profile_selection_id"] = "switch-during-build"
            agent_harness._invalidate_executor_config_cache(sid)
        return [{
            "profile_id": profile_id_override,
            "model": profile_id_override,
            "provider": "openai",
            "transport": object(),
            "max_output_tokens": 128,
        }]

    monkeypatch.setattr(
        agent_harness, "resolve_executor_candidates_for_session", candidates
    )
    first = agent_harness.resolve_executor_config_for_session(sid)
    second = agent_harness.resolve_executor_config_for_session(sid)
    assert resolved == ["profile-a", "profile-b"]
    assert first is second
    assert first[1] == "profile-b"
    assert first[0]._bound_model_selection_id == "switch-during-build"


def test_session_endpoint_routes_subagent_targets_into_switch_pipeline(monkeypatch):
    """The bottom-right selector must reuse the subagent switch pipeline."""
    import agent_subagent
    import webui

    store = _MetadataStore()
    store.meta = {
        "is_subagent": True,
        "parent_session_id": "parent-1",
        "model_profile_id": "profile-a",
    }
    captured = {}
    reset_calls = []
    invalidated = []
    monkeypatch.setattr(webui, "session_manager", store)
    monkeypatch.setattr(webui.model_profiles, "is_usable_profile", lambda _profile: True)
    monkeypatch.setattr(webui.model_profiles, "get_profile", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        webui,
        "_invalidate_executor_config_cache",
        lambda sid="": invalidated.append(sid),
    )
    monkeypatch.setattr(
        webui,
        "reset_executor_failure_state_for_session",
        lambda sid: reset_calls.append(sid) or 1,
    )

    async def fake_switch(parent, child, profile_id, **kwargs):
        captured.update({"parent": parent, "child": child, "profile_id": profile_id, **kwargs})
        return {
            "ok": True,
            "agent_id": child,
            "profile_id": profile_id,
            "model": "model-b",
            "previous_profile_id": "profile-a",
            "running": False,
            "switch_id": "switch-1",
            "handover": False,
            "interrupted_current_step": False,
            "continuation_queued": False,
        }

    monkeypatch.setattr(agent_subagent, "switch_subagent_model_profile", fake_switch)

    response = asyncio.run(
        webui.set_session_model_profile(
            "child-1",
            _JsonRequest({"profile_id": "profile-b"}),
        )
    )

    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["ok"] is True
    assert payload["profile_id"] == "profile-b"
    assert captured == {
        "parent": "parent-1",
        "child": "child-1",
        "profile_id": "profile-b",
        "requested_by": "user",
        "handover": False,
    }
    # The pipeline owns every durable write; the generic path must not run.
    assert invalidated == []
    assert reset_calls == []
    assert store.meta["model_profile_id"] == "profile-a"


def test_session_endpoint_rejects_subagent_without_parent(monkeypatch):
    import webui

    store = _MetadataStore()
    store.meta = {"is_subagent": True, "model_profile_id": "profile-a"}
    monkeypatch.setattr(webui, "session_manager", store)
    monkeypatch.setattr(webui.model_profiles, "is_usable_profile", lambda _profile: True)
    monkeypatch.setattr(webui.model_profiles, "get_profile", lambda *_args, **_kwargs: {})

    response = asyncio.run(
        webui.set_session_model_profile(
            "child-1",
            _JsonRequest({"profile_id": "profile-b"}),
        )
    )

    assert response.status_code == 409
