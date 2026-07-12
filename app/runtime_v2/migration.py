from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional

from .model_projection import RuntimeModelProjection
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

    MANIFEST_VERSION = 1
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
        export_legacy: bool = False,
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
                "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "verification": verification,
                "actions": {
                    "v2_from_v1": v2_from_v1,
                    "model_v2_from_v1": model_v2_from_v1,
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
            raise

        return {
            "ok": True,
            "session_id": session_id,
            "v2_from_v1": v2_from_v1,
            "model_v2_from_v1": model_v2_from_v1,
            "v1_from_v2": v1_from_v2,
            "model_v2_to_v1": model_v2_to_v1,
            "verification": verification,
            "manifest_version": self.MANIFEST_VERSION,
            "manifest_path": str(manifest_path),
        }

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
        fixed_rel = [
            Path("events.jsonl"),
            Path("snapshots/latest.json"),
            Path("snapshots/ui_projection_index.json"),
            Path(self.MANIFEST_FILE),
        ]
        fixed = {
            str(relative): (session_dir / relative).read_bytes()
            if (session_dir / relative).is_file()
            else None
            for relative in fixed_rel
        }
        blobs: dict[str, bytes] = {}
        blob_root = session_dir / "blobs"
        if blob_root.is_dir():
            for path in blob_root.rglob("*"):
                if path.is_file():
                    blobs[str(path.relative_to(blob_root))] = path.read_bytes()
        return {"session_dir": session_dir, "fixed": fixed, "blobs": blobs}

    def _restore_v2_state(
        self,
        projection: RuntimeUiProjection,
        session_id: str,
        state: dict,
    ) -> None:
        session_dir = Path(state["session_dir"])
        for relative, content in dict(state.get("fixed") or {}).items():
            path = session_dir / relative
            if content is None:
                path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".rollback.tmp")
            tmp.write_bytes(content)
            tmp.replace(path)
        blob_root = session_dir / "blobs"
        if blob_root.exists():
            shutil.rmtree(blob_root)
        for relative, content in dict(state.get("blobs") or {}).items():
            path = blob_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        projection.invalidate_cache(session_id)
        events = projection.event_log.read_all(session_id)
        projection.event_log._update_seq_cache(
            session_id,
            max((event.seq for event in events), default=0),
        )

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
