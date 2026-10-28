"""Durable, at-most-once delivery of task notifications to host providers."""
import asyncio
import inspect
import time

from .policy import Principal


async def deliver_notifications(control):
    def pending():
        with control.store.transaction() as db:
            return [dict(row) for row in db.execute("SELECT * FROM automation_notices WHERE status='pending' LIMIT 20")]
    for notice in await asyncio.to_thread(pending):
        if notice["kind"] == "dispatch":
            task = control.store.get("automations", notice["operation_id"])
            sid = (task or {}).get("target", {}).get("session_id", "")
            if sid and not control.manager.get_session_summary(sid):
                sid = ""
            op = {"id": "", "status": "failed", "delivery": "rejected", "session_id": sid, "run_id": "",
                  "created": time.time(), "updated": time.time(), "error": (task or {}).get("last_error")}
        else:
            op = await asyncio.to_thread(control.store.get_operation, notice["operation_id"])
            task = control.store.get("automations", op["request"].get("_automation_id")) if op else None
        status, error = "suppressed", ""
        mode = (task or {}).get("notification", "never")
        enabled = task and not task.get("deleted") and mode != "never"
        if notice["kind"] == "pending_human":
            enabled = enabled and op["status"] not in {"succeeded", "failed", "stopped", "cancelled", "unknown", "interrupted"}
            enabled = enabled and control.callbacks.get("pending_human", lambda _: 0)(op["session_id"]) > 0
        else:
            enabled = enabled and (mode == "always" or op["status"] != "succeeded")
        callback = control.callbacks.get("notify_automation")
        if enabled and callback and not control.callbacks.get("notification_ready", lambda: True)():
            continue  # Providers register after control startup; retain the outbox.
        if enabled and callback:
            try:
                control.authorize(Principal(**task["_principal"]), "automation.get" if notice["kind"] == "dispatch" else "session.get",
                                  {} if notice["kind"] == "dispatch" else {"session_id": op["session_id"]})
                # Claim before calling an external provider. A crash in delivery is
                # left unknown instead of resending a possibly displayed toast.
                with control.store.transaction() as db:
                    claimed = db.execute("UPDATE automation_notices SET status='sending' WHERE id=? AND status='pending'", (notice["id"],)).rowcount
                if not claimed:
                    continue
                value = callback(task, control.receipt(op), notice["kind"])
                failures = await value if inspect.isawaitable(value) else value
                status, error = ("failed", str(failures)[:1000]) if failures else ("delivered", "")
            except Exception as exc:
                status, error = "failed", str(exc)[:1000]
        with control.store.transaction() as db:
            db.execute("UPDATE automation_notices SET status=?,error=? WHERE id=?", (status, error, notice["id"]))
