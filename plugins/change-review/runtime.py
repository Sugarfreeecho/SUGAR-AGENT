"""Hot-path callbacks that connect tool execution to the plugin store."""

from __future__ import annotations

import importlib.util
import hashlib
import sys
import logging
import time
from pathlib import Path


def _store_module():
    path = Path(__file__).with_name("store.py").resolve()
    try:
        stat = path.stat()
        signature = f"{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        signature = "missing"
    digest = hashlib.sha256(f"{path}:{signature}".encode()).hexdigest()[:16]
    name = f"myagent_change_review_store_{digest}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load change-review store")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def initialize(host_module):
    store_module = _store_module()
    session_manager = host_module.session_manager

    def log_timing(state, store, stage, started, **extra):
        fields = dict.fromkeys(('inventory_ms', 'signature_ms', 'read_hash_ms', 'blob_io_ms',
                                'diff_ms', 'index_read_ms', 'index_write_ms', 'lock_wait_ms',
                                'baseline_ms', 'maintenance_ms', 'ui_commit_ms'), 0.0)
        fields.update(dict.fromkeys(('files', 'cache_hits', 'changed_count', 'sweep_deferred', 'inventory_calls', 'sweep_count'), 0))
        fields.update(store.timings)
        fields.update(extra)
        breakdown = ' '.join(f'{key}={value:.3f}' if isinstance(value, float)
                             else f'{key}={value}' for key, value in sorted(fields.items()))
        logging.getLogger('agent_harness').info(
            'change_review_timing session=%s stage=%s elapsed_ms=%.3f %s',
            state.get('session_id', ''), stage,
            (time.perf_counter() - started) * 1000, breakdown,
        )

    def coverage_notice(state, store):
        limit = store.timings.get('file_limit')
        if not limit or state.get('_change_review_limit_notice') == limit:
            return
        state['_change_review_limit_notice'] = limit
        state.setdefault('_change_review_pending_events', []).append({
            'type': 'warning',
            'content': f'改动审查超过配置的 {limit} 文件上限，当前仅记录声明路径；shell/MCP 等外部改动可能不被记录。',
        })

    def flush_file_tool_reviews(state):
        if state.get('_change_review_dirty'):
            store = store_module.FileChangeReviewStore(session_manager._get_session_path(state['session_id']))
            started = time.perf_counter()
            events = store.flush_deferred_sweeps()
            coverage_notice(state, store)
            for event in events:
                event = dict(event, session_id=state['session_id'])
                # Commit before acknowledging the outbox, then forward through
                # the normal stream without committing the same event twice.
                with store._measure('ui_commit_ms'):
                    session_manager.append_ui_event(state['session_id'], event, require_commit=True)
                state.setdefault('_change_review_pending_events', []).append(
                    dict(event, _runtime_v2_committed=True))
                store.acknowledge_review_event(event['operation_id'])
            log_timing(state, store, 'batch_flush', started, changes=sum(len(e['changes']) for e in events))
            state['_change_review_dirty'] = False
        return state.pop('_change_review_pending_events', [])

    def before_native_file_tool(
        state,
        tool_name,
        tool_args,
        tool_call_id,
        worktree_root="",
        observe_workspace=False,
    ):
        if tool_name not in {
            "write_file", "edit_file", "apply_patch", "delete_file", "run_shell"
        } and not observe_workspace:
            return None
        session_id = str((state or {}).get("session_id") or "")
        if not session_id:
            return None
        if worktree_root:
            work_root = Path(worktree_root)
        else:
            from agent_tools import active_tool_work_dir

            work_root = active_tool_work_dir()
        store = store_module.FileChangeReviewStore(session_manager._get_session_path(session_id))
        # Recover durable batch obligations before retiring an older baseline.
        # External tools also form a boundary: never defer their workspace audit.
        if not state.get('_change_review_recovery_checked') or observe_workspace or tool_name == 'run_shell':
            if not state.get('_change_review_recovery_checked'):
                state['_change_review_dirty'] = True
            events = flush_file_tool_reviews(state)
            state.setdefault('_change_review_pending_events', []).extend(events)
            state['_change_review_recovery_checked'] = True
        started = time.perf_counter()
        turn_id = str(
            (state or {}).get("_change_review_turn_id")
            or (state or {}).get("_runtime_v2_run_id")
            or ""
        )
        # The arrival of work in a different official turn is the durable end
        # boundary for the previous turn. Keep the current baseline across idle
        # gaps and automatic continuations.
        maintenance_started = time.perf_counter()
        if state.get('_change_review_retired_turn') != turn_id:
            store.finish_other_runs(turn_id)
            state['_change_review_retired_turn'] = turn_id
        maintenance_ms = (time.perf_counter() - maintenance_started) * 1000
        capture = store.begin_capture(
            tool_name,
            tool_args if isinstance(tool_args, dict) else {},
            # The baseline belongs to the official user turn, not to one
            # execution process. Follow-ups and automatic continuations keep
            # this id until the next ordinary user input.
            run_id=turn_id,
            tool_call_id=str(tool_call_id or ""),
            work_root=work_root,
            execution_scope={
                'run_id': str(state.get('_runtime_v2_run_id') or ''),
                'react_iter': int(state.get('_current_react_iter') or 0),
                'stream_seq': int(state.get('_active_stream_seq') or 0),
            },
        )
        store.timings['maintenance_ms'] = maintenance_ms
        coverage_notice(state, store)
        log_timing(state, store, 'before', started, tool=tool_name)
        # Per-capture membership, not a mutable per-run boolean: an external
        # observer may complete concurrently with a native file operation.
        if capture is not None and not observe_workspace and tool_name in {'write_file', 'edit_file', 'apply_patch', 'delete_file'} and state.get('_change_review_batch_active'):
            state.setdefault('_change_review_deferred_captures', {})[capture.capture_id] = True
        return capture

    def after_native_file_tool(state, capture, successful=True):
        session_id = str((state or {}).get("session_id") or "")
        if not session_id or capture is None:
            return []
        store = store_module.FileChangeReviewStore(session_manager._get_session_path(session_id))
        started = time.perf_counter()
        deferred = state.setdefault('_change_review_deferred_captures', {})
        defer = bool(deferred.pop(capture.capture_id, False))
        changes = store.finish_capture(capture, successful=bool(successful), defer_workspace_sweep=defer)
        if defer:
            state['_change_review_dirty'] = True
        coverage_notice(state, store)
        log_timing(state, store, 'after', started, changes=len(changes))
        return changes

    def after_run(state):
        session_id = str((state or {}).get("session_id") or "")
        run_id = str(
            (state or {}).get("_change_review_turn_id")
            or (state or {}).get("_runtime_v2_run_id")
            or ""
        )
        if not session_id or not run_id:
            return None
        # A process ending does not end a user turn: a goal/continuation may
        # resume without another user message. Stale baselines are retired when
        # the next turn first captures a change.
        return None

    def referenced_snapshot_ids(session_id):
        ids = set()
        for event in session_manager._load_ui_events_for_active_runtime(session_id):
            if not isinstance(event, dict):
                continue
            if event.get("type") == "tool_call":
                changes = ((event.get("ui") or {}).get("changes") or [])
                ids.update(
                    str(row.get("snapshot_id") or "")
                    for row in changes if isinstance(row, dict) and row.get("snapshot_id")
                )
            elif event.get("type") in ("file_changes_reverted", "file_changes_restored"):
                ids.update(str(item or "") for item in event.get("snapshot_ids") or [])
            elif event.get('type') == 'file_changes_updated':
                ids.update(str(row.get('snapshot_id') or '') for row in event.get('changes') or []
                           if isinstance(row, dict) and row.get('snapshot_id'))
        return ids

    def history_truncated(session_id):
        store = store_module.FileChangeReviewStore(session_manager._get_session_path(session_id))
        if store.index_path.is_file():
            store.prune_unreferenced(referenced_snapshot_ids(session_id))

    def session_branched(source_session_id, target_session_id):
        source = store_module.FileChangeReviewStore(session_manager._get_session_path(source_session_id))
        if source.index_path.is_file():
            source.copy_referenced_to(
                session_manager._get_session_path(target_session_id),
                # The branch starts with the source history. Resolve the
                # references from that history before copying; the target has
                # no UI events yet (and therefore no references to discover).
                referenced_snapshot_ids(source_session_id),
            )

    return {
        "before_native_file_tool": before_native_file_tool,
        "after_native_file_tool": after_native_file_tool,
        "flush_file_tool_reviews": flush_file_tool_reviews,
        "after_run": after_run,
        "history_truncated": history_truncated,
        "session_branched": session_branched,
    }
