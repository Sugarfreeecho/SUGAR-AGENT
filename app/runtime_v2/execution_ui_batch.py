"""Plan completed display updates privately, then append and project one batch.

The facts and their order are unchanged. No execution cache or snapshot is
published during planning; the existing event writer must flush the whole
batch before its projection or public commit receipts become visible.
"""
from __future__ import annotations

import asyncio
import copy
import os
from contextlib import nullcontext
from types import SimpleNamespace

from agent_local_timing import local_step, local_timed
from .execution_journal import ExecutionJournal, EVENT_TYPE, apply_execution_update
from .mirror import RuntimeMirror
from .write_probe import batch_append_scope, open_append_writer


class _ExecutionPlan(ExecutionJournal):
    def __init__(self, journal, state):
        self.log = journal.log
        # The caller holds the live journal lock. Complete-event record() only
        # changes seq and individual execution rows; detach each written row.
        self._planned = {**state, "records": dict(state["records"])}
        self._detached_records = set()
        self.rows = []
        self.next_seq = int(state["seq"]) + 1

    def _session_lock(self, session_id):
        # This is a private plan, not the shared journal cache. Keep record()'s
        # real fact transaction/directory checks; the live lock is held outside.
        return nullcontext()

    def record(self, session_id, event):
        if event.get("type") not in {"tool_call", "llm_reasoning", "llm_response"}:
            raise ValueError("execution plan only accepts complete display events")
        return super().record(session_id, event)

    def _state(self, session_id, *args, **kwargs):
        return self._planned

    def _append(self, session_id, state, update, run):
        seq = self.next_seq
        self.next_seq += 1
        self.rows.append({"type": EVENT_TYPE, "payload": update, "run_id": run})
        identity = str(update.get("execution_id") or "")
        if identity and identity not in self._detached_records:
            prior = state["records"].get(identity)
            if prior is not None:
                state["records"][identity] = copy.deepcopy(prior)
            self._detached_records.add(identity)
        apply_execution_update(state["records"], update, seq)
        state["seq"] = seq
        # record() consumes only seq. Real events/IDs are allocated by the
        # ordinary append writer after all planning has succeeded.
        return SimpleNamespace(seq=seq)


def _signature(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, getattr(stat, "st_ctime_ns", None)


@local_timed("execution_ui_batch")
def commit_display_batch(manager, session_id, events, *, prepare_ui_event,
                         timeout_seconds=None, cancel_event=None):
    """Return committed rows, or None when the existing individual path is needed."""
    from . import runtime_v2_primary, runtime_v2_strict

    if (not events or not runtime_v2_primary() or not runtime_v2_strict()
            or any(event.get("type") not in {"tool_call", "llm_reasoning", "llm_response"}
                   or any(event.get(key) for key in ("_subagent_forward", "_skip_persist", "ephemeral",
                                                     "_runtime_v2_committed")) for event in events)):
        return None

    def check_cancelled():
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError()
        from session_lifecycle import is_session_deleted
        if is_session_deleted(session_id):
            raise RuntimeError("cannot commit UI events to a deleted session")

    check_cancelled()
    resolver = getattr(manager, "_resolve_session_path", None)
    journal = ExecutionJournal(manager.sessions_dir, resolver)
    mirror = RuntimeMirror(manager.sessions_dir, resolver, transaction_timeout_seconds=timeout_seconds)
    path = journal.log.event_path(session_id)
    with journal.log.session_transaction(session_id, timeout_seconds=timeout_seconds), journal._session_lock(session_id):
        # The fast path extends an existing fact source. First-event bootstrap
        # retains the original path, including its error/recovery behavior.
        if not path.exists():
            return None
        with batch_append_scope(path), open_append_writer(path) as writer:
            before = _signature(os.fstat(writer.fileno()))
            if not before[1] or None in before:
                return None
            if _signature(path.stat()) != before:
                raise RuntimeError("event source identity changed before UI batch planning")
            with local_step("ui_batch_prepare"):
                state = journal._state(session_id)
                first_seq = int(state["seq"]) + 1
                plan = _ExecutionPlan(journal, state)
                prepared, output = [], []
                for raw in events:
                    check_cancelled()
                    row = plan.record(session_id, dict(raw))
                    storage = prepare_ui_event(row)
                    mapped = mirror._map_ui_event(session_id, storage)
                    if not mapped or mapped.get("_set_extension_latest"):
                        return None
                    plan.rows.append({"type": mapped["type"], "payload": mapped.get("payload") or {},
                                      "run_id": mapped.get("run_id") or row.get("run_id")})
                    plan.next_seq += 1
                    prepared.append(storage)
                    output.append(row)
            check_cancelled()
            if (_signature(path.stat()) != before or _signature(os.fstat(writer.fileno())) != before
                    or journal.log.next_seq(session_id, _event_path=path) != first_seq):
                raise RuntimeError("event source changed while preparing UI batch")
            with local_step("ui_batch_append"):
                committed = journal.log._append_many_unlocked(session_id, plan.rows)
            if [event.seq for event in committed] != list(range(first_seq, plan.next_seq)):
                raise RuntimeError("UI batch sequence differs from its prepared execution references")
            with local_step("ui_batch_project"):
                snapshot = mirror.snapshots.read_for_update(session_id)
                if (mirror.snapshots._projection_version_matches(snapshot)
                        and int(snapshot.get("last_seq") or 0) == committed[0].seq - 1):
                    for event in committed:
                        snapshot = mirror.projector.project_incremental(snapshot, event)
                else:
                    snapshot = mirror.snapshots.project_after_append(
                        session_id, snapshot, journal.log, mirror.projector, committed[-1].seq)
                mirror.snapshots.stamp_event_log(session_id, snapshot, path)
                mirror.snapshots.write_checkpointed(session_id, snapshot)
            with local_step("ui_batch_journal_refresh"):
                # Replay the committed suffix through the normal guarded cache
                # path. The private planner never replaces live journal state.
                journal._state(session_id)
            check_cancelled()
            for storage in prepared:
                manager._apply_appended_ui_event_side_effects(session_id, storage)
    return [{**event, "_runtime_v2_committed": True} for event in output]
