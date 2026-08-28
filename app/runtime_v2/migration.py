from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional

from .history_ops import RuntimeHistoryOps
from .model_projection import RuntimeModelProjection
from .snapshot_store import SnapshotStore
from .ui_projection import RuntimeUiProjection


class RuntimeV2VerificationError(RuntimeError):
    """Raised when an explicit migration/export cannot be verified."""

    def __init__(self, verification: dict) -> None:
        self.verification = dict(verification or {})
        super().__init__(
            "Runtime V2 migration/export verification failed: "
            + json.dumps(self.verification, ensure_ascii=False, sort_keys=True)
        )


class RuntimeV2MigrationService:
    """Explicit Runtime V2 migration/export boundary.

    Normal Runtime V2 read/write paths should not import or call this service.
    It is for user/admin-triggered sync, migration, export, and compatibility
    maintenance only.
    """

    MANIFEST_VERSION = 2
    MANIFEST_FILE = "runtime_v2_migration.json"

    def __init__(
        self,
        sessions_dir: str | Path,
        *,
        path_resolver: Optional[Callable[[str], str | Path]] = None,
    ) -> None:
        self.sessions_dir = Path(sessions_dir)
        self.path_resolver = path_resolver

    def sync_session(
        self,
        session_id: str,
        *,
        load_legacy_ui_events: Callable[[], Iterable[dict]],
        save_legacy_ui_events: Optional[Callable[[List[dict]], None]],
        load_legacy_model_messages: Callable[[], Iterable[dict]],
        save_legacy_model_messages: Optional[Callable[[List[dict]], None]],
        load_legacy_context: Optional[Callable[[], str]] = None,
        load_legacy_todo: Optional[Callable[[], dict]] = None,
        load_file_fingerprints: Optional[Callable[[], dict]] = None,
        export_legacy: bool = False,
        conflict_policy: str = "raise",
    ) -> dict:
        # Resolve and validate every legacy input before the first V2 write.
        # A loader failure therefore cannot leave a partially migrated event log.
        legacy_events = [
            dict(event)
            for event in list(load_legacy_ui_events() or [])
            if isinstance(event, dict)
        ]
        legacy_model_messages = [
            dict(item)
            for item in list(load_legacy_model_messages() or [])
            if isinstance(item, dict)
        ]
        legacy_context = str(load_legacy_context() or "") if load_legacy_context is not None else ""
        loaded_todo = load_legacy_todo() if load_legacy_todo is not None else {}
        legacy_todo = dict(loaded_todo) if isinstance(loaded_todo, dict) else {}
        if conflict_policy not in {"raise", "record"}:
            raise ValueError("conflict_policy must be 'raise' or 'record'")
        if export_legacy and save_legacy_ui_events is None:
            raise ValueError("save_legacy_ui_events is required when export_legacy=True")
        if export_legacy and save_legacy_model_messages is None:
            raise ValueError("save_legacy_model_messages is required when export_legacy=True")

        ui_projection = RuntimeUiProjection(
            self.sessions_dir,
            path_resolver=self.path_resolver,
        )
        model_projection = RuntimeModelProjection(
            self.sessions_dir,
            path_resolver=self.path_resolver,
        )
        rollback_state = self._capture_v2_state(ui_projection, session_id)
        exported_ui = False
        exported_model = False
        try:
            if export_legacy:
                # Export is V2-authoritative and never backfills V2 from V1.
                v2_from_v1 = {
                    "checked": True,
                    "action": "skipped_export_mode",
                    "legacy_count": len(legacy_events),
                    "projected_count": len(ui_projection.read_ui_events_fast(session_id)),
                    "written": 0,
                }
                model_v2_from_v1 = {
                    "checked": True,
                    "action": "skipped_export_mode",
                    "legacy_count": len(legacy_model_messages),
                    "projected_count": len(model_projection.read_message_dicts(session_id)),
                    "written": 0,
                }
            else:
                v2_from_v1 = ui_projection.sync_from_legacy_if_needed(
                    session_id,
                    lambda: legacy_events,
                )
                model_v2_from_v1 = model_projection.sync_from_legacy_if_needed(
                    session_id,
                    legacy_model_messages,
                    reason="explicit_migration_model_sync",
                )

            projected_events = ui_projection.read_ui_events_fast(session_id)
            v2_model_messages = model_projection.read_message_dicts(session_id)
            context_v2_from_v1, todo_v2_from_v1 = self._migrate_optional_state(
                session_id,
                legacy_context=legacy_context,
                legacy_todo=legacy_todo,
                enabled=not export_legacy,
            )
            v1_from_v2 = {
                "checked": True,
                "action": "skipped" if not export_legacy else "none",
                "legacy_count": len(legacy_events),
                "projected_count": len(projected_events),
            }
            model_v2_to_v1 = {
                "checked": True,
                "action": "skipped" if not export_legacy else "none",
                "legacy_count": len(legacy_model_messages),
                "projected_count": len(v2_model_messages),
            }
            effective_legacy_events = legacy_events
            effective_legacy_model = legacy_model_messages
            if export_legacy and not self._rows_equal(legacy_events, projected_events, kind="ui"):
                # Mark the export as attempted before calling into legacy code. A
                # saver may persist successfully and then raise, in which case its
                # original content still has to be restored.
                exported_ui = True
                save_legacy_ui_events([dict(event) for event in projected_events])
                v1_from_v2 = {
                    "checked": True,
                    "action": "replace",
                    "legacy_count": len(legacy_events),
                    "projected_count": len(projected_events),
                    "written": len(projected_events),
                }
            if export_legacy and not self._rows_equal(
                legacy_model_messages,
                v2_model_messages,
                kind="model",
            ):
                exported_model = True
                save_legacy_model_messages([dict(item) for item in v2_model_messages])
                model_v2_to_v1 = {
                    "checked": True,
                    "action": "replace",
                    "legacy_count": len(legacy_model_messages),
                    "projected_count": len(v2_model_messages),
                    "written": len(v2_model_messages),
                }

            if export_legacy:
                # Never verify the values passed to a callback. Verify what the
                # legacy loaders can actually read after the save completed.
                effective_legacy_events = self._dict_rows(load_legacy_ui_events())
                effective_legacy_model = self._dict_rows(load_legacy_model_messages())

            ui_verification = self._verification(
                effective_legacy_events,
                projected_events,
                kind="ui",
            )
            model_verification = self._verification(
                effective_legacy_model,
                v2_model_messages,
                kind="model",
            )
            verification = {
                "verified": bool(ui_verification["verified"] and model_verification["verified"]),
                "ui": ui_verification,
                "model": model_verification,
            }
            if not verification["verified"]:
                raise RuntimeV2VerificationError(verification)
            manifest = {
                "manifest_version": self.MANIFEST_VERSION,
                "session_id": session_id,
                "operation": "export" if export_legacy else "migrate",
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "file_fingerprints": self._load_fingerprints(load_file_fingerprints),
                "verification": verification,
                "actions": {
                    "v2_from_v1": v2_from_v1,
                    "model_v2_from_v1": model_v2_from_v1,
                    "context_v2_from_v1": context_v2_from_v1,
                    "todo_v2_from_v1": todo_v2_from_v1,
                    "v1_from_v2": v1_from_v2,
                    "model_v2_to_v1": model_v2_to_v1,
                },
            }
            manifest_path = self._write_manifest(ui_projection, session_id, manifest)
        except Exception as exc:
            rollback_errors: list[str] = []
            if export_legacy:
                try:
                    if exported_ui and save_legacy_ui_events is not None:
                        save_legacy_ui_events([dict(event) for event in legacy_events])
                except Exception as rollback_exc:
                    rollback_errors.append(f"legacy_ui:{rollback_exc}")
                try:
                    if exported_model and save_legacy_model_messages is not None:
                        save_legacy_model_messages([
                            dict(item) for item in legacy_model_messages
                        ])
                except Exception as rollback_exc:
                    rollback_errors.append(f"legacy_model:{rollback_exc}")
            try:
                self._restore_v2_state(ui_projection, session_id, rollback_state)
            except Exception as rollback_exc:
                rollback_errors.append(f"runtime_v2:{rollback_exc}")
            if rollback_errors:
                raise RuntimeError(
                    "migration/export failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from exc
            if conflict_policy == "record" and isinstance(exc, RuntimeV2VerificationError):
                blocked_manifest = {
                    "manifest_version": self.MANIFEST_VERSION,
                    "session_id": session_id,
                    "operation": "migrate",
                    "status": "blocked",
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "file_fingerprints": self._load_fingerprints(load_file_fingerprints),
                    "verification": dict(exc.verification or {}),
                    "actions": {
                        "v2_from_v1": locals().get("v2_from_v1", {}),
                        "model_v2_from_v1": locals().get("model_v2_from_v1", {}),
                    },
                }
                manifest_path = self._write_manifest(ui_projection, session_id, blocked_manifest)
                return {
                    "ok": False,
                    "blocked": True,
                    "session_id": session_id,
                    "error": str(exc),
                    "verification": dict(exc.verification or {}),
                    "manifest_version": self.MANIFEST_VERSION,
                    "manifest_path": str(manifest_path),
                }
            raise
        finally:
            self._discard_v2_state(rollback_state)

        return {
            "ok": True,
            "session_id": session_id,
            "v2_from_v1": v2_from_v1,
            "model_v2_from_v1": model_v2_from_v1,
            "context_v2_from_v1": context_v2_from_v1,
            "todo_v2_from_v1": todo_v2_from_v1,
            "v1_from_v2": v1_from_v2,
            "model_v2_to_v1": model_v2_to_v1,
            "verification": verification,
            "manifest_version": self.MANIFEST_VERSION,
            "manifest_path": str(manifest_path),
        }

    def _migrate_optional_state(
        self,
        session_id: str,
        *,
        legacy_context: str,
        legacy_todo: dict,
        enabled: bool,
    ) -> tuple[dict, dict]:
        snapshot = SnapshotStore(
            self.sessions_dir,
            path_resolver=self.path_resolver,
        ).read_consistent(session_id)
        context = snapshot.get("context") if isinstance(snapshot, dict) else {}
        summary = context.get("summary") if isinstance(context, dict) else {}
        current_context = str(summary.get("summary") or "") if isinstance(summary, dict) else ""
        extensions = snapshot.get("extensions") if isinstance(snapshot, dict) else {}
        todo_plugin = extensions.get("session-todo") if isinstance(extensions, dict) else {}
        todo_row = todo_plugin.get("plan") if isinstance(todo_plugin, dict) else {}
        current_todo = todo_row.get("value") if isinstance(todo_row, dict) else {}
        current_todo = dict(current_todo) if isinstance(current_todo, dict) else {}
        clean_legacy_todo = self._canonical_todo(legacy_todo)
        clean_current_todo = self._canonical_todo(current_todo)

        context_action = self._optional_state_action(legacy_context, current_context, enabled=enabled)
        todo_action = self._optional_state_action(clean_legacy_todo, clean_current_todo, enabled=enabled)
        ops = RuntimeHistoryOps(self.sessions_dir, path_resolver=self.path_resolver)
        if context_action["action"] == "backfill":
            ops.commit_context_summary(session_id, legacy_context)
        if todo_action["action"] == "backfill":
            from .extension_state import SessionExtensionStateStore

            SessionExtensionStateStore(
                self.sessions_dir,
                path_resolver=self.path_resolver,
            ).set_latest(
                session_id,
                "session-todo",
                "plan",
                clean_legacy_todo,
            )
        return context_action, todo_action

    @staticmethod
    def _optional_state_action(source: Any, target: Any, *, enabled: bool) -> dict:
        source_present = bool(source)
        target_present = bool(target)
        if not enabled:
            action = "skipped_export_mode"
        elif not source_present:
            action = "none"
        elif not target_present:
            action = "backfill"
        elif source == target:
            action = "none"
        else:
            # Context/todo do not have an append-only ordering signal.  Existing
            # V2 state is therefore authoritative and a differing legacy value
            # is surfaced for review rather than guessed or overwritten.
            action = "v2_preserved"
        return {
            "checked": True,
            "action": action,
            "source_present": source_present,
            "target_present": target_present,
        }

    @classmethod
    def _canonical_todo(cls, todo: dict) -> dict:
        clean = dict(todo or {})
        clean.pop("updated_at", None)
        clean.pop("seq", None)
        if not clean.get("has_plan") and not list(clean.get("items") or []):
            return {}
        return cls._canonical_value(clean)

    @staticmethod
    def _load_fingerprints(loader: Optional[Callable[[], dict]]) -> dict:
        if loader is None:
            return {}
        value = loader()
        return dict(value) if isinstance(value, dict) else {}

    @classmethod
    def _rows_equal(cls, left: Iterable[dict], right: Iterable[dict], *, kind: str) -> bool:
        return [cls._canonical_row(row, kind=kind) for row in left if isinstance(row, dict)] == [
            cls._canonical_row(row, kind=kind) for row in right if isinstance(row, dict)
        ]

    @staticmethod
    def _dict_rows(rows: Iterable[dict] | None) -> list[dict]:
        return [dict(row) for row in list(rows or []) if isinstance(row, dict)]

    def _write_manifest(self, projection: RuntimeUiProjection, session_id: str, manifest: dict) -> Path:
        path = projection.event_log.session_dir(session_id) / self.MANIFEST_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(path)
        return path

    def _capture_v2_state(self, projection: RuntimeUiProjection, session_id: str) -> dict:
        session_dir = projection.event_log.session_dir(session_id)
        session_dir.parent.mkdir(parents=True, exist_ok=True)
        backup_dir = Path(tempfile.mkdtemp(
            prefix=f".runtime-v2-migration-{session_id}-",
            dir=str(session_dir.parent),
        ))
        fixed_rel = [
            Path("events.jsonl"),
            Path("snapshots/latest.json"),
            Path("snapshots/ui_projection_index.json"),
            Path("snapshots/seq_offset_index.json"),
            Path(self.MANIFEST_FILE),
        ]
        present: list[str] = []
        for relative in fixed_rel:
            source = session_dir / relative
            if not source.is_file():
                continue
            target = backup_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            present.append(str(relative))
        blob_root = session_dir / "blobs"
        if blob_root.is_dir():
            shutil.copytree(blob_root, backup_dir / "blobs")
        return {
            "session_dir": session_dir,
            "backup_dir": backup_dir,
            "fixed_rel": [str(relative) for relative in fixed_rel],
            "present": present,
            "had_blobs": blob_root.is_dir(),
        }

    def _restore_v2_state(
        self,
        projection: RuntimeUiProjection,
        session_id: str,
        state: dict,
    ) -> None:
        session_dir = Path(state["session_dir"])
        backup_dir = Path(state["backup_dir"])
        present = set(state.get("present") or [])
        for relative in list(state.get("fixed_rel") or []):
            path = session_dir / relative
            if relative not in present:
                path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".rollback.tmp")
            shutil.copy2(backup_dir / relative, tmp)
            tmp.replace(path)
        blob_root = session_dir / "blobs"
        if blob_root.exists():
            shutil.rmtree(blob_root)
        if state.get("had_blobs") and (backup_dir / "blobs").is_dir():
            shutil.copytree(backup_dir / "blobs", blob_root)
        projection.invalidate_cache(session_id)
        events = projection.event_log.read_all(session_id)
        projection.event_log._update_seq_cache(
            session_id,
            max((event.seq for event in events), default=0),
        )

    @staticmethod
    def _discard_v2_state(state: dict) -> None:
        backup_dir = Path(str((state or {}).get("backup_dir") or ""))
        if not backup_dir.name.startswith(".runtime-v2-migration-"):
            return
        try:
            shutil.rmtree(backup_dir)
        except FileNotFoundError:
            pass

    @classmethod
    def _verification(cls, source: Iterable[dict], target: Iterable[dict], *, kind: str) -> dict:
        source_rows = [cls._canonical_row(item, kind=kind) for item in source if isinstance(item, dict)]
        target_rows = [cls._canonical_row(item, kind=kind) for item in target if isinstance(item, dict)]
        if source_rows == target_rows:
            status = "match"
        elif not source_rows and target_rows:
            status = "v2_only"
        elif len(source_rows) <= len(target_rows) and target_rows[: len(source_rows)] == source_rows:
            status = "v2_ahead"
        else:
            status = "mismatch"
        return {
            "status": status,
            "verified": status in {"match", "v2_only", "v2_ahead"},
            "source_count": len(source_rows),
            "target_count": len(target_rows),
            "source_sha256": cls._rows_sha256(source_rows),
            "target_sha256": cls._rows_sha256(target_rows),
        }

    @classmethod
    def _canonical_row(cls, row: dict, *, kind: str) -> dict:
        ignored = {
            "runtime_seq",
            "runtime_event_type",
            "created_at",
            "session_id",
            "rewritten",
            "rewritten_by_seq",
        }
        clean = {
            str(key): cls._canonical_value(value)
            for key, value in row.items()
            if str(key) not in ignored
        }
        if kind == "model":
            role = str(clean.get("type") or clean.get("role") or "").strip().lower()
            role = {"human": "user", "llm": "assistant", "ai": "assistant", "agent": "assistant"}.get(role, role)
            clean.pop("role", None)
            clean["type"] = role
        return clean

    @classmethod
    def _canonical_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): cls._canonical_value(item) for key, item in sorted(value.items())}
        if isinstance(value, list):
            return [cls._canonical_value(item) for item in value]
        return value

    @staticmethod
    def _rows_sha256(rows: list[dict]) -> str:
        raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
