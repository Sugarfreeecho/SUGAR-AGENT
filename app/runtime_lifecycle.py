"""Durable, user-confirmed backend restart requests shared with the supervisor.

This module has no application imports or process-control side effects. Only a
supervisor holding its launch secret can claim a checkpointed restart.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

TERMINAL = frozenset({"completed", "denied", "cancelled", "failed"})
EXECUTING = frozenset({"authorized", "checkpointed", "draining", "stopping", "starting", "recovering"})
ENV_PREFIX = "MYAGENT_LIFECYCLE_"


class LifecycleConflict(ValueError):
    pass


def state_path() -> Path:
    selected = os.getenv(ENV_PREFIX + "STATE_PATH", "")
    if selected:
        path = Path(selected)
        if not path.is_absolute():
            raise LifecycleConflict("lifecycle state path must be absolute")
        return path
    from security.store import security_state_dir
    return security_state_dir() / "runtime-lifecycle.sqlite3"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def supervisor_environment(supervisor_id: str, token: str, instance_id: str = "",
                           restart_id: str = "") -> dict[str, str]:
    return {ENV_PREFIX + "SUPERVISOR_ID": supervisor_id, ENV_PREFIX + "TOKEN": token,
            ENV_PREFIX + "INSTANCE_ID": instance_id or uuid.uuid4().hex,
            ENV_PREFIX + "RESTART_ID": restart_id}


class LifecycleStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else state_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS supervisors (
                    id TEXT PRIMARY KEY, secret TEXT NOT NULL, seen REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS instances (
                    id TEXT PRIMARY KEY, supervisor TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS restarts (
                    id TEXT PRIMARY KEY, target TEXT NOT NULL, supervisor TEXT NOT NULL,
                    phase TEXT NOT NULL, updated REAL NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS restart_target ON restarts(target, updated);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def heartbeat(self, supervisor_id: str, token: str) -> None:
        with self.connect() as db:
            secret = _digest(token)
            previous = db.execute("SELECT secret FROM supervisors WHERE id=?", (supervisor_id,)).fetchone()
            if previous and not hmac.compare_digest(previous["secret"], secret):
                raise LifecycleConflict("supervisor identity changed")
            db.execute("INSERT OR REPLACE INTO supervisors VALUES(?,?,?)", (supervisor_id, secret, time.time()))

    def available(self, supervisor_id: str, token: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT * FROM supervisors WHERE id=?", (supervisor_id,)).fetchone()
        return bool(row and time.time() - row["seen"] < 8
                    and hmac.compare_digest(row["secret"], _digest(token)))

    def instance(self, instance_id: str, supervisor_id: str, payload: dict) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO instances VALUES(?,?,?)",
                       (instance_id, supervisor_id, json.dumps(payload, ensure_ascii=False)))

    def read_instance(self, instance_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM instances WHERE id=?", (instance_id,)).fetchone()
        return json.loads(row["payload"]) if row else {}

    def read(self, restart_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM restarts WHERE id=?", (restart_id,)).fetchone()
        if not row:
            raise LifecycleConflict("restart request not found")
        return json.loads(row["payload"])

    def recent(self, supervisor_id: str, target: str = "") -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM restarts WHERE supervisor=? OR target=? ORDER BY updated DESC LIMIT 20",
                              (supervisor_id, target)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def active_for_root(self, data_root: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM restarts WHERE phase NOT IN ('completed','denied','cancelled','failed')").fetchall()
        records = [json.loads(row["payload"]) for row in rows]
        return [record for record in records if record.get("data_root")
                and Path(record["data_root"]).resolve() == Path(data_root).resolve()]

    @staticmethod
    def _write(db, record: dict) -> dict:
        record = dict(record, revision=int(record.get("revision", 0)) + 1, updated_at=time.time())
        db.execute("INSERT OR REPLACE INTO restarts VALUES(?,?,?,?,?,?)", (
            record["restart_id"], record["target_instance_id"], record["supervisor_id"],
            record["phase"], record["updated_at"], json.dumps(record, ensure_ascii=False)))
        return record

    def create(self, *, instance_id: str, supervisor_id: str, session_id: str = "",
               run_id: str = "", tool_call_id: str = "", reason: str,
               change_summary: str = "", resume_hint: str = "", impact: dict | None = None,
               data_root: str = "") -> dict:
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise LifecycleConflict("请提供不超过 2000 字的重启原因")
        for text in (change_summary, resume_hint):
            if not isinstance(text, str) or len(text) > 4000:
                raise LifecycleConflict("重启说明过长或格式无效")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT payload FROM restarts WHERE target=? ORDER BY updated DESC", (instance_id,)).fetchall()
            for row in rows:
                existing = json.loads(row["payload"])
                if (tool_call_id and existing.get("tool_call_id") == tool_call_id
                        and existing.get("run_id") == run_id):
                    return existing
                if (run_id and existing.get("run_id") == run_id and existing.get("session_id") == session_id
                        and existing["phase"] in {"denied", "cancelled"}):
                    return existing
                if existing["phase"] not in TERMINAL:
                    return existing
            record = dict(restart_id=uuid.uuid4().hex, target_instance_id=instance_id,
                          supervisor_id=supervisor_id, session_id=session_id, run_id=run_id,
                          tool_call_id=tool_call_id, reason=reason.strip(), change_summary=change_summary,
                          resume_hint=resume_hint, impact=impact or {}, phase="awaiting_confirmation",
                          created_at=time.time(), resume_requester=True, request_version=1, data_root=data_root)
            record["request_digest"] = _digest(record)
            return self._write(db, record)

    def decide(self, restart_id: str, *, instance_id: str, digest: str, allow: bool,
               resume: bool = True, impact: dict | None = None) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM restarts WHERE id=?", (restart_id,)).fetchone()
            if not row:
                raise LifecycleConflict("restart request not found")
            record = json.loads(row["payload"])
            if record["target_instance_id"] != instance_id:
                raise LifecycleConflict("目标实例已变化，请重新申请重启")
            if not hmac.compare_digest(str(record["request_digest"]), str(digest)):
                raise LifecycleConflict("重启请求已变化，请重新确认")
            if record["phase"] != "awaiting_confirmation":
                return record
            if allow and impact is not None and impact != record.get("impact"):
                record.update(impact=impact, request_version=record["request_version"] + 1)
                record["request_digest"] = _digest({k: v for k, v in record.items()
                                                    if k not in {"request_digest", "revision", "updated_at"}})
                return dict(self._write(db, record), confirmation_changed=True)
            record.update(phase="authorized" if allow else "denied", resume_requester=bool(resume),
                          decided_at=time.time(), decision="allow_once" if allow else "deny")
            # A manual request has no tool/run checkpoint to wait for.
            if allow and not record.get("tool_call_id"):
                record["phase"] = "checkpointed"
            return self._write(db, record)

    def transition(self, restart_id: str, phase: str, *, expected: set[str] | frozenset | None = None,
                   **fields) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM restarts WHERE id=?", (restart_id,)).fetchone()
            if not row:
                raise LifecycleConflict("restart request not found")
            record = json.loads(row["payload"])
            if record["phase"] in TERMINAL or (expected is not None and record["phase"] not in expected):
                return record
            record.update(fields, phase=phase)
            return self._write(db, record)

    def claim(self, supervisor_id: str, token: str) -> dict | None:
        if not self.available(supervisor_id, token):
            return None
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM restarts WHERE supervisor=? AND phase='checkpointed' ORDER BY updated LIMIT 1",
                             (supervisor_id,)).fetchone()
            if not row:
                return None
            record = json.loads(row["payload"])
            record.update(phase="draining", expected_new_instance_id=uuid.uuid4().hex, claimed_at=time.time())
            return self._write(db, record)


class RuntimeLifecycle:
    def __init__(self, manager, *, store: LifecycleStore | None = None, environment=None):
        env = os.environ if environment is None else environment
        self.store = store or LifecycleStore()
        self.manager = manager
        self.instance_id = env.get(ENV_PREFIX + "INSTANCE_ID") or uuid.uuid4().hex
        self.supervisor_id = env.get(ENV_PREFIX + "SUPERVISOR_ID", "")
        self.token = env.get(ENV_PREFIX + "TOKEN", "")
        self.restart_id = env.get(ENV_PREFIX + "RESTART_ID", "")
        self.ui_token = secrets.token_urlsafe(32)
        self.draining = False
        self.ready = False
        self._prepare_lock = asyncio.Lock()
        from run_ownership import current_process_identity
        _, self.process_started_at = current_process_identity()
        if self.restart_id:
            record = self.store.read(self.restart_id)
            if record.get("expected_new_instance_id") != self.instance_id:
                raise LifecycleConflict("新实例身份与重启请求不符")
            summary_reader = getattr(self.manager, "get_session_summary", None)
            requester_exists = not record.get("session_id") or not callable(summary_reader) or bool(summary_reader(record["session_id"]))
            if requester_exists and not record.get("resume_requester", True) and record.get("session_id"):
                self.manager.request_interrupt(record["session_id"], reason="manual_stop")
            if requester_exists:
                self.restore_requester_context(record)
            else:
                self.store.transition(record["restart_id"], record["phase"],
                                      recovery_summary="服务已启动；请求任务已不在当前会话库，未自动续跑。")
        for record in self.store.recent(self.supervisor_id, self.instance_id) if self.supervisor_id else []:
            if (record["phase"] not in TERMINAL and record["target_instance_id"] != self.instance_id
                    and record.get("expected_new_instance_id") != self.instance_id):
                self.store.transition(record["restart_id"], "failed", error="目标实例已被替换，旧重启请求未执行")
        # A full supervisor relaunch must not leave the browser waiting forever
        # on an old operation. Never touch a live/unknown foreign owner.
        from run_ownership import _process_start_time
        for record in self.store.active_for_root(str(manager.sessions_dir)):
            if record["target_instance_id"] == self.instance_id or record.get("expected_new_instance_id") == self.instance_id:
                continue
            instance = self.store.read_instance(record["target_instance_id"])
            if not instance.get("pid"):
                continue
            status, started = _process_start_time(int(instance["pid"]))
            reused = started is not None and instance.get("process_started_at") is not None and abs(started - instance["process_started_at"]) >= .01
            if status == "dead" or reused:
                self.store.transition(record["restart_id"], "failed", expected={record["phase"]},
                                      error="旧实例已结束，原重启结果未确认；当前服务已由新的监督器启动")
        self.store.instance(self.instance_id, self.supervisor_id, {
            "pid": os.getpid(), "started_at": time.time(), "ready": False,
            "process_started_at": self.process_started_at,
            "data_root": str(manager.sessions_dir),
        })

    def available(self) -> bool:
        return bool(self.supervisor_id and self.token and self.store.available(self.supervisor_id, self.token))

    def impact(self) -> dict:
        from session_lifecycle import active_run_rows
        from execution_services.jobs import _SERVICE
        jobs = list(_SERVICE.jobs.copy().values()) if _SERVICE else []
        terminals = list(_SERVICE.terminals.sessions.copy().values()) if _SERVICE and _SERVICE.terminals else []
        runs = {(row["session_id"], row["run_id"]) for row in active_run_rows()}
        module = sys.modules.get("agent_subagent")
        registry = getattr(module, "subagent_registry", None)
        if registry:
            runs.update(registry.running_runs().items())
        return {"running_tasks": len(runs),
                "background_jobs": sum(job.visible and not job.done.is_set() for job in jobs),
                "terminals": sum(getattr(item, "status", "") == "running" for item in terminals)}

    def request(self, *, session_id="", run_id="", tool_call_id="", **arguments) -> dict:
        if not self.available():
            raise LifecycleConflict("restart_unavailable：当前启动方式没有可用的外部监督器，请从托盘或桌面版启动")
        if self.draining:
            raise LifecycleConflict("服务正在重启，请等待恢复")
        if not self.ready:
            raise LifecycleConflict("服务尚未就绪，请稍后申请重启")
        return self.store.create(instance_id=self.instance_id, supervisor_id=self.supervisor_id,
                                 session_id=session_id, run_id=run_id, tool_call_id=tool_call_id,
                                 impact=self.impact(), data_root=str(self.manager.sessions_dir), **arguments)

    def restore_requester_context(self, record: dict) -> None:
        """Give the replacement run a durable receipt before recovery can start."""
        sid = record.get("session_id")
        if not sid or not hasattr(self.manager, "repository"):
            return
        if record.get("data_root") and Path(record["data_root"]).resolve() != Path(self.manager.sessions_dir).resolve():
            self.store.transition(record["restart_id"], record["phase"],
                recovery_summary="数据目录已变化，未自动恢复原目录中的请求任务。")
            return
        from runtime_v2 import RuntimeHistoryOps, SnapshotStore
        resolver = getattr(self.manager, "_resolve_session_path", None)
        root = self.manager.repository.sessions_dir
        operation_id = "lifecycle-restart-result:" + record["restart_id"]
        snapshot = SnapshotStore(root, path_resolver=resolver).read_consistent(sid)
        if operation_id in set(snapshot.get("operation_ids") or []):
            return
        RuntimeHistoryOps(root, path_resolver=resolver).append_model_message(
            sid, "system", "[服务重启回执] 本次用户确认的重启已经启动新的后端实例。"
            "原重启请求已经消费，不要重复申请同一次重启。请检查新行为后继续。\n"
            + str(record.get("resume_hint") or "") + "\nrestart_id=" + record["restart_id"],
            operation_id=operation_id,
        )

    def blocks_session(self, session_id: str) -> bool:
        if not self.supervisor_id:
            return False
        return any(record.get("session_id") == session_id and record["phase"] not in TERMINAL
                   for record in self.store.recent(self.supervisor_id, self.instance_id))

    def request_manual(self, reason: str) -> dict:
        if not self.draining:
            return self.request(reason=reason)
        records = self.store.recent(self.supervisor_id, self.instance_id)
        if not self.available() or not records or records[0]["phase"] != "failed":
            raise LifecycleConflict("服务正在处理已有重启，请等待结果")
        # A failed partial drain stays frozen. A new human-confirmed operation
        # may replace it, without reopening execution on a partly stopped host.
        return self.store.create(instance_id=self.instance_id, supervisor_id=self.supervisor_id,
                                 reason=reason, impact=self.impact(), data_root=str(self.manager.sessions_dir))

    def status(self, restart_id="", *, include_ui=False) -> dict:
        if restart_id:
            record = self.store.read(restart_id)
            same_root = bool(record.get("data_root") and Path(record["data_root"]).resolve() == Path(self.manager.sessions_dir).resolve())
            if record["supervisor_id"] != self.supervisor_id and record["target_instance_id"] != self.instance_id and not same_root:
                raise LifecycleConflict("重启请求不属于当前实例")
            records = [record]
        else:
            records = self.store.recent(self.supervisor_id, self.instance_id) if self.supervisor_id else []
        result = dict(ok=True, instance_id=self.instance_id, ready=self.ready, draining=self.draining,
                      restart_available=self.available(), operations=records[:5])
        if include_ui:
            result["ui_token"] = self.ui_token
        return result

    def mark_ready(self) -> None:
        self.ready = True
        self.store.instance(self.instance_id, self.supervisor_id, {"pid": os.getpid(), "ready": True,
                            "process_started_at": self.process_started_at,
                            "data_root": str(self.manager.sessions_dir)})
        if self.restart_id:
            record = self.store.read(self.restart_id)
            if record.get("expected_new_instance_id") != self.instance_id:
                raise LifecycleConflict("新实例身份与重启请求不符")
            self.store.transition(self.restart_id, "completed", expected={"starting", "recovering"},
                                  new_instance_id=self.instance_id,
                                  recovery_summary=record.get("recovery_summary") or
                                  ("服务已启动，本次任务按你的选择保持停止。其他符合条件的任务将由后台恢复。"
                                   if not record.get("resume_requester", True) else
                                   "服务已启动，符合条件的任务将由后台恢复；待审批和手动停止的任务保持等待。"))

    def checkpoint(self, restart_id: str, session_id: str, run_id: str) -> dict:
        record = self.store.read(restart_id)
        if (record["target_instance_id"], record["session_id"], record["run_id"]) != (self.instance_id, session_id, run_id):
            raise LifecycleConflict("重启检查点身份不匹配")
        return self.store.transition(restart_id, "checkpointed", expected={"authorized"}, checkpoint_at=time.time())


_service: RuntimeLifecycle | None = None
_exit_callback = None


def set_exit_callback(callback) -> None:
    global _exit_callback
    _exit_callback = callback


def configure(manager, **kwargs) -> RuntimeLifecycle:
    global _service
    _service = RuntimeLifecycle(manager, **kwargs)
    return _service


def current() -> RuntimeLifecycle | None:
    return _service


def is_draining() -> bool:
    return bool(_service and _service.draining)


async def invoke_restart(context, arguments):
    from tool_registry import ToolOutcome
    service = current()
    if service is None:
        return ToolOutcome.failed("restart_unavailable", "重启服务尚未初始化")
    from agent_subagent import subagent_registry
    if subagent_registry.is_running(context.session_id):
        return ToolOutcome.failed("restart_requires_parent", "请由主 Agent 申请服务重启")
    if context.services.get("tool_batch_size", 1) != 1:
        return ToolOutcome.failed("restart_must_be_single", "请单独调用 request_restart，不要与其他工具并发")
    try:
        record = await asyncio.to_thread(service.request, session_id=context.session_id,
                                        run_id=context.run_id, tool_call_id=context.tool_call_id, **dict(arguments))
    except (LifecycleConflict, TypeError) as exc:
        return ToolOutcome.failed("restart_unavailable", str(exc))
    restart_id = record["restart_id"]
    if record.get("run_id") != context.run_id or record.get("tool_call_id") != context.tool_call_id:
        return ToolOutcome.completed(json.dumps({"status": "restart_already_requested", "restart_id": restart_id}))
    context.state["_runtime_stage"] = "waiting_user:request_restart"
    await context.publish({"type": "lifecycle_changed", "operation": record, "ephemeral": True})
    from session_event_bus import publish_lifecycle_event
    await publish_lifecycle_event(record)
    try:
        from notification_providers import notify_user
        await notify_user("Agent 请求重启", "有一个服务重启请求等待你确认。", context.session_id)
        while record["phase"] == "awaiting_confirmation":
            check = context.services.get("interaction_interrupt_check")
            if check and check():
                service.store.transition(restart_id, "cancelled", expected={"awaiting_confirmation"})
                return ToolOutcome.completed(json.dumps({"status": "cancelled", "restart_id": restart_id}))
            await asyncio.sleep(.25)
            record = await asyncio.to_thread(service.store.read, restart_id)
        if record["phase"] == "authorized":
            if record.get("run_id") != context.run_id or record.get("tool_call_id") != context.tool_call_id:
                return ToolOutcome.completed(json.dumps({"status": "restart_already_requested", "restart_id": restart_id}))
            context.state["_lifecycle_restart_id"] = restart_id
            return ToolOutcome.completed(json.dumps({"status": "restart_authorized", "restart_id": restart_id,
                                                     "resume_hint": record.get("resume_hint", "")}, ensure_ascii=False))
        return ToolOutcome.completed(json.dumps({"status": record["phase"], "restart_id": restart_id}, ensure_ascii=False))
    except asyncio.CancelledError:
        service.store.transition(restart_id, "cancelled", expected={"awaiting_confirmation", "authorized"})
        raise


def register_routes(app, manager) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    # FastAPI resolves postponed endpoint annotations against module globals.
    globals()["Request"] = Request

    def require_ui(request, service):
        origin = request.headers.get("origin", "")
        from urllib.parse import urlsplit
        if (request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}
                or (origin and urlsplit(origin).netloc != request.url.netloc)
                or not hmac.compare_digest(request.headers.get("x-myagent-lifecycle-ui", ""), service.ui_token)):
            raise LifecycleConflict("请通过应用中的重启确认卡进行操作")

    @app.get("/api/lifecycle/status")
    async def lifecycle_status(request: Request, restart_id: str = ""):
        service = current()
        if service is None:
            return JSONResponse({"ok": False, "error": "lifecycle_unavailable"}, status_code=503)
        try:
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"error": "cross_site_request"}, status_code=403)
            return JSONResponse(await asyncio.to_thread(service.status, restart_id, include_ui=True),
                                headers={"Cache-Control": "no-store"})
        except LifecycleConflict as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)

    @app.get("/api/ready")
    async def ready():
        service = current()
        return JSONResponse({"ok": bool(service and service.ready and not service.draining),
                             "instance_id": service.instance_id if service else "",
                             "protocol": "myagent-lifecycle-v1"},
                            status_code=200 if service and service.ready and not service.draining else 503,
                            headers={"Cache-Control": "no-store"})

    @app.post("/api/lifecycle/restarts")
    async def create_restart(request: Request):
        service = current()
        if not service:
            return JSONResponse({"error": "lifecycle_unavailable"}, status_code=503)
        try:
            require_ui(request, service)
            data = await request.json()
            operation = await asyncio.to_thread(service.request_manual, str(data.get("reason") or "用户请求重启服务"))
            from session_event_bus import publish_lifecycle_event
            await publish_lifecycle_event(operation)
            return JSONResponse({"ok": True, "operation": operation}, status_code=202)
        except (LifecycleConflict, ValueError) as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)

    @app.post("/api/lifecycle/restarts/{restart_id}/decision")
    async def decide_restart(restart_id: str, request: Request):
        service = current()
        if not service:
            return JSONResponse({"error": "lifecycle_unavailable"}, status_code=503)
        try:
            require_ui(request, service)
            data = await request.json()
            if data.get("decision") not in {"allow_once", "deny"}:
                raise LifecycleConflict("只支持本次允许或拒绝")
            if data["decision"] == "allow_once" and not service.available():
                raise LifecycleConflict("外部监督器已离线，未执行重启")
            record = await asyncio.to_thread(service.store.decide, restart_id, instance_id=service.instance_id,
                digest=str(data.get("request_digest") or ""), allow=data["decision"] == "allow_once",
                resume=data.get("resume_requester") is not False, impact=service.impact())
            from session_event_bus import publish_lifecycle_event
            await publish_lifecycle_event(record)
            return JSONResponse({"ok": True, "operation": record}, status_code=409 if record.get("confirmation_changed") else 202)
        except (LifecycleConflict, ValueError) as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)

    @app.post("/api/lifecycle/prepare")
    async def prepare_restart(request: Request):
        service = current()
        if not service or not service.token or not hmac.compare_digest(request.headers.get("x-myagent-supervisor", ""), service.token):
            return JSONResponse({"error": "invalid_supervisor"}, status_code=403)
        data = await request.json()
        async with service._prepare_lock:
            record = await asyncio.to_thread(service.store.read, str(data.get("restart_id") or ""))
            if record["target_instance_id"] != service.instance_id or record["phase"] != "draining":
                return JSONResponse({"error": "stale_restart"}, status_code=409)
            service.draining = True
            try:
                from session_event_bus import publish_lifecycle_event
                await publish_lifecycle_event(record)
                warnings = await asyncio.wait_for(prepare_runtime(manager), timeout=55)
                service.store.transition(record["restart_id"], "draining", expected={"draining"}, cleanup_warnings=warnings)
                from starlette.background import BackgroundTask
                return JSONResponse({"ok": True, "instance_id": service.instance_id, "exiting": _exit_callback is not None},
                                    background=BackgroundTask(_exit_callback) if _exit_callback is not None else None)
            except Exception as exc:
                service.store.transition(record["restart_id"], "failed", error="保存运行状态失败：" + str(exc))
                return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


async def prepare_runtime(manager) -> list[str]:
    """Freeze admission before bounded cancellation and explicit durable flushes."""
    from session_lifecycle import active_run_rows, cancel_run_tasks
    warnings = []
    module = sys.modules.get("agent_subagent")
    registry = getattr(module, "subagent_registry", None)
    child_runs = registry.running_runs() if registry else {}
    rows = active_run_rows() + [{"session_id": sid, "run_id": rid} for sid, rid in child_runs.items()]
    for row in rows:
        manager.request_interrupt(row["session_id"], run_id=row["run_id"], reason="process_restart")
    await cancel_run_tasks({row["session_id"] for row in rows})
    if registry:
        await registry.cancel_for_restart()
    webui = sys.modules.get("webui")
    if webui is not None and getattr(webui, "session_manager", None) is manager:
        from agent_team.tools import stop_auto_scheduler
        for stop in (stop_auto_scheduler, webui.stop_webui_lifecycle):
            try:
                await asyncio.wait_for(stop(), timeout=20)
            except Exception as exc:
                warnings.append(str(exc))
    import runtime_observability
    import execution_metrics
    await asyncio.to_thread(runtime_observability.flush)
    await asyncio.to_thread(execution_metrics.flush)
    from execution_services.jobs import _SERVICE
    if _SERVICE is not None:
        await _SERVICE.shutdown()
    return warnings
