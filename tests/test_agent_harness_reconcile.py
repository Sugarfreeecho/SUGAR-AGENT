import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _manager_with(**attrs):
    import agent_harness

    mgr = agent_harness.SessionManager.__new__(agent_harness.SessionManager)
    for name, value in attrs.items():
        setattr(mgr, name, value)
    return mgr


class _Repository:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir


def test_reconcile_does_not_rebuild_when_llm_user_count_matches_ui():
    import agent_harness

    ui_events = [
        {"type": "user", "content": "u1"},
        {"type": "final", "content": "a1"},
        {"type": "user", "content": "u2"},
    ]
    llm_history = [
        {"type": "user", "content": "u1"},
        {
            "type": "assistant",
            "content": "",
            "tool_calls": [{"name": "search", "args": {}, "id": "call_1"}],
        },
        {"type": "tool", "content": "tool result", "tool_call_id": "call_1"},
        {"type": "assistant", "content": "a1", "metadata": {"is_final": True}},
        {"type": "user", "content": "u2"},
        {"type": "assistant", "content": "a2", "metadata": {"is_final": True}},
    ]
    saved_llm = []

    def fail_rebuild(*args, **kwargs):
        raise AssertionError("reconcile must not rebuild llm_history when user counts match")

    mgr = _manager_with(
        _runtime_v2_primary=lambda: False,
        _load_ui_events=lambda sid: ui_events,
        _load_llm_history=lambda sid: llm_history,
        _load_work_messages=lambda sid: [],
        _save_llm_history=lambda sid, msgs: saved_llm.append(msgs),
        _save_work_messages=lambda sid, msgs: None,
        _rebuild_llm_work_from_ui=fail_rebuild,
        _observe_runtime_v2_history=lambda *args, **kwargs: None,
    )

    changed = agent_harness.SessionManager.reconcile_llm_work_to_ui_user_count(
        mgr,
        "s1",
        include_work=False,
    )

    assert changed is False
    assert saved_llm == []


def test_reconcile_trims_only_extra_tail_turn_and_preserves_tools():
    import agent_harness

    ui_events = [
        {"type": "user", "content": "u1"},
        {"type": "final", "content": "a1"},
        {"type": "user", "content": "u2"},
    ]
    llm_history = [
        {"type": "user", "content": "u1"},
        {
            "type": "assistant",
            "content": "",
            "tool_calls": [{"name": "search", "args": {}, "id": "call_1"}],
        },
        {"type": "tool", "content": "tool result", "tool_call_id": "call_1"},
        {"type": "assistant", "content": "a1", "metadata": {"is_final": True}},
        {"type": "user", "content": "u2"},
        {"type": "assistant", "content": "a2", "metadata": {"is_final": True}},
        {"type": "user", "content": "extra"},
        {"type": "system", "content": "New Agent Loop Start"},
    ]
    saved_llm = []
    observed = []

    mgr = _manager_with(
        _runtime_v2_primary=lambda: False,
        _load_ui_events=lambda sid: ui_events,
        _load_llm_history=lambda sid: llm_history,
        _load_work_messages=lambda sid: [],
        _save_llm_history=lambda sid, msgs: saved_llm.append(msgs),
        _save_work_messages=lambda sid, msgs: None,
        _observe_runtime_v2_history=lambda *args, **kwargs: observed.append((args, kwargs)),
    )

    changed = agent_harness.SessionManager.reconcile_llm_work_to_ui_user_count(
        mgr,
        "s1",
        include_work=False,
    )

    assert changed is True
    assert len(saved_llm) == 1
    assert saved_llm[0] == llm_history[:6]
    assert any(m.get("type") == "tool" for m in saved_llm[0])
    assert observed == []


def test_legacy_rebuild_paths_do_not_replace_runtime_v2_model_history():
    source = (ROOT / "app" / "agent_harness.py").read_text(encoding="utf-8")
    forbidden_reasons = [
        "legacy_truncate",
        "legacy_branch",
        "legacy_repair",
        "legacy_reconcile",
        "legacy_tail_restored",
    ]
    for reason in forbidden_reasons:
        assert f'reason="{reason}"' not in source


def test_runtime_v2_active_ui_events_read_projection_without_legacy(monkeypatch, tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeMirror

    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("s1", {"type": "user", "content": "u1"})
    mirror.mirror_ui_event("s1", {"type": "final", "content": "a1"})

    def fail_legacy(_sid):
        raise AssertionError("Runtime V2 active UI history must not read legacy ui_events")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        _runtime_v2_primary=lambda: True,
        _load_ui_events=fail_legacy,
        _resolve_session_path=lambda sid: tmp_path / sid,
    )

    events = agent_harness.SessionManager._load_ui_events_for_active_runtime(mgr, "s1")

    assert [event["content"] for event in events] == ["u1", "a1"]


