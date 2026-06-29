import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _FakeRepository:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir


class _FakeSessionManager:
    def __init__(self, sessions_dir: Path, events: list[dict]):
        self.repository = _FakeRepository(sessions_dir)
        self.events = list(events)
        self.page_calls: list[dict] = []
        self.display_calls = 0
        self.count_calls = 0
        self.truncate_calls: list[dict] = []
        self.branch_calls: list[dict] = []
        self.list_calls: list[dict] = []

    def _resolve_session_path(self, session_id: str) -> Path:
        return self.repository.sessions_dir / session_id

    def get_ui_event_count(self, session_id: str) -> int:
        self.count_calls += 1
        return len(self.events)

    def get_ui_events_for_display(self, session_id: str) -> list[dict]:
        self.display_calls += 1
        return [dict(event) for event in self.events]

    def get_ui_events_page(self, session_id: str, limit: int = 200, before_index=None, turns=None) -> dict:
        self.page_calls.append({
            "session_id": session_id,
            "limit": limit,
            "before_index": before_index,
            "turns": turns,
        })
        return {
            "events": [dict(event) for event in self.events[-2:]],
            "total": len(self.events),
            "range_start": max(0, len(self.events) - 2),
            "range_end": len(self.events),
            "has_older": len(self.events) > 2,
            "has_newer": False,
            "source": "fake_legacy_page",
        }

    def truncate_session_at_event_index(
        self,
        session_id: str,
        before_index: int,
        *,
        truncate_before_seq=None,
        create_backup: bool = True,
    ) -> bool:
        self.truncate_calls.append({
            "session_id": session_id,
            "before_index": before_index,
            "truncate_before_seq": truncate_before_seq,
            "create_backup": create_backup,
        })
        return True

    def branch_session_at_event_index(
        self,
        session_id: str,
        before_index: int,
        *,
        branch_after_seq=None,
    ) -> dict:
        self.branch_calls.append({
            "session_id": session_id,
            "before_index": before_index,
            "branch_after_seq": branch_after_seq,
        })
        return {"ok": True, "session_id": "branch-1", "name": "branch"}

    def list_sessions(self, include_archived: bool = False) -> list[dict]:
        self.list_calls.append({"include_archived": include_archived})
        return [{
            "id": "s1",
            "name": "Session 1",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "archived": False,
        }]

    def archived_session_count(self) -> int:
        return 0


class _NoLegacyUiSessionManager(_FakeSessionManager):
    def get_ui_event_count(self, session_id: str) -> int:
        raise AssertionError("Runtime V2 messages path must not read legacy UI count")

    def get_ui_events_for_display(self, session_id: str) -> list[dict]:
        raise AssertionError("Runtime V2 messages path must not read legacy UI events")

    def get_ui_events_page(self, session_id: str, limit: int = 200, before_index=None, turns=None) -> dict:
        raise AssertionError("Runtime V2 messages path must not read legacy UI page")


def _json_response_payload(response) -> dict | list:
    return json.loads(response.body.decode("utf-8"))


def test_messages_turn_page_prefers_runtime_v2_projection(monkeypatch, tmp_path):
    import runtime_v2
    from runtime_v2 import RuntimeMirror
    import webui

    monkeypatch.setattr(runtime_v2, "runtime_v1_primary", lambda: False)
    mirror = RuntimeMirror(tmp_path)
    for event in [
        {"type": "user", "content": "u0"},
        {"type": "final", "content": "a0"},
        {"type": "user", "content": "u1"},
        {"type": "final", "content": "a1"},
    ]:
        mirror.mirror_ui_event("s1", event)
    fake = _FakeSessionManager(tmp_path, [
        {"type": "user", "content": "legacy"},
    ])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.get_session_messages(
        "s1",
        limit=None,
        before_index=None,
        after_index=None,
        turns=5,
    ))
    payload = _json_response_payload(response)

    assert payload["source"] == "runtime_v2_tail_index"
    assert payload["total"] == 4
    assert [event["content"] for event in payload["events"]] == ["u0", "a0", "u1", "a1"]
    assert fake.page_calls == []
    assert fake.display_calls == 0


def test_messages_full_read_prefers_runtime_v2_projection(monkeypatch, tmp_path):
    import runtime_v2
    from runtime_v2 import RuntimeMirror
    import webui

    monkeypatch.setattr(runtime_v2, "runtime_v1_primary", lambda: False)
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "u0"})
    mirror.mirror_ui_event("s1", {"type": "final", "content": "a0"})
    fake = _FakeSessionManager(tmp_path, [
        {"type": "user", "content": "legacy"},
    ])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.get_session_messages(
        "s1",
        limit=None,
        before_index=None,
        after_index=None,
        turns=None,
    ))
    payload = _json_response_payload(response)

    assert [event["content"] for event in payload] == ["u0", "a0"]
    assert fake.display_calls == 0
    assert fake.page_calls == []


