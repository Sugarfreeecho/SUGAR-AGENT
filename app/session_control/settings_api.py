"""Same-origin native settings adapter; authority remains in the control service."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from fastapi.responses import JSONResponse

from .errors import ControlError, envelope
from .policy import Principal

METHODS = frozenset({"system.health", "session.list", "session.get", "tool_catalog.list",
    "automation.list", "automation.get", "automation.create", "automation.update", "automation.pause",
    "automation.resume", "automation.run", "automation.delete", "automation.history", "operation.get", "operation.cancel"})


def local_trigger(raw):
    """Resolve an explicitly zoned wall-clock one-shot without browser timezone drift."""
    if not isinstance(raw, dict) or "local_at" not in raw:
        return raw
    try:
        value = datetime.fromisoformat(raw["local_at"])
        if value.tzinfo is not None or raw.get("kind") != "at":
            raise ValueError()
        zone = ZoneInfo(raw.get("time_zone", "Asia/Shanghai"))
        aware = value.replace(tzinfo=zone, fold=0)
        if datetime.fromtimestamp(aware.timestamp(), zone).replace(tzinfo=None) != value:
            raise ValueError()
    except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
        raise ControlError("invalid_schedule", "Invalid local date/time or timezone; daylight-saving gaps cannot be scheduled") from exc
    return {"kind": "at", "at": aware.isoformat(), "time_zone": str(zone)}


def register_settings_adapter(application):
    async def rpc(request: Request):
        try:
            from remote_control.gateway import _is_direct_loopback_request
            from plugin_web_gateway import validate_plugin_write_origin, PluginWebError
            if not _is_direct_loopback_request(request) or request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise ControlError("forbidden", "Native schedule settings require a direct local connection", status=403)
            if request.headers.get("x-myagent-settings") != "schedules":
                raise ControlError("forbidden", "Native settings header required", status=403)
            try:
                validate_plugin_write_origin(request.method, origin=request.headers.get("origin", ""),
                    scheme=request.url.scheme, host=request.headers.get("host", ""),
                    fetch_site=request.headers.get("sec-fetch-site", ""), require_origin=True)
            except PluginWebError as exc:
                raise ControlError(exc.code, str(exc), status=exc.status) from exc
            body = await application.body(request)
            method, params = body.get("method"), body.get("params", {})
            if method not in METHODS:
                raise ControlError("forbidden", "Method is unavailable in schedule settings", status=403)
            if not isinstance(params, dict) or any(k.startswith("_") for k in params):
                raise ControlError("invalid_params", "Reserved or invalid request parameters")
            if method == "automation.list":
                params = {**params, "kind_filter": "schedule"}
            if method in {"automation.create", "automation.update"} and "trigger" in params:
                params = {**params, "trigger": local_trigger(params["trigger"])}
                if not isinstance(params["trigger"], dict) or params["trigger"].get("kind") == "event":
                    raise ControlError("invalid_schedule", "Use a time trigger for scheduled tasks")
                try:
                    ZoneInfo(params["trigger"].get("time_zone", "Asia/Shanghai"))
                except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
                    raise ControlError("invalid_schedule", "Choose a valid IANA timezone") from exc
            if method in {"automation.create", "automation.update"} and "end_local" in params:
                params = dict(params)
                end = params.pop("end_local")
                params["end_at"] = datetime.fromisoformat(local_trigger({"kind": "at", **end})["at"]).timestamp() if end else None
            result, replay = await application.service.execute(Principal("native:schedules", "Schedule settings", True),
                method, params, idempotency_key=body.get("idempotency_key", ""))
            if method in {"automation.create", "automation.update", "automation.pause", "automation.resume", "automation.run", "automation.delete", "operation.cancel"}:
                await asyncio.to_thread(application.identities.remote.audit,
                    principal_id="native:schedules", action=method, target=str(params.get("id") or ""),
                    outcome="replayed" if replay else "ok")
            return JSONResponse(envelope(result, operation_id=result.get("operation_id")), headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return application.error(exc)
    application.router.add_api_route("/api/settings/session-control", rpc, methods=["POST"])
