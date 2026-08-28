from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.runtime_v2 import (
    ExtensionStateConflict,
    ExtensionStateError,
    ExtensionStateNotFound,
    RuntimeProjector,
    SessionEventLog,
    SessionExtensionStateStore,
    SnapshotStore,
)


def _store(tmp_path, session_id: str = "s1", **kwargs):
    (tmp_path / session_id).mkdir(parents=True, exist_ok=True)
    return SessionExtensionStateStore(tmp_path, **kwargs)


def test_extension_state_compare_and_set_is_revisioned_and_replayable(tmp_path):
    store = _store(tmp_path)

    assert store.get("s1", "session-todo", "plan") == {
        "revision": 0,
        "value": None,
        "updated_at": None,
        "seq": 0,
    }
    first = store.compare_and_set(
        "s1",
        "session-todo",
        "plan",
        expected_revision=0,
        value={"items": [{"id": "1", "status": "pending"}]},
    )
    assert first["revision"] == 1
    assert first["value"]["items"][0]["id"] == "1"

    with pytest.raises(ExtensionStateConflict) as exc_info:
        store.compare_and_set(
            "s1", "session-todo", "plan", expected_revision=0, value={}
        )
    assert exc_info.value.actual_revision == 1

    snapshot_path = tmp_path / "s1" / "snapshots" / "latest.json"
    snapshot_path.unlink()
    recovered = SessionExtensionStateStore(tmp_path).get(
        "s1", "session-todo", "plan"
    )
    assert recovered["revision"] == 1
    assert recovered["value"] == first["value"]


def test_lightweight_extension_read_does_not_copy_whole_runtime_snapshot(
    tmp_path, monkeypatch
):
    store = _store(tmp_path)
    store.compare_and_set(
        "s1",
        "demo",
        "panel",
        expected_revision=0,
        value={"active": True},
    )
    snapshot = store.snapshots.read_for_update("s1")
    snapshot["large_unrelated_payload"] = "x" * 100_000

    def fail_full_read(_session_id):
        raise AssertionError("lightweight UI projection must not deepcopy the full snapshot")

    monkeypatch.setattr(store.snapshots, "read", fail_full_read)
    extensions = store.read_all_lightweight("s1")

    assert extensions["demo"]["panel"]["value"] == {"active": True}
    assert "large_unrelated_payload" not in extensions


def test_extension_state_patch_supports_objects_arrays_and_root_replace(tmp_path):
    store = _store(tmp_path)
    created = store.compare_and_set(
        "s1",
        "demo",
        "settings",
        expected_revision=0,
        value={"enabled": False, "labels": ["one"]},
    )
    patched = store.patch(
        "s1",
        "demo",
        "settings",
        expected_revision=created["revision"],
        operations=[
            {"op": "replace", "path": "/enabled", "value": True},
            {"op": "add", "path": "/labels/-", "value": "two"},
            {"op": "remove", "path": "/labels/0"},
        ],
    )
    assert patched["revision"] == 2
    assert patched["value"] == {"enabled": True, "labels": ["two"]}

    replaced = store.patch(
        "s1",
        "demo",
        "settings",
        expected_revision=2,
        operations=[{"op": "replace", "path": "", "value": [1, 2]}],
    )
    assert replaced["value"] == [1, 2]


def test_extension_events_are_generic_and_bounded_in_projection(tmp_path):
    store = _store(tmp_path)
    for index in range(105):
        store.append_event("s1", "demo", "changed", {"index": index})

    snapshot = SnapshotStore(tmp_path).read("s1")
    assert len(snapshot["extension_events"]) == 100
    assert snapshot["extension_events"][0]["data"] == {"index": 5}
    assert snapshot["extension_events"][-1]["event_name"] == "changed"
    event_types = {event.type for event in SessionEventLog(tmp_path).read_all("s1")}
    assert event_types == {"extension_event"}

    from app.runtime_v2.ui_projection import RuntimeUiProjection

    visible = RuntimeUiProjection(tmp_path).read_ui_events("s1")
    assert len(visible) == 105
    assert visible[-1] == {
        "type": "extension_event",
        "plugin_id": "demo",
        "event_name": "changed",
        "data": {"index": 104},
        "created_at": visible[-1]["created_at"],
        "runtime_seq": 105,
        "runtime_event_type": "extension_event",
    }


def test_extension_state_rejects_missing_sessions_invalid_ids_and_large_values(tmp_path):
    store = SessionExtensionStateStore(tmp_path, max_state_bytes=32)
    with pytest.raises(ExtensionStateNotFound):
        store.get("missing", "demo", "state")

    (tmp_path / "s1").mkdir()
    with pytest.raises(ExtensionStateError, match="plugin_id"):
        store.get("s1", "../demo", "state")
    with pytest.raises(ExtensionStateError, match="exceeds"):
        store.compare_and_set(
            "s1", "demo", "state", expected_revision=0, value={"text": "x" * 64}
        )
    with pytest.raises(ExtensionStateError, match="JSON serializable"):
        store.compare_and_set(
            "s1", "demo", "state", expected_revision=0, value={"bad": {1, 2}}
        )


def test_concurrent_compare_and_set_allows_exactly_one_writer(tmp_path):
    store = _store(tmp_path)

    def write(value: int):
        try:
            return store.compare_and_set(
                "s1", "demo", "counter", expected_revision=0, value=value
            )
        except ExtensionStateConflict:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(8)))

    winners = [item for item in results if item is not None]
    assert len(winners) == 1
    assert store.get("s1", "demo", "counter")["revision"] == 1


def test_projector_ignores_stale_extension_revisions():
    projector = RuntimeProjector()
    from app.runtime_v2 import RuntimeEvent

    events = [
        RuntimeEvent(
            seq=1,
            type="extension_state_changed",
            session_id="s1",
            payload={"plugin_id": "demo", "namespace": "state", "revision": 2, "value": "new"},
        ),
        RuntimeEvent(
            seq=2,
            type="extension_state_changed",
            session_id="s1",
            payload={"plugin_id": "demo", "namespace": "state", "revision": 1, "value": "old"},
        ),
    ]
    snapshot = projector.project(events)
    assert snapshot["extensions"]["demo"]["state"]["value"] == "new"


def test_todo_compatibility_bridge_writes_generic_namespace(tmp_path):
    from app.session_todo_extension import read_todo_extension, write_todo_extension

    class Manager:
        sessions_dir = tmp_path

    (tmp_path / "s1").mkdir()
    manager = Manager()
    row = write_todo_extension(
        manager,
        "s1",
        [{"id": "1", "text": "ship", "status": "in_progress"}],
        run_id="run-1",
    )

    assert row["revision"] == 1
    assert read_todo_extension(manager, "s1") == {
        "schema_version": 1,
        "has_plan": True,
        "items": [{"id": "1", "text": "ship", "status": "in_progress"}],
        "done": 0,
        "total": 1,
        "cleared": False,
    }
    events = SessionEventLog(tmp_path).read_all("s1")
    assert events[-1].type == "extension_state_changed"
    assert events[-1].run_id == "run-1"