def test_message_count_prefers_runtime_v2_projection(monkeypatch, tmp_path):
    import runtime_v2
    from runtime_v2 import RuntimeMirror
    import webui

    monkeypatch.setattr(runtime_v2, "runtime_v1_primary", lambda: False)
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "u0"})
    mirror.mirror_ui_event("s1", {"type": "final", "content": "a0"})
    fake = _FakeSessionManager(tmp_path, [
        {"type": "user", "content": "legacy"},
    ])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.get_session_message_count("s1"))
    payload = _json_response_payload(response)

    assert payload == {"count": 2, "source": "runtime_v2"}
    assert fake.count_calls == 0


def test_messages_empty_runtime_v2_projection_does_not_fallback_legacy(monkeypatch, tmp_path):
    import runtime_v2
    import webui

    monkeypatch.setattr(runtime_v2, "runtime_v1_primary", lambda: False)
    fake = _NoLegacyUiSessionManager(tmp_path, [{"type": "user", "content": "legacy"}])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.get_session_messages(
        "s1",
        limit=None,
        before_index=None,
        after_index=None,
        turns=None,
    ))
    payload = _json_response_payload(response)

    assert payload == []


def test_message_count_empty_runtime_v2_projection_does_not_fallback_legacy(monkeypatch, tmp_path):
    import runtime_v2
    import webui

    monkeypatch.setattr(runtime_v2, "runtime_v1_primary", lambda: False)
    fake = _NoLegacyUiSessionManager(tmp_path, [{"type": "user", "content": "legacy"}])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.get_session_message_count("s1"))
    payload = _json_response_payload(response)

    assert payload == {"count": 0, "source": "runtime_v2"}


def test_messages_projection_error_does_not_fallback_legacy(monkeypatch, tmp_path):
    import runtime_v2
    import runtime_v2.ui_projection
    import webui

    class _BrokenProjection:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("projection unavailable")

    monkeypatch.setattr(runtime_v2, "runtime_v1_primary", lambda: False)
    monkeypatch.setattr(runtime_v2.ui_projection, "RuntimeUiProjection", _BrokenProjection)
    fake = _NoLegacyUiSessionManager(tmp_path, [{"type": "user", "content": "legacy"}])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.get_session_messages(
        "s1",
        limit=None,
        before_index=None,
        after_index=None,
        turns=None,
    ))
    payload = _json_response_payload(response)

    assert payload == []


def test_message_count_projection_error_does_not_fallback_legacy(monkeypatch, tmp_path):
    import runtime_v2
    import runtime_v2.ui_projection
    import webui

    class _BrokenProjection:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("projection unavailable")

    monkeypatch.setattr(runtime_v2, "runtime_v1_primary", lambda: False)
    monkeypatch.setattr(runtime_v2.ui_projection, "RuntimeUiProjection", _BrokenProjection)
    fake = _NoLegacyUiSessionManager(tmp_path, [{"type": "user", "content": "legacy"}])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.get_session_message_count("s1"))
    payload = _json_response_payload(response)

    assert payload == {"count": 0, "source": "runtime_v2_projection_error"}


def test_truncate_route_passes_runtime_seq_boundary(monkeypatch, tmp_path):
    import webui

    fake = _FakeSessionManager(tmp_path, [])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.truncate_session_events(
        "s1",
        before_index=10,
        before_seq=99,
        backup=True,
    ))
    payload = _json_response_payload(response)

    assert payload == {"ok": True}
    assert fake.truncate_calls == [{
        "session_id": "s1",
        "before_index": 10,
        "truncate_before_seq": 99,
        "create_backup": True,
    }]


def test_branch_route_passes_runtime_seq_boundary(monkeypatch, tmp_path):
    import webui

    fake = _FakeSessionManager(tmp_path, [])
    monkeypatch.setattr(webui, "session_manager", fake)

    response = asyncio.run(webui.branch_session_events(
        "s1",
        before_index=10,
        after_seq=123,
    ))
    payload = _json_response_payload(response)

    assert payload == {"ok": True, "session_id": "branch-1", "name": "branch"}
    assert fake.branch_calls == [{
        "session_id": "s1",
        "before_index": 10,
        "branch_after_seq": 123,
    }]


def test_sessions_state_uses_lightweight_run_status(monkeypatch, tmp_path):
    import webui

    fake = _FakeSessionManager(tmp_path, [])
    monkeypatch.setattr(webui, "session_manager", fake)
    monkeypatch.setattr(webui, "is_run_active", lambda sid: sid == "s1")
    monkeypatch.setattr(webui, "get_run_started_at", lambda sid: "2026-01-01T00:00:00Z")
    monkeypatch.setattr(webui, "_active_chat_by_session", {})

    def fail_snapshot(_sid):
        raise AssertionError("/sessions/state must not read Runtime V2 snapshots")

    monkeypatch.setattr(webui, "_runtime_v2_snapshot", fail_snapshot)

    payload = webui._build_sessions_state_snapshot(include_archived=False)

    assert fake.list_calls == [{"include_archived": False}]
    assert payload["sessions"][0]["id"] == "s1"
    assert payload["sessions"][0]["stream_active"] is True
    assert payload["sessions"][0]["run_active"] is True
    assert payload["active_runs"][0]["session_id"] == "s1"
    assert payload["active_runs"][0]["lightweight"] is True
