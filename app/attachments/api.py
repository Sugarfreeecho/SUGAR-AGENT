"""HTTP admission and portable backup for the shared attachment store."""
import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from . import get_attachment_store
from .access import principal_for_request, require_attachment
from .admission import AdmissionContext, admit_content
from .errors import AttachmentError
from .lifecycle import add_bundle, import_bundle
from .locking import attachment_lock
from .registry import AttachmentRegistry


def register_attachment_api(app, work_dir, gateway_resolver):
    router = APIRouter(prefix="/api/attachments", tags=["attachments"])
    store = get_attachment_store(work_dir)

    @router.post("/ingest")
    async def ingest(request: Request):
        from vision_api import read_json
        actor = principal_for_request(request, gateway_resolver(), "write")
        payload = await read_json(request)
        urls = payload.get("urls")
        if not isinstance(urls, list) or not urls or len(urls) > store.limits.max_images_per_message or any(not isinstance(url, str) or not url.startswith(("http://", "https://")) for url in urls):
            raise HTTPException(400, "urls must be a nonempty image URL array within the message count limit")
        # This explicit operation always stores images, independent of chat's
        # passthrough mode. It accepts no local filesystem path from HTTP.
        from dataclasses import replace
        from .remote import RemoteImagePolicy
        policy = RemoteImagePolicy.from_env()
        if policy.mode == "disabled":
            raise HTTPException(403, "Remote images are disabled")
        def commit():
            blocks = admit_content([{"type": "image_url", "image_url": {"url": url}} for url in urls],
                                   AdmissionContext(store, replace(policy, mode="ingest")), strict=True)
            refs = [block["attachment"] for block in blocks]
            AttachmentRegistry(store).grant(actor.device_id, [ref["attachmentId"] for ref in refs])
            return refs
        try:
            return {"ok": True, "images": await asyncio.to_thread(commit)}
        except AttachmentError as exc:
            return JSONResponse({"ok": False, "code": exc.code, "error": str(exc)}, status_code=400)

    @router.post("/export")
    async def export(request: Request):
        from vision_api import read_json
        actor = principal_for_request(request, gateway_resolver(), "admin")
        payload = await read_json(request)
        ids = payload.get("attachmentIds")
        if not isinstance(ids, list) or len(ids) > 2000:
            raise HTTPException(400, "Invalid attachmentIds")
        def build():
            fd, name = tempfile.mkstemp(prefix="myagent-images-", suffix=".zip")
            os.close(fd)
            path = Path(name)
            try:
                with attachment_lock(store.root.parent, "catalog"), zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
                    for identity in ids:
                        require_attachment(store, actor, identity)
                    add_bundle(archive, store, ids)
                return path
            except Exception:
                path.unlink(missing_ok=True)
                raise
        path = await asyncio.to_thread(build)
        return FileResponse(path, media_type="application/zip", filename="attachments.zip", background=BackgroundTask(path.unlink, missing_ok=True))

    @router.post("/import")
    async def restore(request: Request):
        actor = principal_for_request(request, gateway_resolver(), "admin")
        limit = min(int(os.getenv("ATTACHMENT_STORE_MAX_BYTES", str(10 * 1024 ** 3))), 512 * 1024 ** 2)
        fd, name = tempfile.mkstemp(prefix="myagent-image-import-", suffix=".zip")
        os.close(fd)
        path = Path(name)
        try:
            size = 0
            with path.open("wb") as target:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, "Attachment archive too large")
                    await asyncio.to_thread(target.write, chunk)
            refs = await asyncio.to_thread(import_bundle, store, path)
            await asyncio.to_thread(AttachmentRegistry(store).grant, actor.device_id, [ref["attachmentId"] for ref in refs])
            return {"ok": True, "images": refs}
        except (AttachmentError, zipfile.BadZipFile, KeyError, ValueError, TypeError) as exc:
            return JSONResponse({"ok": False, "code": getattr(exc, "code", "INVALID_ATTACHMENT_BUNDLE")}, status_code=400)
        finally:
            path.unlink(missing_ok=True)

    app.include_router(router)
