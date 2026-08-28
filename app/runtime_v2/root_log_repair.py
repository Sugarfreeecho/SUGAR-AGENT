from __future__ import annotations

import hashlib
import json
import os
import shutil
from copy import deepcopy
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore
from .ui_projection import RuntimeUiProjection


class RuntimeV2RootEventLogRepairService:
    """Explicit repair for historical malformed/conflicting root event logs.

    This service is deliberately absent from every normal open/send path.  It
    retains parseable facts in their physical JSONL order, drops only lines
    that cannot be parsed as a RuntimeEvent, and raises only colliding or
    backwards sequence values enough to restore strict monotonicity.  Published
    sequence references are translated only when their old target is unique;
    an ambiguous reference makes the whole operation refuse without writing.
    """

    MANIFEST_VERSION = 1
    MANIFEST_FILE = "runtime_v2_root_event_log_repair.json"
    _LOCAL_REFERENCE_FIELDS = {
        "message_deleted": ("target_seq",),
        "message_rewritten": ("target_seq",),
        "visible_range_changed": ("from_seq", "to_seq", "target_seq"),
        "model_window_changed": ("from_seq", "to_seq"),
        "history_compacted": ("compacted_before_seq",),
        "context_summary_committed": ("source_seq",),
        "context_summary_started": ("source_seq",),
        "context_summary_finished": ("source_seq",),
    }
    _LOCAL_NESTED_REFERENCE_PATHS = {
        "visible_range_changed": (
            ("restore_context_summary", "source_seq"),
            ("restore_context_summary", "changed_at_seq"),
            ("restore_history_compaction", "compacted_before_seq"),
            ("restore_history_compaction", "changed_at_seq"),
            ("restore_context_tokens", "seq"),
            ("restore_context_tokens", "stale_at_seq"),
        ),
    }

    def __init__(
        self,
        sessions_dir: str | Path,
        *,
        path_resolver: Optional[Callable[[str], str | Path]] = None,
    ) -> None:
        self.sessions_dir = Path(sessions_dir).resolve()
        self.path_resolver = path_resolver
        self.event_log = SessionEventLog(self.sessions_dir, path_resolver=path_resolver)
        self.snapshots = SnapshotStore(self.sessions_dir, path_resolver=path_resolver)
        self.projector = RuntimeProjector()

    def inspect(self, session_id: str) -> dict:
        sid = self.event_log._validate_session_id(session_id)
        path = self.event_log.event_path(sid)
        events, malformed = self._read_source(path, sid)
        sequences = [int(event.seq) for _line, event in events]
        counts = Counter(sequences)
        duplicate_sequences = sum(count - 1 for count in counts.values())
        non_monotonic = sum(
            1 for index in range(1, len(sequences))
            if sequences[index] <= sequences[index - 1]
        )
        conflicts: list[str] = []
        if not path.is_file():
            conflicts.append("events.jsonl is missing")
        invalid_sessions = sorted({event.session_id for _line, event in events if event.session_id != sid})
        if invalid_sessions:
            conflicts.append(f"event session_id mismatch:{','.join(invalid_sessions)}")
        invalid_sequences = [event.seq for _line, event in events if int(event.seq) <= 0]
        if invalid_sequences:
            conflicts.append("non-positive event seq is not repairable")
        mapping = self._stable_sequence_mapping(events)
        conflicts.extend(self._reference_conflicts(events, mapping))
        if malformed or duplicate_sequences or non_monotonic:
            conflicts.extend(self._external_reference_conflicts(sid, mapping))
        return {
            "ok": not conflicts,
            "session_id": sid,
            "event_path": str(path),
            "source_sha256": self._file_sha256(path),
            "valid_events": len(events),
            "malformed_lines": len(malformed),
            "malformed_line_numbers": [row["line"] for row in malformed],
            "malformed_line_sha256": [row["sha256"] for row in malformed],
            "duplicate_sequences": duplicate_sequences,
            "duplicate_sequence_values": sorted(seq for seq, count in counts.items() if count > 1),
            "non_monotonic_sequences": non_monotonic,
            "resequence_required": bool(duplicate_sequences or non_monotonic),
            "repair_required": bool(malformed or duplicate_sequences or non_monotonic),
            "first_changed_line": next(
                (line for line, _old, new in mapping if _old != new),
                None,
            ),
            "last_repaired_seq": mapping[-1][2] if mapping else 0,
            "conflicts": conflicts,
        }

    def repair(self, session_id: str, *, apply: bool = False) -> dict:
        sid = self.event_log._validate_session_id(session_id)
        if not apply:
            inspection = self.inspect(sid)
            if inspection["conflicts"]:
                return {**inspection, "action": "refused", "applied": False, "verified": False}
            if not inspection["repair_required"]:
                return {**inspection, "action": "clean", "applied": False, "verified": True}
            path = self.event_log.event_path(sid)
            source_events, _malformed = self._read_source(path, sid)
            repaired_events, sequence_map = self._build_repaired_events(source_events)
            before_ui = self._semantic_ui(source_events)
            before_model = self._semantic_model(source_events)
            semantic_projection_verified = (
                self._semantic_ui([(index + 1, event) for index, event in enumerate(repaired_events)]) == before_ui
                and self._semantic_model([(index + 1, event) for index, event in enumerate(repaired_events)]) == before_model
            )
            if not semantic_projection_verified:
                return {
                    **inspection,
                    "action": "refused",
                    "applied": False,
                    "verified": False,
                    "conflicts": ["stable resequence changes UI or model projection"],
                }
            return {
                **inspection,
                "action": "dry_run",
                "applied": False,
                "verified": False,
                "semantic_projection_verified": True,
                "repaired_sha256": self._bytes_sha256(self._encode_events(repaired_events)),
                "sequence_changes": sum(1 for row in sequence_map if row["old_seq"] != row["new_seq"]),
            }
        with self.event_log.session_transaction(sid):
            inspection = self.inspect(sid)
            if inspection["conflicts"]:
                return {**inspection, "action": "refused", "applied": False, "verified": False}
            if not inspection["repair_required"]:
                return {**inspection, "action": "clean", "applied": False, "verified": True}

            path = self.event_log.event_path(sid)
            source_bytes = path.read_bytes()
            source_hash = self._bytes_sha256(source_bytes)
            if source_hash != inspection["source_sha256"]:
                return {
                    **inspection,
                    "action": "refused",
                    "applied": False,
                    "verified": False,
                    "conflicts": ["events.jsonl changed during inspection"],
                }
            source_events, malformed = self._read_source(path, sid)
            repaired_events, sequence_map = self._build_repaired_events(source_events)
            repaired_bytes = self._encode_events(repaired_events)
            repaired_hash = self._bytes_sha256(repaired_bytes)
            before_ui = self._semantic_ui(source_events)
            before_model = self._semantic_model(source_events)
            if (
                self._semantic_ui([(index + 1, event) for index, event in enumerate(repaired_events)]) != before_ui
                or self._semantic_model([(index + 1, event) for index, event in enumerate(repaired_events)]) != before_model
            ):
                return {
                    **inspection,
                    "action": "refused",
                    "applied": False,
                    "verified": False,
                    "conflicts": ["stable resequence changes UI or model projection"],
                }
            backup_dir = self._new_backup_dir(sid, source_hash)
            snapshot_path = self.snapshots.path(sid)
            index_path = self.event_log.session_dir(sid) / "snapshots" / "ui_projection_index.json"
            self._backup_file(path, backup_dir / "events.jsonl")
            self._backup_optional(snapshot_path, backup_dir / "latest.json")
            self._backup_optional(index_path, backup_dir / "ui_projection_index.json")
            manifest_path = backup_dir / self.MANIFEST_FILE
            manifest = {
                "manifest_version": self.MANIFEST_VERSION,
                "operation": "runtime_v2_root_event_log_repair",
                "status": "pending",
                "session_id": sid,
                "created_at": self._now_iso(),
                "source_sha256": source_hash,
                "repaired_sha256": repaired_hash,
                "source_size": len(source_bytes),
                "repaired_size": len(repaired_bytes),
                "valid_events": len(source_events),
                "malformed_lines": [dict(row) for row in malformed],
                "sequence_map": sequence_map,
                "snapshot_existed": snapshot_path.is_file(),
                "ui_index_existed": index_path.is_file(),
            }
            self._write_json_atomic(manifest_path, manifest)

            try:
                if self._file_sha256(path) != source_hash:
                    raise RuntimeError("events.jsonl changed before commit")
                self._write_bytes_atomic(path, repaired_bytes)
                snapshot = self.projector.project(repaired_events)
                self.snapshots.stamp_event_log(sid, snapshot, path)
                self.snapshots.write(sid, snapshot)
                index_path.unlink(missing_ok=True)
                self._verify_repaired_state(
                    sid,
                    repaired_events,
                    repaired_hash,
                    before_ui,
                    before_model,
                )
                manifest["status"] = "complete"
                manifest["completed_at"] = self._now_iso()
                manifest["snapshot_last_seq"] = int(snapshot.get("last_seq") or 0)
                self._write_json_atomic(manifest_path, manifest)
                self._invalidate_seq_cache(sid)
                RuntimeUiProjection(self.sessions_dir, path_resolver=self.path_resolver).invalidate_cache(sid)
                return {
                    **inspection,
                    "action": "repaired",
                    "applied": True,
                    "verified": True,
                    "manifest_path": str(manifest_path),
                    "backup_dir": str(backup_dir),
                    "repaired_sha256": repaired_hash,
                    "sequence_changes": sum(1 for row in sequence_map if row["old_seq"] != row["new_seq"]),
                }
            except Exception as exc:
                rollback_error = ""
                try:
                    self._restore_file(backup_dir / "events.jsonl", path, existed=True)
                    self._restore_file(
                        backup_dir / "latest.json",
                        snapshot_path,
                        existed=bool(manifest["snapshot_existed"]),
                    )
                    self._restore_file(
                        backup_dir / "ui_projection_index.json",
                        index_path,
                        existed=bool(manifest["ui_index_existed"]),
                    )
                    if self._file_sha256(path) != source_hash:
                        raise RuntimeError("event log rollback hash mismatch")
                except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O failure
                    rollback_error = f"{type(rollback_exc).__name__}: {rollback_exc}"
                manifest["status"] = "rollback_failed" if rollback_error else "rolled_back"
                manifest["failed_at"] = self._now_iso()
                manifest["error"] = f"{type(exc).__name__}: {exc}"
                if rollback_error:
                    manifest["rollback_error"] = rollback_error
                self._write_json_atomic(manifest_path, manifest)
                self._invalidate_seq_cache(sid)
                return {
                    **inspection,
                    "action": "rollback_failed" if rollback_error else "rolled_back",
                    "applied": False,
                    "verified": False,
                    "manifest_path": str(manifest_path),
                    "backup_dir": str(backup_dir),
                    "repaired_sha256": repaired_hash,
                    "error": manifest["error"],
                    "rollback_error": rollback_error,
                }

    def _build_repaired_events(
        self,
        source_events: list[tuple[int, RuntimeEvent]],
    ) -> tuple[list[RuntimeEvent], list[dict]]:
        raw_mapping = self._stable_sequence_mapping(source_events)
        old_to_new: dict[int, list[int]] = defaultdict(list)
        for _line, old_seq, new_seq in raw_mapping:
            old_to_new[old_seq].append(new_seq)
        repaired: list[RuntimeEvent] = []
        mapping_rows: list[dict] = []
        for (line, event), (_map_line, old_seq, new_seq) in zip(source_events, raw_mapping):
            payload = deepcopy(dict(event.payload or {}))
            for container, field, label in self._reference_slots(event.type, payload, event.session_id):
                value = container.get(field)
                if value is None:
                    continue
                try:
                    target = int(value)
                except (TypeError, ValueError):
                    raise ValueError(f"invalid {event.type}.{label} reference")
                if target <= 0:
                    continue
                targets = old_to_new.get(target) or []
                if len(targets) != 1:
                    raise ValueError(f"ambiguous {event.type}.{label} reference to old seq {target}")
                container[field] = targets[0]
            repaired.append(RuntimeEvent(
                seq=new_seq,
                type=event.type,
                session_id=event.session_id,
                timestamp=event.timestamp,
                run_id=event.run_id,
                payload=payload,
            ))
            mapping_rows.append({"line": line, "old_seq": old_seq, "new_seq": new_seq})
        return repaired, mapping_rows

    @staticmethod
    def _stable_sequence_mapping(events: list[tuple[int, RuntimeEvent]]) -> list[tuple[int, int, int]]:
        previous = 0
        mapping: list[tuple[int, int, int]] = []
        for line, event in events:
            old_seq = int(event.seq)
            new_seq = old_seq if old_seq > previous else previous + 1
            mapping.append((line, old_seq, new_seq))
            previous = new_seq
        return mapping

    def _reference_conflicts(
        self,
        events: list[tuple[int, RuntimeEvent]],
        mapping: list[tuple[int, int, int]],
    ) -> list[str]:
        old_to_new: dict[int, list[int]] = defaultdict(list)
        for _line, old_seq, new_seq in mapping:
            old_to_new[old_seq].append(new_seq)
        conflicts: list[str] = []
        for line, event in events:
            for container, field, label in self._reference_slots(event.type, event.payload, event.session_id):
                if container.get(field) is None:
                    continue
                try:
                    target = int(container[field])
                except (TypeError, ValueError):
                    conflicts.append(f"line {line} has invalid {event.type}.{label} reference")
                    continue
                if target > 0 and len(old_to_new.get(target) or []) != 1:
                    conflicts.append(
                        f"line {line} has ambiguous {event.type}.{label} reference to old seq {target}"
                    )
        return conflicts

    @classmethod
    def _reference_slots(cls, event_type: str, payload: dict, session_id: str):
        for field in cls._LOCAL_REFERENCE_FIELDS.get(event_type, ()):
            yield payload, field, field
        for parent_key, field in cls._LOCAL_NESTED_REFERENCE_PATHS.get(event_type, ()):
            parent = payload.get(parent_key)
            if isinstance(parent, dict):
                yield parent, field, f"{parent_key}.{field}"
        if (
            event_type == "history_branch_created"
            and str(payload.get("source_session_id") or "") == session_id
        ):
            yield payload, "branch_from_seq", "branch_from_seq"
        if str(payload.get("branch_source_session_id") or "") == session_id:
            yield payload, "branch_source_runtime_seq", "branch_source_runtime_seq"
        if str(payload.get("inherited_from_session_id") or "") == session_id:
            yield payload, "inherited_from_runtime_seq", "inherited_from_runtime_seq"

    def _external_reference_conflicts(
        self,
        session_id: str,
        mapping: list[tuple[int, int, int]],
    ) -> list[str]:
        old_to_new: dict[int, list[int]] = defaultdict(list)
        for _line, old_seq, new_seq in mapping:
            old_to_new[old_seq].append(new_seq)
        conflicts: set[str] = set()
        if not self.sessions_dir.is_dir():
            return []
        for directory in self.sessions_dir.iterdir():
            if not directory.is_dir() or directory.resolve() == self.event_log.session_dir(session_id).resolve():
                continue
            path = directory / "events.jsonl"
            if not path.is_file():
                continue
            with path.open("rb") as fh:
                for line_number, raw in enumerate(fh, 1):
                    try:
                        row = json.loads(raw.decode("utf-8"))
                    except Exception:
                        continue
                    if not isinstance(row, dict) or not isinstance(row.get("payload"), dict):
                        continue
                    event_type = str(row.get("type") or "")
                    payload = row["payload"]
                    references: list[tuple[str, Any]] = []
                    if (
                        event_type == "history_branch_created"
                        and str(payload.get("source_session_id") or "") == session_id
                    ):
                        references.append(("branch_from_seq", payload.get("branch_from_seq")))
                    if str(payload.get("branch_source_session_id") or "") == session_id:
                        references.append(("branch_source_runtime_seq", payload.get("branch_source_runtime_seq")))
                    if str(payload.get("inherited_from_session_id") or "") == session_id:
                        references.append(("inherited_from_runtime_seq", payload.get("inherited_from_runtime_seq")))
                    for field, raw_target in references:
                        try:
                            target = int(raw_target)
                        except (TypeError, ValueError):
                            conflicts.add(
                                f"external {directory.name}:{line_number} has invalid {field} reference"
                            )
                            continue
                        targets = old_to_new.get(target) or []
                        if len(targets) != 1 or targets[0] != target:
                            conflicts.add(
                                f"external {directory.name}:{line_number} {field} would become stale"
                            )
        return sorted(conflicts)

    def _verify_repaired_state(
        self,
        session_id: str,
        expected_events: list[RuntimeEvent],
        repaired_hash: str,
        before_ui: list[dict],
        before_model: list[dict],
    ) -> None:
        path = self.event_log.event_path(session_id)
        if self._file_sha256(path) != repaired_hash:
            raise RuntimeError("repaired event log hash mismatch")
        actual = self.event_log.read_all(session_id)
        if [event.to_dict() for event in actual] != [event.to_dict() for event in expected_events]:
            raise RuntimeError("repaired event log content mismatch")
        sequences = [event.seq for event in actual]
        if any(sequences[index] <= sequences[index - 1] for index in range(1, len(sequences))):
            raise RuntimeError("repaired event sequence is not strictly monotonic")
        if self._semantic_ui([(index + 1, event) for index, event in enumerate(actual)]) != before_ui:
            raise RuntimeError("UI projection changed during root event-log repair")
        if self._semantic_model([(index + 1, event) for index, event in enumerate(actual)]) != before_model:
            raise RuntimeError("model projection changed during root event-log repair")
        expected_snapshot = self.projector.project(actual)
        snapshot = self.snapshots.read(session_id)
        snapshot.pop("_event_log", None)
        snapshot.pop("_projection", None)
        expected_snapshot.pop("_event_log", None)
        expected_snapshot.pop("_projection", None)
        if snapshot != expected_snapshot:
            raise RuntimeError("snapshot rebuild verification failed")

    @staticmethod
    def _semantic_ui(events: list[tuple[int, RuntimeEvent]]) -> list[dict]:
        rows = RuntimeUiProjection.events_to_ui(event for _line, event in events)
        return [
            {key: value for key, value in row.items() if key not in {"runtime_seq", "rewritten_by_seq"}}
            for row in rows
        ]

    def _semantic_model(self, events: list[tuple[int, RuntimeEvent]]) -> list[dict]:
        rows = list(self.projector.project(event for _line, event in events).get("raw_model_messages") or [])
        return [
            {
                key: value
                for key, value in row.items()
                if key not in {"seq", "replaced_by_seq", "rewritten_by_seq"}
            }
            for row in rows
            if isinstance(row, dict)
        ]

    @staticmethod
    def _read_source(path: Path, session_id: str) -> tuple[list[tuple[int, RuntimeEvent]], list[dict]]:
        events: list[tuple[int, RuntimeEvent]] = []
        malformed: list[dict] = []
        if not path.is_file():
            return events, malformed
        with path.open("rb") as fh:
            for line_number, raw in enumerate(fh, 1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped.decode("utf-8"))
                    event = RuntimeEvent.from_dict(row)
                    events.append((line_number, event))
                except Exception as exc:
                    malformed.append({
                        "line": line_number,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size": len(raw),
                        "error": f"{type(exc).__name__}: {exc}",
                    })
        return events, malformed

    def _new_backup_dir(self, session_id: str, source_hash: str) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        path = (
            self.event_log.session_dir(session_id)
            / ".runtime_v2_repair_backups"
            / "root_event_logs"
            / f"{stamp}_{source_hash[:12]}"
        )
        path.mkdir(parents=True, exist_ok=False)
        return path

    def _invalidate_seq_cache(self, session_id: str) -> None:
        with SessionEventLog._seq_cache_guard:
            SessionEventLog._seq_cache.pop(self.event_log._cache_scope_for(session_id), None)

    @staticmethod
    def _encode_events(events: list[RuntimeEvent]) -> bytes:
        return "".join(
            json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
            for event in events
        ).encode("utf-8")

    @classmethod
    def _backup_file(cls, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if cls._file_sha256(source) != cls._file_sha256(target):
            raise RuntimeError(f"backup verification failed:{source.name}")

    @classmethod
    def _backup_optional(cls, source: Path, target: Path) -> None:
        if source.is_file():
            cls._backup_file(source, target)

    @classmethod
    def _restore_file(cls, backup: Path, target: Path, *, existed: bool) -> None:
        if existed:
            if not backup.is_file():
                raise RuntimeError(f"missing rollback backup:{backup.name}")
            cls._write_bytes_atomic(target, backup.read_bytes())
            return
        target.unlink(missing_ok=True)

    @staticmethod
    def _write_bytes_atomic(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".repair.tmp")
        with tmp.open("wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    @staticmethod
    def _write_json_atomic(path: Path, data: dict) -> None:
        encoded = (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        RuntimeV2RootEventLogRepairService._write_bytes_atomic(path, encoded)

    @staticmethod
    def _bytes_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _file_sha256(path: Path) -> str:
        if not path.is_file():
            return hashlib.sha256(b"").hexdigest()
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
