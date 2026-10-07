from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_store():
    name = "test_change_review_store"
    if name in sys.modules:
        return sys.modules[name]
    path = ROOT / "plugins" / "change-review" / "store.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_plugin_module(filename, name):
    path = ROOT / "plugins" / "change-review" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def review(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "app"))
    import agent_tools

    monkeypatch.setattr(agent_tools, "WORK_DIR", tmp_path / "workspace")
    agent_tools.WORK_DIR.mkdir()
    store = _load_store().FileChangeReviewStore(tmp_path / "session")
    with agent_tools.tool_work_dir_override(agent_tools.WORK_DIR):
        yield store, agent_tools.WORK_DIR


def capture(store, workspace, tool, args, mutate, run="run-1", call="call-1"):
    started = store.begin_capture(
        tool, args, run_id=run, tool_call_id=call, work_root=workspace
    )
    mutate()
    return store.finish_capture(started)


def init_git_workspace(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "review@test.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Review Test"], check=True)


def test_create_modify_delete_and_undo(review):
    store, workspace = review
    path = workspace / "hello.txt"
    changes = capture(
        store,
        workspace,
        "write_file",
        {"path": "hello.txt", "contents": "one\ntwo\n"},
        lambda: path.write_text("one\ntwo\n", encoding="utf-8"),
    )
    assert len(changes) == 1
    assert changes[0]["operation"] == "create"
    assert (changes[0]["added"], changes[0]["removed"]) == (2, 0)
    assert changes[0]["diff"].startswith("--- a/hello.txt")

    result = store.undo([changes[0]["snapshot_id"]], "undo-create")
    assert result["ok"] is True
    assert not path.exists()
    store.commit_undo("undo-create")
    assert store.undo([changes[0]["snapshot_id"]], "undo-create")["idempotent_replay"] is True


def test_runtime_callback_captures_real_write_file_invocation(tmp_path):
    sys.path.insert(0, str(ROOT / "app"))
    import agent_tools

    workspace = tmp_path / "workspace"; workspace.mkdir()
    session_dir = tmp_path / "session"

    class Manager:
        def _get_session_path(self, _session_id):
            return session_dir

    runtime = _load_plugin_module("runtime.py", "test_change_review_runtime")
    callbacks = runtime.initialize(SimpleNamespace(session_manager=Manager()))
    state = {"session_id": "write-session", "_runtime_v2_run_id": "write-run"}
    with agent_tools.tool_work_dir_override(workspace):
        capture_state = callbacks["before_native_file_tool"](
            state,
            "write_file",
            {"path": "created.txt", "contents": "hello\n"},
            "write-call",
            "",
        )
        result = agent_tools.write_file(path="created.txt", contents="hello\n")
        changes = callbacks["after_native_file_tool"](state, capture_state, result.startswith("Successfully"))
    assert result.startswith("Successfully wrote file")
    assert len(changes) == 1
    assert changes[0]["path"] == "created.txt"


