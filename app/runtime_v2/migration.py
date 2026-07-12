from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional

from .model_projection import RuntimeModelProjection
from .ui_projection import RuntimeUiProjection


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
        ui_projection = RuntimeUiProjection(
            self.sessions_dir,
            path_resolver=self.path_resolver,
        )
        legacy_events = [
            dict(event)
            for event in list(load_legacy_ui_events() or [])
            if isinstance(event, dict)
        ]
        v2_from_v1 = ui_projection.sync_from_legacy_if_needed(
            session_id,
            lambda: legacy_events,
        )
        projected_events = ui_projection.read_ui_events_fast(session_id)
        v1_from_v2 = {
            "checked": True,
            "action": "skipped" if not export_legacy else "none",
            "legacy_count": len(legacy_events),
            "projected_count": len(projected_events),
        }
        if export_legacy and len(projected_events) > len(legacy_events):
            if save_legacy_ui_events is None:
                raise ValueError("save_legacy_ui_events is required when export_legacy=True")
            save_legacy_ui_events([dict(event) for event in projected_events])
            v1_from_v2 = {
                "checked": True,
                "action": "replace",
                "legacy_count": len(legacy_events),
                "projected_count": len(projected_events),
                "written": len(projected_events),
            }

        legacy_model_messages = [
            dict(item)
            for item in list(load_legacy_model_messages() or [])
            if isinstance(item, dict)
        ]
        model_projection = RuntimeModelProjection(self.sessions_dir)
        model_v2_from_v1 = model_projection.sync_from_legacy_if_needed(
            session_id,
            legacy_model_messages,
            reason="explicit_migration_model_sync",
        )
        v2_model_messages = model_projection.read_message_dicts(session_id)
        model_v2_to_v1 = {
            "checked": True,
            "action": "skipped" if not export_legacy else "none",
            "legacy_count": len(legacy_model_messages),
            "projected_count": len(v2_model_messages or []),
        }
        if export_legacy and v2_model_messages and v2_model_messages != legacy_model_messages:
            if save_legacy_model_messages is None:
                raise ValueError("save_legacy_model_messages is required when export_legacy=True")
            save_legacy_model_messages([dict(item) for item in v2_model_messages])
            model_v2_to_v1 = {
                "checked": True,
                "action": "replace",
                "legacy_count": len(legacy_model_messages),
                "projected_count": len(v2_model_messages),
                "written": len(v2_model_messages),
            }

        ui_verification = self._verification(legacy_events, projected_events, kind="ui")
        model_verification = self._verification(legacy_model_messages, v2_model_messages, kind="model")
        verification = {
            "verified": bool(ui_verification["verified"] and model_verification["verified"]),
            "ui": ui_verification,
            "model": model_verification,
        }
        manifest = {
            "manifest_version": self.MANIFEST_VERSION,
            "session_id": session_id,
            "operation": "migrate_and_export" if export_legacy else "migrate",
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