def test_runtime_v2_active_ui_events_empty_projection_does_not_fallback_legacy(tmp_path):
    import agent_harness

    def fail_legacy(_sid):
        raise AssertionError("Runtime V2 active UI history must not fallback to legacy ui_events")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        _runtime_v2_primary=lambda: True,
        _load_ui_events=fail_legacy,
        _resolve_session_path=lambda sid: tmp_path / sid,
    )

    events = agent_harness.SessionManager._load_ui_events_for_active_runtime(mgr, "s1")

    assert events == []


def test_runtime_v2_truncate_only_changes_visible_range_without_legacy_rebuild():
    import agent_harness

    observed = []

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 truncate must not write or rebuild legacy history")

    mgr = _manager_with(
        _runtime_v2_primary=lambda: True,
        _load_ui_events_for_active_runtime=lambda sid: [
            {"type": "user", "content": "u1"},
            {"type": "final", "content": "a1"},
            {"type": "user", "content": "u2"},
            {"type": "final", "content": "a2"},
        ],
        _backup_session_before_truncate=fail_legacy,
        _save_ui_events=fail_legacy,
        _rebuild_llm_work_from_ui=fail_legacy,
        _save_llm_history=fail_legacy,
        _save_work_messages=fail_legacy,
        _save_dialogue_history=fail_legacy,
        remove_llm_compress_prefix_backup=fail_legacy,
        _observe_runtime_v2_history=lambda *args, **kwargs: observed.append((args, kwargs)),
    )

    changed = agent_harness.SessionManager.truncate_session_at_event_index(
        mgr,
        "s1",
        2,
        create_backup=True,
    )

    assert changed is True
    assert observed == [
        (
            ("truncate_ui_history", "s1"),
            {"before_index": 2, "reason": "runtime_v2_truncate"},
        )
    ]


def test_runtime_v2_branch_creates_v2_branch_without_legacy_rebuild(tmp_path):
    import agent_harness

    source_id = "11111111-1111-4111-8111-111111111111"
    source_dir = tmp_path / source_id
    source_dir.mkdir(parents=True)
    observed = []
    saved_meta = []
    saved_index = []

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 branch must not read/write or rebuild legacy history")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        index=[],
        _runtime_v2_primary=lambda: True,
        _resolve_session_path=lambda sid: tmp_path / sid,
        _load_ui_events_for_active_runtime=lambda sid: [
            {"type": "user", "content": "u1"},
            {"type": "final", "content": "a1"},
        ],
        _load_metadata=lambda sid: {"name": "Source"},
        _save_metadata=lambda sid, meta: saved_meta.append((sid, dict(meta))),
        _save_index=lambda: saved_index.append(True),
        _copy_branch_sidecar_files=lambda source, new: None,
        _observe_runtime_v2_history=lambda *args, **kwargs: observed.append((args, kwargs)),
        _load_llm_history=fail_legacy,
        _load_work_messages=fail_legacy,
        _rebuild_llm_work_from_ui=fail_legacy,
        _save_ui_events=fail_legacy,
        _save_llm_history=fail_legacy,
        _save_work_messages=fail_legacy,
        _save_dialogue_history=fail_legacy,
    )

    result = agent_harness.SessionManager.branch_session_at_event_index(
        mgr,
        source_id,
        2,
    )

    assert result["ok"] is True
    new_id = result["session_id"]
    assert (tmp_path / new_id).is_dir()
    assert saved_meta and saved_meta[0][0] == new_id
    assert saved_meta[0][1]["branched_from"] == source_id
    assert saved_index == [True]
    assert observed == [
        (
            ("create_branch", new_id),
            {"source_session_id": source_id, "branch_from_seq": 2, "name": "(1)Source"},
        )
    ]


def test_runtime_v2_repair_and_reconcile_skip_legacy_rebuilds():
    import agent_harness

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 repair/reconcile must not touch legacy history")

    mgr = _manager_with(
        _runtime_v2_primary=lambda: True,
        _load_ui_events=fail_legacy,
        _load_llm_history=fail_legacy,
        _load_work_messages=fail_legacy,
        _rebuild_llm_work_from_ui=fail_legacy,
        _save_llm_history=fail_legacy,
        _save_work_messages=fail_legacy,
    )

    repaired = agent_harness.SessionManager.repair_compacted_llm_history_from_ui(mgr, "s1")
    reconciled = agent_harness.SessionManager.reconcile_llm_work_to_ui_user_count(mgr, "s1")

    assert repaired is False
    assert reconciled is False


def test_runtime_v2_append_tail_mirrors_events_without_legacy_rebuild():
    import agent_harness

    mirrored = []
    observed = []

    class _Mirror:
        def mirror_ui_event(self, session_id, event):
            mirrored.append((session_id, dict(event)))

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 append tail must not touch legacy history")

    mgr = _manager_with(
        _runtime_v2_primary=lambda: True,
        _runtime_mirror=lambda: _Mirror(),
        _observe_runtime_v2_history=lambda *args, **kwargs: observed.append((args, kwargs)),
        _load_ui_events=fail_legacy,
        _save_ui_events=fail_legacy,
        _rebuild_llm_work_from_ui=fail_legacy,
        _save_llm_history=fail_legacy,
        _save_work_messages=fail_legacy,
        _save_dialogue_history=fail_legacy,
    )

    changed = agent_harness.SessionManager.append_ui_events_tail(
        mgr,
        "s1",
        [
            {"type": "user", "content": "u1"},
            {"type": "final", "content": "a1"},
        ],
    )

    assert changed is True
    assert mirrored == [
        ("s1", {"type": "user", "content": "u1"}),
        ("s1", {"type": "final", "content": "a1"}),
    ]
    assert observed == [
        (
            ("observe_legacy_tail_restored", "s1"),
            {"tail_count": 2, "merged_event_count": 2},
        )
    ]


