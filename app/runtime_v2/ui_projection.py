from __future__ import annotations

import os
import json
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .event_log import SessionEventLog
from .event_schema import RuntimeEvent
from .mirror import RuntimeMirror
from .config import runtime_v2_enabled


class RuntimeUiProjection:
    """Project Runtime V2 events into the legacy UI event shape.

    This lets the existing frontend switch read paths before the visual
    renderer is rewritten to consume native Runtime V2 events.
    """

    _cache_lock = threading.Lock()
    _events_cache: Dict[str, tuple[tuple[bool, int, int], List[dict]]] = {}
    _events_cache_order: List[str] = []
    _events_cache_max = 64

    def __init__(self, sessions_dir: str | Path, path_resolver: Optional[Callable[[str], str | Path]] = None):
        self.sessions_dir = Path(sessions_dir)
        self._path_resolver = path_resolver
        self.event_log = SessionEventLog(self.sessions_dir, path_resolver=path_resolver)

    def ensure_backfilled_from_legacy(self, session_id: str, legacy_events: Iterable[dict]) -> int:
        if self.event_log.event_path(session_id).exists() and self._has_ui_projectable_events(session_id):
            return 0
        mirror = RuntimeMirror(self.sessions_dir, path_resolver=self._path_resolver)
        count = 0
        for event in legacy_events or []:
            if not isinstance(event, dict):
                continue
            mirrored = mirror.mirror_ui_event(session_id, event)
            if mirrored is None:
                mirrored = mirror.append(session_id, "legacy_ui_event", dict(event))
            if mirrored is not None:
                count += 1
        if count:
            self.invalidate_cache(session_id)
        return count

    def replace_from_legacy(self, session_id: str, legacy_events: Iterable[dict], reason: str = "legacy_ui_backfill_replace") -> int:
        mirror = RuntimeMirror(self.sessions_dir, path_resolver=self._path_resolver)
        mirror.append(session_id, "legacy_truncate_observed", {
            "before_index": 0,
            "old_event_count": len(self.read_ui_events(session_id)),
            "new_event_count": 0,
            "reason": reason,
        })
        count = 0
        for event in legacy_events or []:
            if not isinstance(event, dict):
                continue
            mirrored = mirror.mirror_ui_event(session_id, event)
            if mirrored is None:
                mirrored = mirror.append(session_id, "legacy_ui_event", dict(event))
            if mirrored is not None:
                count += 1
        self.invalidate_cache(session_id)
        return count

    def sync_from_legacy_if_needed(self, session_id: str, legacy_loader: Callable[[], Iterable[dict]]) -> dict:
        legacy = [event for event in list(legacy_loader() or []) if isinstance(event, dict)]
        projected = self._projected_ui_events_cached(session_id)
        if not legacy:
            return {"checked": True, "action": "none", "legacy_count": 0, "projected_count": len(projected)}
        if not projected:
            wrote = self.ensure_backfilled_from_legacy(session_id, legacy)
            return {"checked": True, "action": "backfill", "legacy_count": len(legacy), "projected_count": 0, "written": wrote}
        if len(projected) < len(legacy):
            wrote = self.replace_from_legacy(session_id, legacy, reason="legacy_ui_sync_on_open")
            return {
                "checked": True,
                "action": "replace",
                "legacy_count": len(legacy),
                "projected_count": len(projected),
                "written": wrote,
            }
        return {
            "checked": True,
            "action": "none",
            "legacy_count": len(legacy),
            "projected_count": len(projected),
        }

    def read_ui_events(self, session_id: str, legacy_loader: Optional[Callable[[], Iterable[dict]]] = None) -> List[dict]:
        projected = self._projected_ui_events_cached(session_id)
        if legacy_loader is not None:
            legacy = [event for event in list(legacy_loader() or []) if isinstance(event, dict)]
            if legacy and not projected:
                self.ensure_backfilled_from_legacy(session_id, legacy)
                projected = self._projected_ui_events_cached(session_id)
            elif legacy and len(projected) < len(legacy):
                self.replace_from_legacy(session_id, legacy, reason="legacy_ui_sync_on_read")
                projected = self._projected_ui_events_cached(session_id)
        return projected

    def read_ui_events_fast(self, session_id: str) -> List[dict]:
        return self._projected_ui_events_cached(session_id)

    def needs_legacy_backfill(self, session_id: str) -> bool:
        return runtime_v2_enabled() and not self._has_ui_projectable_events(session_id)

    def _has_ui_projectable_events(self, session_id: str) -> bool:
        for event in self.event_log.iter_events(session_id):
            if self.event_to_ui(event) is not None:
                return True
        return False

    def count_ui_events(self, session_id: str) -> int:
        return len(self.read_ui_events(session_id))

    def count_ui_events_light(self, session_id: str) -> tuple[int, int]:
        """Return projected UI count and latest truncate seq.

        This is still a linear pass when metadata is unavailable, but it does
        not materialize every UI payload into a list. It keeps paged V2 reads
        compatible with the legacy event-index contract.
        """
        index = self._read_or_build_ui_index(session_id)
        if index:
            return int(index.get("total") or 0), int(index.get("latest_truncate_seq") or 0)
        return self._count_ui_events_linear(session_id)

    def _count_ui_events_linear(self, session_id: str) -> tuple[int, int]:
        count = 0
        latest_truncate_seq = 0
        for event in self.event_log.iter_events(session_id):
            if event.type == "legacy_truncate_observed":
                payload = dict(event.payload or {})
                new_count = payload.get("new_event_count")
                if new_count is None:
                    new_count = payload.get("before_index")
                try:
                    count = max(0, int(new_count))
                    latest_truncate_seq = int(event.seq)
                except (TypeError, ValueError):
                    pass
                continue
            if event.type == "visible_range_changed":
                payload = dict(event.payload or {})
                if payload.get("to_ui_index") is not None:
                    try:
                        count = max(0, int(payload.get("to_ui_index")))
                        latest_truncate_seq = int(event.seq)
                    except (TypeError, ValueError):
                        pass
                    continue
            if self.event_to_ui(event) is not None:
                count += 1
        return count, latest_truncate_seq

    def _ui_index_path(self, session_id: str) -> Path:
        return self.event_log.session_dir(session_id) / "snapshots" / "ui_projection_index.json"

    def _read_or_build_ui_index(self, session_id: str) -> dict:
        signature = self._event_log_signature(session_id)
        path = self._ui_index_path(session_id)
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and tuple(data.get("signature") or ()) == signature:
                return data
        except Exception:
            pass
        try:
            return self._build_ui_index(session_id, signature)
        except Exception:
            return {}

    def _build_ui_index(self, session_id: str, signature: Optional[tuple[bool, int, int]] = None) -> dict:
        if signature is None:
            signature = self._event_log_signature(session_id)
        total = 0
        latest_truncate_seq = 0
        user_indices: List[int] = []
        for event in self.event_log.iter_events(session_id):
            if event.type == "legacy_truncate_observed":
                payload = dict(event.payload or {})
                new_count = payload.get("new_event_count")
                if new_count is None:
                    new_count = payload.get("before_index")
                try:
                    total = max(0, int(new_count))
                    user_indices = [idx for idx in user_indices if idx < total]
                    latest_truncate_seq = int(event.seq)
                except (TypeError, ValueError):
                    pass
                continue
            if event.type == "visible_range_changed":
                payload = dict(event.payload or {})
                if payload.get("to_ui_index") is not None:
                    try:
                        total = max(0, int(payload.get("to_ui_index")))
                        user_indices = [idx for idx in user_indices if idx < total]
                        latest_truncate_seq = int(event.seq)
                    except (TypeError, ValueError):
                        pass
                    continue
            ui = self.event_to_ui(event)
            if ui is None:
                continue
            if ui.get("type") == "user":
                user_indices.append(total)
            total += 1
        data = {
            "signature": list(signature),
            "total": total,
            "latest_truncate_seq": latest_truncate_seq,
            "user_indices": user_indices,
        }
        path = self._ui_index_path(session_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
            tmp.replace(path)
        except Exception:
            pass
        return data

    def invalidate_cache(self, session_id: str) -> None:
        key = self._cache_key(session_id)
        with self._cache_lock:
            self._events_cache.pop(key, None)
            try:
                self._events_cache_order.remove(key)
            except ValueError:
                pass
        try:
            self._ui_index_path(session_id).unlink(missing_ok=True)
        except Exception:
            pass

    def _projected_ui_events_cached(self, session_id: str) -> List[dict]:
        key = self._cache_key(session_id)
        signature = self._event_log_signature(session_id)
        with self._cache_lock:
            cached = self._events_cache.get(key)
            if cached and cached[0] == signature:
                return [dict(event) for event in cached[1]]
        projected = self.events_to_ui(self.event_log.read_all(session_id))
        with self._cache_lock:
            self._events_cache[key] = (signature, projected)
            if key in self._events_cache_order:
                self._events_cache_order.remove(key)
            self._events_cache_order.append(key)
            while len(self._events_cache_order) > self._events_cache_max:
                old_key = self._events_cache_order.pop(0)
                self._events_cache.pop(old_key, None)
        return [dict(event) for event in projected]

    def _event_log_signature(self, session_id: str) -> tuple[bool, int, int]:
        path = self.event_log.event_path(session_id)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return (False, 0, 0)
        return (True, int(stat.st_mtime_ns), int(stat.st_size))

    def _cache_key(self, session_id: str) -> str:
        return f"{self.sessions_dir.resolve()}::{session_id}"

    def read_ui_page(
        self,
        session_id: str,
        *,
        limit: int = 200,
        before_index: Optional[int] = None,
        after_index: Optional[int] = None,
        turns: Optional[int] = None,
        legacy_loader: Optional[Callable[[], Iterable[dict]]] = None,
    ) -> dict:
        if legacy_loader is None and before_index is None and after_index is None and turns is not None:
            page = self._read_recent_turns_from_tail(session_id, turns=int(turns))
            if page is not None:
                return page
        events = self.read_ui_events(session_id, legacy_loader=legacy_loader)
        return self._page_events(events, limit=limit, before_index=before_index, after_index=after_index, turns=turns)

    def _read_recent_turns_from_tail(self, session_id: str, *, turns: int) -> Optional[dict]:
        turn_count = max(1, min(int(turns), 50))
        max_bytes_limit = max(
            64 * 1024,
            int(os.getenv("RUNTIME_V2_TAIL_MAX_BYTES", str(8 * 1024 * 1024))),
        )
        window = max(
            64 * 1024,
            int(os.getenv("RUNTIME_V2_TAIL_INITIAL_BYTES", str(512 * 1024))),
        )
        max_events = max(500, int(os.getenv("RUNTIME_V2_TAIL_MAX_EVENTS", "8000")))
        index = self._read_or_build_ui_index(session_id)
        total = int(index.get("total") or 0) if index else 0
        latest_truncate_seq = int(index.get("latest_truncate_seq") or 0) if index else 0
        if total <= 0:
            return {
                "events": [],
                "total": 0,
                "range_start": 0,
                "range_end": 0,
                "has_older": False,
                "has_newer": False,
                "source": "runtime_v2_tail",
            }
        user_indices_index = list(index.get("user_indices") or []) if index else []
        if user_indices_index:
            if len(user_indices_index) <= turn_count:
                wanted_start = 0
            else:
                wanted_start = int(user_indices_index[len(user_indices_index) - turn_count])
            wanted_len = max(0, total - wanted_start)
        else:
            wanted_start = 0
            wanted_len = total
        while window <= max_bytes_limit:
            runtime_events, reached_start = self.event_log.read_tail_window(
                session_id,
                max_bytes=window,
                max_events=max_events,
            )
            if not runtime_events:
                return None
            if any(
                event.type == "legacy_truncate_observed"
                or (
                    event.type == "visible_range_changed"
                    and dict(event.payload or {}).get("to_ui_index") is not None
                )
                for event in runtime_events
            ):
                return None
            ui_events: List[dict] = []
            for event in runtime_events:
                if latest_truncate_seq and event.seq <= latest_truncate_seq:
                    continue
                ui = self.event_to_ui(event)
                if ui is not None:
                    ui_events.append(ui)
            if not ui_events:
                if reached_start:
                    return {
                        "events": [],
                        "total": total,
                        "range_start": total,
                        "range_end": total,
                        "has_older": total > 0,
                        "has_newer": False,
                        "source": "runtime_v2_tail",
                    }
                window *= 2
                continue
            if len(ui_events) >= wanted_len:
                selected = ui_events[-wanted_len:] if wanted_len > 0 else []
                return {
                    "events": selected,
                    "total": total,
                    "range_start": wanted_start,
                    "range_end": total,
                    "has_older": wanted_start > 0,
                    "has_newer": False,
                    "source": "runtime_v2_tail_index",
                    "tail_reached_start": bool(reached_start),
                }
            user_indices = [
                i for i, ev in enumerate(ui_events)
                if isinstance(ev, dict) and ev.get("type") == "user"
            ]
            if len(user_indices) >= turn_count or reached_start or window >= max_bytes_limit:
                if not user_indices:
                    start = 0
                elif len(user_indices) <= turn_count:
                    start = 0
                else:
                    start = user_indices[len(user_indices) - turn_count]
                selected = ui_events[start:]
                range_end = total
                range_start = max(0, range_end - len(selected))
                return {
                    "events": selected,
                    "total": total,
                    "range_start": range_start,
                    "range_end": range_end,
                    "has_older": range_start > 0,
                    "has_newer": False,
                    "source": "runtime_v2_tail",
                    "tail_reached_start": bool(reached_start),
                }
            window *= 2
        return None

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
            if event.type == "visible_range_changed":
                payload = dict(event.payload or {})
                if payload.get("to_ui_index") is not None:
                    try:
                        out = out[:max(0, int(payload.get("to_ui_index")))]
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
            return {"type": "user", "content": payload.get("content") or "", "created_at": event.timestamp}
        if event.type == "message_assistant_final":
            return {"type": "final", "content": payload.get("content") or "", "created_at": event.timestamp}
        if event.type == "tool_started":
            data = dict(payload)
            data["type"] = data.get("type") or "tool_call"
            data.setdefault("created_at", event.timestamp)
            return data
        if event.type == "tool_finished":
            data = dict(payload)
            data["type"] = data.get("type") or "tool_call"
            data.setdefault("created_at", event.timestamp)
            return data
        if event.type == "context_summary_committed":
            return {
                "type": "context_summary_body",
                "content": payload.get("summary") or "",
                "created_at": event.timestamp,
            }
        if event.type == "todo_updated":
            data = dict(payload)
            data["type"] = data.get("type") or "todo_plan"
            data.setdefault("created_at", event.timestamp)
            return data
        if event.type == "context_tokens":
            data = dict(payload)
            data["type"] = data.get("type") or "context_tokens"
            data.setdefault("created_at", event.timestamp)
            return data
        if event.type == "legacy_ui_event":
            data = dict(payload)
            if data.get("type"):
                data.setdefault("created_at", event.timestamp)
                return data
            content = data.get("content") or data.get("message") or data.get("text")
            if content:
                return {"type": "log", "content": str(content), "created_at": event.timestamp}
            return None
        if event.type.startswith("subagent_"):
            data = dict(payload)
            data["type"] = data.get("type") or event.type
            data.setdefault("created_at", event.timestamp)
            return data
        return None

    @staticmethod
    def _page_events(
        events: List[dict],
        *,
        limit: int = 200,
        before_index: Optional[int] = None,
        after_index: Optional[int] = None,
        turns: Optional[int] = None,
    ) -> dict:
        total = len(events)
        user_indices = [
            i for i, ev in enumerate(events)
            if isinstance(ev, dict) and ev.get("type") == "user"
        ]
        lim = max(1, min(int(limit), 500))

        if after_index is not None:
            start = max(0, min(int(after_index) + 1, total))
            end = min(total, start + lim)
            return {
                "events": events[start:end],
                "total": total,
                "range_start": start,
                "range_end": end,
                "has_older": start > 0,
                "has_newer": end < total,
            }

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
