from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .mirror import RuntimeMirror
from .config import runtime_v2_enabled


class RuntimeUiProjection:
    """Project Runtime V2 events into the legacy UI event shape.

    This lets the existing frontend switch read paths before the visual
    renderer is rewritten to consume native Runtime V2 events.
    """

    def __init__(self, sessions_dir: str | Path):
        self.sessions_dir = Path(sessions_dir)
        self.event_log = SessionEventLog(self.sessions_dir)

    def ensure_backfilled_from_legacy(self, session_id: str, legacy_events: Iterable[dict]) -> int:
        if not runtime_v2_enabled():
            return 0
        if self.event_log.event_path(session_id).exists() and self._has_ui_projectable_events(session_id):
            return 0
        mirror = RuntimeMirror(self.sessions_dir)
        count = 0
        for event in legacy_events or []:
            if not isinstance(event, dict):
                continue
            if mirror.mirror_ui_event(session_id, event) is not None:
                count += 1
        return count

    def read_ui_events(self, session_id: str) -> List[dict]:
        return self.events_to_ui(self.event_log.read_all(session_id))

    def needs_legacy_backfill(self, session_id: str) -> bool:
        return runtime_v2_enabled() and not self._has_ui_projectable_events(session_id)

    def _has_ui_projectable_events(self, session_id: str) -> bool:
        for event in self.event_log.iter_events(session_id):
            if self.event_to_ui(event) is not None:
                return True
        return False

    def count_ui_events(self, session_id: str) -> int:
        return len(self.read_ui_events(session_id))

    def read_ui_page(
        self,
        session_id: str,
        *,
        limit: int = 200,
        before_index: Optional[int] = None,
        turns: Optional[int] = None,
    ) -> dict:
        events = self.read_ui_events(session_id)
        return self._page_events(events, limit=limit, before_index=before_index, turns=turns)

    @classmethod
    def events_to_ui(cls, events: Iterable[RuntimeEvent]) -> List[dict]:
        out: List[dict] = []
        for event in events:
            if event.type == "legacy_truncate_observed":
                payload = dict(event.payload or {})
                new_count = payload.get("new_event_count")
                if new_count is None:
                    new_count = payload.get("before_index")
                try:
                    out = out[:max(0, int(new_count))]
                except (TypeError, ValueError):
                    pass
                continue
            ui = cls.event_to_ui(event)
            if ui is not None:
                out.append(ui)
        return out

    @staticmethod
    def event_to_ui(event: RuntimeEvent) -> Optional[dict]:
        payload = dict(event.payload or {})
        if event.type == "message_user":
            return {"type": "user", "content": payload.get("content") or ""}
        if event.type == "message_assistant_final":
            return {"type": "final", "content": payload.get("content") or ""}
        if event.type == "tool_started":
            data = dict(payload)
            data["type"] = data.get("type") or "tool_call"
            return data
        if event.type == "tool_finished":
            data = dict(payload)
            data["type"] = data.get("type") or "tool_call"
            return data
        if event.type == "context_summary_committed":
            return {
                "type": "context_summary_body",
                "content": payload.get("summary") or "",
            }
        if event.type == "todo_updated":
            data = dict(payload)
            data["type"] = data.get("type") or "todo_plan"
            return data
        if event.type == "context_tokens":
            data = dict(payload)
            data["type"] = data.get("type") or "context_tokens"
            return data
        if event.type == "legacy_ui_event":
            data = dict(payload)
            if data.get("type"):
                return data
            content = data.get("content") or data.get("message") or data.get("text")
            if content:
                return {"type": "log", "content": str(content)}
            return None
        if event.type.startswith("subagent_"):
            data = dict(payload)
            data["type"] = data.get("type") or event.type
            return data
        return None

    @staticmethod
    def _page_events(
        events: List[dict],
        *,
        limit: int = 200,
        before_index: Optional[int] = None,
        turns: Optional[int] = None,
    ) -> dict:
        total = len(events)
        user_indices = [
            i for i, ev in enumerate(events)
            if isinstance(ev, dict) and ev.get("type") == "user"
        ]

        def turn_start(end_exclusive: int, turn_count: int) -> int:
            end_exclusive = max(0, min(int(end_exclusive), total))
            turn_count = max(1, min(int(turn_count), 50))
            before_users = [i for i in user_indices if i < end_exclusive]
            if not before_users:
                return 0
            if len(before_users) <= turn_count:
                return 0
            return before_users[len(before_users) - turn_count]

        if turns is not None:
            turn_count = max(1, min(int(turns), 50))
            end = total if before_index is None else max(0, min(int(before_index), total))
            start = turn_start(end, turn_count)
            return {
                "events": events[start:end],
                "total": total,
                "range_start": start,
                "range_end": end,
                "has_older": start > 0,
                "has_newer": end < total,
            }

        lim = max(1, min(int(limit), 500))
        end = total if before_index is None else max(0, min(int(before_index), total))
        start = max(0, end - lim)
        return {
            "events": events[start:end],
            "total": total,
            "range_start": start,
            "range_end": end,
            "has_older": start > 0,
            "has_newer": end < total,
        }
