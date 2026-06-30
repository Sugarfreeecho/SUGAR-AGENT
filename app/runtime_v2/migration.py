from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .model_projection import RuntimeModelProjection
from .ui_projection import RuntimeUiProjection


class RuntimeV2MigrationService:
    """Explicit Runtime V2 migration/export boundary.

    Normal Runtime V2 read/write paths should not import or call this service.
    It is for user/admin-triggered sync, migration, export, and compatibility
    maintenance only.
    """

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

        return {
            "ok": True,
            "session_id": session_id,
            "v2_from_v1": v2_from_v1,
            "model_v2_from_v1": model_v2_from_v1,
            "v1_from_v2": v1_from_v2,
            "model_v2_to_v1": model_v2_to_v1,
        }
