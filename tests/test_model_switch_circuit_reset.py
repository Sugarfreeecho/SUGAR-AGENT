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
