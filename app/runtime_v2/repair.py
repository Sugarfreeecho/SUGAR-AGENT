from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore
from .ui_projection import RuntimeUiProjection


class RuntimeV2SubagentRepairService:
    """Explicit, append-only repair for historical nested-subagent split logs.

    Affected builds wrote UI facts below ``parent/subagents/child`` and model
    facts below ``sessions/child``. Repair never renumbers a published
    canonical event. It accepts only the known complementary model-fact shape,
    appends missing facts with their original timestamp/payload, rebuilds the
    snapshot, verifies that UI projection is unchanged, then archives the
    top-level ghost with a crash-resumable manifest.
    """

    MANIFEST_VERSION = 2
    MANIFEST_FILE = "runtime_v2_subagent_repair.json"
    MODEL_FACT_TYPES = frozenset({
        "model_user",
        "model_assistant",
        "model_tool",
        "model_system",
    })

    def __init__(
        self,
        sessions_dir: str | Path,
        *,
        path_resolver: Callable[[str], str | Path],
    ) -> None:
        self.sessions_dir = Path(sessions_dir).resolve()
        self.path_resolver = path_resolver
        self.projector = RuntimeProjector()

    def inspect(self, parent_session_id: str, child_session_id: str) -> dict:
        parent_id = str(parent_session_id or "").strip()
        child_id = str(child_session_id or "").strip()
        canonical_dir, ghost_dir = self._paths(parent_id, child_id)
        canonical_events, canonical_bad = self._read_events(canonical_dir, child_id)
        ghost_events, ghost_bad = self._read_events(ghost_dir, child_id)
        canonical_path = canonical_dir / "events.jsonl"
        ghost_path = ghost_dir / "events.jsonl"
        canonical_model_types = Counter(
            event.type for event in canonical_events if event.type in self.MODEL_FACT_TYPES
        )
        ghost_unknown_types = Counter(
            event.type for event in ghost_events if event.type not in self.MODEL_FACT_TYPES
        )
        canonical_active = len(self.projector.project(canonical_events).get("active_runs") or [])
        ghost_active = len(self.projector.project(ghost_events).get("active_runs") or [])
        return {
            "ok": True,
            "parent_session_id": parent_id,
            "child_session_id": child_id,
            "split_brain": bool(
                canonical_dir != ghost_dir
                and canonical_path.is_file()
                and ghost_path.is_file()
            ),
            "canonical_dir": str(canonical_dir),
            "ghost_dir": str(ghost_dir),
            "canonical_event_count": len(canonical_events),
            "ghost_event_count": len(ghost_events),
            "canonical_event_types": dict(Counter(event.type for event in canonical_events)),
            "ghost_event_types": dict(Counter(event.type for event in ghost_events)),
            "canonical_model_types": dict(canonical_model_types),
            "ghost_unknown_types": dict(ghost_unknown_types),
            "canonical_malformed_lines": canonical_bad,
            "ghost_malformed_lines": ghost_bad,
            "canonical_active_runs": canonical_active,
            "ghost_active_runs": ghost_active,
            "canonical_sha256": self._file_sha256(canonical_path),
            "ghost_sha256": self._file_sha256(ghost_path),
        }

    def repair(
        self,
        parent_session_id: str,
        child_session_id: str,
        *,
        apply: bool = False,
        archive_ghost: bool = True,
        legacy_model_messages: Optional[list[dict]] = None,
    ) -> dict:
        # Kept in the signature so older callers fail safely: legacy is never
        # used by this V2-to-V2 repair. Migration remains a separate service.
        if legacy_model_messages is not None:
            raise ValueError("legacy model recovery belongs to explicit migration, not V2 repair")
        inspection = self.inspect(parent_session_id, child_session_id)
        if not inspection["split_brain"]:
            return {**inspection, "applied": False, "action": "no_split_brain"}
        conflicts = self._conflicts(inspection)
        canonical_dir = Path(inspection["canonical_dir"])
        ghost_dir = Path(inspection["ghost_dir"])
        child_id = inspection["child_session_id"]
        canonical_events, _ = self._read_events(canonical_dir, child_id)
        ghost_events, _ = self._read_events(ghost_dir, child_id)
        plan, plan_stats = self._plan_import(child_id, canonical_events, ghost_events)
        blob_audit = self._audit_blob_refs(
            ghost_events,
            ghost_dir,
            canonical_dir,
            copy_files=False,
        )
        conflicts.extend(blob_audit["errors"])
        result = {
            **inspection,
            **plan_stats,
            "ok": not conflicts,
            "blob_refs": blob_audit,
            "conflicts": conflicts,
            "applied": False,
            "action": "refused" if conflicts else "dry_run",
        }
        if conflicts or not apply:
            return result

        canonical_log = SessionEventLog(
            self.sessions_dir,
            path_resolver=self.path_resolver,
        )
        ghost_log = SessionEventLog(self.sessions_dir)
        manifest_path = canonical_dir / self.MANIFEST_FILE
        backup_dir: Optional[Path] = None
        committed_events: list[RuntimeEvent] = []
        final_stats = dict(plan_stats)
        with canonical_log.session_transaction(child_id):
            with ghost_log.session_transaction(child_id):
                locked_canonical = canonical_log.read_all(child_id)
                locked_ghost, locked_bad = self._read_events(ghost_dir, child_id)
                locked_inspection = {
                    **inspection,
                    "canonical_malformed_lines": [],
                    "ghost_malformed_lines": locked_bad,
                    "canonical_active_runs": len(
                        self.projector.project(locked_canonical).get("active_runs") or []
                    ),
                    "ghost_active_runs": len(
                        self.projector.project(locked_ghost).get("active_runs") or []
                    ),
                    "canonical_model_types": dict(Counter(
                        event.type
                        for event in locked_canonical
                        if event.type in self.MODEL_FACT_TYPES
                    )),
                    "ghost_unknown_types": dict(Counter(
                        event.type
                        for event in locked_ghost
                        if event.type not in self.MODEL_FACT_TYPES
                    )),
                }
                locked_conflicts = self._conflicts(locked_inspection)
                locked_blob_audit = self._audit_blob_refs(
                    locked_ghost,
                    ghost_dir,
                    canonical_dir,
                    copy_files=False,
                )
                locked_conflicts.extend(locked_blob_audit["errors"])
                if locked_conflicts:
                    return {
                        **result,
                        "ok": False,
                        "conflicts": locked_conflicts,
                        "action": "refused_after_lock",
                    }

                locked_plan, final_stats = self._plan_import(
                    child_id,
                    locked_canonical,
                    locked_ghost,
                )
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                backup_dir = (
                    self.sessions_dir
                    / ".runtime_v2_repair_backups"
                    / child_id
                    / stamp
                )
                backup_dir.mkdir(parents=True, exist_ok=False)
                canonical_event_path = canonical_dir / "events.jsonl"
                ghost_event_path = ghost_dir / "events.jsonl"
                shutil.copy2(canonical_event_path, backup_dir / "canonical.events.jsonl")
                shutil.copy2(ghost_event_path, backup_dir / "ghost.events.jsonl")
                canonical_snapshot = canonical_dir / "snapshots" / "latest.json"
                ghost_snapshot = ghost_dir / "snapshots" / "latest.json"
                if canonical_snapshot.is_file():
                    shutil.copy2(canonical_snapshot, backup_dir / "canonical.latest.json")
                if ghost_snapshot.is_file():
                    shutil.copy2(ghost_snapshot, backup_dir / "ghost.latest.json")

                pending_manifest = {
                    "manifest_version": self.MANIFEST_VERSION,
                    "status": "pending",
                    "operation": "runtime_v2_subagent_split_brain_repair",
                    "created_at": datetime.now(timezone.utc).isoformat(
                        timespec="milliseconds"
                    ).replace("+00:00", "Z"),
                    "parent_session_id": inspection["parent_session_id"],
                    "child_session_id": child_id,
                    "canonical_sha256_before": self._file_sha256(canonical_event_path),
                    "ghost_sha256": self._file_sha256(ghost_event_path),
                    "backup_dir": str(backup_dir),
                    **final_stats,
                }
                self._write_json_atomic(manifest_path, pending_manifest)

                ui_before = self._project_ui_from_events(child_id, locked_canonical)
                copied_blob_audit = self._audit_blob_refs(
                    locked_ghost,
                    ghost_dir,
                    canonical_dir,
                    copy_files=True,
                )
                if copied_blob_audit["errors"]:
                    raise RuntimeError("blob copy verification failed: " + "; ".join(copied_blob_audit["errors"]))

                committed_events = self._append_imported_unlocked(
                    canonical_log,
                    child_id,
                    locked_plan,
                )
                all_events = canonical_log.read_all(child_id)
                snapshot = self.projector.project(all_events)
                snapshots = SnapshotStore(
                    self.sessions_dir,
                    path_resolver=self.path_resolver,
                )
                snapshots.stamp_event_log(child_id, snapshot, canonical_event_path)
                snapshots.write(child_id, snapshot)

                ui_after = self._project_ui_from_events(child_id, all_events)
                if self._ui_hash(ui_before) != self._ui_hash(ui_after):
                    shutil.copy2(backup_dir / "canonical.events.jsonl", canonical_event_path)
                    restored_events = canonical_log.read_all(child_id)
                    restored_snapshot = self.projector.project(restored_events)
                    snapshots.stamp_event_log(child_id, restored_snapshot, canonical_event_path)
                    snapshots.write(child_id, restored_snapshot)
                    canonical_log._update_seq_cache(
                        child_id,
                        max((event.seq for event in restored_events), default=0),
                    )
                    failed_manifest = {
                        **pending_manifest,
                        "status": "rolled_back",
                        "error": "UI projection changed during model-only repair",
                    }
                    self._write_json_atomic(manifest_path, failed_manifest)
                    raise RuntimeError("UI projection changed during model-only repair")

                committed_manifest = {
                    **pending_manifest,
                    "status": "committed_pending_archive",
                    "completed_at": datetime.now(timezone.utc).isoformat(
                        timespec="milliseconds"
                    ).replace("+00:00", "Z"),
                    "canonical_sha256_after": self._file_sha256(canonical_event_path),
                    "appended_event_count": len(committed_events),
                    "blob_refs": copied_blob_audit,
                    "ui_sha256_before": self._ui_hash(ui_before),
                    "ui_sha256_after": self._ui_hash(ui_after),
                    "model_message_count_after": len(snapshot.get("model_messages") or []),
                }
                self._write_json_atomic(manifest_path, committed_manifest)

        RuntimeUiProjection(
            self.sessions_dir,
            path_resolver=self.path_resolver,
        ).invalidate_cache(child_id)

        archive_path = ""
        archive_error = ""
        if archive_ghost and ghost_dir.is_dir() and backup_dir is not None:
            target = backup_dir / "ghost_session"
            try:
                shutil.move(str(ghost_dir), str(target))
                archive_path = str(target)
            except Exception as exc:
                archive_error = str(exc)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update({
            "status": "complete" if not archive_error else "committed_pending_archive",
            "ghost_archive_path": archive_path,
            "ghost_archive_error": archive_error,
        })
        self._write_json_atomic(manifest_path, manifest)
        return {
            **result,
            **final_stats,
            "ok": not bool(archive_error),
            "conflicts": [],
            "applied": True,
            "action": "repaired" if not archive_error else "committed_pending_archive",
            "appended_event_count": len(committed_events),
            "backup_dir": str(backup_dir or ""),
            "ghost_archive_path": archive_path,
            "ghost_archive_error": archive_error,
            "manifest_path": str(manifest_path),
        }

    def _paths(self, parent_id: str, child_id: str) -> tuple[Path, Path]:
        if not parent_id or not child_id:
            raise ValueError("parent_session_id and child_session_id are required")
        parent_dir = Path(self.path_resolver(parent_id)).resolve()
        canonical = Path(self.path_resolver(child_id)).resolve()
        expected = (parent_dir / "subagents" / child_id).resolve()
        ghost = (self.sessions_dir / child_id).resolve()
        for path in (parent_dir, canonical, expected, ghost):
            path.relative_to(self.sessions_dir)
        if canonical != expected:
            raise ValueError("child path does not match the supplied parent relationship")
        return canonical, ghost

    @staticmethod
    def _read_events(session_dir: Path, child_id: str) -> tuple[list[RuntimeEvent], list[dict]]:
        path = session_dir / "events.jsonl"
        if not path.is_file():
            return [], []
        events: list[RuntimeEvent] = []
        malformed: list[dict] = []
        with path.open("rb") as fh:
            for line_number, raw in enumerate(fh, start=1):
                if not raw.strip():
                    continue
                try:
                    data = json.loads(raw.decode("utf-8"))
                    event = RuntimeEvent.from_dict(data)
                except Exception as exc:
                    malformed.append({
                        "line": line_number,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "error": str(exc),
                    })
                    continue
                if event.session_id != child_id:
                    malformed.append({
                        "line": line_number,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "error": "event session_id does not match child",
                    })
                    continue
                events.append(event)
        return events, malformed

    def _conflicts(self, inspection: dict) -> list[str]:
        conflicts: list[str] = []
        if inspection.get("canonical_malformed_lines"):
            conflicts.append("canonical event log contains malformed physical lines")
        if inspection.get("ghost_malformed_lines"):
            conflicts.append("ghost event log contains malformed physical lines")
        if inspection.get("canonical_active_runs") or inspection.get("ghost_active_runs"):
            conflicts.append("canonical or ghost snapshot contains an active run")
        if inspection.get("ghost_unknown_types"):
            conflicts.append(
                "ghost contains non-model facts: "
                + ",".join(sorted(inspection["ghost_unknown_types"]))
            )
        # A pending/previous repair may already have appended these exact model
        # facts. _plan_import can resume idempotently; unrelated canonical model
        # facts are rejected because append order would be ambiguous.
        canonical_model_types = inspection.get("canonical_model_types") or {}
        manifest_path = Path(inspection["canonical_dir"]) / self.MANIFEST_FILE
        pending = {}
        try:
            pending = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pending = {}
        if canonical_model_types and str(pending.get("status") or "") not in {
            "pending",
            "committed_pending_archive",
            "complete",
        }:
            conflicts.append("canonical already contains unrelated model facts")
        return conflicts

    def _plan_import(
        self,
        child_id: str,
        canonical_events: list[RuntimeEvent],
        ghost_events: list[RuntimeEvent],
    ) -> tuple[list[RuntimeEvent], dict]:
        canonical_fingerprints = {
            self._fact_fingerprint(event) for event in canonical_events
        }
        model_user_counts = Counter(
            str((event.payload or {}).get("content") or "")
            for event in ghost_events
            if event.type == "model_user"
        )
        synthetic: list[RuntimeEvent] = []
        synthetic_index = 0
        for ui_event in canonical_events:
            content = self._ui_user_content(ui_event)
            if content is None:
                continue
            if model_user_counts[content] > 0:
                model_user_counts[content] -= 1
                continue
            synthetic_index += 1
            synthetic.append(RuntimeEvent(
                seq=synthetic_index,
                type="model_user",
                session_id=child_id,
                timestamp=ui_event.timestamp,
                run_id=ui_event.run_id,
                payload={
                    "role": "user",
                    "content": content,
                    "repair_source": "canonical_ui_user",
                    "repair_source_seq": int(ui_event.seq),
                },
            ))

        candidates = [("synthetic", event) for event in synthetic]
        candidates.extend(("ghost", event) for event in ghost_events)
        candidates.sort(key=lambda item: (
            str(item[1].timestamp or ""),
            0 if item[0] == "synthetic" else 1,
            int(item[1].seq),
        ))
        planned: list[RuntimeEvent] = []
        skipped = 0
        for _source, event in candidates:
            if self._fact_fingerprint(event) in canonical_fingerprints:
                skipped += 1
                continue
            planned.append(event)
        return planned, {
            "planned_append_count": len(planned),
            "ghost_model_fact_count": len(ghost_events),
            "synthesized_model_user_events": len(synthetic),
            "already_imported_events": skipped,
        }

    @staticmethod
    def _ui_user_content(event: RuntimeEvent) -> Optional[str]:
        payload = dict(event.payload or {})
        if event.type == "message_user":
            return str(payload.get("content") or "")
        if event.type in {"ui_event", "legacy_ui_event"} and str(payload.get("type") or "") == "user":
            return str(payload.get("content") or "")
        return None

    def _append_imported_unlocked(
        self,
        event_log: SessionEventLog,
        child_id: str,
        planned: list[RuntimeEvent],
    ) -> list[RuntimeEvent]:
        if not planned:
            return []
        next_seq = event_log.next_seq(child_id)
        appended = [
            RuntimeEvent(
                seq=next_seq + index,
                type=event.type,
                session_id=child_id,
                timestamp=event.timestamp,
                run_id=event.run_id,
                # Exact deep JSON copy: business fields named seq/source_seq
                # inside model/tool payloads must remain untouched.
                payload=json.loads(json.dumps(event.payload or {}, ensure_ascii=False)),
            )
            for index, event in enumerate(planned)
        ]
        path = event_log.event_path(child_id)
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            for event in appended:
                fh.write(json.dumps(
                    event.to_dict(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ))
                fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        event_log._update_seq_cache(child_id, appended[-1].seq)
        return appended

    def _audit_blob_refs(
        self,
        events: list[RuntimeEvent],
        source_dir: Path,
        target_dir: Path,
        *,
        copy_files: bool,
    ) -> dict:
        descriptors: list[dict] = []

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                if isinstance(value.get("blob_ref"), str):
                    descriptors.append(value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        for event in events:
            visit(event.payload)
        errors: list[str] = []
        copied = 0
        checked = 0
        seen: set[str] = set()
        for descriptor in descriptors:
            ref = str(descriptor.get("blob_ref") or "")
            if ref in seen:
                continue
            seen.add(ref)
            relative = Path(ref)
            if not ref or relative.is_absolute() or ".." in relative.parts:
                errors.append(f"invalid blob_ref:{ref}")
                continue
            source = (source_dir / relative).resolve()
            target = (target_dir / relative).resolve()
            try:
                source.relative_to(source_dir.resolve())
                target.relative_to(target_dir.resolve())
            except ValueError:
                errors.append(f"blob_ref outside session:{ref}")
                continue
            if not source.is_file():
                errors.append(f"missing blob_ref:{ref}")
                continue
            actual = self._file_sha256(source)
            expected = str(descriptor.get("sha256") or "")
            if expected and expected != actual:
                errors.append(f"blob hash mismatch:{ref}")
                continue
            if target.is_file() and self._file_sha256(target) != actual:
                errors.append(f"canonical blob conflict:{ref}")
                continue
            checked += 1
            if copy_files and not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                if self._file_sha256(target) != actual:
                    errors.append(f"copied blob verification failed:{ref}")
                    continue
                copied += 1
        return {
            "checked": checked,
            "copied": copied,
            "errors": errors,
        }

    def _project_ui_from_events(self, child_id: str, events: list[RuntimeEvent]) -> list[dict]:
        projection = RuntimeUiProjection(
            self.sessions_dir,
            path_resolver=self.path_resolver,
        )
        return projection._events_to_ui(child_id, events)

    @staticmethod
    def _ui_hash(events: list[dict]) -> str:
        return hashlib.sha256(json.dumps(
            events,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()

    @staticmethod
    def _fact_fingerprint(event: RuntimeEvent) -> str:
        return hashlib.sha256(json.dumps({
            "type": event.type,
            "timestamp": event.timestamp,
            "run_id": event.run_id,
            "payload": event.payload,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

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
    def _write_json_atomic(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, path)
