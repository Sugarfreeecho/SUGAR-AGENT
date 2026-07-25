import json

from app.runtime_v2 import RuntimeEvent, RuntimeMirror, RuntimeProjector, RuntimeUiProjection, SessionEventLog, SnapshotStore
from app.runtime_v2.versions import EVENT_SCHEMA_VERSION, PROJECTOR_VERSION, UI_PROJECTION_INDEX_VERSION


def test_runtime_event_schema_version_is_serialized_and_future_versions_fail():
    row = RuntimeEvent(seq=1, type="message_user", session_id="s1").to_dict()
    assert row["schema_version"] == EVENT_SCHEMA_VERSION
    assert RuntimeEvent.from_dict({key: value for key, value in row.items() if key != "schema_version"}).seq == 1
    row["schema_version"] = EVENT_SCHEMA_VERSION + 1
    try:
        RuntimeEvent.from_dict(row)
    except ValueError as exc:
        assert "newer than supported" in str(exc)
    else:
        raise AssertionError("future event schema must fail closed")


def test_snapshot_with_stale_projector_version_rebuilds(tmp_path):
    log = SessionEventLog(tmp_path)
    log.append("s1", "message_user", {"content": "hello"})
    store = SnapshotStore(tmp_path)
    stale = RuntimeProjector().project(log.read_all("s1"))
    store.stamp_event_log("s1", stale, log.event_path("s1"))
    stale["_projection"]["projector_version"] = PROJECTOR_VERSION - 1
    stale["messages"] = []
    store.write("s1", stale)

    rebuilt = store.read_consistent("s1", log, RuntimeProjector())

    assert rebuilt["_projection"]["projector_version"] == PROJECTOR_VERSION
    assert rebuilt["messages"][0]["payload"]["content"] == "hello"


def test_ui_index_with_stale_version_rebuilds(tmp_path):
    projection = RuntimeUiProjection(tmp_path)
    RuntimeMirror(tmp_path).append("s1", "message_user", {"content": "hello"})
    turns = projection.read_user_turns_light("s1")
    assert len(turns) == 1
    path = projection._ui_index_path("s1")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["index_version"] = UI_PROJECTION_INDEX_VERSION - 1
    data["total"] = 999
    path.write_text(json.dumps(data), encoding="utf-8")

    rebuilt = projection.read_user_turns_light("s1")

    assert len(rebuilt) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["index_version"] == UI_PROJECTION_INDEX_VERSION


def test_incremental_projector_matches_full_replay():
    events = [
        RuntimeEvent(seq=1, type="message_user", session_id="s1", payload={"content": "u1"}),
        RuntimeEvent(seq=2, type="model_user", session_id="s1", payload={"content": "u1"}),
        RuntimeEvent(seq=3, type="run_started", session_id="s1", run_id="r1"),
        RuntimeEvent(seq=4, type="message_assistant_delta", session_id="s1", run_id="r1", payload={"delta": "a"}),
        RuntimeEvent(seq=5, type="message_assistant_delta", session_id="s1", run_id="r1", payload={"delta": "1"}),
        RuntimeEvent(seq=6, type="model_assistant", session_id="s1", payload={"content": "a1"}),
        RuntimeEvent(seq=7, type="context_tokens", session_id="s1", payload={"estimated": 10}),
        RuntimeEvent(seq=8, type="message_rewritten", session_id="s1", payload={"target_seq": 1, "content": "u1-new"}),
        RuntimeEvent(seq=9, type="run_finished", session_id="s1", run_id="r1"),
    ]
    projector = RuntimeProjector()
    incremental = projector.empty_snapshot()
    for event in events:
        incremental = projector.project_incremental(incremental, event)

    assert incremental == projector.project(events)


def test_checkpoint_lag_recovers_incrementally_after_memory_cache_loss(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS", "100")
    mirror = RuntimeMirror(tmp_path)
    mirror.append("s1", "message_user", {"content": "one"})
    mirror.append("s1", "message_assistant_final", {"content": "two"})
    store = SnapshotStore(tmp_path)
    assert store.wait_for_checkpoint("s1", timeout_seconds=2)
    path = store.path("s1")
    assert json.loads(path.read_text(encoding="utf-8"))["last_seq"] == 1

    SnapshotStore._memory_cache.clear()
    rebuilt = SnapshotStore(tmp_path).read_consistent("s1")

    assert rebuilt["last_seq"] == 2
    assert [row["payload"]["content"] for row in rebuilt["visible_messages"]] == ["one", "two"]
