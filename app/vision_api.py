"""Standalone vision requests, sharing attachment admission and native transports."""
import asyncio
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from attachments import get_attachment_store
from attachments.access import principal_for_request, require_attachment
from attachments.admission import AdmissionContext, admit_content
from attachments.content import project_request_images, redact_image_payloads
from attachments.errors import AttachmentError
from attachments.lifecycle import garbage_collect
from attachments.metrics import snapshot as metrics_snapshot
from attachments.metrics import count, duration
from attachments.registry import AttachmentRegistry
from attachments.locking import attachment_lock

TERMINAL = {"completed", "failed", "cancelled"}


async def read_json(request, limit=256 * 1024):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(413, "Vision request too large")
    try:
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise HTTPException(400, "Expected a JSON object") from None


class VisionJobs:
    def __init__(self, work_dir, candidate_resolver):
        self.work_dir = Path(work_dir)
        self.path = self.work_dir / ".sugaragent" / "vision" / "requests.sqlite3"
        self.candidate_resolver = candidate_resolver
        self._schema_ready = False

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._schema_ready:
            with attachment_lock(self.path.parent, "vision-schema"):
                setup = sqlite3.connect(self.path, timeout=30)
                try:
                    setup.execute("PRAGMA journal_mode=WAL")
                    setup.execute("CREATE TABLE IF NOT EXISTS jobs (owner TEXT, id TEXT, fingerprint TEXT, state TEXT, result TEXT, updated REAL, cancelled INTEGER DEFAULT 0, PRIMARY KEY(owner,id))")
                    setup.execute("CREATE TABLE IF NOT EXISTS events (owner TEXT, id TEXT, seq INTEGER, payload TEXT, PRIMARY KEY(owner,id,seq))")
                    setup.execute("CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state,updated)")
                    setup.commit()
                    self._schema_ready = True
                finally:
                    setup.close()
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def start(self, owner, payload):
        identity = str(payload.get("requestId") or "")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", identity):
            raise HTTPException(400, "requestId must be a stable 1-128 character identifier")
        canonical = {key: value for key, value in payload.items() if key != "stream"}
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.connection() as db:
            existing = db.execute("SELECT fingerprint FROM jobs WHERE owner=? AND id=?", (owner.device_id, identity)).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise HTTPException(409, "requestId was already used for different input")
                return identity
        if not isinstance(payload.get("prompt"), str) or not payload["prompt"].strip():
            raise HTTPException(400, "prompt is required")
        if not isinstance(payload.get("modelProfileId"), str):
            raise HTTPException(400, "modelProfileId is required")
        output = payload.get("output") or {"format": "text"}
        if not isinstance(output, dict) or output.get("format", "text") not in {"text", "json_schema"}:
            raise HTTPException(400, "Unsupported output format")
        if output.get("format") == "json_schema":
            import jsonschema
            schema = output.get("schema")
            if not isinstance(schema, dict):
                raise HTTPException(400, "output.schema is required")
            def check_refs(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key in {"$ref", "$dynamicRef"} and (not isinstance(item, str) or not item.startswith("#")):
                            raise HTTPException(400, "Only local JSON Schema references are allowed")
                        check_refs(item)
                elif isinstance(value, list):
                    for item in value:
                        check_refs(item)
            check_refs(schema)
            try:
                jsonschema.Draft202012Validator.check_schema(schema)
            except jsonschema.SchemaError:
                raise HTTPException(400, "Invalid output schema") from None
        images = payload.get("images")
        if not isinstance(images, list) or not images:
            raise HTTPException(400, "images must be a nonempty attachment reference array")
        store = get_attachment_store(self.work_dir)
        if len(images) > store.limits.max_images_per_message:
            raise AttachmentError("Too many images in message", "TOO_MANY_IMAGES")
        # Access and aggregate limits are checked before a job is reserved.
        refs = [require_attachment(store, owner, item.get("attachmentId")) for item in images if isinstance(item, dict)]
        if len(refs) != len(images):
            raise HTTPException(400, "Invalid image reference")
        admit_content([{"type": "image", "attachment": ref} for ref in refs], AdmissionContext(store), strict=True)
        candidate = self.candidate_resolver(payload["modelProfileId"])
        initial = {"requestId": identity, "status": "accepted", "modelProfileId": candidate.get("profile_id", payload["modelProfileId"]),
                   "answer": "", "images": [], "usage": None}
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            # Recover abandoned reservations before applying the global bound.
            for stale_owner, stale_id, body in db.execute("SELECT owner,id,result FROM jobs WHERE state NOT IN ('completed','failed','cancelled') AND updated<?", (time.time() - 180,)).fetchall():
                stale = json.loads(body)
                stale.update(status="failed", error={"code": "VISION_INTERRUPTED", "message": "Worker stopped before completion"})
                db.execute("UPDATE jobs SET state='failed',result=? WHERE owner=? AND id=?", (json.dumps(stale), stale_owner, stale_id))
                self._publish_in_db(db, stale_owner, stale_id, {"type": "failed", **stale})
            existing = db.execute("SELECT fingerprint FROM jobs WHERE owner=? AND id=?", (owner.device_id, identity)).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise HTTPException(409, "requestId was already used for different input")
                return identity
            pending = db.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('completed','failed','cancelled')").fetchone()[0]
            if pending >= int(os.getenv("VISION_MAX_CONCURRENT_REQUESTS", "4")):
                raise HTTPException(429, "Vision concurrency limit reached")
            if db.execute("SELECT count(*) FROM jobs").fetchone()[0] >= int(os.getenv("VISION_MAX_STORED_REQUESTS", "10000")):
                raise HTTPException(507, "Vision history limit reached; prune completed request history")
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,0)", (owner.device_id, identity, fingerprint, "accepted", json.dumps(initial), time.time()))
        try:
            AttachmentRegistry(store).pin(owner.device_id, "vision:" + identity, [r["attachmentId"] for r in refs])
            threading.Thread(target=self._run, args=(owner.device_id, identity, payload, refs, candidate), name="vision-request", daemon=True).start()
        except Exception:
            initial.update(status="failed", error={"code": "VISION_START_FAILED", "message": "Could not start vision worker"})
            self.save(owner.device_id, identity, initial)
            raise
        return identity

    def publish(self, owner, identity, event):
        event = redact_image_payloads(event)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._publish_in_db(db, owner, identity, event)

    @staticmethod
    def _publish_in_db(db, owner, identity, event):
        seq = db.execute("SELECT coalesce(max(seq),0)+1 FROM events WHERE owner=? AND id=?", (owner, identity)).fetchone()[0]
        db.execute("INSERT INTO events VALUES (?,?,?,?)", (owner, identity, seq, json.dumps(event, ensure_ascii=False)))

    def finish(self, owner, identity, result):
        result = redact_image_payloads(result)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._publish_in_db(db, owner, identity, {"type": result["status"], **result})
            db.execute("UPDATE jobs SET state=?,result=?,updated=? WHERE owner=? AND id=?",
                       (result["status"], json.dumps(result, ensure_ascii=False), time.time(), owner, identity))
        count("vision." + result["status"])

    def save(self, owner, identity, result):
        with self.connection() as db:
            db.execute("UPDATE jobs SET state=?,result=?,updated=? WHERE owner=? AND id=?",
                       (result["status"], json.dumps(redact_image_payloads(result), ensure_ascii=False), time.time(), owner, identity))

    def cancelled(self, owner, identity):
        with self.connection() as db:
            row = db.execute("SELECT cancelled FROM jobs WHERE owner=? AND id=?", (owner, identity)).fetchone()
            return bool(row and row[0])

    def get(self, owner, identity):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT result,updated,state FROM jobs WHERE owner=? AND id=?", (owner, identity)).fetchone()
            if row is None:
                raise HTTPException(404, "Vision request not found")
            result = json.loads(row[0])
            if row[2] not in TERMINAL and time.time() - row[1] > 180:
                result.update(status="failed", error={"code": "VISION_INTERRUPTED", "message": "Worker stopped before completion; use a new requestId to retry"})
                db.execute("UPDATE jobs SET state='failed',result=? WHERE owner=? AND id=?", (json.dumps(result), owner, identity))
                self._publish_in_db(db, owner, identity, {"type": "failed", **result})
            return result

    def cancel(self, owner, identity):
        result = self.get(owner, identity)
        if result["status"] not in TERMINAL:
            with self.connection() as db:
                db.execute("UPDATE jobs SET cancelled=1 WHERE owner=? AND id=?", (owner, identity))
        return {"requestId": identity, "cancellationRequested": result["status"] not in TERMINAL, "status": result["status"]}

    def events(self, owner, identity, after):
        with self.connection() as db:
            return [(seq, json.loads(body)) for seq, body in db.execute("SELECT seq,payload FROM events WHERE owner=? AND id=? AND seq>? ORDER BY seq LIMIT 100", (owner, identity, after))]

    def prune(self, owner, identity):
        self.get(owner, identity)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state FROM jobs WHERE owner=? AND id=?", (owner, identity)).fetchone()
            if row and row[0] not in TERMINAL:
                raise HTTPException(409, "Cancel and wait for completion before pruning")
            db.execute("DELETE FROM events WHERE owner=? AND id=?", (owner, identity))
            db.execute("DELETE FROM jobs WHERE owner=? AND id=?", (owner, identity))
            AttachmentRegistry(get_attachment_store(self.work_dir)).pin(owner, "vision:" + identity, [])
        return {"requestId": identity, "deleted": True}

    def _run(self, owner, identity, payload, refs, candidate):
        result = self.get(owner, identity)
        store = get_attachment_store(self.work_dir)
        done = threading.Event()
        def heartbeat():
            while not done.wait(10):
                with self.connection() as db:
                    db.execute("UPDATE jobs SET updated=? WHERE owner=? AND id=? AND state NOT IN ('completed','failed','cancelled')", (time.time(), owner, identity))
        threading.Thread(target=heartbeat, daemon=True, name="vision-heartbeat").start()
        stream = None
        started = time.monotonic()
        deadline = started + float(os.getenv("VISION_REQUEST_TIMEOUT_SECONDS", "120"))
        try:
            self.publish(owner, identity, {"type": "accepted", "requestId": identity})
            if self.cancelled(owner, identity):
                raise AttachmentError("Vision request cancelled", "ATTACHMENT_CANCELLED")
            prompt = payload["prompt"]
            output = payload.get("output") or {}
            if output.get("format") == "json_schema":
                prompt += "\nReturn only JSON matching this schema:\n" + json.dumps(output["schema"], ensure_ascii=False)
            route = SimpleNamespace(_myagent_image_request_policy=candidate.get("image_request_policy") or {})
            result["images"] = []
            messages = project_request_images([{"role": "user", "content": [{"type": "text", "text": prompt}, *[{"type": "image", "attachment": ref} for ref in refs]]}],
                store=store, client=route, image_enabled="image" in set(candidate.get("input_modalities") or []), image_states=result["images"])
            result["status"] = "running"
            self.save(owner, identity, result)
            for image in result["images"]:
                self.publish(owner, identity, {"type": "image_prepared" if image["state"] == "prepared" else "image_omitted", **image})
            if not any(image["state"] == "prepared" for image in result["images"]):
                raise AttachmentError("No image fits the selected model capability and budget", "VISION_NO_IMAGES")
            if self.cancelled(owner, identity):
                raise AttachmentError("Vision request cancelled", "ATTACHMENT_CANCELLED")
            kwargs = {"model": candidate["model"], "messages": messages, "max_tokens": int(candidate.get("max_output_tokens") or 8192),
                      "temperature": candidate.get("temperature", 0), "timeout": min(30.0, max(0.1, deadline - time.monotonic()))}
            if candidate.get("extra_body"):
                kwargs["extra_body"] = candidate["extra_body"]
            if candidate.get("reasoning_effort"):
                kwargs["reasoning_effort"] = candidate["reasoning_effort"]
            stream = iter(candidate["transport"].stream_completion(**kwargs))
            last_save = time.monotonic()
            for event in stream:
                if self.cancelled(owner, identity):
                    raise AttachmentError("Vision request cancelled", "ATTACHMENT_CANCELLED")
                if time.monotonic() >= deadline:
                    raise AttachmentError("Vision request timed out", "VISION_TIMEOUT")
                for image in result["images"]:
                    if image["state"] == "prepared":
                        image["state"] = "sent"
                if event.kind == "content_delta":
                    result["answer"] += event.text
                    if len(result["answer"]) > 256 * 1024:
                        raise AttachmentError("Model output exceeds result limit", "VISION_OUTPUT_TOO_LARGE")
                    self.publish(owner, identity, {"type": "answer_delta", "text": event.text})
                if event.usage is not None:
                    result["usage"] = event.usage
                if time.monotonic() - last_save > 1:
                    self.save(owner, identity, result)
                    last_save = time.monotonic()
            if self.cancelled(owner, identity):
                raise AttachmentError("Vision request cancelled", "ATTACHMENT_CANCELLED")
            if not result["answer"].strip():
                raise AttachmentError("Model returned no answer", "VISION_EMPTY_RESPONSE")
            if output.get("format") == "json_schema":
                import jsonschema
                try:
                    structured = json.loads(result["answer"])
                    jsonschema.Draft202012Validator(output["schema"]).validate(structured)
                    result["structured"] = structured
                except (ValueError, jsonschema.ValidationError):
                    raise AttachmentError("Model output did not match the requested schema", "VISION_OUTPUT_INVALID") from None
            result["status"] = "completed"
        except Exception as exc:
            code = "ATTACHMENT_CANCELLED" if self.cancelled(owner, identity) else getattr(exc, "code", "VISION_PROVIDER_FAILED")
            result["status"] = "cancelled" if code == "ATTACHMENT_CANCELLED" else "failed"
            result["error"] = {"code": code, "message": str(exc) if isinstance(exc, AttachmentError) else "Vision provider request failed"}
        finally:
            if stream is not None:
                close = getattr(stream, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
            done.set()
            duration("vision", time.monotonic() - started)
            self.finish(owner, identity, result)
            # Retain references with completed request history. They are released
            # by explicit request-history pruning, never just by completion.


def register_vision_api(app, work_dir, candidate_resolver, gateway_resolver):
    jobs = VisionJobs(work_dir, candidate_resolver)
    router = APIRouter(prefix="/api/vision", tags=["vision"])
    def actor(request, scope="read"):
        return principal_for_request(request, gateway_resolver(), scope)

    @router.post("/analyze")
    async def analyze(request: Request):
        principal = actor(request, "write")
        payload = await read_json(request)
        try:
            identity = await asyncio.to_thread(jobs.start, principal, payload)
        except AttachmentError as exc:
            return JSONResponse({"ok": False, "code": exc.code, "error": str(exc)}, status_code=400)
        if payload.get("stream"):
            return stream_response(principal.device_id, identity, request, 0)
        while True:
            result = await asyncio.to_thread(jobs.get, principal.device_id, identity)
            if result["status"] in TERMINAL:
                return JSONResponse(result)
            if await request.is_disconnected():
                return JSONResponse({"requestId": identity, "status": "running"}, status_code=202)
            await asyncio.sleep(0.1)

    def stream_response(owner, identity, request, after):
        async def events():
            cursor = after
            while True:
                rows = await asyncio.to_thread(jobs.events, owner, identity, cursor)
                for seq, event in rows:
                    cursor = seq
                    yield f"id: {seq}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                result = await asyncio.to_thread(jobs.get, owner, identity)
                if result["status"] in TERMINAL and not rows:
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.1)
        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @router.get("/requests/{identity}")
    async def status(identity: str, request: Request):
        principal = actor(request)
        return await asyncio.to_thread(jobs.get, principal.device_id, identity)

    @router.get("/requests/{identity}/events")
    async def events(identity: str, request: Request, after: int = 0):
        principal = actor(request)
        await asyncio.to_thread(jobs.get, principal.device_id, identity)
        return stream_response(principal.device_id, identity, request, max(0, after))

    @router.delete("/requests/{identity}")
    async def cancel(identity: str, request: Request):
        principal = actor(request, "write")
        return await asyncio.to_thread(jobs.cancel, principal.device_id, identity)

    @router.get("/metrics")
    async def metrics(request: Request):
        actor(request, "admin")
        return metrics_snapshot()

    @router.delete("/requests/{identity}/history")
    async def prune(identity: str, request: Request):
        principal = actor(request, "write")
        return await asyncio.to_thread(jobs.prune, principal.device_id, identity)

    @router.post("/gc")
    async def gc(request: Request):
        actor(request, "admin")
        payload = await read_json(request)
        try:
            grace = float(payload.get("graceSeconds", 7 * 86400))
            if not math.isfinite(grace) or grace < 86400:
                raise ValueError()
        except (TypeError, ValueError):
            raise HTTPException(400, "graceSeconds must be finite and at least 86400") from None
        return await asyncio.to_thread(garbage_collect, get_attachment_store(work_dir),
                                       [Path(work_dir) / "sessions", Path(work_dir) / ".sugaragent" / "vision"],
                                       dry_run=payload.get("dryRun", True) is not False,
                                       grace_seconds=grace)

    app.include_router(router)
    return jobs