def test_runtime_v2_subagent_output_does_not_fallback_legacy(tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeSubagentStore

    store = RuntimeSubagentStore(tmp_path)
    store.upsert_task("parent", "agent1", {"status": "completed"})

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 subagent output must not read legacy subagent files")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        _runtime_v2_primary=lambda: True,
        _runtime_subagent_store=lambda: store,
        list_subagent_tasks=fail_legacy,
        validate_subagent_resume=fail_legacy,
        _get_session_path=fail_legacy,
    )

    result = agent_harness.SessionManager.read_subagent_task_output(mgr, "parent", "agent1")

    assert result == {"ok": False, "error": "output not found"}


def test_runtime_v2_subagent_output_reads_v2_store(tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeSubagentStore

    store = RuntimeSubagentStore(tmp_path)
    store.write_task_output("parent", "agent1", "final text")

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 subagent output must not read legacy subagent files")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        _runtime_v2_primary=lambda: True,
        _runtime_subagent_store=lambda: store,
        list_subagent_tasks=fail_legacy,
        validate_subagent_resume=fail_legacy,
        _get_session_path=fail_legacy,
    )

    result = agent_harness.SessionManager.read_subagent_task_output(mgr, "parent", "agent1")

    assert result["ok"] is True
    assert result["content"] == "final text"


def test_runtime_v2_pending_subagent_results_do_not_fallback_legacy(tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeSubagentStore

    store = RuntimeSubagentStore(tmp_path)

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 pending subagent path must not read legacy pending files")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        _runtime_v2_primary=lambda: True,
        _runtime_subagent_store=lambda: store,
        _load_metadata=lambda sid: {},
        _get_pending_subagent_results_path=fail_legacy,
    )
    mgr.repository.load_json_list = fail_legacy

    assert agent_harness.SessionManager._load_pending_subagent_results(mgr, "parent") == []


def test_runtime_v2_pending_subagent_continue_uses_v2_ui_projection(tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeMirror, RuntimeSubagentStore

    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("parent", {"type": "user", "content": "u"})
    mirror.mirror_ui_event("parent", {"type": "final", "content": "a"})
    store = RuntimeSubagentStore(tmp_path)
    store.append_pending_result("parent", {
        "agent_id": "agent1",
        "description": "worker",
        "status": "completed",
        "result": "done",
        "after_final_index": 1,
    })

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 pending continue must not read legacy ui/pending files")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        _runtime_v2_primary=lambda: True,
        _runtime_subagent_store=lambda: store,
        _resolve_session_path=lambda sid: tmp_path / sid,
        _load_metadata=lambda sid: {},
        _load_ui_events=fail_legacy,
        _get_pending_subagent_results_path=fail_legacy,
        _save_pending_subagent_results=lambda sid, rows: store.save_pending_results(sid, rows),
    )
    mgr.repository.load_json_list = fail_legacy

    assert agent_harness.SessionManager.can_continue_after_subagents(mgr, "parent") is True
    lines = agent_harness.SessionManager.consume_pending_subagent_notifications(mgr, "parent")

    assert len(lines) == 1
    assert "Subagent agent1" in lines[0]
    assert store.list_pending_results("parent") == []


def test_runtime_v2_append_pending_subagent_result_writes_only_v2_store(tmp_path):
    import agent_harness
    from runtime_v2 import RuntimeMirror, RuntimeSubagentStore

    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event("parent", {"type": "user", "content": "u"})
    mirror.mirror_ui_event("parent", {"type": "final", "content": "a"})
    store = RuntimeSubagentStore(tmp_path)

    def fail_legacy(*args, **kwargs):
        raise AssertionError("Runtime V2 append pending subagent result must not touch legacy files")

    mgr = _manager_with(
        repository=_Repository(tmp_path),
        _runtime_v2_primary=lambda: True,
        _runtime_subagent_store=lambda: store,
        _resolve_session_path=lambda sid: tmp_path / sid,
        _load_ui_events=fail_legacy,
        _get_pending_subagent_results_path=fail_legacy,
    )
    mgr.repository.load_json_list = fail_legacy
    mgr.repository.save_json_list = fail_legacy

    agent_harness.SessionManager.append_pending_subagent_result(mgr, "parent", {
        "agent_id": "agent1",
        "status": "completed",
        "result": "done",
    })

    rows = store.list_pending_results("parent")
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "agent1"
    assert rows[0]["after_final_index"] == 1
