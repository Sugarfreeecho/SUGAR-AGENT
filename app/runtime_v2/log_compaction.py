from __future__ import annotations

import copy
import json
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
        if any(event.type == "history_branch_created" for event in events):
            raise RuntimeV2LogCompactionError("branched sessions are not compacted automatically")
        if self._is_referenced_by_branch(session_id):
            raise RuntimeV2LogCompactionError("session is referenced by a branch")

    def _is_referenced_by_branch(self, session_id: str) -> bool:
        target = str(session_id)
        for event_path in self.sessions_dir.rglob("events.jsonl"):
            if event_path == self.event_log.event_path(session_id):
                continue
            try:
                with event_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        if target not in line or "history_branch_created" not in line:
                            continue
                        data = json.loads(line)
                        if data.get("type") != "history_branch_created":
                            continue
                        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
                        if str(payload.get("source_session_id") or "") == target:
                            return True
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return False

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
