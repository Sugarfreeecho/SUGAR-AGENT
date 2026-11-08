from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Callable, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent, now_iso
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore
from .ui_projection import RuntimeUiProjection

logger = logging.getLogger(__name__)


class RuntimeV2LogCompactionError(RuntimeError):
    pass


class RuntimeV2LogCompactionService:
    """Explicit offline compaction for inactive, unbranched Runtime V2 logs."""

    def __init__(
        self,
        sessions_dir: str | Path,
        path_resolver: Optional[Callable[[str], str | Path]] = None,
    ) -> None:
        self.sessions_dir = Path(sessions_dir)
        self._path_resolver = path_resolver
        self.event_log = SessionEventLog(sessions_dir, path_resolver=path_resolver)
        self.snapshots = SnapshotStore(sessions_dir, path_resolver=path_resolver)
        self.projector = RuntimeProjector()
        self.ui_projection = RuntimeUiProjection(sessions_dir, path_resolver=path_resolver)

    def compact(
        self,
        session_id: str,
        *,
        keep_backup: bool = True,
        force: bool = False,
    ) -> dict:
        with self.event_log.session_transaction(session_id):
            path = self.event_log.event_path(session_id)
            if not path.exists():
                return {"compacted": False, "reason": "missing", "bytes_before": 0, "bytes_after": 0}
            events = self.event_log.read_all(session_id)
            if not events:
                return {"compacted": False, "reason": "empty", "bytes_before": 0, "bytes_after": 0}
            snapshot = self.projector.project(events)
            if not force:
                self._assert_offline_safe(session_id, events, snapshot)
            if not self.snapshots.wait_for_checkpoint(session_id, timeout_seconds=5.0):
                raise RuntimeV2LogCompactionError("snapshot checkpoint did not become idle")

            ui_events = self.ui_projection.read_ui_events(session_id)
            baseline = self._baseline_snapshot(snapshot)
            compacted = RuntimeEvent(
                seq=int(snapshot.get("last_seq") or events[-1].seq),
                type="runtime_snapshot_compacted",
                session_id=session_id,
                timestamp=now_iso(),
                payload={"snapshot": baseline, "ui_events": ui_events},
            )
            encoded = (
                json.dumps(compacted.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            before_size = int(path.stat().st_size)
            if len(encoded) >= before_size:
                return {
                    "compacted": False,
                    "reason": "no_savings",
                    "events_before": len(events),
                    "bytes_before": before_size,
                    "bytes_after": before_size,
                }
            tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.compact.tmp")
            backup = path.with_name(f"events.precompact.{int(events[-1].seq)}.jsonl.bak")
            try:
                with tmp.open("xb") as fh:
                    fh.write(encoded)
                    fh.flush()
                    os.fsync(fh.fileno())
                if keep_backup:
                    shutil.copy2(path, backup)
                os.replace(tmp, path)
                rebuilt = self.projector.project(self.event_log.read_all(session_id))
                if self._semantic_snapshot(rebuilt) != self._semantic_snapshot(snapshot):
                    if keep_backup and backup.exists():
                        os.replace(backup, path)
                    raise RuntimeV2LogCompactionError("compacted projection did not match source")
                self.event_log.seq_offset_index_path(session_id).unlink(missing_ok=True)
                self.event_log._update_seq_cache(session_id, int(compacted.seq))
                self.snapshots.stamp_event_log(session_id, rebuilt, path)
                self.snapshots.write(session_id, rebuilt)
                self.ui_projection.invalidate_cache(session_id)
                try:
                    self.ui_projection.seed_compacted_ui(session_id, ui_events, compacted.seq)
                except Exception:
                    # The facts are committed. A derivative can be rebuilt on
                    # demand without declaring the successful compaction failed.
                    logger.warning("compacted_ui_rows_seed_failed session=%s", session_id, exc_info=True)
                return {
                    "compacted": True,
                    "events_before": len(events),
                    "events_after": 1,
                    "bytes_before": before_size,
                    "bytes_after": int(path.stat().st_size),
                    "backup": str(backup) if keep_backup else "",
                }
            finally:
                tmp.unlink(missing_ok=True)

    def _assert_offline_safe(self, session_id: str, events: list[RuntimeEvent], snapshot: dict) -> None:
        if snapshot.get("active_runs"):
            raise RuntimeV2LogCompactionError("session has an active run")
        if snapshot.get("pending_interactions") or snapshot.get("pending_approvals"):
            raise RuntimeV2LogCompactionError("session has pending human interaction")
        # A *child* branch keeps a ``history_branch_created`` row describing
        # where it forked from. That row is what makes this session a branch,
        # not what makes it a branch source: compacting it only folds its own
        # history and leaves the parent untouched. Refusing here blocked every
        # forked conversation from ever being compacted.
        if self._is_referenced_by_branch(session_id):
            raise RuntimeV2LogCompactionError("session is referenced by a branch")

    # ------------------------------------------------------------------
    # Subagent logs
    # ------------------------------------------------------------------
    def subagent_roots(self, parent_session_id: str) -> list[Path]:
        """Return every subagent log root that belongs to one parent session."""
        parent_dir = Path(self.sessions_dir) / parent_session_id / "subagents"
        if not parent_dir.is_dir():
            return []
        return [child for child in sorted(parent_dir.iterdir()) if (child / "events.jsonl").is_file()]

    def compact_subagents(
        self,
        parent_session_id: str,
        *,
        keep_backup: bool = False,
        only_terminal: bool = True,
    ) -> list[dict]:
        """Compact finished subagent logs.

        Each subagent keeps its own event log under
        ``<parent>/subagents/<agent_id>/``.  They are never touched by the root
        session sweep, yet in one archived session they accounted for 76 MiB of
        events.  A finished subagent log is append-only history: its task is
        over, so the same offline compaction rules apply.
        """
        results: list[dict] = []
        for agent_dir in self.subagent_roots(parent_session_id):
            agent_id = agent_dir.name
            try:
                if only_terminal and not self._subagent_is_terminal(agent_dir):
                    results.append({
                        "session_id": f"{parent_session_id}/subagents/{agent_id}",
                        "compacted": False,
                        "reason": "active",
                    })
                    continue
                # A subagent log lives directly at ``<agent_dir>/events.jsonl``,
                # so the agent dir *is* the session dir: pass its parent as the
                # sessions root and the directory name as the session id.
                service = RuntimeV2LogCompactionService(
                    agent_dir.parent,
                    path_resolver=None,
                )
                result = service.compact(agent_id, keep_backup=keep_backup, force=False)
                results.append({"session_id": f"{parent_session_id}/subagents/{agent_id}", **result})
            except Exception as exc:  # keep one bad subagent from stopping the sweep
                logger.warning("subagent_compaction_failed parent=%s agent=%s", parent_session_id, agent_id, exc_info=True)
                results.append({
                    "session_id": f"{parent_session_id}/subagents/{agent_id}",
                    "compacted": False,
                    "error": str(exc),
                })
        return results

    @staticmethod
    def _subagent_is_terminal(agent_dir: Path) -> bool:
        """A subagent is compactable once its metadata reports a terminal state."""
        meta_path = agent_dir / "metadata.json"
        try:
            with meta_path.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            return False
        if not isinstance(meta, dict):
            return False
        status = str(
            meta.get("subagent_run_status") or meta.get("status") or ""
        ).strip().lower()
        if status not in {"finished", "failed", "interrupted", "completed", "cancelled", "stopped"}:
            return False
        # ``compact`` re-checks the projection for active runs; this is only a
        # cheap pre-filter so a live subagent is never even opened for rewrite.
        return bool(meta.get("subagent_run_finished_at") or meta.get("archived"))

    def prune_derived(self, session_id: str) -> dict:
        """Delete rebuildable side files of an idle session.

        ``execution_recovery.chk`` is a coalesced cache of the execution
        journal: it is rebuilt from ``events.jsonl`` on the next run, so an idle
        session does not need to keep it on disk. One archived session carried
        14 MiB there plus 22 MiB across its subagents.
        """
        removed: list[str] = []
        freed = 0
        session_dir = Path(self.sessions_dir) / session_id
        try:
            snapshot = self.snapshots.read(session_id)
        except Exception:
            snapshot = {}
        if snapshot.get("active_runs") or snapshot.get("pending_interactions") or snapshot.get("pending_approvals"):
            return {"pruned": [], "bytes_freed": 0, "skipped": "session is active"}
        targets = [session_dir / "snapshots" / "execution_recovery.chk"]
        sub_root = session_dir / "subagents"
        if sub_root.is_dir():
            targets.extend(sorted(sub_root.glob("*/snapshots/execution_recovery.chk")))
        for path in targets:
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
                path.unlink()
            except OSError:
                continue
            removed.append(str(path.relative_to(session_dir)))
            freed += size
        return {"pruned": removed, "bytes_freed": freed}

    def _is_referenced_by_branch(self, session_id: str) -> bool:
        target = str(session_id)
        return target in self._branch_sources()

    def _branch_sources(self) -> set[str]:
        """Every session id that some other session branched from.

        Built once per service instance. A full ``rglob`` per session made a
        batch sweep quadratic — 17 GiB of logs re-read once per session — and
        branch references can only come from a root session log, never from a
        subagent log.
        """
        cached = getattr(self, "_branch_source_cache", None)
        if cached is not None:
            return cached
        sources: set[str] = set()
        for event_path in self.sessions_dir.glob("*/events.jsonl"):
            try:
                if event_path.stat().st_size < 200:
                    continue
                with event_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        if "history_branch_created" not in line:
                            continue
                        try:
                            data = json.loads(line)
                        except ValueError:
                            continue
                        if data.get("type") != "history_branch_created":
                            continue
                        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
                        source = str(payload.get("source_session_id") or "").strip()
                        if source:
                            sources.add(source)
            except (OSError, TypeError):
                continue
        self._branch_source_cache = sources
        return sources

    @staticmethod
    def _baseline_snapshot(snapshot: dict) -> dict:
        baseline = copy.deepcopy(snapshot)
        baseline.pop("_event_log", None)
        baseline.pop("_projection", None)
        baseline["history_ops"] = [
            row for row in baseline.get("history_ops") or []
            if isinstance(row, dict)
            and row.get("type") not in {"model_history_replaced", "model_prefix_compacted"}
        ]
        return baseline

    @staticmethod
    def _semantic_snapshot(snapshot: dict) -> dict:
        value = copy.deepcopy(snapshot)
        value.pop("_event_log", None)
        value.pop("_projection", None)
        value.pop("updated_at", None)
        value.pop("history_ops", None)
        return value
