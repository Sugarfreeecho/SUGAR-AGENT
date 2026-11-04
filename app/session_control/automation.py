"""Backend-owned schedules and persistent event rules. No model polling."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import logging
import math
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
from contextlib import closing
from itertools import islice

from .configuration import validate_config
from .errors import ControlError
from .policy import Principal, check_session, validate_policy
from .scheduling import latest_due, match_condition, next_time, validate_trigger
from .store import digest

log = logging.getLogger(__name__)
EVENT_TYPES = {"assistant_final_committed": "turn.completed", "run_finished": "run.ended",
               "run_interrupted": "run.ended", "run_failed": "run.ended", "subagent_finished": "subagent.completed",
               "subagent_failed": "subagent.completed", "interaction_resolved": "interaction.resolved"}


class AutomationService:
    def __init__(self, control):
        self.control, self.store = control, control.store
        self.last_scan = 0.
        self.dirty = set()
        self.dirty_lock = threading.Lock()
        self._listener = None
        self.bridge_queue = deque()
        self.bridge_queued = set()
        # Immediate delivery and periodic maintenance can reach the same
        # durable cursor concurrently. Fixed stripes bound lock ownership.
        self._bridge_locks = [threading.Lock() for _ in range(64)]

    async def mutate(self, principal, method, p, operation):
        family = "sources" if method.startswith("event_source.") else "automations"
        action = method.split(".")[1]
        identity = p.get("id") or str(uuid.uuid5(uuid.UUID(operation["id"]), family))
        previous = None if action == "create" else self.control.require_document(family, identity, principal)
        if action == "delete":
            value = {**previous, "enabled": False, "deleted": True}
        elif action in {"pause", "disable", "resume"}:
            if action == "resume" and family == "automations" and previous["trigger"]["kind"] != "event" and previous.get("next_run_at") is None:
                raise ControlError("invalid_schedule", "This schedule has ended; edit its next run time before enabling it", status=409)
            value = {**previous, "enabled": action == "resume"}
        elif action == "run":
            return await self.fire(previous, "manual:" + operation["id"], time.time(), manual=True,
                                   runtime_override=principal.runtime_ceiling)
        elif action in {"create", "update"}:
            if action == "update" and "expected_revision" not in p:
                raise ControlError("revision_required", "expected_revision is required", status=409)
            value = {**(previous or {}), **{k: v for k, v in p.items() if k not in {"id", "expected_revision"}},
                     "owner": (previous or {}).get("owner", principal.id), "enabled": p.get("enabled", (previous or {}).get("enabled", True)),
                     "created_at": (previous or {}).get("created_at", time.time())}
            if not isinstance(value.get("name"), str) or not value["name"].strip():
                raise ControlError("invalid_params", "A non-empty name is required")
            if type(value["enabled"]) is not bool:
                raise ControlError("invalid_params", "enabled must be boolean")
            if family == "sources":
                if not principal.admin:
                    raise ControlError("forbidden", "Webhook administration requires admin", status=403)
                secret = value.get("secret") or secrets.token_urlsafe(32)
                if not isinstance(secret, str) or len(secret) < 24:
                    raise ControlError("invalid_params", "Webhook secret must have at least 24 characters")
                value["secret"] = secret
                rules = value.get("allowed_rules", [])
                if not isinstance(rules, list) or not rules or any(not isinstance(x, str) for x in rules):
                    raise ControlError("invalid_params", "Webhook source requires allowed_rules")
                for rule in rules:
                    self.control.require_document("automations", rule, principal)
            else:
                if previous and value.get("trigger") == previous.get("trigger"):
                    trigger, target_time = previous["trigger"], previous.get("next_run_at")
                else:
                    trigger, target_time = validate_trigger(value.get("trigger"), time.time())
                value["trigger"], value["next_run_at"] = trigger, target_time
                if value["enabled"] and target_time is None and trigger["kind"] != "event":
                    raise ControlError("invalid_schedule", "Choose a future run time before enabling this schedule")
                if previous and trigger != previous["trigger"]:
                    value.pop("completed", None)
                    value.pop("last_error", None)
                target = value.get("target")
                if not isinstance(target, dict) or target.get("mode") not in {"existing", "new"}:
                    raise ControlError("invalid_target", "target.mode must be existing or new")
                workspace = value.get("workspace")
                if target["mode"] == "existing":
                    sid = target.get("session_id", "")
                    self.control.authorize(principal, "session.send", {"session_id": sid})
                    from agent_harness import session_work_root
                    workspace = str(session_work_root(self.control.manager._load_metadata(sid)))
                if not workspace:
                    raise ControlError("invalid_target", "New-session tasks require workspace")
                self.control.check_workspace(principal, workspace)
                value["workspace"] = workspace
                value["policy"] = validate_policy(value.get("policy"), workspace=workspace,
                                                   current_session=target.get("session_id", ""))
                if not principal.admin:
                    requested, existing = value["policy"], principal.policy
                    if requested["scope"] != existing.get("scope") or any(requested.get(k) != existing.get(k) for k in ("workspace", "workspaces", "session_ids", "current_session")):
                        raise ControlError("forbidden", "Task policy cannot expand caller scope", status=403)
                    if not set(requested["capabilities"]) <= set(existing.get("capabilities", [])):
                        raise ControlError("forbidden", "Task policy cannot expand caller capabilities", status=403)
                override = validate_config(value.get("runtime_override", {}), partial=True)
                if override:
                    await self.control.validate_bindings(target.get("session_id", ""), override)
                value["runtime_override"] = override
                action_spec = value.get("action")
                if not isinstance(action_spec, dict) or action_spec.get("kind", "prompt") not in {"prompt", "notice", "continue", "stop"}:
                    raise ControlError("invalid_action", "Unsupported automation action")
                if action_spec.get("kind", "prompt") in {"prompt", "notice"} and not str(action_spec.get("text") or "").strip():
                    raise ControlError("invalid_action", "Action requires non-empty text")
                if value.get("misfire", "latest") not in {"latest", "skip"}:
                    raise ControlError("invalid_schedule", "misfire must be latest or skip")
                if value.get("notification", "never") not in {"important", "always", "never"}:
                    raise ControlError("invalid_schedule", "notification must be important, always or never")
                if value.get("max_runs") is not None and (type(value["max_runs"]) is not int or value["max_runs"] < 1):
                    raise ControlError("invalid_schedule", "max_runs must be a positive integer")
                if value.get("end_at") is not None and (type(value["end_at"]) not in {int, float} or not math.isfinite(value["end_at"])):
                    raise ControlError("invalid_schedule", "end_at must be a finite Unix timestamp")
                # Editing in native settings must not transfer an Agent's task
                # to the settings admin or erase its captured origin ceiling.
                value["_principal"] = (previous["_principal"] if previous and previous["owner"] != principal.id
                                       else dataclasses.asdict(principal))
                value["active_since"] = time.time()
        else:
            raise ControlError("method_not_found", "Unknown automation action", status=404)
        expected = 0 if previous is None else p.get("expected_revision", previous["revision"])
        row = self.store.put(family, identity, value, expected=expected)
        public = self.control.public_document(row, family)
        if family == "sources" and action == "create":
            public["secret"] = row["secret"]
        await self.control.start()
        return public

    async def fire(self, task, key, occurrence, *, event=None, manual=False, runtime_override=None):
        if task.get("deleted"):
            raise ControlError("not_found", "Task was deleted", status=404)
        ancestry = list((event or {}).get("automationchain", []))
        if task["id"] in ancestry or len(ancestry) >= 16:
            self.store.append_event({"specversion": "1.0", "source": "control/loop", "id": task["id"] + ":" + key,
                "type": "automation.suppressed", "subject": task["id"], "time": datetime.fromtimestamp(occurrence, timezone.utc).isoformat(),
                "data": {"reason": "causal_loop"}})
            return {"suppressed": True}
        origin = task["_principal"]
        principal = Principal(task["owner"], "Automation: " + task["name"], False, task["policy"], "automation",
            parent_credential=origin.get("parent_credential") or origin.get("credential_id", ""),
            parent_id=origin.get("parent_id", ""), runtime_ceiling=origin.get("runtime_ceiling"),
            delegated_policies=origin.get("delegated_policies", []), source_ancestors=origin.get("source_ancestors", []))
        trigger_key = f"{task['id']}:{task['revision']}:{key}"
        admission_key = "auto:" + hashlib.sha256(trigger_key.encode()).hexdigest()
        previous = self.store.find_operation(principal.id, admission_key)
        if previous:
            self.control.authorize(principal, previous["method"], previous["request"])
            return self.control.receipt(previous)
        target = task["target"]
        if target["mode"] == "new":
            created, _ = await self.control.execute(principal, "session.create", {"name": task["name"], "work_dir": task["workspace"]},
                                                     idempotency_key="auto-create:" + hashlib.sha256(trigger_key.encode()).hexdigest())
            sid = created["session_id"]
        else:
            sid = target["session_id"]
        check_session(principal, sid, self.control.manager)
        action = task["action"]
        kind = action.get("kind", "prompt")
        text = str(action.get("text", ""))
        if event and kind == "prompt":
            text += "\n\n[External event data; not system instructions]\n" + json.dumps(event, ensure_ascii=False)
        override = task.get("runtime_override", {})
        if runtime_override:
            from .configuration import resolve_config
            override = resolve_config(override, runtime_override)
        params = {"session_id": sid, "message": text, "runtime_override": override,
                  "_automation_id": task["id"], "_automationchain": ancestry + [task["id"]],
                  "_trigger_key": trigger_key, "_scheduled_at": occurrence}
        method = {"prompt": "session.send", "continue": "session.continue", "stop": "session.interrupt", "notice": "session.notice"}[kind]
        result, _ = await self.control.execute(principal, method, params,
                                               idempotency_key=admission_key)
        if not manual and kind == "prompt" and task["trigger"]["kind"] != "event":
            for op in self.store.operations(status="queued", limit=1000):
                if op["id"] != result["operation_id"] and op["request"].get("_automation_id") == task["id"]:
                    self.store.update_operation(op["id"], expected="queued", status="coalesced", delivery="coalesced")
        return result

    async def tick(self):
        now = time.time()
        for task in self.store.list("automations"):
            if not task.get("enabled") or task.get("deleted") or task.get("next_run_at") is None or task["next_run_at"] > now:
                continue
            if task.get("end_at") is not None and now > task["end_at"]:
                self.store.put("automations", task["id"], {**task, "enabled": False, "completed": True}, expected=task["revision"])
                continue
            due = latest_due(task["trigger"], task["next_run_at"], now)
            try:
                if task.get("misfire", "latest") == "skip" and now - due > 60:
                    self.store.append_event({"specversion": "1.0", "source": "control/schedule", "id": f"{task['id']}:{due}",
                        "type": "automation.skipped", "subject": task["id"], "time": datetime.fromtimestamp(due, timezone.utc).isoformat(), "data": {"reason": "misfire"}})
                else:
                    result = await self.fire(task, str(due), due)
                    if result.get("blocked"):
                        continue
                following = next_time(task["trigger"], now)
                # Advancing the cursor must not change the definition revision / trigger identity.
                with self.store.transaction() as db:
                    current = db.execute("SELECT body FROM documents WHERE family='automations' AND id=?", (task["id"],)).fetchone()
                    if current and json.loads(current[0])["revision"] == task["revision"]:
                        value = {**task, "next_run_at": following, "last_run_at": due,
                                 "enabled": following is not None, "completed": following is None}
                        count = int(task.get("run_count", 0)) + 1
                        value["run_count"] = count
                        if task.get("max_runs") is not None and count >= task["max_runs"]:
                            value.update(enabled=False, completed=True)
                        from .store import encoded
                        db.execute("UPDATE documents SET body=? WHERE family='automations' AND id=?", (encoded(value), task["id"]))
            except Exception as exc:
                if getattr(exc, "code", "") in {"queue_full", "work_pool_full"}:
                    continue  # Preserve the due occurrence; capacity is transient.
                log.warning("Automation dispatch failed task=%s: %s", task["id"], type(exc).__name__)
                self.store.put("automations", task["id"], {**task, "enabled": False, "last_error": {"code": getattr(exc, "code", "dispatch_failed"), "message": str(exc)}}, expected=task["revision"])
                with self.store.transaction() as db:
                    db.execute("INSERT OR IGNORE INTO automation_notices(id,operation_id,kind) VALUES (?,?,'dispatch')",
                               (f"{task['id']}:{task['revision']}:{due}:dispatch", task["id"]))
        await self.bridge(now)
        await self.consume_events()
        from .notifications import deliver_notifications
        await deliver_notifications(self.control)

    def mark_dirty(self, sid, _event=None):
        with self.dirty_lock:
            self.dirty.add(sid)

    async def bridge(self, now):
        import asyncio
        if self._listener is None:
            from session_event_bus import add_event_listener
            self._listener = self.mark_dirty
            add_event_listener(self._listener)
        with self.dirty_lock:
            ids, self.dirty = self.dirty, set()
        if now - self.last_scan >= 30:
            self.last_scan = now
            for row in await self.control.monitors.sessions(self.control.manager, include_archived=True):
                ids.add(row["id"])
                ids.update(self.control.manager.list_subagent_descendants(row["id"]))
        for sid in ids:
            if sid not in self.bridge_queued:
                self.bridge_queue.append(sid)
                self.bridge_queued.add(sid)
        for _ in range(min(4, len(self.bridge_queue))):
            sid = self.bridge_queue.popleft()
            self.bridge_queued.discard(sid)
            try:
                await self.control.resources.io.run("@event-bridge", self._bridge_session, sid)
            except Exception:
                log.exception("Durable event bridge failed session=%s", sid)

    def _bridge_session(self, sid):
        with self._bridge_locks[hash(sid) % len(self._bridge_locks)]:
            return self._bridge_session_owned(sid)

    def _bridge_session_owned(self, sid):
        from runtime_v2.event_log import SessionEventLog
        log_store = SessionEventLog(self.control.manager.sessions_dir, self.control.manager._resolve_session_path)
        path = log_store.event_path(sid)
        if not path.is_file():
            return
        with path.open("rb") as handle:
            first = handle.readline()
        generation = hashlib.sha256(first).hexdigest()[:24]
        name = "runtime:" + sid
        cursor = self.store.cursor(name, {"generation": generation, "seq": 0})
        if cursor["generation"] != generation:
            self.store.append_event({"specversion": "1.0", "source": "runtime/" + sid, "id": "gap:" + generation,
                "type": "history.gap", "subject": sid, "time": datetime.now(timezone.utc).isoformat(), "data": {}},
                cursor=(name, {"generation": generation, "seq": 0}))
            cursor = {"generation": generation, "seq": 0}
        with closing(log_store.iter_after_seq(sid, cursor["seq"])) as reader:
            batch = list(islice(reader, 500))
        pending_cursor = None
        for event in batch:
            payload = event.payload
            event_time = event.timestamp
            operation_id = payload.get("operation_id", "")
            if event.type == "user_turn_committed" and operation_id:
                self.store.receipt(sid, operation_id, {"seq": event.seq, "run_id": event.run_id})
                if self.store.get_operation(operation_id):
                    self.store.update_operation(operation_id, delivery="committed")
            event_type = EVENT_TYPES.get(event.type)
            if event.type == "extension_state_changed" and payload.get("plugin_id") == "agent-goal":
                event_type = "goal.state_changed"
            semantic_id = generation + ":" + str(event.seq)
            if event.type == "extension_state_changed" and payload.get("plugin_id") == "execution-tools" and str(payload.get("namespace", "")).startswith("job."):
                job = payload.get("value") or {}
                if job.get("status") in {"completed", "failed", "killed", "interrupted"}:
                    event_type = "job.completed"
                    normalized = {k: job.get(k) for k in ("id", "status", "finished_at", "exit_code", "kind")}
                    semantic_id = "job:" + digest(normalized)
                    payload = {"job": normalized}
                    if type(job.get("finished_at")) in {int, float}:
                        event_time = datetime.fromtimestamp(job["finished_at"], timezone.utc).isoformat()
            next_cursor = {"generation": generation, "seq": event.seq}
            if event_type:
                chain = []
                op = self.store.operation_for_run(sid, event.run_id)
                if op:
                    chain = op["request"].get("_automationchain", [])
                self.store.append_event({"specversion": "1.0", "source": "runtime/" + sid,
                    "id": semantic_id, "type": event_type, "subject": sid,
                    "time": event_time, "automationchain": chain,
                    "data": {"session_id": sid, "run_id": event.run_id, "runtime_type": event.type, "payload": payload}}, cursor=(name, next_cursor))
                # This commit also covers preceding non-semantic facts. Keep
                # the business event and its cursor in the same transaction.
                pending_cursor = None
            else:
                pending_cursor = next_cursor
        if pending_cursor is not None:
            # Token/trace facts do not emit control events. Committing once
            # per batch avoids hundreds of SQLite open/fsync/close cycles;
            # a crash merely replays those facts after the last durable event.
            self.store.set_cursor(name, pending_cursor)
        if len(batch) == 500:
            self.mark_dirty(sid)
            return True
        return False

    async def consume_events(self):
        cursor = self.store.cursor("rules", 0)
        events = self.store.events(cursor)
        if not events:
            return
        # All rules consume one shared source batch. Build a type index once,
        # rather than reloading/decoding every definition for every event.
        by_type = {}
        for task in self.store.list("automations"):
            if task.get("enabled") and not task.get("deleted") and task["trigger"]["kind"] == "event":
                for kind in set(task["trigger"]["types"]):
                    by_type.setdefault(kind, []).append(task)
        if not by_type:
            # An empty ruleset must not turn historical backfill into hundreds
            # of independent cursor transactions and repeated rule queries.
            self.store.set_cursors({"rules": events[-1]["cursor"], "event_highwater": events[-1]["cursor"]})
            return
        inactive = set()
        retry_cursor = None
        for event in events:
            candidates = by_type.get(event["type"], ())
            if not candidates:
                continue
            try:
                occurred = datetime.fromisoformat(event["time"].replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError, KeyError):
                continue
            for task in candidates:
                if task["id"] in inactive:
                    continue
                if not match_condition(task["trigger"].get("condition"), event):
                    continue
                # New rules never replay a pre-existing historical corpus implicitly.
                if occurred < task.get("active_since", task["created_at"]):
                    continue
                # Cache discovery, not authority: a pause, edit, or deletion
                # while another dispatch awaits takes effect before this fire.
                live = self.store.get("automations", task["id"])
                if not live or not live.get("enabled") or live.get("deleted") or live["revision"] != task["revision"]:
                    inactive.add(task["id"])
                    continue
                source_id = event.get("source", "").removeprefix("webhook/")
                if event["source"].startswith("webhook/"):
                    source = self.store.get("sources", source_id)
                    if not source or task["id"] not in source.get("allowed_rules", []):
                        continue
                else:
                    try:
                        check_session(Principal(task["owner"], policy=task["policy"]), event["subject"], self.control.manager)
                    except ControlError:
                        continue
                try:
                    await self.fire(task, event["source"] + ":" + event["id"], occurred, event=event)
                except Exception as exc:
                    if getattr(exc, "code", "") in {"queue_full", "work_pool_full"}:
                        # A full subscriber must not stop other subscribers in
                        # this batch. Retry its facts without duplicating accepted
                        # dispatches, using the original stable trigger keys.
                        retry_cursor = event["cursor"] if retry_cursor is None else min(retry_cursor, event["cursor"])
                        inactive.add(task["id"])
                        continue
                    inactive.add(task["id"])
                    try:
                        self.store.put("automations", task["id"], {**task, "enabled": False,
                            "last_error": {"code": getattr(exc, "code", "dispatch_failed"), "message": str(exc)}}, expected=task["revision"])
                    except ControlError as conflict:
                        if conflict.code != "revision_conflict":
                            raise
        # Accepted rule actions have stable idempotency keys. If a crash
        # precedes this commit, replay reuses those admissions without firing
        # duplicate model runs. Keep the two watermarks atomic as well.
        completed_cursor = events[-1]["cursor"] if retry_cursor is None else retry_cursor - 1
        self.store.set_cursors({"rules": completed_cursor, "event_highwater": completed_cursor})
