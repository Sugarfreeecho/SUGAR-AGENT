"""Read-only adapters for Runtime events written before optional features moved out.

Keep legacy product vocabulary here so the current projector and event catalog
remain domain-neutral. Adapters must never be used for new writes.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

from .event_schema import RuntimeEvent


def map_legacy_ui_optional_event(event: Mapping[str, Any]) -> dict | None:
    """Translate retired UI payloads without teaching the current mirror domains."""

    if str(event.get("type") or "") != "todo_plan":
        return None
    value = dict(event)
    for key in ("type", "created_at", "runtime_seq", "source"):
        value.pop(key, None)
    value.setdefault("schema_version", 1)
    return {
        "type": "extension_state_changed",
        "payload": {
            "plugin_id": "session-todo",
            "namespace": "plan",
            "revision": 1,
            "value": value,
        },
        "_set_extension_latest": True,
    }


def _extension_value(snapshot: Mapping[str, Any] | None, plugin_id: str, namespace: str) -> dict:
    extensions = snapshot.get("extensions") if isinstance(snapshot, Mapping) else {}
    plugin = extensions.get(plugin_id) if isinstance(extensions, Mapping) else {}
    row = plugin.get(namespace) if isinstance(plugin, Mapping) else {}
    value = row.get("value") if isinstance(row, Mapping) else {}
    return copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def normalize_legacy_optional_event(
    event: RuntimeEvent,
    snapshot: Mapping[str, Any] | None = None,
) -> RuntimeEvent:
    if event.type == "todo_updated":
        payload = dict(event.payload or {}) if isinstance(event.payload, Mapping) else {}
        value = payload.get("todo") if isinstance(payload.get("todo"), Mapping) else payload
        clean_value = copy.deepcopy(dict(value))
        clean_value.setdefault("schema_version", 1)
        plugin_id, namespace = "session-todo", "plan"
    elif event.type.startswith("goal_"):
        payload = dict(event.payload or {}) if isinstance(event.payload, Mapping) else {}
        if payload.get("_goal_delta"):
            clean_value = _extension_value(snapshot, "agent-goal", "goal")
            goal_id = payload.get("id")
            if goal_id and clean_value.get("id") not in {None, goal_id}:
                clean_value = {}
            if goal_id:
                clean_value["id"] = goal_id
            changed = payload.get("set")
            if isinstance(changed, Mapping):
                clean_value.update(copy.deepcopy(dict(changed)))
            removed = payload.get("unset")
            if isinstance(removed, list):
                for key in removed:
                    clean_value.pop(str(key), None)
            appended = payload.get("append")
            if isinstance(appended, Mapping):
                for key, values in appended.items():
                    if not isinstance(values, list):
                        continue
                    existing = list(clean_value.get(str(key)) or [])
                    existing.extend(copy.deepcopy(values))
                    clean_value[str(key)] = existing
        else:
            clean_value = copy.deepcopy(payload)
        clean_value.setdefault("schema_version", 1)
        plugin_id, namespace = "agent-goal", "goal"
    elif event.type.startswith("team_"):
        # The compatibility adapter is the only Runtime module that knows the
        # retired Team event vocabulary. New Team writes use extension state.
        try:
            from agent_team.projection import apply_team_event
        except ImportError:  # package import style
            from app.agent_team.projection import apply_team_event

        current = _extension_value(snapshot, "agent-team", "team")
        clean_value = apply_team_event(
            current or None,
            event.type,
            event.payload,
            timestamp=event.timestamp,
            seq=event.seq,
        )
        plugin_id, namespace = "agent-team", "team"
    else:
        return event
    return RuntimeEvent(
        seq=event.seq,
        type="extension_state_changed",
        session_id=event.session_id,
        timestamp=event.timestamp,
        run_id=event.run_id,
        payload={
            "plugin_id": plugin_id,
            "namespace": namespace,
            # A sequence-derived revision preserves ordering across multiple
            # legacy events. The next normal CAS write continues from it.
            "revision": max(1, int(event.seq)),
            "value": clean_value,
            "legacy_event_type": event.type,
        },
        schema_version=event.schema_version,
    )


__all__ = ["map_legacy_ui_optional_event", "normalize_legacy_optional_event"]
