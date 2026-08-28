"""Agent Team-owned state projection, outside the Runtime V2 core."""
from __future__ import annotations

import copy
from typing import Any, Mapping


def apply_team_event(
    current: Any,
    event_type: str,
    payload: Mapping[str, Any] | None,
    *,
    timestamp: str,
    seq: int,
) -> dict | None:
    """Apply one Team semantic action to plugin-owned state."""

    data = copy.deepcopy(dict(payload or {}))
    kind = str(event_type or "").strip()
    if kind == "team_created":
        return {
            "team_id": str(data.get("team_id") or ""),
            "title": str(data.get("title") or ""),
            "status": str(data.get("status") or "active"),
            "max_members": int(data.get("max_members") or 4),
            "created_at": timestamp,
            "updated_at": timestamp,
            "seq": seq,
            "members": {},
            "tasks": {},
            "messages": {},
            "permissions": {},
        }
    if not isinstance(current, Mapping):
        return None
    team = copy.deepcopy(dict(current))
    team["updated_at"] = timestamp
    team["seq"] = seq
    team["last_event"] = kind

    if kind == "team_status_changed":
        if data.get("status"):
            team["status"] = str(data["status"])
        if "detail" in data:
            team["status_detail"] = data.get("detail")
    elif kind == "team_member_added":
        member_id = str(data.get("member_id") or "").strip()
        if member_id:
            member = dict(data)
            member.update(
                member_id=member_id,
                state=str(member.get("state") or "starting"),
                created_at=timestamp,
                updated_at=timestamp,
                seq=seq,
            )
            team.setdefault("members", {})[member_id] = member
    elif kind in {"team_member_updated", "team_member_state_changed", "team_member_removed"}:
        member_id = str(data.get("member_id") or "").strip()
        member = (team.get("members") or {}).get(member_id)
        if isinstance(member, dict):
            if kind == "team_member_removed":
                member.update(state="stopped", removed=True, removed_at=timestamp)
            elif kind == "team_member_updated":
                member.update({key: value for key, value in data.items() if key != "member_id"})
            else:
                member["state"] = str(data.get("state") or member.get("state") or "idle")
                if "detail" in data:
                    member["detail"] = data.get("detail")
            member.update(updated_at=timestamp, seq=seq)
    elif kind == "team_task_created":
        task_id = str(data.get("task_id") or "").strip()
        if task_id:
            task = dict(data)
            task.update(
                task_id=task_id,
                status=str(task.get("status") or "pending"),
                created_at=timestamp,
                updated_at=timestamp,
                seq=seq,
            )
            team.setdefault("tasks", {})[task_id] = task
    elif kind in {"team_task_updated", "team_task_claimed", "team_task_released"}:
        task_id = str(data.get("task_id") or "").strip()
        task = (team.get("tasks") or {}).get(task_id)
        if isinstance(task, dict):
            if kind == "team_task_claimed":
                task.update(
                    assignee_id=str(data.get("member_id") or "") or None,
                    status="in_progress",
                    claimed_at=timestamp,
                )
            elif kind == "team_task_released":
                task.update(
                    assignee_id=None,
                    status="pending",
                    released_at=timestamp,
                    release_reason=data.get("reason") or "",
                )
            else:
                task.update({key: value for key, value in data.items() if key != "task_id"})
                if task.get("status") in {"completed", "cancelled"}:
                    task["completed_at"] = timestamp
            task.update(updated_at=timestamp, seq=seq)
    elif kind == "team_message_enqueued":
        message_id = str(data.get("message_id") or "").strip()
        if message_id:
            message = dict(data)
            recipients = [str(value) for value in message.get("recipient_ids") or [] if str(value)]
            message.update(
                recipient_ids=recipients,
                status="queued",
                deliveries={
                    recipient: {"status": "queued", "updated_at": timestamp}
                    for recipient in recipients
                },
                created_at=timestamp,
                updated_at=timestamp,
                seq=seq,
            )
            team.setdefault("messages", {})[message_id] = message
    elif kind in {
        "team_message_delivery_started",
        "team_message_delivered",
        "team_message_consumed",
        "team_message_delivery_failed",
    }:
        states_by_event = {
            "team_message_delivery_started": "delivering",
            "team_message_delivered": "delivered",
            "team_message_consumed": "consumed",
            "team_message_delivery_failed": "failed",
        }
        message_id = str(data.get("message_id") or "").strip()
        recipient_id = str(data.get("recipient_id") or "").strip()
        message = (team.get("messages") or {}).get(message_id)
        if isinstance(message, dict) and recipient_id:
            delivery = message.setdefault("deliveries", {}).setdefault(recipient_id, {})
            delivery.update(status=states_by_event[kind], updated_at=timestamp, seq=seq)
            if data.get("error"):
                delivery["error"] = data["error"]
            states = [str(value.get("status") or "queued") for value in message["deliveries"].values()]
            if states and all(state == "consumed" for state in states):
                message["status"] = "consumed"
            elif "failed" in states:
                message["status"] = "failed"
            elif states and all(state in {"delivered", "consumed"} for state in states):
                message["status"] = "delivered"
            elif "delivering" in states:
                message["status"] = "delivering"
            else:
                message["status"] = "queued"
            message.update(updated_at=timestamp, seq=seq)
    elif kind == "team_permission_requested":
        permission_id = str(data.get("permission_id") or "").strip()
        if permission_id:
            permission = dict(data)
            permission.update(
                permission_id=permission_id,
                status="pending",
                created_at=timestamp,
                updated_at=timestamp,
                seq=seq,
            )
            team.setdefault("permissions", {})[permission_id] = permission
    elif kind in {"team_permission_resolved", "team_permission_consumed"}:
        permission_id = str(data.get("permission_id") or "").strip()
        permission = (team.get("permissions") or {}).get(permission_id)
        if isinstance(permission, dict):
            permission.update({key: value for key, value in data.items() if key != "permission_id"})
            permission["updated_at"] = timestamp
            if kind == "team_permission_resolved":
                permission["resolved_at"] = timestamp
            else:
                permission.update(status="consumed", consumed_at=timestamp)
            permission["seq"] = seq
    elif kind == "team_shutdown_requested":
        team.update(
            status="shutting_down",
            shutdown_requested_at=timestamp,
            shutdown_reason=data.get("reason") or "",
        )
    elif kind == "team_shutdown_completed":
        team.update(status="stopped", shutdown_completed_at=timestamp)
        for member in (team.get("members") or {}).values():
            if isinstance(member, dict) and member.get("state") not in {"failed", "stopped"}:
                member.update(state="stopped", updated_at=timestamp)
    elif kind == "team_archived":
        team.update(status="archived", archived_at=timestamp)
    return team


__all__ = ["apply_team_event"]
