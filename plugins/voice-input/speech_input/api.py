"""Plugin-owned transient speech HTTP API; audio never becomes an attachment."""
import asyncio
import json
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from attachments.access import principal_for_request
from .protocol import MAX_AUDIO_BYTES
from .service import SpeechError, SpeechService


async def read_body(request, limit):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, "Speech request exceeds size limit")
        data.extend(chunk)
    return bytes(data)


def register_speech_api(app, work_dir, gateway_resolver=lambda: None, service=None, enabled_resolver=lambda: True):
    service = service or SpeechService(work_dir)
    router = APIRouter(prefix="/api/speech", tags=["speech"])

    def actor(request, scope="read", require_enabled=True):
        if require_enabled and not enabled_resolver():
            raise HTTPException(404, "Voice plugin is disabled")
        return principal_for_request(request, gateway_resolver(), scope)

    async def payload(request):
        try:
            value = json.loads(await read_body(request, 24 * 1024))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except ValueError as error:
            raise HTTPException(400, "Expected a JSON object") from error

    def failed(error):
        return JSONResponse({"ok": False, "code": error.code, "error": str(error)}, status_code=error.status)

    @router.get("/status")
    async def status(request: Request):
        actor(request, require_enabled=False)
        return {**await service.snapshot(), "plugin_enabled": enabled_resolver()}

    @router.patch("/config")
    async def configure(request: Request):
        actor(request, "admin")
        try:
            return await service.configure(await payload(request))
        except SpeechError as error:
            return failed(error)

    @router.post("/prepare")
    async def prepare(request: Request):
        actor(request, "admin")
        data = await payload(request)
        if set(data) - {"source"} or not isinstance(data.get("source", "auto"), str):
            raise HTTPException(400, "Invalid model source")
        try:
            await service.prepare(data.get("source", "auto"))
            return await service.snapshot()
        except SpeechError as error:
            return failed(error)

    @router.delete("/prepare")
    async def cancel_preparation(request: Request):
        actor(request, "admin")
        await service.cancel_preparation()
        return await service.snapshot()

    @router.post("/transcribe")
    async def transcribe(request: Request):
        principal = actor(request, "write")
        identity = request.headers.get("x-speech-request-id", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identity):
            raise HTTPException(400, "A speech request id is required")
        audio = await read_body(request, MAX_AUDIO_BYTES)
        task = asyncio.create_task(service.transcribe(audio, principal.device_id, identity))
        try:
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    break
                await asyncio.wait({task}, timeout=0.1)
            return {"ok": True, **await task}
        except asyncio.CancelledError:
            return JSONResponse({"ok": False, "code": "cancelled"}, status_code=409)
        except SpeechError as error:
            return failed(error)
        except ValueError as error:
            return JSONResponse({"ok": False, "code": "invalid-audio", "error": str(error)}, status_code=400)
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @router.delete("/transcriptions/{identity}")
    async def cancel(identity: str, request: Request):
        principal = actor(request, "write")
        await service.cancel(principal.device_id, identity)
        return {"ok": True}

    @router.post("/synthesize")
    async def synthesize(request: Request):
        principal = actor(request, "write")
        data = await payload(request)
        identity = data.get("requestId", "")
        if not isinstance(identity, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identity):
            raise HTTPException(400, "A speech request id is required")
        task = asyncio.create_task(service.synthesize(data.get("text"), principal.device_id, identity))
        try:
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    break
                await asyncio.wait({task}, timeout=.1)
            audio, media_type = await task
            return Response(audio, media_type=media_type, headers={"Cache-Control": "no-store"})
        except asyncio.CancelledError:
            return JSONResponse({"ok": False, "code": "cancelled"}, status_code=409)
        except SpeechError as error:
            return failed(error)
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @router.post("/synthesize/stream")
    async def synthesize_stream(request: Request):
        principal = actor(request, "write")
        data = await payload(request)
        identity = data.get("requestId", "")
        if not isinstance(identity, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identity):
            raise HTTPException(400, "A speech request id is required")
        try:
            key, rate = service.stream_parameters(data.get("text"))
        except SpeechError as error:
            return failed(error)

        async def audio():
            async for chunk in service.stream_speech(data["text"], key, principal.device_id, identity):
                if await request.is_disconnected():
                    return
                yield chunk

        return StreamingResponse(audio(), media_type="audio/pcm", headers={
            "Cache-Control": "no-store", "X-Sample-Rate": str(rate), "X-Channels": "1", "X-Format": "pcm16",
        })

    app.include_router(router)
    return service
