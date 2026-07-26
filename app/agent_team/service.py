"""High-level Agent Team control-plane service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import (
    MEMBER_STATES,
    TASK_PRIORITIES,
    TASK_STATUSES,
    AgentTeamConflictError,
    AgentTeamNotFoundError,
    AgentTeamValidationError,
    TeamLimits,
    choice,
    clean_id,
    clean_text,
    new_id,
)
from .store import RuntimeTeamStore


def _positive_env_int(name: str, default: int) -> int:
    try:
        return max(1, int(str(os.getenv(name, str(default)) or default).strip()))
    except (TypeError, ValueError):
        return max(1, int(default))


class AgentTeamService:
    """Manage one flat team per root session through durable semantic events."""

    def __init__(
        self,
        sessions_dir: str | Path,
        *,
        path_resolver=None,
        limits: TeamLimits | None = None,
    ) -> None:
        self.store = RuntimeTeamStore(sessions_dir, path_resolver=path_resolver)
        self.limits = limits or TeamLimits(
            max_members=_positive_env_int("AGENT_TEAM_MAX_MEMBERS", 4),
            max_tasks=_positive_env_int("AGENT_TEAM_MAX_TASKS", 1000),
            max_messages=_positive_env_int("AGENT_TEAM_MAX_MESSAGES", 2000),
            max_permissions=_positive_env_int("AGENT_TEAM_MAX_PERMISSIONS", 500),
            max_message_chars=_positive_env_int("AGENT_TEAM_MAX_MESSAGE_CHARS", 32_000),
        )

    def read_team(self, session_id: str) -> Optional[dict]:
        snapshot = self.store.read_snapshot(clean_id(session_id, "session_id"))
        team = snapshot.get("team")
        return team if isinstance(team, dict) else None

    def create_team(self, session_id: str, title: str = "") -> dict:
        sid = clean_id(session_id, "session_id")
        team_id = new_id("team")
        payload = {
            "team_id": team_id,
            "title": clean_text(title, "title", max_length=200, required=False),
            "status": "active",
            "max_members": self.limits.max_members,
        }

        def guard(snapshot: dict) -> None:
            current = snapshot.get("team")
            if isinstance(current, dict) and current.get("status") != "archived":
                raise AgentTeamConflictError("this session already has an active team")

        self.store.append_event(sid, "team_created", payload, guard=guard)
        return self._required_team(sid)

    def add_member(
        self,
        session_id: str,
        *,
        name: str,
        role: str,
        prompt: str = "",
        child_session_id: str = "",
        model_profile_id: str = "",
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        member_id = new_id("member")
        member_name = clean_text(name, "name", max_length=80)
        payload = {
            "member_id": member_id,
            "name": member_name,
            "role": clean_text(role, "role", max_length=120),
            "prompt": clean_text(prompt, "prompt", max_length=16_000, required=False),
            "child_session_id": clean_id(child_session_id, "child_session_id") if child_session_id else "",
            "model_profile_id": clean_text(
                model_profile_id, "model_profile_id", max_length=160, required=False
            ),
            "state": "starting",
        }

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            self._require_active(team)
            members = team.get("members") or {}
            active = [m for m in members.values() if m.get("state") not in {"stopped", "failed"}]
            if len(active) >= self.limits.max_members:
                raise AgentTeamConflictError("team member limit reached")
            if any(str(m.get("name") or "").casefold() == member_name.casefold() for m in members.values()):
                raise AgentTeamConflictError(f"member name already exists: {member_name}")

        self.store.append_event(sid, "team_member_added", payload, guard=guard)
        return self._required_team(sid)["members"][member_id]

    def set_member_state(
        self,
        session_id: str,
        member_id: str,
        state: str,
        *,
        detail: str = "",
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        mid = clean_id(member_id, "member_id")
        next_state = choice(state, "state", MEMBER_STATES)
        payload = {
            "member_id": mid,
            "state": next_state,
            "detail": clean_text(detail, "detail", max_length=2000, required=False),
        }

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            if team.get("status") in {"stopped", "archived"}:
                raise AgentTeamConflictError("team is no longer mutable")
            self._member(team, mid)

        self.store.append_event(sid, "team_member_state_changed", payload, guard=guard)
        return self._required_team(sid)["members"][mid]

    def remove_member(self, session_id: str, member_id: str, *, reason: str = "") -> dict:
        sid = clean_id(session_id, "session_id")
        mid = clean_id(member_id, "member_id")

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            if team.get("status") in {"stopped", "archived"}:
                raise AgentTeamConflictError("team is no longer mutable")
            member = self._member(team, mid)
            assigned = [
                task_id
                for task_id, task in (team.get("tasks") or {}).items()
                if task.get("assignee_id") == mid and task.get("status") == "in_progress"
            ]
            if assigned:
                raise AgentTeamConflictError(
                    f"release member task before removal: {assigned[0]}"
                )
            if member.get("removed"):
                raise AgentTeamConflictError("member is already removed")

        self.store.append_event(
            sid,
            "team_member_removed",
            {
                "member_id": mid,
                "reason": clean_text(reason, "reason", max_length=2000, required=False),
            },
            guard=guard,
        )
        return self._required_team(sid)["members"][mid]

    def bind_member_session(
        self,
        session_id: str,
        member_id: str,
        child_session_id: str,
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        mid = clean_id(member_id, "member_id")
        child_id = clean_id(child_session_id, "child_session_id")

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            self._require_active(team)
            member = self._member(team, mid)
            existing = str(member.get("child_session_id") or "")
            if existing and existing != child_id:
                raise AgentTeamConflictError("member is already bound to another session")
            for other_id, other in (team.get("members") or {}).items():
                if other_id != mid and str(other.get("child_session_id") or "") == child_id:
                    raise AgentTeamConflictError("child session is already bound to another member")

        self.store.append_event(
            sid,
            "team_member_updated",
            {"member_id": mid, "child_session_id": child_id},
            guard=guard,
        )
        return self._required_team(sid)["members"][mid]

    def create_task(
        self,
        session_id: str,
        *,
        title: str,
        description: str = "",
        priority: str = "normal",
        depends_on: Iterable[str] = (),
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        task_id = new_id("teamtask")
        dependencies = [clean_id(item, "depends_on") for item in depends_on]
        if task_id in dependencies:
            raise AgentTeamValidationError("task cannot depend on itself")
        payload = {
            "task_id": task_id,
            "title": clean_text(title, "title", max_length=300),
            "description": clean_text(description, "description", max_length=32_000, required=False),
            "priority": choice(priority, "priority", TASK_PRIORITIES, default="normal"),
            "depends_on": list(dict.fromkeys(dependencies)),
            "status": "pending",
            "assignee_id": None,
        }

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            self._require_active(team)
            tasks = team.get("tasks") or {}
            if len(tasks) >= self.limits.max_tasks:
                raise AgentTeamConflictError("team task limit reached")
            missing = [dep for dep in payload["depends_on"] if dep not in tasks]
            if missing:
                raise AgentTeamNotFoundError(f"dependency task not found: {missing[0]}")

        self.store.append_event(sid, "team_task_created", payload, guard=guard)
        return self._required_team(sid)["tasks"][task_id]

    def update_task(
        self,
        session_id: str,
        task_id: str,
        *,
        status: str,
        result: str = "",
        detail: str = "",
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        tid = clean_id(task_id, "task_id")
        next_status = choice(status, "status", TASK_STATUSES)
        payload = {
            "task_id": tid,
            "status": next_status,
            "result": clean_text(result, "result", max_length=64_000, required=False),
            "detail": clean_text(detail, "detail", max_length=4000, required=False),
        }

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            if team.get("status") in {"stopped", "archived"}:
                raise AgentTeamConflictError("team is no longer mutable")
            task = self._task(team, tid)
            current_status = str(task.get("status") or "pending")
            if current_status in {"completed", "cancelled"} and next_status != current_status:
                raise AgentTeamConflictError("terminal task status cannot be reopened")

        self.store.append_event(sid, "team_task_updated", payload, guard=guard)
        return self._required_team(sid)["tasks"][tid]

    def claim_task(self, session_id: str, task_id: str, member_id: str) -> dict:
        sid = clean_id(session_id, "session_id")
        tid = clean_id(task_id, "task_id")
        mid = clean_id(member_id, "member_id")

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            self._require_active(team)
            member = self._member(team, mid)
            if member.get("state") in {"stopping", "stopped", "failed"}:
                raise AgentTeamConflictError("member cannot claim work in its current state")
            owned = [
                existing_id
                for existing_id, existing in (team.get("tasks") or {}).items()
                if existing_id != tid
                and existing.get("assignee_id") == mid
                and existing.get("status") == "in_progress"
            ]
            if owned:
                raise AgentTeamConflictError(
                    f"member already owns in-progress task: {owned[0]}"
                )
            task = self._task(team, tid)
            if task.get("status") not in {"pending", "blocked"}:
                raise AgentTeamConflictError("task is not claimable")
            if task.get("assignee_id"):
                raise AgentTeamConflictError("task is already claimed")
            tasks = team.get("tasks") or {}
            incomplete = [dep for dep in task.get("depends_on") or [] if (tasks.get(dep) or {}).get("status") != "completed"]
            if incomplete:
                raise AgentTeamConflictError(f"task dependency is incomplete: {incomplete[0]}")

        self.store.append_event(
            sid,
            "team_task_claimed",
            {"task_id": tid, "member_id": mid},
            guard=guard,
        )
        return self._required_team(sid)["tasks"][tid]

    def claim_next_task(self, session_id: str, member_id: str) -> Optional[dict]:
        """Dependency-aware CAS claim of the highest-priority ready task."""
        sid = clean_id(session_id, "session_id")
        mid = clean_id(member_id, "member_id")
        priority_rank = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        # Another scheduler can win between the read and claim. Retry against
        # the freshly projected task graph instead of assigning twice.
        for _ in range(16):
            team = self._required_team(sid)
            member = self._member(team, mid)
            if member.get("state") not in {"idle", "starting"}:
                return None
            if any(
                task.get("assignee_id") == mid and task.get("status") == "in_progress"
                for task in (team.get("tasks") or {}).values()
                if isinstance(task, dict)
            ):
                return None
            tasks = team.get("tasks") or {}
            ready = []
            for task in tasks.values():
                if not isinstance(task, dict):
                    continue
                if task.get("status") != "pending":
                    continue
                if task.get("assignee_id"):
                    continue
                dependencies = task.get("depends_on") or []
                if any(
                    (tasks.get(dep) or {}).get("status") != "completed"
                    for dep in dependencies
                ):
                    continue
                ready.append(task)
            if not ready:
                return None
            ready.sort(
                key=lambda task: (
                    priority_rank.get(str(task.get("priority") or "normal"), 2),
                    int(task.get("seq") or 0),
                    str(task.get("task_id") or ""),
                )
            )
            candidate = str(ready[0].get("task_id") or "")
            try:
                return self.claim_task(sid, candidate, mid)
            except AgentTeamConflictError:
                continue
        return None

    def release_task(self, session_id: str, task_id: str, member_id: str, reason: str = "") -> dict:
        sid = clean_id(session_id, "session_id")
        tid = clean_id(task_id, "task_id")
        mid = clean_id(member_id, "member_id")

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            if team.get("status") in {"stopped", "archived"}:
                raise AgentTeamConflictError("team is no longer mutable")
            task = self._task(team, tid)
            if task.get("assignee_id") != mid:
                raise AgentTeamConflictError("only the current assignee may release this task")
            if task.get("status") != "in_progress":
                raise AgentTeamConflictError("only an in-progress task may be released")

        self.store.append_event(
            sid,
            "team_task_released",
            {
                "task_id": tid,
                "member_id": mid,
                "reason": clean_text(reason, "reason", max_length=2000, required=False),
            },
            guard=guard,
        )
        return self._required_team(sid)["tasks"][tid]

    def send_message(
        self,
        session_id: str,
        *,
        sender_id: str,
        recipient_ids: Iterable[str],
        content: str,
        reply_to: str = "",
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        sender = clean_id(sender_id, "sender_id")
        recipients = list(dict.fromkeys(clean_id(x, "recipient_id") for x in recipient_ids))
        if not recipients:
            raise AgentTeamValidationError("at least one recipient is required")
        message_id = new_id("teammsg")
        payload = {
            "message_id": message_id,
            "sender_id": sender,
            "recipient_ids": recipients,
            "content": clean_text(content, "content", max_length=self.limits.max_message_chars),
            "reply_to": clean_id(reply_to, "reply_to") if reply_to else "",
            "status": "queued",
        }

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            self._require_active(team)
            if len(team.get("messages") or {}) >= self.limits.max_messages:
                raise AgentTeamConflictError("team message limit reached")
            if sender != "lead":
                self._member(team, sender)
            for recipient in recipients:
                if recipient != "lead":
                    self._member(team, recipient)
            if payload["reply_to"] and payload["reply_to"] not in (team.get("messages") or {}):
                raise AgentTeamNotFoundError("reply_to message not found")

        self.store.append_event(sid, "team_message_enqueued", payload, guard=guard)
        return self._required_team(sid)["messages"][message_id]

    def update_message_delivery(
        self,
        session_id: str,
        message_id: str,
        recipient_id: str,
        status: str,
        *,
        error: str = "",
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        msg_id = clean_id(message_id, "message_id")
        recipient = clean_id(recipient_id, "recipient_id")
        mapping = {
            "delivering": "team_message_delivery_started",
            "delivered": "team_message_delivered",
            "consumed": "team_message_consumed",
            "failed": "team_message_delivery_failed",
        }
        event_type = mapping.get(str(status or "").strip().lower())
        if not event_type:
            raise AgentTeamValidationError("invalid message delivery status")

        def guard(snapshot: dict) -> None:
            message = self._message(self._team_from_snapshot(snapshot), msg_id)
            if recipient not in (message.get("recipient_ids") or []):
                raise AgentTeamConflictError("recipient is not addressed by this message")
            current = str(
                (((message.get("deliveries") or {}).get(recipient) or {}).get("status") or "queued")
            )
            next_status = {
                "team_message_delivery_started": "delivering",
                "team_message_delivered": "delivered",
                "team_message_consumed": "consumed",
                "team_message_delivery_failed": "failed",
            }[event_type]
            transitions = {
                "queued": {"delivering", "delivered", "failed"},
                "delivering": {"delivered", "failed"},
                "delivered": {"consumed"},
                "failed": {"delivering", "delivered"},
                "consumed": set(),
            }
            if next_status != current and next_status not in transitions.get(current, set()):
                raise AgentTeamConflictError(
                    f"invalid delivery transition: {current} -> {next_status}"
                )

        self.store.append_event(
            sid,
            event_type,
            {
                "message_id": msg_id,
                "recipient_id": recipient,
                "error": clean_text(error, "error", max_length=4000, required=False),
            },
            guard=guard,
        )
        return self._required_team(sid)["messages"][msg_id]

    def request_permission(
        self,
        session_id: str,
        *,
        member_id: str,
        action: str,
        resource: str = "",
        detail: str = "",
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        mid = clean_id(member_id, "member_id")
        permission_id = new_id("teamperm")
        payload = {
            "permission_id": permission_id,
            "member_id": mid,
            "action": clean_text(action, "action", max_length=300),
            "resource": clean_text(resource, "resource", max_length=4000, required=False),
            "detail": clean_text(detail, "detail", max_length=8000, required=False),
        }

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            self._require_active(team)
            if len(team.get("permissions") or {}) >= self.limits.max_permissions:
                raise AgentTeamConflictError("team permission limit reached")
            self._member(team, mid)

        self.store.append_event(sid, "team_permission_requested", payload, guard=guard)
        return self._required_team(sid)["permissions"][permission_id]

    def resolve_permission(
        self,
        session_id: str,
        permission_id: str,
        *,
        decision: str,
        resolved_by: str = "lead",
        reason: str = "",
    ) -> dict:
        sid = clean_id(session_id, "session_id")
        permission = clean_id(permission_id, "permission_id")
        resolution = choice(decision, "decision", {"allowed", "denied"})
        resolver = clean_id(resolved_by, "resolved_by")

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            if team.get("status") in {"stopped", "archived"}:
                raise AgentTeamConflictError("team is no longer mutable")
            request = (team.get("permissions") or {}).get(permission)
            if not isinstance(request, dict):
                raise AgentTeamNotFoundError(f"permission not found: {permission}")
            if request.get("status") != "pending":
                raise AgentTeamConflictError("permission has already been resolved")
            if resolver != "lead":
                self._member(team, resolver)

        self.store.append_event(
            sid,
            "team_permission_resolved",
            {
                "permission_id": permission,
                "status": resolution,
                "decision": resolution,
                "resolved_by": resolver,
                "reason": clean_text(reason, "reason", max_length=4000, required=False),
            },
            guard=guard,
        )
        return self._required_team(sid)["permissions"][permission]

    def consume_permission(
        self,
        session_id: str,
        *,
        member_id: str,
        action: str,
        resource: str = "",
    ) -> dict | None:
        """Atomically consume one matching one-shot permission, if available."""

        sid = clean_id(session_id, "session_id")
        mid = clean_id(member_id, "member_id")
        requested_action = clean_text(action, "action", max_length=300)
        requested_resource = clean_text(
            resource, "resource", max_length=4000, required=False
        )
        event_payload = {
            "permission_id": "",
            "member_id": mid,
            "action": requested_action,
            "resource": requested_resource,
        }

        class _NoMatchingPermission(Exception):
            pass

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            self._member(team, mid)
            for permission_id, permission in (team.get("permissions") or {}).items():
                if not isinstance(permission, dict):
                    continue
                if permission.get("status") != "allowed":
                    continue
                if str(permission.get("member_id") or "") != mid:
                    continue
                allowed_action = str(permission.get("action") or "")
                if allowed_action not in {requested_action, "*"}:
                    continue
                allowed_resource = str(permission.get("resource") or "")
                if allowed_resource and allowed_resource not in {requested_resource, "*"}:
                    continue
                event_payload["permission_id"] = str(permission_id)
                return
            raise _NoMatchingPermission()

        try:
            self.store.append_event(
                sid,
                "team_permission_consumed",
                event_payload,
                guard=guard,
            )
        except _NoMatchingPermission:
            return None
        return self._required_team(sid)["permissions"].get(
            event_payload["permission_id"]
        )

    def request_shutdown(self, session_id: str, reason: str = "") -> dict:
        sid = clean_id(session_id, "session_id")

        def guard(snapshot: dict) -> None:
            self._require_active(self._team_from_snapshot(snapshot))

        self.store.append_event(
            sid,
            "team_shutdown_requested",
            {"reason": clean_text(reason, "reason", max_length=2000, required=False)},
            guard=guard,
        )
        return self._required_team(sid)

    def complete_shutdown(self, session_id: str) -> dict:
        sid = clean_id(session_id, "session_id")

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            if team.get("status") != "shutting_down":
                raise AgentTeamConflictError("team shutdown has not been requested")

        self.store.append_event(sid, "team_shutdown_completed", {}, guard=guard)
        return self._required_team(sid)

    def archive_team(self, session_id: str) -> dict:
        sid = clean_id(session_id, "session_id")

        def guard(snapshot: dict) -> None:
            team = self._team_from_snapshot(snapshot)
            if team.get("status") != "stopped":
                raise AgentTeamConflictError("complete shutdown before archiving")

        self.store.append_event(sid, "team_archived", {}, guard=guard)
        return self._required_team(sid)

    def list_inbox(self, session_id: str, recipient_id: str, *, include_consumed: bool = False) -> list[dict]:
        recipient = clean_id(recipient_id, "recipient_id")
        team = self._required_team(clean_id(session_id, "session_id"))
        rows = []
        for message in (team.get("messages") or {}).values():
            if recipient not in (message.get("recipient_ids") or []):
                continue
            delivery = (message.get("deliveries") or {}).get(recipient) or {}
            if not include_consumed and delivery.get("status") == "consumed":
                continue
            rows.append(message)
        return sorted(rows, key=lambda row: int(row.get("seq") or 0))

    def _required_team(self, session_id: str) -> dict:
        team = self.read_team(session_id)
        if not isinstance(team, dict):
            raise AgentTeamNotFoundError("team not found")
        return team

    @staticmethod
    def _team_from_snapshot(snapshot: dict) -> dict:
        team = snapshot.get("team")
        if not isinstance(team, dict):
            raise AgentTeamNotFoundError("team not found")
        return team

    @staticmethod
    def _require_active(team: dict) -> None:
        if team.get("status") != "active":
            raise AgentTeamConflictError("team is not active")

    @staticmethod
    def _member(team: dict, member_id: str) -> dict:
        member = (team.get("members") or {}).get(member_id)
        if not isinstance(member, dict):
            raise AgentTeamNotFoundError(f"member not found: {member_id}")
        return member

    @staticmethod
    def _task(team: dict, task_id: str) -> dict:
        task = (team.get("tasks") or {}).get(task_id)
        if not isinstance(task, dict):
            raise AgentTeamNotFoundError(f"task not found: {task_id}")
        return task

    @staticmethod
    def _message(team: dict, message_id: str) -> dict:
        message = (team.get("messages") or {}).get(message_id)
        if not isinstance(message, dict):
            raise AgentTeamNotFoundError(f"message not found: {message_id}")
        return message