def test_runtime_callback_can_observe_an_unknown_external_tool(tmp_path):
    sys.path.insert(0, str(ROOT / "app"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    init_git_workspace(workspace)
    session_dir = tmp_path / "session"

    class Manager:
        def _get_session_path(self, _session_id):
            return session_dir

    runtime = _load_plugin_module("runtime.py", "test_change_review_external_runtime")
    callbacks = runtime.initialize(SimpleNamespace(session_manager=Manager()))
    state = {"session_id": "external-session", "_runtime_v2_run_id": "external-run"}
    capture_state = callbacks["before_native_file_tool"](
        state, "third_party_writer", {}, "external-call", str(workspace), True
    )
    (workspace / "external.txt").write_text("created externally\n", encoding="utf-8")
    changes = callbacks["after_native_file_tool"](state, capture_state, True)

    assert len(changes) == 1
    assert changes[0]["path"] == "external.txt"
    assert changes[0]["operation"] == "create"
    callbacks["after_run"](state)
    continuation_state = {
        "session_id": "external-session",
        "_runtime_v2_run_id": "continuation-process",
        "_change_review_turn_id": "external-run",
    }
    continued_capture = callbacks["before_native_file_tool"](
        continuation_state, "third_party_writer", {}, "continuation-call", str(workspace), True
    )
    (workspace / "external.txt").write_text(
        "created externally\ncontinued in same turn\n", encoding="utf-8"
    )
    continued = callbacks["after_native_file_tool"](
        continuation_state, continued_capture, True
    )
    assert continued[0]["snapshot_id"] == changes[0]["snapshot_id"]
    assert continued[0]["turn_id"] == "external-run"
    assert continued[0]["added"] == 2
    callbacks["after_run"](continuation_state)
    stored = json.loads((session_dir / "change_reviews/index.json").read_text(encoding="utf-8"))
    # A process ending is not a user-turn boundary: keep its workspace baseline
    # for an automatic continuation in the same turn.
    assert stored["baselines"]
    next_state = {
        "session_id": "external-session",
        "_runtime_v2_run_id": "next-process",
        "_change_review_turn_id": "next-user-turn",
    }
    pending = callbacks["before_native_file_tool"](
        next_state, "third_party_writer", {}, "next-call", str(workspace), True
    )
    callbacks["after_native_file_tool"](next_state, pending, True)
    stored = json.loads((session_dir / "change_reviews/index.json").read_text(encoding="utf-8"))
    assert {row["run_id"] for row in stored["baselines"].values()} == {"next-user-turn"}
    store = _load_store().FileChangeReviewStore(session_dir)
    store.finish_run("next-user-turn")
    assert not list((session_dir / "change_reviews/baselines").glob("*.zip"))
    store.undo([changes[0]["snapshot_id"]], "undo-after-baseline-cleanup")
    assert not (workspace / "external.txt").exists()


@pytest.mark.parametrize("large_payload", [False, True])
def test_long_goal_continuations_keep_patch_stats_in_the_official_turn(tmp_path, monkeypatch, large_payload):
    sys.path.insert(0, str(ROOT / "app"))
    import agent_loop
    import agent_tools
    from runtime_v2.history_ops import RuntimeHistoryOps

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session_dir = tmp_path / "sessions" / "goal-session"
    ops = RuntimeHistoryOps(tmp_path / "sessions")
    monkeypatch.setattr(agent_loop, "_runtime_v2_is_primary", lambda: True)
    monkeypatch.setattr(agent_loop, "_runtime_v2_react_history_ops", lambda: ops)
    ops.event_log.append("goal-session", "user_turn_committed", {
        "content": "Finish the goal", "turn_id": "official-turn",
    }, run_id="origin-run")
    runtime = _load_plugin_module("runtime.py", "test_long_goal_change_review_runtime")
    callbacks = runtime.initialize(SimpleNamespace(session_manager=SimpleNamespace(
        _get_session_path=lambda _sid: session_dir,
    )))
    target = workspace / "goal.txt"
    target.write_text("original\n", encoding="utf-8")
    first_snapshot = None
    with agent_tools.tool_work_dir_override(workspace):
        for index in range(3):
            if index:
                # Either the byte window or event-count window excludes the
                # original user message. Steers do not start a new turn.
                rows = [{"type": "model_assistant", "run_id": f"run-{index}",
                         "payload": {"content": "x" * (2 * 1024 * 1024 + 100)}}] if large_payload else [
                    {"type": "model_assistant", "run_id": f"run-{index}",
                     "payload": {"content": "progress"}} for _ in range(4010)
                ]
                rows.append({"type": "user_turn_committed", "run_id": f"run-{index}",
                             "payload": {"ui_type": "user_steer", "content": "Keep going"}})
                ops.event_log.append_batch("goal-session", rows)
            state = {
                "session_id": "goal-session", "_runtime_v2_run_id": f"run-{index}",
                "_change_review_turn_id": agent_loop._latest_official_user_turn_id("goal-session") or f"run-{index}",
            }
            before = "original" if index == 0 else f"change-{index - 1}"
            patch = "\n".join([
                "*** Begin Patch", "*** Update File: goal.txt", "@@",
                f"-{before}", f"+change-{index}", "+added", "*** End Patch",
            ])
            capture_state = callbacks["before_native_file_tool"](
                state, "apply_patch", {"patch": patch}, f"patch-{index}", "",
            )
            result = agent_tools.apply_patch(patch=patch)
            changes = callbacks["after_native_file_tool"](state, capture_state, True)
            assert len(changes) == 1, result
            row = changes[0]
            if first_snapshot is None:
                first_snapshot = row["snapshot_id"]
            assert row["turn_id"] == "official-turn"
            assert row["snapshot_id"] == first_snapshot
            assert (row["added"], row["removed"]) == (index + 2, 1)
            assert "-original" in row["diff"]
            callbacks["after_run"](state)

    # A new ordinary user turn must still start a new review baseline.
    ops.event_log.append("goal-session", "user_turn_committed", {
        "content": "Next task", "turn_id": "next-turn",
    }, run_id="next-run")
    assert agent_loop._latest_official_user_turn_id("goal-session") == "next-turn"


def test_real_apply_patch_keeps_line_endings_and_reports_hunk_diff(review):
    store, workspace = review
    import agent_tools

    path = workspace / "patched.py"
    path.write_bytes(b"alpha\nbeta\ngamma\n")
    patch = "\n".join([
        "*** Begin Patch",
        "*** Update File: patched.py",
        "@@",
        " alpha",
        "-beta",
        "+delta",
        " gamma",
        "*** End Patch",
    ])

    with agent_tools.tool_work_dir_override(workspace):
        started = store.begin_capture(
            "apply_patch", {"patch": patch}, run_id="patch-run",
            tool_call_id="patch-call", work_root=workspace,
        )
        result = agent_tools.apply_patch(patch)
        changes = store.finish_capture(started, successful=result.startswith("Done!"))

    assert result.startswith("Done!")
    assert path.read_bytes() == b"alpha\ndelta\ngamma\n"
    assert len(changes) == 1
    assert (changes[0]["added"], changes[0]["removed"]) == (1, 1)
    assert changes[0]["diff"].count("+delta") == 1
    assert "-alpha" not in changes[0]["diff"]


def test_real_apply_patch_does_not_turn_large_lf_file_into_full_file_diff(review):
    store, workspace = review
    import agent_tools

    path = workspace / "large_patch.py"
    original_lines = [f"value_{index} = {index}" for index in range(1, 1801)]
    path.write_bytes(("\n".join(original_lines) + "\n").encode("utf-8"))
    patch = "\n".join([
        "*** Begin Patch",
        "*** Update File: large_patch.py",
        "@@",
        " value_899 = 899",
        "-value_900 = 900",
        "-value_901 = 901",
        "+value_900 = 'changed'",
        "+value_901 = 'changed'",
        "+value_901_5 = 'inserted'",
        " value_902 = 902",
        "*** End Patch",
    ])

    with agent_tools.tool_work_dir_override(workspace):
        started = store.begin_capture(
            "apply_patch", {"patch": patch}, run_id="large-patch-run",
            tool_call_id="large-patch-call", work_root=workspace,
        )
        result = agent_tools.apply_patch(patch)
        changes = store.finish_capture(started, successful=result.startswith("Done!"))

    assert result.startswith("Done!")
    assert b"\r\n" not in path.read_bytes()
    assert len(changes) == 1
    assert (changes[0]["added"], changes[0]["removed"]) == (3, 2)
    assert changes[0]["diff"].count("+value_901_5 = 'inserted'") == 1
    assert "-value_1 = 1" not in changes[0]["diff"]


def test_same_round_same_file_is_cumulative(review):
    store, workspace = review
    path = workspace / "same.txt"
    path.write_text("a\nb\n", encoding="utf-8")
    first = capture(
        store, workspace, "edit_file", {"path": "same.txt"},
        lambda: path.write_text("a\nc\n", encoding="utf-8"), call="call-1",
    )[0]
    second = capture(
        store, workspace, "edit_file", {"path": "same.txt"},
        lambda: path.write_text("a\nc\nd\n", encoding="utf-8"), call="call-2",
    )[0]
    assert second["snapshot_id"] == first["snapshot_id"]
    assert second["turn_id"] == "run-1"
    assert second["revision"] == 2
    assert (second["added"], second["removed"]) == (2, 1)
    store.undo([second["snapshot_id"]], "undo-cumulative")
    assert path.read_text(encoding="utf-8") == "a\nb\n"


def test_noop_has_no_change_but_failed_tool_reports_actual_partial_write(review):
    store, workspace = review
    path = workspace / "unchanged.txt"
    path.write_text("same", encoding="utf-8")
    assert capture(store, workspace, "edit_file", {"path": "unchanged.txt"}, lambda: None) == []
    assert capture(store, workspace, "apply_patch", {"patch": "invalid"}, lambda: None) == []

    started = store.begin_capture(
        "write_file", {"path": "unchanged.txt"}, run_id="failed-run",
        tool_call_id="failed-call", work_root=workspace,
    )
    path.write_text("partially-written", encoding="utf-8")
    partial = store.finish_capture(started, successful=False)
    assert len(partial) == 1
    assert partial[0]["operation"] == "modify"
    assert (partial[0]["added"], partial[0]["removed"]) == (1, 1)


def test_same_round_return_to_baseline_is_not_undoable(review):
    module = _load_store()
    store, workspace = review
    path = workspace / "baseline.txt"
    path.write_text("before\n", encoding="utf-8")
    first = capture(
        store, workspace, "edit_file", {"path": "baseline.txt"},
        lambda: path.write_text("after\n", encoding="utf-8"),
    )[0]
    second = capture(
        store, workspace, "edit_file", {"path": "baseline.txt"},
        lambda: path.write_text("before\n", encoding="utf-8"), call="call-2",
    )[0]
    assert second["effective"] is False
    with pytest.raises(module.SnapshotGoneError):
        store.undo([first["snapshot_id"]], "undo-neutralized")


def test_git_process_baseline_tracks_non_native_changes_and_net_zero_cleanup(tmp_path):
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    tracked = workspace / "tracked.txt"
    tracked.write_text("one\ntwo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "tracked.txt"], check=True)
    store = module.FileChangeReviewStore(tmp_path / "session")

    scratch = workspace / ".playwright-mcp" / "page.yml"
    first = capture(
        store,
        workspace,
        "mcp_browser_snapshot",
        {},
        lambda: (scratch.parent.mkdir(), scratch.write_text("temporary\n", encoding="utf-8")),
        run="process-1",
        call="mcp-1",
    )
    assert len(first) == 1
    assert first[0]["path"] == ".playwright-mcp/page.yml"
    assert first[0]["operation"] == "create"
    assert (first[0]["added"], first[0]["removed"]) == (1, 0)

    cleaned = capture(
        store,
        workspace,
        "delete_file",
        {"path": str(scratch.parent)},
        lambda: shutil.rmtree(scratch.parent),
        run="process-1",
        call="native-delete",
    )
    row = next(item for item in cleaned if item["snapshot_id"] == first[0]["snapshot_id"])
    assert row["effective"] is False
    with pytest.raises(module.SnapshotGoneError):
        store.undo([first[0]["snapshot_id"]], "undo-net-zero")


def test_git_process_baseline_reports_true_insertions_and_deletions(tmp_path):
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    path = workspace / "tracked.txt"
    path.write_text("one\ntwo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "tracked.txt"], check=True)
    store = module.FileChangeReviewStore(tmp_path / "session")

    inserted = capture(
        store,
        workspace,
        "run_shell",
        {"command": "append"},
        lambda: path.write_text("one\ntwo\nthree\n", encoding="utf-8"),
        run="insert-run",
    )
    assert len(inserted) == 1
    assert (inserted[0]["added"], inserted[0]["removed"]) == (1, 0)
    store.undo([inserted[0]["snapshot_id"]], "undo-insert")
    store.commit_undo("undo-insert")

    deleted = capture(
        store,
        workspace,
        "mcp_delete",
        {},
        path.unlink,
        run="delete-run",
    )
    assert len(deleted) == 1
    assert deleted[0]["operation"] == "delete"
    assert (deleted[0]["added"], deleted[0]["removed"]) == (0, 2)
    store.undo([deleted[0]["snapshot_id"]], "undo-delete")
    assert path.read_text(encoding="utf-8") == "one\ntwo\n"


def test_gitignore_change_does_not_turn_an_existing_file_into_a_fake_delete(tmp_path):
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    visible = workspace / "visible.txt"
    visible.write_text("still here\n", encoding="utf-8")
    store = module.FileChangeReviewStore(tmp_path / "session")

    changes = capture(
        store,
        workspace,
        "run_shell",
        {},
        lambda: (workspace / ".gitignore").write_text("visible.txt\n", encoding="utf-8"),
        run="ignore-run",
    )

    assert [row["path"] for row in changes] == [".gitignore"]
    assert visible.read_text(encoding="utf-8") == "still here\n"


def test_workspace_cache_reuses_unchanged_bytes_across_store_instances(tmp_path, monkeypatch):
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    for index in range(12):
        (workspace / f"{index}.txt").write_text("before\n", encoding="utf-8")
    store = module.FileChangeReviewStore(tmp_path / "session")
    capture(store, workspace, "run_shell", {}, lambda: None)
    original = module._read_regular_file
    reads = []

    def read(path):
        reads.append(path)
        return original(path)

    monkeypatch.setattr(module, "_read_regular_file", read)
    # The plugin constructs a new store for each before/after callback.
    fresh = module.FileChangeReviewStore(tmp_path / "session")
    assert capture(fresh, workspace, "run_shell", {}, lambda: None) == []
    assert reads == []
    changes = capture(fresh, workspace, "run_shell", {}, lambda: (workspace / "5.txt").write_text("after\n"))
    assert [row["path"] for row in changes] == ["5.txt"]
    assert set(reads) == {workspace / "5.txt"}
    fresh.undo([changes[0]["snapshot_id"]], "undo-cached")
    assert (workspace / "5.txt").read_text() == "before\n"


def test_workspace_cache_detects_same_size_write_with_restored_mtime(tmp_path):
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    path = workspace / "same.txt"
    path.write_bytes(b"before\n")
    store = module.FileChangeReviewStore(tmp_path / "session")
    capture(store, workspace, "run_shell", {}, lambda: None)
    before = path.stat()

    def mutate():
        path.write_bytes(b"after!\n")
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

    rows = capture(store, workspace, "run_shell", {}, mutate)
    assert len(rows) == 1
    store.undo([rows[0]["snapshot_id"]], "undo-restored-mtime")
    assert path.read_bytes() == b"before\n"


def test_declared_batch_sweeps_once_and_preserves_external_undo(tmp_path, monkeypatch):
    module = _load_store()
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    init_git_workspace(workspace)
    external = workspace / 'external.txt'
    external.write_text('original\n')
    store = module.FileChangeReviewStore(tmp_path / 'session')
    inventories = []
    original = store._git_inventory
    monkeypatch.setattr(store, '_git_inventory', lambda root: (inventories.append(root), original(root))[1])
    sys.path.insert(0, str(ROOT / 'app'))
    import agent_tools
    declared = []
    with agent_tools.tool_work_dir_override(workspace):
        for index in range(5):
            name = f'file-{index}.txt'
            pending = store.begin_capture('write_file', {'path': name}, run_id='turn',
                                         tool_call_id=f'call-{index}', work_root=workspace,
                                         execution_scope={'run_id': 'execution', 'react_iter': 3, 'stream_seq': 7})
            (workspace / name).write_text('created\n')
            if index == 2:
                external.write_text('external modification\n')
            rows = store.finish_capture(pending, defer_workspace_sweep=True)
            assert [row['path'] for row in rows] == [name]
            declared.extend(rows)
    assert len(inventories) == 1  # first baseline only
    events = store.flush_deferred_sweeps()
    assert len(inventories) == 2
    assert len(events) == 1
    event = events[0]
    assert event['type'] == 'file_changes_updated'
    assert event['run_id'] == 'execution' and event['react_iter'] == 3
    assert event['tool_call_id'] == 'call-4'
    assert [row['path'] for row in event['changes']] == ['external.txt']
    all_rows = declared + event['changes']
    store.undo([row['snapshot_id'] for row in all_rows], 'undo-batch')
    store.commit_undo('undo-batch')
    assert external.read_text() == 'original\n'
    assert not list(workspace.glob('file-*.txt'))
    store.restore([row['snapshot_id'] for row in all_rows], 'restore-batch')
    store.commit_restore('restore-batch')
    assert len(list(workspace.glob('file-*.txt'))) == 5
    assert external.read_text() == 'external modification\n'


def test_deferred_sweep_recovers_and_outbox_retries_until_ack(tmp_path, monkeypatch):
    module = _load_store()
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    init_git_workspace(workspace)
    store = module.FileChangeReviewStore(tmp_path / 'session')
    pending = store.begin_capture('run_shell', {}, run_id='turn', tool_call_id='last-call', work_root=workspace)
    (workspace / 'external.txt').write_text('new\n')
    store.finish_capture(pending, defer_workspace_sweep=True)
    # A new process has no in-memory signature cache; recovery must use only
    # the persisted baseline, obligation and content blobs.
    monkeypatch.setattr(module, '_workspace_scans', {})
    fresh = module.FileChangeReviewStore(tmp_path / 'session')
    events = fresh.flush_deferred_sweeps()
    assert len(events) == 1
    assert fresh.flush_deferred_sweeps() == events
    fresh.acknowledge_review_event(events[0]['operation_id'])
    assert fresh.flush_deferred_sweeps() == []
    assert not fresh._load()['deferred_sweeps']


def test_runtime_external_tool_is_batch_boundary_and_logs_breakdown(tmp_path, caplog):
    import agent_tools
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    init_git_workspace(workspace)
    session_dir = tmp_path / 'session'
    durable = []
    manager = SimpleNamespace(_get_session_path=lambda _sid: session_dir,
                              append_ui_event=lambda sid, event, **kwargs: durable.append(dict(event)))
    runtime = _load_plugin_module('runtime.py', 'test_review_batch_runtime')
    callbacks = runtime.initialize(SimpleNamespace(session_manager=manager))
    state = {'session_id': 'session', '_runtime_v2_run_id': 'run', '_change_review_batch_active': True,
             '_current_react_iter': 2, '_active_stream_seq': 4}
    caplog.set_level('INFO', logger='agent_harness')
    with agent_tools.tool_work_dir_override(workspace):
        pending = callbacks['before_native_file_tool'](state, 'write_file', {'path': 'native.txt'}, 'native')
        (workspace / 'native.txt').write_text('native\n')
        (workspace / 'outside.txt').write_text('before external tool\n')
        native = callbacks['after_native_file_tool'](state, pending)
        assert [row['path'] for row in native] == ['native.txt']
        external = callbacks['before_native_file_tool'](state, 'mcp_writer', {}, 'external', str(workspace), True)
        assert [row['path'] for row in durable[0]['changes']] == ['outside.txt']
        (workspace / 'outside.txt').write_text('after external tool\n')
        after = callbacks['after_native_file_tool'](state, external)
        assert [row['path'] for row in after] == ['outside.txt']
    updates = callbacks['flush_file_tool_reviews'](state)
    assert updates[0]['_runtime_v2_committed'] is True
    assert len(durable) == 1
    assert callbacks['flush_file_tool_reviews'](state) == []
    assert 'inventory_ms=' in caplog.text and 'signature_ms=' in caplog.text


def test_workspace_limit_skips_first_baseline_but_keeps_declared_review(tmp_path, monkeypatch):
    import agent_tools
    module = _load_store()
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    init_git_workspace(workspace)
    for index in range(3):
        (workspace / f'{index}.txt').write_text('original\n')
    monkeypatch.setenv('MYAGENT_CHANGE_REVIEW_MAX_WORKSPACE_FILES', '2')
    store = module.FileChangeReviewStore(tmp_path / 'session')
    with agent_tools.tool_work_dir_override(workspace):
        pending = store.begin_capture('write_file', {'path': '0.txt'}, run_id='turn', tool_call_id='call', work_root=workspace)
        assert store.timings['coverage'] == 'declared_paths'
        assert store.timings['files'] == 3
        assert not list((store.root / 'baselines').glob('*.zip'))
        (workspace / '0.txt').write_text('changed\n')
        rows = store.finish_capture(pending)
    assert [row['path'] for row in rows] == ['0.txt']
    store.undo([rows[0]['snapshot_id']], 'undo-limited')
    assert (workspace / '0.txt').read_text() == 'original\n'
    assert store.begin_capture('run_shell', {}, run_id='turn', tool_call_id='external', work_root=workspace) is None


def test_parallel_signatures_keep_cache_and_detect_restored_mtime(tmp_path, monkeypatch):
    module = _load_store()
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    init_git_workspace(workspace)
    for index in range(260):
        (workspace / f'{index}.txt').write_bytes(b'before\n')
    store = module.FileChangeReviewStore(tmp_path / 'session')
    capture(store, workspace, 'run_shell', {}, lambda: None)
    monkeypatch.setenv('MYAGENT_CHANGE_REVIEW_SIGNATURE_WORKERS', '8')
    monkeypatch.setenv('MYAGENT_CHANGE_REVIEW_SIGNATURE_PARALLEL_MIN_FILES', '0')
    path = workspace / '129.txt'
    before = path.stat()
    def mutate():
        path.write_bytes(b'after!\n')
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    rows = capture(store, workspace, 'run_shell', {}, mutate)
    assert store.timings['scan_workers'] == 8
    assert store.timings['cache_hits'] == 259
    assert store.timings['changed_count'] == 1
    assert [row['path'] for row in rows] == ['129.txt']
    store.undo([rows[0]['snapshot_id']], 'undo-parallel')
    assert path.read_bytes() == b'before\n'


def test_workspace_update_replays_without_entering_model_history(tmp_path):
    from runtime_v2.mirror import RuntimeMirror
    from runtime_v2.ui_projection import RuntimeUiProjection
    from runtime_v2.model_projection import RuntimeModelProjection
    event = {'type': 'file_changes_updated', 'run_id': 'run', 'react_iter': 2, 'stream_seq': 4,
             'tool_call_id': 'tool', 'changes': [{'path': 'external.txt', 'snapshot_id': 'snapshot', 'revision': 1}]}
    RuntimeMirror(tmp_path).mirror_ui_event('session', event)
    events = RuntimeUiProjection(tmp_path).read_ui_events('session')
    assert events[0]['type'] == 'file_changes_updated'
    assert events[0]['run_id'] == 'run' and events[0]['changes'] == event['changes']
    assert RuntimeModelProjection(tmp_path).read_message_dicts('session') == []


def test_deferred_declared_row_already_uses_turn_origin(review):
    store, workspace = review
    init_git_workspace(workspace)
    target = workspace / 'origin.txt'
    target.write_text('turn origin\n')
    capture(store, workspace, 'run_shell', {}, lambda: None)
    target.write_text('external before declaration\n')
    pending = store.begin_capture('write_file', {'path': 'origin.txt'}, run_id='run-1',
                                 tool_call_id='declared', work_root=workspace)
    target.write_text('declared final\n')
    rows = store.finish_capture(pending, defer_workspace_sweep=True)
    assert '-turn origin' in rows[0]['diff']
    assert 'external before declaration' not in rows[0]['diff']
    assert store.flush_deferred_sweeps() == []
    store.undo([rows[0]['snapshot_id']], 'undo-immediate-origin')
    assert target.read_text() == 'turn origin\n'


def test_pending_sweep_and_delivery_survive_baseline_cleanup_and_prune(tmp_path):
    module = _load_store()
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    init_git_workspace(workspace)
    path = workspace / 'external.txt'
    path.write_text('before\n')
    store = module.FileChangeReviewStore(tmp_path / 'session')
    pending = store.begin_capture('run_shell', {}, run_id='old', tool_call_id='tool', work_root=workspace)
    path.write_text('after\n')
    store.finish_capture(pending, defer_workspace_sweep=True)
    store.finish_run('old')
    store.finish_other_runs('new')
    assert store._load()['baselines']
    events = store.flush_deferred_sweeps()
    snapshot = events[0]['changes'][0]['snapshot_id']
    store.prune_unreferenced([])
    assert not store._load()['records'][snapshot].get('dropped')
    store.finish_other_runs('new')
    assert not store._load()['baselines']
    store.undo([snapshot], 'undo-unacked')
    assert path.read_text() == 'before\n'


def test_runtime_delivery_failure_keeps_retryable_outbox(tmp_path):
    import agent_tools
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    init_git_workspace(workspace)
    runtime = _load_plugin_module('runtime.py', 'test_review_delivery_runtime')
    durable = []

    def append(_sid, event, **kwargs):
        assert kwargs['require_commit']
        if not durable:
            durable.append('failed')
            raise OSError('injected durable UI failure')
        durable.append(dict(event))

    callbacks = runtime.initialize(SimpleNamespace(session_manager=SimpleNamespace(
        _get_session_path=lambda sid: tmp_path / 'session', append_ui_event=append)))
    state = {'session_id': 'session', '_runtime_v2_run_id': 'run', '_change_review_batch_active': True}
    with agent_tools.tool_work_dir_override(workspace):
        pending = callbacks['before_native_file_tool'](state, 'write_file', {'path': 'native.txt'}, 'native')
        (workspace / 'native.txt').write_text('native\n')
        (workspace / 'external.txt').write_text('external\n')
        callbacks['after_native_file_tool'](state, pending)
    with pytest.raises(OSError, match='injected'):
        callbacks['flush_file_tool_reviews'](state)
    assert state['_change_review_dirty']
    updates = callbacks['flush_file_tool_reviews'](state)
    assert [row['path'] for row in updates[0]['changes']] == ['external.txt']
    assert updates[0]['_runtime_v2_committed']
    assert callbacks['flush_file_tool_reviews'](state) == []


def test_git_inventory_stays_within_subdirectory(tmp_path):
    module = _load_store()
    init_git_workspace(tmp_path)
    (tmp_path / "outside.txt").write_text("outside")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inside.txt").write_text("inside")
    assert module.FileChangeReviewStore._git_inventory(nested) == [nested / "inside.txt"]


def test_has_git_repository_finds_enclosing_repository(tmp_path):
    module = _load_store()
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert module._has_git_repository(nested) is True


def test_git_inventory_skips_spawn_outside_a_repository(tmp_path, monkeypatch):
    """非 git 工作区不该再白跑一次 git（旧行为：每次捕获都 spawn 一次并返回 128）。"""

    module = _load_store()
    monkeypatch.setattr(module, "_has_git_repository", lambda _root: False)

    def _fail(*_args, **_kwargs):
        raise AssertionError("non-git workspace must not spawn git")

    monkeypatch.setattr(module.subprocess, "run", _fail)
    assert module.FileChangeReviewStore._git_inventory(tmp_path) is None


def test_repeated_lines_diff_is_small_and_has_original_line_numbers(tmp_path):
    store = _load_store().FileChangeReviewStore(tmp_path / "session")
    lines = ["same\n"] * 19000
    changed = list(lines)
    changed[9000] = "changed\n"
    diff = store._diff("repeated.txt", "".join(lines).encode(), "".join(changed).encode())
    assert (diff["added"], diff["removed"]) == (1, 1)
    assert "@@ -8998,7 +8998,7 @@" in diff["diff"]
    assert len(diff["diff"].splitlines()) == 11


def test_separated_edits_in_repeated_lines_keep_exact_small_hunks(tmp_path):
    store = _load_store().FileChangeReviewStore(tmp_path / "session")
    lines = ["same\n"] * 19000
    changed = list(lines)
    changed[100] = "first\n"
    changed[18000] = "second\n"
    result = store._diff("repeated.txt", "".join(lines).encode(), "".join(changed).encode())
    assert (result["added"], result["removed"]) == (2, 2)
    assert result["diff"].count("@@ -") == 2
    assert len(result["diff"].splitlines()) < 25


def test_bounded_matcher_reconstructs_repeated_insert_delete_replace():
    import random

    module = _load_store()
    rng = random.Random(73)
    for _ in range(10):
        before = [rng.choice(["a\n", "b\n"]) for _ in range(1100)]
        after = list(before)
        after[200:202] = ["replacement\n"]
        after[800:800] = ["inserted\n"]
        del after[400]
        matcher = module._bounded_line_matcher(before, after)
        assert matcher is not None
        rebuilt = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                assert before[i1:i2] == after[j1:j2]
                rebuilt.extend(before[i1:i2])
            elif tag in {"replace", "insert"}:
                rebuilt.extend(after[j1:j2])
        assert rebuilt == after


def test_binary_and_large_file_omit_line_diff(review):
    store, workspace = review
    binary = workspace / "binary.dat"
    binary.write_bytes(b"before\x00bytes")
    binary_change = capture(
        store, workspace, "write_file", {"path": "binary.dat"},
        lambda: binary.write_bytes(b"after\x00bytes"),
    )[0]
    assert binary_change["diff"] is None
    assert binary_change["diff_omitted_reason"] == "binary"
    assert binary_change["added"] is None

    large = workspace / "large.txt"
    large.write_bytes(b"a" * (1024 * 1024 + 1))
    large_change = capture(
        store, workspace, "write_file", {"path": "large.txt"},
        lambda: large.write_bytes(b"b" * (1024 * 1024 + 1)), run="run-2",
    )[0]
    assert large_change["diff_omitted_reason"] == "too_large_bytes"


def test_text_diff_normalizes_line_endings_instead_of_reporting_whole_file(review):
    store, workspace = review
    path = workspace / "crlf.py"
    path.write_bytes(b"line one\r\nline two\r\n")
    change = capture(
        store,
        workspace,
        "write_file",
        {"path": "crlf.py", "contents": "line one\nline two\n# comment\n"},
        lambda: path.write_bytes(b"line one\nline two\n# comment\n"),
    )[0]
    assert (change["added"], change["removed"]) == (1, 0)
    assert "-line one" not in change["diff"]
    assert "+# comment" in change["diff"]


def test_same_round_text_return_to_baseline_ignores_newline_only_rewrite(review):
    store, workspace = review
    path = workspace / "roundtrip.py"
    path.write_bytes(b"before\r\n")
    first = capture(
        store,
        workspace,
        "write_file",
        {"path": "roundtrip.py", "contents": "before\n# marker\n"},
        lambda: path.write_bytes(b"before\n# marker\n"),
        run="newline-roundtrip",
    )[0]
    second = capture(
        store,
        workspace,
        "edit_file",
        {"path": "roundtrip.py"},
        lambda: path.write_bytes(b"before\n"),
        run="newline-roundtrip",
        call="roundtrip-2",
    )[0]
    assert second["snapshot_id"] == first["snapshot_id"]
    assert second["effective"] is False


def test_batch_conflict_aborts_without_restoring_any_file(review):
    module = _load_store()
    store, workspace = review
    one = workspace / "one.txt"; two = workspace / "two.txt"
    one.write_text("old-one", encoding="utf-8"); two.write_text("old-two", encoding="utf-8")
    patch = "*** Begin Patch\n*** Update File: one.txt\n@@\n-old-one\n+new-one\n*** Update File: two.txt\n@@\n-old-two\n+new-two\n*** End Patch"
    changes = capture(
        store, workspace, "apply_patch", {"patch": patch},
        lambda: (one.write_text("new-one", encoding="utf-8"), two.write_text("new-two", encoding="utf-8")),
    )
    two.write_text("third-party", encoding="utf-8")
    with pytest.raises(module.ChangeConflictError) as raised:
        store.undo([row["snapshot_id"] for row in changes], "undo-conflict")
    assert raised.value.paths == ["two.txt"]
    assert one.read_text(encoding="utf-8") == "new-one"
    assert two.read_text(encoding="utf-8") == "third-party"


def test_directory_delete_restores_files_and_empty_directories(review):
    store, workspace = review
    root = workspace / "tree"; empty = root / "empty"; nested = root / "nested"
    empty.mkdir(parents=True); nested.mkdir(); (nested / "value.txt").write_text("value", encoding="utf-8")
    changes = capture(
        store, workspace, "delete_file", {"path": "tree"},
        lambda: __import__("shutil").rmtree(root),
    )
    assert [row["path"] for row in changes] == ["tree/nested/value.txt"]
    store.undo([changes[0]["snapshot_id"]], "undo-directory")
    assert (nested / "value.txt").read_text(encoding="utf-8") == "value"
    assert empty.is_dir()

    only_empty = workspace / "only-empty"
    only_empty.mkdir()
    empty_change = capture(
        store, workspace, "delete_file", {"path": "only-empty"},
        lambda: only_empty.rmdir(), run="run-empty",
    )[0]
    assert empty_change["diff_omitted_reason"] == "directory"
    store.undo([empty_change["snapshot_id"]], "undo-empty-directory")
    assert only_empty.is_dir()


def test_prepared_undo_can_roll_back_when_event_commit_fails(review):
    store, workspace = review
    path = workspace / "rollback.txt"; path.write_text("before", encoding="utf-8")
    change = capture(
        store, workspace, "edit_file", {"path": "rollback.txt"},
        lambda: path.write_text("after", encoding="utf-8"),
    )[0]
    store.undo([change["snapshot_id"]], "undo-rollback")
    assert path.read_text(encoding="utf-8") == "before"
    store.rollback_undo("undo-rollback")
    assert path.read_text(encoding="utf-8") == "after"
    assert json.loads(store.index_path.read_text(encoding="utf-8"))["operations"] == {}


def test_branch_copy_and_truncation_cleanup_keep_only_referenced_snapshots(review, tmp_path):
    store, workspace = review
    first_path = workspace / "first.txt"; second_path = workspace / "second.txt"
    first = capture(
        store, workspace, "write_file", {"path": "first.txt"},
        lambda: first_path.write_text("first", encoding="utf-8"),
    )[0]
    second = capture(
        store, workspace, "write_file", {"path": "second.txt"},
        lambda: second_path.write_text("second", encoding="utf-8"), run="run-2",
    )[0]
    branch_dir = tmp_path / "branch"
    store.copy_referenced_to(branch_dir, [first["snapshot_id"]])
    branch_index = json.loads((branch_dir / "change_reviews/index.json").read_text(encoding="utf-8"))
    assert set(branch_index["records"]) == {first["snapshot_id"]}

    store.prune_unreferenced([second["snapshot_id"]])
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert index["records"][first["snapshot_id"]]["reverted"] is True
    assert index["records"][second["snapshot_id"]]["reverted"] is False


def test_manifest_exposes_trusted_plugin_owned_web_and_runtime():
    manifest = json.loads(
        (ROOT / "plugins/change-review/.myagent-plugin/plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["id"] == "change-review"
    assert manifest["capabilities"]["trusted_host"]["workflow_runtime"] == "runtime.py"
    assert manifest["capabilities"]["ui"]["chat.extension"][0]["renderer"]["module"] == "change-review.js"

    from agent_extensions import load_plugins
    from plugins.ui import plugin_ui_contributions

    plugin = next(item for item in load_plugins(force=True).plugins if item.plugin_id == "change-review")
    contribution = next(item for item in plugin_ui_contributions(plugin) if item["slot"] == "chat.extension")
    assert contribution["renderer"]["module"].startswith("/plugin-assets/change-review/change-review.js?v=")

    agent_loop_source = (ROOT / "app/agent_loop.py").read_text(encoding="utf-8")
    assert agent_loop_source.count("observe_workspace=True") == 2
    assert "ToolInvocationKind.MCP" in agent_loop_source
    assert "ToolInvocationKind.PLUGIN" in agent_loop_source


def test_tool_finished_ui_changes_round_trip_without_entering_model_history(tmp_path):
    sys.path.insert(0, str(ROOT / "app"))
    from runtime_v2.history_ops import RuntimeHistoryOps
    from runtime_v2.mirror import RuntimeMirror
    from runtime_v2.model_projection import RuntimeModelProjection
    from runtime_v2.ui_projection import RuntimeUiProjection

    session_id = "review-runtime"
    change = {
        "path": "demo.txt", "snapshot_id": "opaque", "revision": 1,
        "diff": "--- a/demo.txt\n+++ b/demo.txt\n+secret-ui-only\n",
        "added": 1, "removed": 0,
    }
    mirrored = RuntimeMirror(tmp_path).mirror_ui_event(session_id, {
        "type": "tool_call", "tool": "write_file", "args": {"path": "demo.txt"},
        "result": "Successfully wrote file: demo.txt", "tool_call_id": "call-1",
        "ui": {"changes": [change]},
    })
    assert mirrored is not None and mirrored.type == "tool_finished"
    assert mirrored.payload["ui"]["changes"][0]["snapshot_id"] == "opaque"
    RuntimeHistoryOps(tmp_path).append_model_message(
        session_id, "tool", "Successfully wrote file: demo.txt", tool_call_id="call-1"
    )
    projected = RuntimeUiProjection(tmp_path).read_ui_events(session_id)
    assert projected[0]["ui"]["changes"][0]["diff"] == change["diff"]
    model = RuntimeModelProjection(tmp_path).read_message_dicts(session_id)
    assert model[-1]["content"] == "Successfully wrote file: demo.txt"
    assert "secret-ui-only" not in json.dumps(model, ensure_ascii=False)


def test_undo_api_persists_ui_event_and_notifies_child_and_parent(review, tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import plugins.host as plugin_host
    import session_event_bus

    store, workspace = review
    path = workspace / "api.txt"; path.write_text("before", encoding="utf-8")
    change = capture(
        store, workspace, "edit_file", {"path": "api.txt"},
        lambda: path.write_text("after", encoding="utf-8"),
    )[0]

    class Manager:
        repository = SimpleNamespace(sessions_dir=tmp_path, _path_resolver=None)

        def _get_session_path(self, session_id):
            return tmp_path / "session" if session_id == "child" else tmp_path / session_id

        def _load_metadata(self, session_id):
            return {"parent_session_id": "root"} if session_id == "child" else {}

        def get_subagent_parent_id(self, session_id):
            return "root" if session_id == "child" else None

        def list_sessions(self, include_archived=False):
            return [{"id": "root"}]

        def list_subagent_descendants(self, root):
            return ["child"] if root == "root" else []

        def append_ui_event(self, session_id, event):
            persisted.append((session_id, event))

    persisted = []
    notices = []
    published = []
    host = _load_plugin_module("host.py", "test_change_review_host")
    monkeypatch.setattr(plugin_host, "bundled_host_plugin_enabled", lambda _plugin_id: True)
    monkeypatch.setattr(host, "_append_model_notice", lambda _manager, sid, text: notices.append((sid, text)))

    async def publish(session_id, event):
        published.append((session_id, event))

    monkeypatch.setattr(session_event_bus, "publish_session_event", publish)
    app = FastAPI()
    host.install(app, {"session_manager": Manager()}, SimpleNamespace(plugin_id="change-review"))
    with TestClient(app) as client:
        response = client.post(
            "/sessions/child/change-reviews/undo",
            json={"snapshot_ids": [change["snapshot_id"]], "operation_id": "api-undo"},
        )
    assert response.status_code == 200, response.text
    assert path.read_text(encoding="utf-8") == "before"
    assert persisted[0][1]["type"] == "file_changes_reverted"
    assert [session_id for session_id, _text in notices] == ["child", "root"]
    assert [session_id for session_id, _event in published] == ["child", "root"]
    assert published[-1][1]["agent_id"] == "child"


def test_non_git_workspace_observes_declared_file_tools_only(review):
    """Pins the observation surface outside Git: declared paths only."""
    store, workspace = review
    path = workspace / "note.txt"
    path.write_text("one\n", encoding="utf-8")
    assert capture(
        store, workspace, "run_shell", {"command": "append"},
        lambda: path.write_text("one\ntwo\n", encoding="utf-8"),
    ) == []
    rows = capture(
        store, workspace, "write_file", {"path": "note.txt"},
        lambda: path.write_text("one\ntwo\nthree\n", encoding="utf-8"),
        call="declared-only",
    )
    assert len(rows) == 1
    assert rows[0]["path"] == "note.txt"
    assert rows[0]["operation"] == "modify"
    assert (rows[0]["added"], rows[0]["removed"]) == (1, 0)


def test_ignored_file_modify_keeps_origin_and_undo_restores(tmp_path):
    """A Git-ignored file edited via a declared tool must keep its real origin.

    Regression guard for the double-track case (declared path + Git inventory):
    re-origining the record from a synthesized "missing" state turned the
    second capture into a fake create and made undo delete the file.
    """
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    sys.path.insert(0, str(ROOT / "app"))
    import agent_tools

    (workspace / ".gitignore").write_text("logs/\n", encoding="utf-8")
    (workspace / "logs").mkdir()
    log = workspace / "logs" / "app.log"
    log.write_text("old\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", ".gitignore"], check=True)
    store = module.FileChangeReviewStore(tmp_path / "session")

    with agent_tools.tool_work_dir_override(workspace):
        first = capture(
            store, workspace, "write_file", {"path": "logs/app.log"},
            lambda: log.write_text("new\n", encoding="utf-8"), run="ignored-run",
        )
        second = capture(
            store, workspace, "write_file", {"path": "logs/app.log"},
            lambda: log.write_text("new2\n", encoding="utf-8"), run="ignored-run", call="c2",
        )
    assert first[0]["operation"] == "modify"
    assert second[0]["snapshot_id"] == first[0]["snapshot_id"]
    assert second[0]["operation"] == "modify"
    assert (second[0]["added"], second[0]["removed"]) == (1, 1)
    store.undo([second[0]["snapshot_id"]], "undo-ignored-modify")
    assert log.exists()
    assert log.read_text(encoding="utf-8") == "old\n"


def test_undo_then_restore_round_trip(review):
    store, workspace = review
    path = workspace / "round.txt"
    path.write_text("before\n", encoding="utf-8")
    change = capture(
        store, workspace, "write_file", {"path": "round.txt"},
        lambda: path.write_text("after\n", encoding="utf-8"),
    )[0]
    store.undo([change["snapshot_id"]], "undo-round")
    assert path.read_text(encoding="utf-8") == "before\n"
    # A committed undo must keep the blobs a later restore needs.
    store.commit_undo("undo-round")
    result = store.restore([change["snapshot_id"]], "restore-round")
    assert result["ok"] is True
    assert path.read_text(encoding="utf-8") == "after\n"
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert index["records"][change["snapshot_id"]]["reverted"] is False
    assert index["records"][change["snapshot_id"]]["effective"] is True
    assert index["operations"]["restore:restore-round"]["phase"] == "restored"
    store.commit_restore("restore-round")
    replay = store.restore([change["snapshot_id"]], "restore-round")
    assert replay["idempotent_replay"] is True
    # A restored change can be undone again.
    store.undo([change["snapshot_id"]], "undo-round-2")
    assert path.read_text(encoding="utf-8") == "before\n"


def test_restore_conflict_aborts_without_touching_files(review):
    module = _load_store()
    store, workspace = review
    path = workspace / "conflict.txt"
    path.write_text("before\n", encoding="utf-8")
    change = capture(
        store, workspace, "write_file", {"path": "conflict.txt"},
        lambda: path.write_text("after\n", encoding="utf-8"),
    )[0]
    store.undo([change["snapshot_id"]], "undo-conflict-restore")
    path.write_text("third-party\n", encoding="utf-8")
    with pytest.raises(module.ChangeConflictError) as raised:
        store.restore([change["snapshot_id"]], "restore-conflict")
    assert raised.value.paths == ["conflict.txt"]
    assert path.read_text(encoding="utf-8") == "third-party\n"
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert index["records"][change["snapshot_id"]]["reverted"] is True


def test_restore_requires_a_reverted_snapshot(review):
    module = _load_store()
    store, workspace = review
    path = workspace / "active.txt"
    path.write_text("old\n", encoding="utf-8")
    change = capture(
        store, workspace, "write_file", {"path": "active.txt"},
        lambda: path.write_text("new\n", encoding="utf-8"),
    )[0]
    with pytest.raises(module.SnapshotGoneError):
        store.restore([change["snapshot_id"]], "restore-active")


def test_pruned_records_cannot_be_restored(review):
    module = _load_store()
    store, workspace = review
    first_path = workspace / "f1.txt"
    second_path = workspace / "f2.txt"
    first = capture(
        store, workspace, "write_file", {"path": "f1.txt"},
        lambda: first_path.write_text("one\n", encoding="utf-8"),
    )[0]
    second = capture(
        store, workspace, "write_file", {"path": "f2.txt"},
        lambda: second_path.write_text("two\n", encoding="utf-8"), run="run-2",
    )[0]
    store.prune_unreferenced([second["snapshot_id"]])
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert index["records"][first["snapshot_id"]]["dropped"] is True
    with pytest.raises(module.SnapshotGoneError):
        store.restore([first["snapshot_id"]], "restore-dropped")


def test_prepared_restore_can_roll_back_when_event_commit_fails(review):
    store, workspace = review
    path = workspace / "rollback-restore.txt"
    path.write_text("before\n", encoding="utf-8")
    change = capture(
        store, workspace, "edit_file", {"path": "rollback-restore.txt"},
        lambda: path.write_text("after\n", encoding="utf-8"),
    )[0]
    store.undo([change["snapshot_id"]], "undo-rb")
    store.restore([change["snapshot_id"]], "restore-rb")
    assert path.read_text(encoding="utf-8") == "after\n"
    store.rollback_restore("restore-rb")
    assert path.read_text(encoding="utf-8") == "before\n"
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert "restore:restore-rb" not in index["operations"]
    assert index["records"][change["snapshot_id"]]["reverted"] is True


def test_directory_delete_restore_round_trip(review):
    store, workspace = review
    root = workspace / "tree"; empty = root / "empty"; nested = root / "nested"
    empty.mkdir(parents=True); nested.mkdir(); (nested / "value.txt").write_text("value", encoding="utf-8")
    change = capture(
        store, workspace, "delete_file", {"path": "tree"},
        lambda: shutil.rmtree(root),
    )[0]
    store.undo([change["snapshot_id"]], "undo-tree")
    assert (nested / "value.txt").read_text(encoding="utf-8") == "value"
    assert empty.is_dir()
    store.restore([change["snapshot_id"]], "restore-tree")
    assert not root.exists()
    store.undo([change["snapshot_id"]], "undo-tree-2")
    assert (nested / "value.txt").read_text(encoding="utf-8") == "value"

    only_empty = workspace / "only-empty"
    only_empty.mkdir()
    empty_change = capture(
        store, workspace, "delete_file", {"path": "only-empty"},
        lambda: only_empty.rmdir(), run="run-empty",
    )[0]
    store.undo([empty_change["snapshot_id"]], "undo-empty-2")
    assert only_empty.is_dir()
    store.restore([empty_change["snapshot_id"]], "restore-empty")
    assert not only_empty.exists()
    store.undo([empty_change["snapshot_id"]], "undo-empty-3")
    assert only_empty.is_dir()


def test_restore_api_reapplies_and_persists_ui_event(review, tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import plugins.host as plugin_host
    import session_event_bus

    store, workspace = review
    path = workspace / "api-restore.txt"; path.write_text("before\n", encoding="utf-8")
    change = capture(
        store, workspace, "edit_file", {"path": "api-restore.txt"},
        lambda: path.write_text("after\n", encoding="utf-8"),
    )[0]
    store.undo([change["snapshot_id"]], "api-undo-pre")

    class Manager:
        repository = SimpleNamespace(sessions_dir=tmp_path, _path_resolver=None)

        def _get_session_path(self, session_id):
            return tmp_path / "session" if session_id == "child" else tmp_path / session_id

        def _load_metadata(self, session_id):
            return {"parent_session_id": "root"} if session_id == "child" else {}

        def get_subagent_parent_id(self, session_id):
            return "root" if session_id == "child" else None

        def list_sessions(self, include_archived=False):
            return [{"id": "root"}]

        def list_subagent_descendants(self, root):
            return ["child"] if root == "root" else []

        def append_ui_event(self, session_id, event):
            persisted.append((session_id, event))

    persisted = []
    notices = []
    published = []
    host = _load_plugin_module("host.py", "test_change_review_host_restore")
    monkeypatch.setattr(plugin_host, "bundled_host_plugin_enabled", lambda _plugin_id: True)
    monkeypatch.setattr(host, "_append_model_notice", lambda _manager, sid, text: notices.append((sid, text)))

    async def publish(session_id, event):
        published.append((session_id, event))

    monkeypatch.setattr(session_event_bus, "publish_session_event", publish)
    app = FastAPI()
    host.install(app, {"session_manager": Manager()}, SimpleNamespace(plugin_id="change-review"))
    with TestClient(app) as client:
        response = client.post(
            "/sessions/child/change-reviews/restore",
            json={"snapshot_ids": [change["snapshot_id"]], "operation_id": "api-restore"},
        )
    assert response.status_code == 200, response.text
    assert path.read_text(encoding="utf-8") == "after\n"
    assert persisted[0][1]["type"] == "file_changes_restored"
    assert [session_id for session_id, _text in notices] == ["child", "root"]
    assert [session_id for session_id, _event in published] == ["child", "root"]
    assert published[-1][1]["agent_id"] == "child"


def test_temporary_write_and_delete_stay_invisible_even_in_git(tmp_path):
    """A temporary write is shadowed in the store: no row on write or delete."""
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    sys.path.insert(0, str(ROOT / "app"))
    import agent_tools

    store = module.FileChangeReviewStore(tmp_path / "session")
    target = workspace / "scratch_probe.py"
    with agent_tools.tool_work_dir_override(workspace):
        rows = capture(
            store, workspace, "write_file",
            {"path": "scratch_probe.py", "contents": "print(1)\n", "temporary": True},
            lambda: target.write_text("print(1)\n", encoding="utf-8"),
        )
        assert rows == []
        index = json.loads(store.index_path.read_text(encoding="utf-8"))
        assert len(index["temporaries"]) == 1
        assert index["records"] == {}

        rows = capture(
            store, workspace, "delete_file", {"path": "scratch_probe.py"},
            lambda: target.unlink(), call="call-2",
        )
    assert rows == []
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert index["temporaries"] == {}
    assert index["records"] == {}


def test_temporary_write_shell_delete_stays_invisible(tmp_path):
    """A Git sweep must not surface a temporary creation (the old +1 row)."""
    module = _load_store()
    workspace = tmp_path / "repo"
    workspace.mkdir()
    init_git_workspace(workspace)
    sys.path.insert(0, str(ROOT / "app"))
    import agent_tools

    store = module.FileChangeReviewStore(tmp_path / "session")
    target = workspace / "scratch_probe.py"
    with agent_tools.tool_work_dir_override(workspace):
        assert capture(
            store, workspace, "write_file",
            {"path": "scratch_probe.py", "contents": "print(1)\n", "temporary": True},
            lambda: target.write_text("print(1)\n", encoding="utf-8"),
        ) == []
        assert capture(
            store, workspace, "run_shell", {"command": "rm scratch_probe.py"},
            lambda: target.unlink(), call="call-2",
        ) == []
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert index["records"] == {}


def test_temporary_then_normal_write_graduates_with_original_origin(review):
    store, workspace = review
    path = workspace / "graduate.txt"
    assert capture(
        store, workspace, "write_file",
        {"path": "graduate.txt", "contents": "v1\n", "temporary": True},
        lambda: path.write_text("v1\n", encoding="utf-8"),
    ) == []
    rows = capture(
        store, workspace, "write_file", {"path": "graduate.txt", "contents": "v1\nv2\n"},
        lambda: path.write_text("v1\nv2\n", encoding="utf-8"), call="call-2",
    )
    assert len(rows) == 1
    assert rows[0]["operation"] == "create"
    assert rows[0]["before"]["exists"] is False
    assert (rows[0]["added"], rows[0]["removed"]) == (2, 0)
    index = json.loads(store.index_path.read_text(encoding="utf-8"))
    assert index["temporaries"] == {}


def test_temporary_graduation_keeps_preexisting_origin(review):
    store, workspace = review
    path = workspace / "graduate2.txt"
    path.write_text("base\n", encoding="utf-8")
    assert capture(
        store, workspace, "write_file",
        {"path": "graduate2.txt", "contents": "temp\n", "temporary": True},
        lambda: path.write_text("temp\n", encoding="utf-8"),
    ) == []
    rows = capture(
        store, workspace, "edit_file", {"path": "graduate2.txt"},
        lambda: path.write_text("base\nkept\n", encoding="utf-8"), call="call-2",
    )
    assert len(rows) == 1
    assert rows[0]["operation"] == "modify"
    assert (rows[0]["added"], rows[0]["removed"]) == (1, 0)
    store.undo([rows[0]["snapshot_id"]], "undo-graduate")
    assert path.read_text(encoding="utf-8") == "base\n"
