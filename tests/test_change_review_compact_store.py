"""Durable storage migration and abandoned-executor recovery contracts."""
from __future__ import annotations

import json
import importlib.util
import subprocess
import zipfile
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def _load_plugin_module(filename, name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / 'plugins/change-review' / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_store():
    return _load_plugin_module('store.py', 'test_compact_review_store')


@pytest.fixture
def review(tmp_path, monkeypatch):
    import agent_tools
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    monkeypatch.setattr(agent_tools, 'WORK_DIR', workspace)
    # Force the external branch for storage/GC fault-injection contracts below.
    monkeypatch.setattr(_load_store(), 'INLINE_DIFF_BYTES', 0)
    with agent_tools.tool_work_dir_override(workspace):
        yield _load_store().FileChangeReviewStore(tmp_path / 'session'), workspace


def capture(store, workspace, tool, args, mutate, run='run-1', call='call-1'):
    token = store.begin_capture(tool, args, run_id=run, tool_call_id=call, work_root=workspace)
    mutate()
    return store.finish_capture(token)


def init_git_workspace(path):
    subprocess.run(['git', 'init', '-q', str(path)], check=True)


def legacy_index(store):
    index = store._empty()
    index['version'] = 1
    row = {'snapshot_id': 'legacy', 'path': 'legacy.txt', 'run_id': 'turn',
           'turn_id': 'turn', 'revision': 1, 'diff': '--- a/legacy.txt\n+hello\n',
           'added': 1, 'removed': 0, 'effective': True}
    index['records']['legacy'] = dict(row)
    index['operations']['operation'] = {'result': {'ok': True, 'changes': [dict(row)]}}
    index['review_events']['delivery'] = {'type': 'file_changes_updated',
        'operation_id': 'delivery', 'changes': [dict(row)]}
    index['baselines']['turn'] = {'baseline_id': 'baseline', 'entries': {
        'legacy.txt': {'path': 'legacy.txt', 'before': {'exists': False}}}}
    store.root.mkdir(parents=True, exist_ok=True)
    store.index_path.write_text(json.dumps(index), encoding='utf-8')
    return row


def test_v1_migration_keeps_diff_events_operations_and_manifest(review):
    store, _ = review
    row = legacy_index(store)
    index = store._load()
    assert index['version'] == 2
    assert 'diff' not in index['records']['legacy']
    assert 'diff' not in index['review_events']['delivery']['changes'][0]
    assert 'diff' not in index['operations']['operation']['result']['changes'][0]
    assert 'entries' not in index['baselines']['turn']
    fresh = type(store)(store.session_dir)
    assert fresh.public_record(index['records']['legacy'])['diff'] == row['diff']
    assert fresh.flush_deferred_sweeps()[0]['changes'][0]['diff'] == row['diff']
    assert fresh._public_result(index['operations']['operation']['result'])['changes'][0]['diff'] == row['diff']
    fresh._gc_blobs(index)
    assert fresh._baseline_entries(index['baselines']['turn'])['legacy.txt']['path'] == 'legacy.txt'
    first = store.index_path.stat().st_mtime_ns
    fresh._load()
    assert store.index_path.stat().st_mtime_ns == first, 'v2 reads must not rewrite the index'


def test_interrupted_migration_retries_without_losing_v1(review, monkeypatch):
    store, _ = review
    original = legacy_index(store)
    original_save = store._save
    monkeypatch.setattr(store, '_save', lambda _: (_ for _ in ()).throw(OSError('commit interrupted')))
    with pytest.raises(OSError, match='commit interrupted'):
        store._load()
    raw = json.loads(store.index_path.read_text(encoding='utf-8'))
    assert raw['version'] == 1 and raw['records']['legacy']['diff'] == original['diff']
    monkeypatch.setattr(store, '_save', original_save)
    migrated = store._load()
    assert store.public_record(migrated['records']['legacy'])['diff'] == original['diff']


def test_concurrent_v1_readers_share_migration_commit(review):
    store, _ = review
    original = legacy_index(store)
    readers = [type(store)(store.session_dir) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        indices = list(pool.map(lambda reader: reader._load(), readers))
    assert all(index['version'] == 2 for index in indices)
    assert all(reader.public_record(index['records']['legacy'])['diff'] == original['diff']
               for reader, index in zip(readers, indices))


def test_gc_and_branch_preserve_diff_and_undo_restore(review, tmp_path):
    store, workspace = review
    target = workspace / 'file.txt'
    target.write_text('original\n', encoding='utf-8')
    row = capture(store, workspace, 'edit_file', {'path': 'file.txt'},
                  lambda: target.write_text('changed\n', encoding='utf-8'))[0]
    index = store._load()
    record = index['records'][row['snapshot_id']]
    assert 'diff' not in record and record['diff_blob']
    store._gc_blobs(index)
    branch_dir = tmp_path / 'branch'
    store.copy_referenced_to(branch_dir, [row['snapshot_id']])
    branch = type(store)(branch_dir)
    assert branch.public_record(branch._load()['records'][row['snapshot_id']])['diff'] == row['diff']
    store.undo([row['snapshot_id']], 'undo')
    store.commit_undo('undo')
    assert target.read_text(encoding='utf-8') == 'original\n'
    assert store.undo([row['snapshot_id']], 'undo')['changes'][0]['diff'] == row['diff']
    store.restore([row['snapshot_id']], 'restore')
    store.commit_restore('restore')
    assert target.read_text(encoding='utf-8') == 'changed\n'
    assert store.restore([row['snapshot_id']], 'restore')['changes'][0]['diff'] == row['diff']


def test_outbox_keeps_older_revision_diff_until_ack(review):
    store, workspace = review
    target = workspace / 'file.txt'
    first = capture(store, workspace, 'write_file', {'path': 'file.txt'},
                    lambda: target.write_text('first\n', encoding='utf-8'))[0]
    index = store._load()
    event = store._compact_result({'operation_id': 'delivery', 'changes': [first]})
    old_blob = event['changes'][0]['diff_blob']
    index['review_events']['delivery'] = event
    store._save(index)
    capture(store, workspace, 'edit_file', {'path': 'file.txt'},
            lambda: target.write_text('second\n', encoding='utf-8'), call='second')
    store._gc_blobs(store._load())
    fresh = type(store)(store.session_dir)
    assert fresh.flush_deferred_sweeps()[0]['changes'][0]['diff'] == first['diff']
    store.acknowledge_review_event('delivery')
    store._gc_blobs(store._load())
    assert not (store.blob_dir / (old_blob + '.gz')).exists()


def test_manifest_cold_reload_and_damage_are_observable(review):
    store, workspace = review
    module = _load_store()
    init_git_workspace(workspace)
    target = workspace / 'file.txt'
    target.write_text('before\n', encoding='utf-8')
    started = store.begin_capture('run_shell', {}, run_id='turn', tool_call_id='call', work_root=workspace)
    baseline = next(iter(store._load()['baselines'].values()))
    assert 'entries' not in baseline and baseline['entries_archive']
    module._workspace_scans.clear()
    module._baseline_manifests.clear()
    fresh = type(store)(store.session_dir)
    assert fresh.finish_capture(started) == []
    assert fresh.timings.get('changed_count', 0) == 0, 'cold restart should reuse manifest signatures'
    started = store.begin_capture('run_shell', {}, run_id='turn', tool_call_id='next', work_root=workspace)
    module._baseline_manifests.clear()
    with zipfile.ZipFile(store._baseline_archive_path(baseline['baseline_id']), 'a') as archive:
        with pytest.warns(UserWarning, match='Duplicate name'):
            archive.writestr(baseline['entries_archive'], b'broken')
    with pytest.raises(module.SnapshotGoneError):
        store.finish_capture(started)
    assert not store.timings.get('inventory_calls'), 'damaged manifests should fail before scanning files'
    assert started.capture_id in store._load()['pending'], 'failed audit must remain recoverable'


def pending_capture(store, workspace, execution='old', turn='turn'):
    return store.begin_capture('write_file', {'path': 'file.txt'}, run_id=turn,
        tool_call_id='call', work_root=workspace, execution_scope={'run_id': execution})


@pytest.mark.parametrize('same_execution,active,foreign', [(True, False, False), (False, True, False), (False, False, True)])
def test_old_pending_does_not_expire_an_active_or_foreign_executor(review, monkeypatch, same_execution, active, foreign):
    store, workspace = review
    started = pending_capture(store, workspace)
    index = store._load()
    index['pending'][started.capture_id]['created_at'] = 1
    if foreign:
        index['pending'][started.capture_id]['owner'] = {'pid': 98765, 'started_at': 1}
    store._save(index)
    monkeypatch.setattr(_load_store(), '_owner_alive', lambda _: True)
    assert store.recover_pending(current_run_id='old' if same_execution else 'new',
        current_turn_id='next', execution_active=lambda _: active) == 0
    assert started.capture_id in store._load()['pending']


def test_abandoned_capture_recovery_is_durable_and_undoable(review, monkeypatch):
    store, workspace = review
    target = workspace / 'file.txt'
    target.write_text('before\n', encoding='utf-8')
    started = pending_capture(store, workspace)
    target.write_text('after\n', encoding='utf-8')
    monkeypatch.setattr(_load_store(), '_owner_alive', lambda _: False)
    assert store.recover_pending(current_run_id='new', current_turn_id='next') == 1
    fresh = type(store)(store.session_dir)
    assert started.capture_id not in fresh._load()['pending']
    events = fresh.flush_deferred_sweeps()
    assert events[0]['change_review_status']['status'] == 'checked'
    assert '+after' in events[0]['changes'][0]['diff']
    assert fresh.flush_deferred_sweeps() == events, 'delivery retries until explicit ack'
    fresh.undo([events[0]['changes'][0]['snapshot_id']], 'undo-recovery')
    assert target.read_text(encoding='utf-8') == 'before\n'
    fresh.acknowledge_review_event(events[0]['operation_id'])
    assert fresh.flush_deferred_sweeps() == []


def test_completed_tool_recovers_inside_an_active_run_and_keeps_earliest_origin(review):
    store, workspace = review
    target = workspace / 'file.txt'
    target.write_text('original\n', encoding='utf-8')
    lost = pending_capture(store, workspace, execution='active')
    target.write_text('unrecorded\n', encoding='utf-8')
    # An already-committed later revision must not replace the older capture's
    # origin when a previously failed post-tool snapshot is finally recovered.
    capture(store, workspace, 'edit_file', {'path': 'file.txt'},
            lambda: target.write_text('latest\n', encoding='utf-8'), run='turn', call='later')
    assert store.recover_pending(current_run_id='active', current_turn_id='turn',
                                 execution_active=lambda _: True) == 0
    assert store.recover_pending(current_run_id='active', current_turn_id='turn',
        execution_active=lambda _: True, completed_capture_ids=[lost.capture_id]) == 1
    row = store.flush_deferred_sweeps()[0]['changes'][0]
    assert '-original' in row['diff'] and '+latest' in row['diff']
    store.undo([row['snapshot_id']], 'undo-recovered-origin')
    assert target.read_text(encoding='utf-8') == 'original\n'


def test_runtime_retries_failed_post_capture_before_next_tool(review, monkeypatch):
    store, workspace = review
    runtime = _load_plugin_module('runtime.py', 'test_review_post_failure_runtime')
    module = runtime._store_module()
    events = []
    manager = SimpleNamespace(_get_session_path=lambda _: store.session_dir,
        append_ui_event=lambda _sid, event, **_: events.append(event))
    callbacks = runtime.initialize(SimpleNamespace(session_manager=manager))
    state = {'session_id': 'session', '_runtime_v2_run_id': 'active', '_change_review_turn_id': 'turn'}
    target = workspace / 'file.txt'
    target.write_text('original\n', encoding='utf-8')
    token = callbacks['before_native_file_tool'](state, 'edit_file', {'path': str(target)}, 'first')
    target.write_text('after\n', encoding='utf-8')
    original_finish = module.FileChangeReviewStore.finish_capture
    monkeypatch.setattr(module.FileChangeReviewStore, 'finish_capture',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('post probe')))
    with pytest.raises(OSError, match='post probe'):
        callbacks['after_native_file_tool'](state, token)
    assert token.capture_id in state['_change_review_completed_captures']
    monkeypatch.setattr(module.FileChangeReviewStore, 'finish_capture', original_finish)
    next_token = callbacks['before_native_file_tool'](state, 'write_file',
        {'path': str(workspace / 'next.txt')}, 'next')
    assert events and events[0]['change_review_status']['stage'] == 'recovery'
    assert '-original' in events[0]['changes'][0]['diff']
    assert not state['_change_review_completed_captures']
    callbacks['after_native_file_tool'](state, next_token)


def test_legacy_pending_without_baseline_becomes_diagnostic_event(review):
    store, _ = review
    index = store._empty()
    index['pending']['old'] = {'tool': 'run_shell', 'run_id': 'old-turn',
        'tool_call_id': 'old-call', 'entries': [], 'baseline_key': 'missing'}
    store._save(index)
    assert store.recover_pending(current_run_id='new', current_turn_id='new-turn',
                                 execution_active=lambda _: False) == 1
    assert not store._load()['pending']
    event = store.flush_deferred_sweeps()[0]
    assert event['changes'] == []
    assert event['change_review_status']['status'] == 'failed'


def test_baseline_is_protected_until_its_pending_capture_finishes(review):
    store, workspace = review
    init_git_workspace(workspace)
    (workspace / 'file.txt').write_text('before\n', encoding='utf-8')
    started = pending_capture(store, workspace)
    baseline = next(iter(store._load()['baselines'].values()))
    store.finish_run('turn')
    store.finish_other_runs('next')
    assert store._baseline_archive_path(baseline['baseline_id']).is_file()
    store.finish_capture(started)
    store.finish_other_runs('next')
    assert not store._load()['baselines']
    assert not store._baseline_archive_path(baseline['baseline_id']).exists()


def test_http_and_capture_runtimes_share_migration_lock():
    runtime = _load_plugin_module('runtime.py', 'test_review_shared_runtime')
    host = _load_plugin_module('host.py', 'test_review_shared_host')
    assert runtime._store_module() is host._store_module()


def test_git_inventory_failure_is_not_reported_as_no_changes(review, monkeypatch):
    store, workspace = review
    init_git_workspace(workspace)
    def fail(*_args, **_kwargs):
        raise OSError('git unavailable')
    monkeypatch.setattr(_load_store().subprocess, 'run', fail)
    with pytest.raises(_load_store().ChangeReviewError, match='inventory failed'):
        store.begin_capture('run_shell', {}, run_id='turn', tool_call_id='call', work_root=workspace)


def test_tiny_diff_avoids_extra_blob_and_large_revision_externalizes(review, monkeypatch):
    store, workspace = review
    monkeypatch.setattr(_load_store(), 'INLINE_DIFF_BYTES', 512)
    target = workspace / 'tiny.txt'
    row = capture(store, workspace, 'write_file', {'path': 'tiny.txt'},
                  lambda: target.write_text('first\n', encoding='utf-8'))[0]
    record = store._load()['records'][row['snapshot_id']]
    assert record['diff'] == row['diff'] and not record.get('diff_blob')
    assert len(list(store.blob_dir.glob('*.gz'))) == 1, 'only the content snapshot needs a file/fsync'
    large = capture(store, workspace, 'edit_file', {'path': 'tiny.txt'},
        lambda: target.write_text('x' * 2048 + '\n', encoding='utf-8'), call='large')[0]
    record = store._load()['records'][row['snapshot_id']]
    assert 'diff' not in record and record['diff_blob']
    assert store.public_record(record)['diff'] == large['diff']
    small = capture(store, workspace, 'edit_file', {'path': 'tiny.txt'},
        lambda: target.write_text('last\n', encoding='utf-8'), call='small')[0]
    record = store._load()['records'][row['snapshot_id']]
    assert record['diff'] == small['diff'] and 'diff_blob' not in record


@pytest.mark.parametrize('action', ['undo', 'restore'])
def test_missing_diff_fails_before_any_workspace_mutation(review, action):
    store, workspace = review
    target = workspace / 'file.txt'
    target.write_text('before\n', encoding='utf-8')
    row = capture(store, workspace, 'edit_file', {'path': 'file.txt'},
                  lambda: target.write_text('after\n', encoding='utf-8'))[0]
    if action == 'restore':
        store.undo([row['snapshot_id']], 'first-undo')
        store.commit_undo('first-undo')
    expected = target.read_bytes()
    record = store._load()['records'][row['snapshot_id']]
    (store.blob_dir / (record['diff_blob'] + '.gz')).unlink()
    fresh = type(store)(store.session_dir)
    with pytest.raises(_load_store().SnapshotGoneError):
        getattr(fresh, action)([row['snapshot_id']], 'missing-diff')
    assert target.read_bytes() == expected
