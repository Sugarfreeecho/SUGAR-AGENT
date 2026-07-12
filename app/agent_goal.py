"""Durable, session-scoped Goal lifecycle for MyAgent."""
from __future__ import annotations

import os
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


TERMINAL_GOAL_STATUSES = {"completed", "blocked", "cancelled"}
ACTIVE_GOAL_STATUSES = {"active", "paused"}


def goal_enabled() -> bool:
    return os.getenv("GOAL_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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

    def _write(self, session_id: str, goal: Dict[str, Any], event_type: str) -> None:
        if self._runtime_v2_primary():
            self._ops().update_goal(session_id, goal, event_type=event_type)
            return
        path = self._legacy_goal_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(goal, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        self._require_enabled()
        sid = str(session_id or "").strip()
        if self._runtime_v2_primary():
            snapshot = self._ops().snapshots.read(sid)
            goal = snapshot.get("goal") if isinstance(snapshot, dict) else None
        else:
            path = self._legacy_goal_path(sid)
            try:
                goal = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
            except Exception:
                goal = None
        if not isinstance(goal, dict) or not goal.get("id"):
            return None
        return self._with_computed_fields(goal)

    def create(self, session_id: str, objective: str, token_budget: Optional[int] = None) -> Dict[str, Any]:
        self._require_enabled()
        sid = str(session_id or "").strip()
        objective = str(objective or "").strip()
        if not sid:
            raise GoalError("session_id is required")
        if not objective:
            raise GoalError("objective is required")
        existing = self.get(sid)
        if existing and existing.get("status") in ACTIVE_GOAL_STATUSES:
            raise GoalError("An unfinished goal already exists for this session.")
        if token_budget is not None:
            token_budget = int(token_budget)
            if token_budget <= 0:
                raise GoalError("token_budget must be greater than zero")
        now = _now_iso()
        goal = {
            "id": "goal_" + uuid.uuid4().hex[:16],
            "objective": objective,
            "status": "active",
            "token_budget": token_budget,
            "used_tokens": 0,
            "active_seconds": 0.0,
            "active_since_epoch": time.time(),
            "blocked_streak": 0,
            "blocked_fingerprint": None,
            "blocked_reason": None,
            "continuation_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self._write(sid, goal, "goal_created")
        return self._with_computed_fields(goal)

    def update_status(self, session_id: str, status: str, reason: str = "", report_id: str = "") -> Dict[str, Any]:
        self._require_enabled()
        goal = self.get(session_id)
        if not goal:
            raise GoalError("No goal exists for this session.")
        status = str(status or "").strip().lower()
        if status not in {"completed", "blocked"}:
            raise GoalError("Model updates only support completed or blocked.")
        reason = str(reason or "").strip()
        if status == "blocked":
            if not reason:
                raise GoalError("A blocked goal requires a reason.")
            fingerprint = " ".join(reason.lower().split())[:500]
            report_id = str(report_id or "").strip()
            same_report = bool(report_id and goal.get("last_blocker_report_id") == report_id)
            if same_report:
                streak = int(goal.get("blocked_streak") or 0)
            else:
                streak = int(goal.get("blocked_streak") or 0) + 1 if goal.get("blocked_fingerprint") == fingerprint else 1
            goal.update({
                "blocked_streak": streak,
                "blocked_fingerprint": fingerprint,
                "blocked_reason": reason,
                "last_blocker_report_id": report_id or goal.get("last_blocker_report_id"),
            })
            if streak < 3:
                goal["updated_at"] = _now_iso()
                self._write(session_id, self._stored(goal), "goal_updated")
                raise GoalError(f"Blocked condition recorded ({streak}/3); goal remains active.")
        self._stop_clock(goal)
        goal["status"] = status
        goal["updated_at"] = _now_iso()
        self._write(session_id, self._stored(goal), f"goal_{status}")
        return self._with_computed_fields(goal)

    def user_action(self, session_id: str, action: str) -> Optional[Dict[str, Any]]:
        self._require_enabled()
        goal = self.get(session_id)
        if not goal:
            raise GoalError("No goal exists for this session.")
        action = str(action or "").strip().lower()
        if action == "pause" and goal.get("status") == "active":
            self._stop_clock(goal)
            goal["status"] = "paused"
        elif action == "resume" and goal.get("status") == "paused":
            goal["status"] = "active"
            goal["active_since_epoch"] = time.time()
        elif action == "cancel" and goal.get("status") in ACTIVE_GOAL_STATUSES:
            self._stop_clock(goal)
            goal["status"] = "cancelled"
        else:
            raise GoalError(f"Cannot {action} a goal in status {goal.get('status')}.")
        goal["updated_at"] = _now_iso()
        self._write(
            session_id,
            self._stored(goal),
            f"goal_{action}d" if action != "pause" else "goal_paused",
        )
        return self._with_computed_fields(goal)

    def record_run(self, session_id: str, used_tokens: int, continuation: bool = False) -> Optional[Dict[str, Any]]:
        if not goal_enabled():
            return None
        goal = self.get(session_id)
        if not goal or goal.get("status") == "cancelled":
            return goal
        goal["used_tokens"] = max(0, int(goal.get("used_tokens") or 0) + max(0, int(used_tokens or 0)))
        if continuation:
            goal["continuation_count"] = int(goal.get("continuation_count") or 0) + 1
        budget = goal.get("token_budget")
        if goal.get("status") == "active" and budget is not None and goal["used_tokens"] >= int(budget):
            self._stop_clock(goal)
            goal["status"] = "paused"
            goal["pause_reason"] = "token_budget_exhausted"
        goal["updated_at"] = _now_iso()
        self._write(session_id, self._stored(goal), "goal_usage_updated")
        return self._with_computed_fields(goal)

    def should_continue(self, session_id: str) -> bool:
        if not goal_enabled():
            return False
        goal = self.get(session_id)
        return bool(goal and goal.get("status") == "active")

    @staticmethod
    def _stop_clock(goal: Dict[str, Any]) -> None:
        started = goal.get("active_since_epoch")
        if started is not None:
            goal["active_seconds"] = float(goal.get("active_seconds") or 0.0) + max(0.0, time.time() - float(started))
            goal["active_since_epoch"] = None

    @staticmethod
    def _stored(goal: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in goal.items() if k not in {"elapsed_seconds", "remaining_tokens"}}

    @staticmethod
    def _with_computed_fields(goal: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(goal)
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
