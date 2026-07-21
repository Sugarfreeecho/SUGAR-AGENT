"""Durable, session-scoped Goal lifecycle for MyAgent."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


TERMINAL_GOAL_STATUSES = {"completed", "blocked", "cancelled"}
ACTIVE_GOAL_STATUSES = {"active", "paused"}
_TRANSIENT_GOAL_FIELDS = {
    "elapsed_seconds",
    "remaining_tokens",
    "blocker_report_recorded",
    "blocker_report_terminal",
    "required_blocked_streak",
}
_LEGACY_LOCKS: Dict[str, threading.RLock] = {}
_LEGACY_LOCKS_GUARD = threading.Lock()


def goal_enabled() -> bool:
    return os.getenv("GOAL_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _future_iso(seconds: float) -> str:
    value = datetime.now(timezone.utc) + timedelta(seconds=max(0.0, float(seconds or 0.0)))
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _iso_due(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc) <= datetime.now(timezone.utc)
    except Exception:
        return True


class GoalError(ValueError):
    pass


class GoalManager:
    def __init__(self, sessions_dir: Any, path_resolver: Optional[Callable[[str], Any]] = None):
        self.sessions_dir = sessions_dir
        self.path_resolver = path_resolver

    def _require_enabled(self) -> None:
        if not goal_enabled():
            raise GoalError("Goal feature is disabled by GOAL_ENABLED.")

    def _ops(self):
        from runtime_v2 import RuntimeHistoryOps

        return RuntimeHistoryOps(self.sessions_dir, path_resolver=self.path_resolver)

    @staticmethod
    def _runtime_v2_primary() -> bool:
        try:
            from runtime_v2 import runtime_v2_primary

            return bool(runtime_v2_primary())
        except Exception:
            return True

    def _legacy_goal_path(self, session_id: str) -> Path:
        sid = str(session_id or "").strip()
        if not sid:
            raise GoalError("session_id is required")
        base = Path(self.path_resolver(sid)) if self.path_resolver else Path(self.sessions_dir) / sid
        return base / "goal.json"

    @staticmethod
    def _legacy_lock(path: Path) -> threading.RLock:
        key = str(path.resolve())
        with _LEGACY_LOCKS_GUARD:
            lock = _LEGACY_LOCKS.get(key)
            if lock is None:
                lock = threading.RLock()
                _LEGACY_LOCKS[key] = lock
            return lock

    @staticmethod
    def _read_legacy(path: Path) -> Optional[Dict[str, Any]]:
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        except Exception:
            value = None
        return dict(value) if isinstance(value, dict) and value.get("id") else None

    @staticmethod
    def _write_legacy(path: Path, goal: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(goal, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _mutate(
        self,
        session_id: str,
        mutator: Callable[[Optional[Dict[str, Any]]], tuple[str, Dict[str, Any], Dict[str, Any]]],
        *,
        run_id: str = "",
    ) -> Dict[str, Any]:
        self._require_enabled()
        sid = str(session_id or "").strip()
        if not sid:
            raise GoalError("session_id is required")
        if self._runtime_v2_primary():
            _event, response = self._ops().mutate_goal(sid, mutator, run_id=str(run_id or "").strip() or None)
            return self._with_computed_fields(response)
        path = self._legacy_goal_path(sid)
        with self._legacy_lock(path):
            current = self._read_legacy(path)
            event_type, persisted, response = mutator(dict(current) if current else None)
            if str(event_type or "").strip():
                self._write_legacy(path, dict(persisted))
            return self._with_computed_fields(response or persisted or current or {})

    @staticmethod
    def _touch(goal: Dict[str, Any], *, actor: str, run_id: str = "") -> Dict[str, Any]:
        out = dict(goal)
        out["schema_version"] = max(1, int(out.get("schema_version") or 1))
        out["version"] = max(0, int(out.get("version") or 0)) + 1
        out["updated_at"] = _now_iso()
        out["updated_by"] = str(actor or "system")
        if str(run_id or "").strip():
            out["last_run_id"] = str(run_id).strip()
        return out

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        self._require_enabled()
        sid = str(session_id or "").strip()
        if not sid:
            raise GoalError("session_id is required")
        if self._runtime_v2_primary():
            snapshot = self._ops().snapshots.read(sid)
            goal = snapshot.get("goal") if isinstance(snapshot, dict) else None
        else:
            goal = self._read_legacy(self._legacy_goal_path(sid))
        if not isinstance(goal, dict) or not goal.get("id") or goal.get("deleted") is True:
            return None
        return self._with_computed_fields(goal)

    def create(
        self,
        session_id: str,
        objective: str,
        token_budget: Optional[int] = None,
        *,
        actor: str = "model",
        run_id: str = "",
    ) -> Dict[str, Any]:
        self._require_enabled()
        objective = str(objective or "").strip()
        if not objective:
            raise GoalError("objective is required")
        if len(objective) > 12000:
            raise GoalError("objective must not exceed 12000 characters")
        if token_budget is not None:
            token_budget = int(token_budget)
            if token_budget <= 0:
                raise GoalError("token_budget must be greater than zero")

        def mutate(existing: Optional[Dict[str, Any]]):
            if existing and existing.get("status") in ACTIVE_GOAL_STATUSES:
                raise GoalError("An unfinished goal already exists for this session.")
            now = _now_iso()
            goal = {
                "schema_version": 1,
                "version": 1,
                "id": "goal_" + uuid.uuid4().hex[:16],
                "objective": objective,
                "status": "active",
                "token_budget": token_budget,
                "used_tokens": 0,
                "active_seconds": 0.0,
                "active_since_epoch": time.time(),
                "blocked_streak": 0,
                "blocked_fingerprint": None,
                "blocker_key": None,
                "blocked_reason": None,
                "last_blocker_report_id": None,
                "run_count": 0,
                "continuation_count": 0,
                "consecutive_failures": 0,
                "last_error": None,
                "next_retry_at": None,
                "pause_reason": None,
                "accounted_run_ids": [],
                "accounted_usage_ids": [],
                "created_at": now,
                "updated_at": now,
                "created_by": str(actor or "model"),
                "updated_by": str(actor or "model"),
                "last_run_id": str(run_id or "").strip() or None,
            }
            stored = self._stored(goal)
            return "goal_created", stored, stored

        return self._mutate(session_id, mutate, run_id=run_id)

    def update_status(
        self,
        session_id: str,
        status: str,
        reason: str = "",
        report_id: str = "",
        *,
        blocker_key: str = "",
        actor: str = "model",
        run_id: str = "",
    ) -> Dict[str, Any]:
        status = str(status or "").strip().lower()
        if status not in {"completed", "blocked"}:
            raise GoalError("Model updates only support completed or blocked.")
        reason = str(reason or "").strip()
        report_id = str(report_id or "").strip()
        stable_key = " ".join(str(blocker_key or "").lower().split())[:500]

        def mutate(current: Optional[Dict[str, Any]]):
            if not current:
                raise GoalError("No goal exists for this session.")
            if current.get("status") in TERMINAL_GOAL_STATUSES:
                raise GoalError(f"Cannot update a goal in status {current.get('status')}.")
            goal = dict(current)
            if status == "blocked":
                if not reason:
                    raise GoalError("A blocked goal requires a reason.")
                fingerprint = stable_key or " ".join(reason.lower().split())[:500]
                same_report = bool(report_id and goal.get("last_blocker_report_id") == report_id)
                if same_report:
                    streak = int(goal.get("blocked_streak") or 0)
                else:
                    streak = int(goal.get("blocked_streak") or 0) + 1 if goal.get("blocked_fingerprint") == fingerprint else 1
                goal.update({
                    "blocked_streak": streak,
                    "blocked_fingerprint": fingerprint,
                    "blocker_key": stable_key or None,
                    "blocked_reason": reason,
                    "last_blocker_report_id": report_id or goal.get("last_blocker_report_id"),
                })
                if streak < 3:
                    goal = self._touch(goal, actor=actor, run_id=run_id or report_id)
                    response = dict(goal)
                    response.update({
                        "blocker_report_recorded": True,
                        "blocker_report_terminal": False,
                        "required_blocked_streak": 3,
                    })
                    return "goal_updated", self._stored(goal), response
            self._stop_clock(goal)
            goal["status"] = status
            goal["pause_reason"] = None
            goal["next_retry_at"] = None
            if status == "completed":
                goal.update({
                    "blocked_streak": 0,
                    "blocked_fingerprint": None,
                    "blocker_key": None,
                    "blocked_reason": None,
                    "last_blocker_report_id": None,
                })
            goal = self._touch(goal, actor=actor, run_id=run_id or report_id)
            return f"goal_{status}", self._stored(goal), self._stored(goal)

        return self._mutate(session_id, mutate, run_id=run_id or report_id)

    def user_action(
        self,
        session_id: str,
        action: str,
        *,
        additional_budget: Optional[int] = None,
        objective: Optional[str] = None,
        reason: str = "",
        actor: str = "user",
        run_id: str = "",
    ) -> Dict[str, Any]:
        action = str(action or "").strip().lower()
        if additional_budget is not None:
            additional_budget = int(additional_budget)
            if additional_budget <= 0:
                raise GoalError("additional_budget must be greater than zero")
        if action == "edit":
            objective = str(objective or "").strip()
            if not objective:
                raise GoalError("objective is required")
            if len(objective) > 12000:
                raise GoalError("objective must not exceed 12000 characters")

        def mutate(current: Optional[Dict[str, Any]]):
            if not current or current.get("deleted") is True:
                raise GoalError("No goal exists for this session.")
            goal = dict(current)
            if action == "pause" and goal.get("status") == "active":
                self._stop_clock(goal)
                goal["status"] = "paused"
                goal["pause_reason"] = str(reason or "manual")
            elif action == "resume" and goal.get("status") == "paused":
                budget = goal.get("token_budget")
                exhausted = budget is not None and int(goal.get("used_tokens") or 0) >= int(budget)
                if exhausted and additional_budget is None:
                    raise GoalError("Token budget is exhausted; additional_budget is required to resume.")
                if additional_budget is not None:
                    base = int(budget) if budget is not None else int(goal.get("used_tokens") or 0)
                    goal["token_budget"] = base + int(additional_budget)
                goal["status"] = "active"
                goal["active_since_epoch"] = time.time()
                goal["pause_reason"] = None
                goal["next_retry_at"] = None
                goal["consecutive_failures"] = 0
            elif action == "cancel" and goal.get("status") in ACTIVE_GOAL_STATUSES:
                self._stop_clock(goal)
                goal["status"] = "cancelled"
                goal["pause_reason"] = str(reason or "cancelled_by_user")
                goal["next_retry_at"] = None
            elif action == "edit":
                goal["objective"] = str(objective)
            elif action == "delete":
                if goal.get("status") == "active":
                    self._stop_clock(goal)
                goal["status"] = "cancelled"
                goal["pause_reason"] = "deleted_by_user"
                goal["next_retry_at"] = None
                goal["deleted"] = True
                goal["deleted_at"] = _now_iso()
            else:
                raise GoalError(f"Cannot {action} a goal in status {goal.get('status')}.")
            goal = self._touch(goal, actor=actor, run_id=run_id)
            event_types = {
                "pause": "goal_paused",
                "resume": "goal_resumed",
                "cancel": "goal_cancelled",
                "edit": "goal_edited",
                "delete": "goal_deleted",
            }
            event_type = event_types[action]
            return event_type, self._stored(goal), self._stored(goal)

        return self._mutate(session_id, mutate, run_id=run_id)

    def record_usage(
        self,
        session_id: str,
        used_tokens: int,
        *,
        usage_id: str,
        run_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        if not goal_enabled():
            return None
        try:
            if not self.get(session_id):
                return None
        except GoalError:
            return None
        used_tokens = max(0, int(used_tokens or 0))
        usage_id = str(usage_id or "").strip()
        if not usage_id or used_tokens <= 0:
            return self.get(session_id)

        def mutate(current: Optional[Dict[str, Any]]):
            if not current:
                raise GoalError("No goal exists for this session.")
            goal = dict(current)
            accounted = [str(item) for item in goal.get("accounted_usage_ids") or [] if str(item)]
            if usage_id in accounted:
                return "", self._stored(goal), self._stored(goal)
            goal["used_tokens"] = max(0, int(goal.get("used_tokens") or 0) + used_tokens)
            accounted.append(usage_id)
            goal["accounted_usage_ids"] = accounted[-2048:]
            budget = goal.get("token_budget")
            if goal.get("status") == "active" and budget is not None and goal["used_tokens"] >= int(budget):
                self._stop_clock(goal)
                goal["status"] = "paused"
                goal["pause_reason"] = "token_budget_exhausted"
                goal["next_retry_at"] = None
            goal = self._touch(goal, actor="system", run_id=run_id)
            return "goal_usage_updated", self._stored(goal), self._stored(goal)

        try:
            return self._mutate(session_id, mutate, run_id=run_id)
        except GoalError:
            return None

    def record_run(
        self,
        session_id: str,
        used_tokens: int,
        continuation: bool = False,
        *,
        run_id: str = "",
        outcome: str = "finished",
        error: str = "",
    ) -> Optional[Dict[str, Any]]:
        if not goal_enabled():
            return None
        try:
            if not self.get(session_id):
                return None
        except GoalError:
            return None
        used_tokens = max(0, int(used_tokens or 0))
        run_id = str(run_id or "").strip()
        outcome = str(outcome or "finished").strip().lower()

        def mutate(current: Optional[Dict[str, Any]]):
            if not current:
                raise GoalError("No goal exists for this session.")
            goal = dict(current)
            accounted = [str(item) for item in goal.get("accounted_run_ids") or [] if str(item)]
            if run_id and run_id in accounted:
                return "", self._stored(goal), self._stored(goal)
            goal["used_tokens"] = max(0, int(goal.get("used_tokens") or 0) + used_tokens)
            goal["run_count"] = int(goal.get("run_count") or 0) + 1
            goal["current_run_id"] = None
            goal["last_run_outcome"] = outcome
            if continuation:
                goal["continuation_count"] = int(goal.get("continuation_count") or 0) + 1
            if run_id:
                accounted.append(run_id)
                goal["accounted_run_ids"] = accounted[-512:]
            if outcome in {"failed", "error"}:
                failures = int(goal.get("consecutive_failures") or 0) + 1
                goal["consecutive_failures"] = failures
                goal["last_error"] = str(error or "run_failed")[:2000]
                goal["next_retry_at"] = _future_iso(min(300, 2 ** min(failures, 8)))
                max_failures = max(1, int(os.getenv("GOAL_MAX_CONSECUTIVE_FAILURES", "3") or 3))
                if goal.get("status") == "active" and failures >= max_failures:
                    self._stop_clock(goal)
                    goal["status"] = "paused"
                    goal["pause_reason"] = "consecutive_run_failures"
            elif outcome == "finished":
                goal["consecutive_failures"] = 0
                goal["last_error"] = None
                goal["next_retry_at"] = None
            budget = goal.get("token_budget")
            if goal.get("status") == "active" and budget is not None and goal["used_tokens"] >= int(budget):
                self._stop_clock(goal)
                goal["status"] = "paused"
                goal["pause_reason"] = "token_budget_exhausted"
                goal["next_retry_at"] = None
            goal = self._touch(goal, actor="system", run_id=run_id)
            return "goal_usage_updated", self._stored(goal), self._stored(goal)

        try:
            return self._mutate(session_id, mutate, run_id=run_id)
        except GoalError:
            return None

    def mark_continuation_started(self, session_id: str, *, run_id: str = "") -> Dict[str, Any]:
        def mutate(current: Optional[Dict[str, Any]]):
            if not current:
                raise GoalError("No goal exists for this session.")
            if current.get("status") != "active":
                raise GoalError(f"Cannot continue a goal in status {current.get('status')}.")
            budget = current.get("token_budget")
            if budget is not None and int(current.get("used_tokens") or 0) >= int(budget):
                raise GoalError("Token budget is exhausted.")
            if not _iso_due(current.get("next_retry_at")):
                raise GoalError("Goal retry backoff has not elapsed.")
            goal = dict(current)
            goal["current_run_id"] = str(run_id or "").strip() or None
            goal["last_continuation_started_at"] = _now_iso()
            goal = self._touch(goal, actor="system", run_id=run_id)
            return "goal_continuation_started", self._stored(goal), self._stored(goal)

        return self._mutate(session_id, mutate, run_id=run_id)

    def should_continue(self, session_id: str) -> bool:
        if not goal_enabled():
            return False
        goal = self.get(session_id)
        if not goal or goal.get("status") != "active":
            return False
        budget = goal.get("token_budget")
        if budget is not None and int(goal.get("used_tokens") or 0) >= int(budget):
            return False
        return _iso_due(goal.get("next_retry_at"))

    @staticmethod
    def _stop_clock(goal: Dict[str, Any]) -> None:
        started = goal.get("active_since_epoch")
        if started is not None:
            goal["active_seconds"] = float(goal.get("active_seconds") or 0.0) + max(0.0, time.time() - float(started))
            goal["active_since_epoch"] = None

    @staticmethod
    def _stored(goal: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in goal.items() if k not in _TRANSIENT_GOAL_FIELDS}

    @staticmethod
    def _with_computed_fields(goal: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(goal)
        if not out.get("id"):
            return out
        elapsed = float(out.get("active_seconds") or 0.0)
        if out.get("status") == "active" and out.get("active_since_epoch") is not None:
            elapsed += max(0.0, time.time() - float(out["active_since_epoch"]))
        out["elapsed_seconds"] = int(elapsed)
        budget = out.get("token_budget")
        out["remaining_tokens"] = None if budget is None else max(0, int(budget) - int(out.get("used_tokens") or 0))
        return out


def manager_for(session_manager: Any) -> GoalManager:
    return GoalManager(
        session_manager.sessions_dir,
        path_resolver=getattr(session_manager, "_resolve_session_path", None),
    )
