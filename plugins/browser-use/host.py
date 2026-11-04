"""Browser settings, scoped pairing and live UI transport for SugarAgent."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from .runtime import BrowserManager
from .page_context import normalize_context, with_page_reference

_manager = None
CAPABILITIES = ["system.health", "session.list", "session.get", "session.history", "session.search", "session.attach", "session.detach",
    "session.config.get", "operation.get", "operation.wait", "session.create", "session.send", "session.steer", "session.interrupt",
    "session.update", "session.archive", "session.delete", "session.config.update", "approval.list", "approval.resolve",
    # The paired browser is a trusted local path: it manages its own schedules
    # exactly like the main window. Ownership still scopes every object, and
    # admin surfaces (device.revoke, webhook sources, native settings) stay closed.
    "read", "automation.list", "automation.get", "automation.history", "automation.create",
    "automation.update", "automation.pause", "automation.resume", "automation.run", "automation.delete"]


def pairing_identity(code):
    return hashlib.sha256("".join(str(code).upper().split()).replace("-", "").encode()).hexdigest()


def extension_origin():
    # Keep the installed plugin self-contained. A contract test checks this id
    # against the fixed public key shipped with the extension manifest.
    return "chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo"


def restore_pairing_grants(application):
    """Separate existing user pairings from short-lived plugin run leases.

    Migrate only live original browser grants, never delegated task credentials,
    expired/revoked grants, capabilities, or a pairing removed by the user.
    Live original pairings are also brought up to the current trusted capability
    set so an existing pairing never needs to be redone after a capability change.
    """
    paired = {row["id"] for row in application.store.list("browser_connections")
              if not row.get("revoked") and row.get("origin") == extension_origin()}
    if not paired:
        return
    with application.store.transaction() as db:
        rows = db.execute("SELECT token_hash,principal,policy FROM grants WHERE revoked=0 AND expires>?", (time.time(),)).fetchall()
        for token_hash, raw, policy in rows:
            principal = json.loads(raw)
            ancestors = principal.get("source_ancestors") or []
            if (principal.get("id") not in paired or principal.get("admin") or principal.get("parent_id")
                    or principal.get("parent_credential") or principal.get("delegated_policies")
                    or len(ancestors) != 1 or ancestors[0].get("id") != "browser-use"
                    or ancestors[0].get("kind", "plugin") not in {"plugin", "browser-pairing"}
                    or not set(json.loads(policy).get("capabilities", [])).issubset(CAPABILITIES)):
                continue
            principal["source_ancestors"] = [{**ancestors[0], "kind": "browser-pairing"}]
            row_policy = json.loads(policy)
            granted = list(row_policy.get("capabilities", []))
            missing = [name for name in CAPABILITIES if name not in granted]
            if missing:
                row_policy["capabilities"] = [*granted, *missing]
            db.execute("UPDATE grants SET principal=?, policy=? WHERE token_hash=?",
                       (json.dumps(principal), json.dumps(row_policy), token_hash))


def websocket_close_code(error):
    from session_control.errors import ControlError
    if isinstance(error, PermissionError) or isinstance(error, ControlError) and error.status == 401:
        return 4401
    if isinstance(error, ControlError) and error.status == 403:
        return 4403
    return 1011


def control():
    from session_control.public import control_application
    return control_application()


def authorize_session(principal, method, session_id):
    from session_control.errors import ControlError
    try:
        control().service.authorize(principal, method, {"session_id": session_id})
    except ControlError as error:
        raise HTTPException(error.status, error.message) from error


async def history_reference(principal, session_id, predicate):
    def find(value):
        if isinstance(value, dict):
            if predicate(value):
                return value
            children = value.values()
        elif isinstance(value, list):
            children = value
        else:
            return None
        for child in children:
            result = find(child)
            if result is not None:
                return result
        return None
    before = None
    while True:
        page = await control().service._read(principal, "session.history", {"session_id": session_id, "limit": 500, "before_index": before})
        result = find(page.get("events", []))
        if result is not None:
            return result
        next_before = page.get("range_start")
        if not page.get("has_older") or next_before is None or next_before == before:
            return None
        before = next_before


def require_local_ui(request):
    if not _manager or not _manager.enabled():
        raise HTTPException(404, "Browser plugin is disabled")
    from remote_control.gateway import _is_direct_loopback_request
    from plugin_web_gateway import validate_plugin_write_origin, PluginWebError
    if not _is_direct_loopback_request(request):
        raise HTTPException(403, "Browser connections are local-only")
    try:
        validate_plugin_write_origin(request.method, origin=request.headers.get("origin", ""), scheme=request.url.scheme,
            host=request.headers.get("host", ""), fetch_site=request.headers.get("sec-fetch-site", ""), require_origin=True)
    except PluginWebError as error:
        raise HTTPException(error.status, str(error)) from error


def authenticate(request):
    from session_control.errors import ControlError
    from remote_control.gateway import _is_direct_loopback_request
    if not _is_direct_loopback_request(request):
        raise HTTPException(403, "Browser connections are local-only")
    if not _manager or not _manager.enabled():
        raise HTTPException(503, "Browser connection plugin is temporarily unavailable")
    origin = request.headers.get("origin", "").rstrip("/")
    # Chromium extension workers can omit Origin on authenticated GETs.
    # These reads still require the paired bearer identity below. Explicit
    # foreign origins and all writes without the extension origin stay denied.
    if origin != extension_origin() and (origin or request.method not in {"GET", "HEAD"}):
        raise HTTPException(403, "Unexpected browser extension origin")
    try:
        application = control()
        principal = application.principal(request)
        record = application.store.get("browser_connections", principal.id)
        if not record or record.get("revoked") or record.get("origin") != extension_origin():
            raise HTTPException(401, "Browser authorization was revoked")
        application.identities.ensure_live(principal)
        application.service.authorize(principal, "system.health", {})
        return principal, record
    except ControlError as error:
        raise HTTPException(error.status, error.message) from error


def tool_definitions(context, plugin):
    return list(_manager.catalog) if _manager and _manager.active and context["is_enabled"](plugin.plugin_id) else []


def install(app, context, plugin):
    router = APIRouter(prefix="/api/browser/v1", tags=["browser-use"])
    from .human import install_human_routes
    install_human_routes(router, authenticate, authorize_session, control)
    from .subagents import install_subagent_routes
    install_subagent_routes(router, authenticate, control)

    def require_setup_ui(request):
        from remote_control.gateway import _is_direct_loopback_request
        from urllib.parse import urlsplit
        origin = request.headers.get("origin", "")
        if not _is_direct_loopback_request(request) or request.headers.get("sec-fetch-site") == "cross-site" or (origin and urlsplit(origin).netloc != request.url.netloc):
            raise HTTPException(403, "Setup is available only in the local app settings")

    @router.get("/setup")
    async def setup_status(request: Request):
        require_setup_ui(request)
        from .setup import snapshot
        return {**await asyncio.to_thread(snapshot), "plugin_enabled": bool(_manager and _manager.enabled()), "protocol": 1}

    @router.post("/setup/install")
    async def setup_install(request: Request):
        require_local_ui(request)
        from .setup import install_runtime
        if _manager and any(runtime.state.get("connected") for runtime in _manager.runtimes.values()):
            raise HTTPException(409, "浏览器已连接，运行组件无需重新安装。")
        try:
            return await install_runtime()
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @router.get("/setup/download")
    async def setup_download(request: Request):
        require_setup_ui(request)
        from .setup import snapshot, ROOT
        from fastapi.responses import FileResponse
        info = await asyncio.to_thread(snapshot)
        if not info["download_ready"]:
            raise HTTPException(404, "扩展包尚未构建")
        path = ROOT / "outputs" / "browser-extension" / ("sugaragent-browser-" + info["version"] + ".zip")
        return FileResponse(path, filename=path.name, media_type="application/zip", headers={"Cache-Control": "no-store"})

    @router.post("/setup/reveal")
    async def setup_reveal(request: Request):
        require_local_ui(request)
        from .setup import reveal_extension
        try:
            await asyncio.to_thread(reveal_extension)
        except (OSError, ValueError) as error:
            raise HTTPException(409, str(error)) from error
        return {"opened": True}

    @router.get("/status")
    async def status():
        application = control()
        records = application.store.list("browser_connections")
        return {"extension_origin": extension_origin(), "plugin_enabled": bool(_manager and _manager.enabled()),
                "devices": [{**record, "runtime": dict(_manager.runtimes[record["id"]].state) if _manager and record["id"] in _manager.runtimes else {"connected": False}} for record in records],
                "default_browser": _manager.default_browser if _manager else ""}

    @router.post("/pairings")
    async def pairing(request: Request):
        require_local_ui(request)
        application = control()
        data = await application.body(request, 4096)
        issued = await asyncio.to_thread(application.identities.remote.create_pairing,
            label=str(data.get("name") or "SugarAgent Browser")[:100], scopes=["read", "write", "approvals"], ttl_seconds=600)
        identity = pairing_identity(issued["code"])
        application.store.put("browser_pairings", identity, {"expires": time.time() + 600, "name": str(data.get("name") or "SugarAgent 浏览器")[:100]})
        return issued

    @router.post("/claim")
    async def claim(request: Request):
        from remote_control.gateway import _is_direct_loopback_request
        if not _is_direct_loopback_request(request):
            raise HTTPException(403, "Browser pairing is local-only")
        if not _manager or not _manager.enabled():
            raise HTTPException(404, "Browser plugin is disabled")
        if request.headers.get("origin", "").rstrip("/") != extension_origin():
            raise HTTPException(403, "Unexpected browser extension origin")
        application = control()
        data = await application.body(request, 4096)
        code = str(data.get("code") or "").strip().upper()
        identity = pairing_identity(code)
        pairing = application.store.get("browser_pairings", identity)
        if not pairing or pairing["expires"] < time.time():
            raise HTTPException(401, "Invalid or expired browser pairing code")
        from remote_control.store import PairingCodeError
        try:
            issued = await asyncio.to_thread(application.identities.remote.consume_pairing, code,
                device_name=str(pairing.get("name") or data.get("name") or "SugarAgent Browser")[:100])
        except PairingCodeError as error:
            raise HTTPException(401, "Invalid or expired pairing code") from error
        application.store.delete("browser_pairings", identity)
        from session_control.policy import Principal
        from session_control.public import source_state
        source = source_state("browser-use", True)
        browser_id = issued["device_id"]
        principal = Principal(browser_id, issued["device_name"], policy={"scope": "all", "capabilities": CAPABILITIES},
            source_ancestors=[{"id": "browser-use", "epoch": source["epoch"], "kind": "browser-pairing"}])
        token = application.identities.issue(principal, ttl=365 * 24 * 3600)
        record = {"id": browser_id, "name": issued["device_name"], "origin": extension_origin(), "revoked": False, "created_at": time.time()}
        application.store.put("browser_connections", browser_id, record)
        return {"token": token, "browser_id": browser_id}

    @router.get("/connection")
    async def connection_status(request: Request):
        principal, record = await asyncio.to_thread(authenticate, request)
        return {"paired": True, "browser_id": record["id"]}

    @router.post("/devices/{browser_id}/revoke")
    async def revoke(browser_id: str, request: Request):
        require_local_ui(request)
        application = control()
        record = application.store.get("browser_connections", browser_id)
        if not record:
            raise HTTPException(404, "Browser not found")
        application.identities.remote.revoke_device(browser_id)
        application.store.put("browser_connections", browser_id, {**record, "revoked": True})
        if _manager:
            runtime=_manager.forget_browser(browser_id)
            if runtime:
                await _manager.service.call(runtime.close)
        selected=application.store.get("browser_preferences", "default") or {}
        if selected.get("browser_id")==browser_id:
            remaining=[row["id"] for row in application.store.list("browser_connections") if not row.get("revoked")]
            fallback=_manager.default_browser if _manager and _manager.default_browser in remaining else next(iter(remaining),"")
            application.store.put("browser_preferences", "default", {"browser_id":fallback})
        return {"revoked": True}

    @router.post("/default")
    async def select_default(request: Request):
        require_local_ui(request)
        application = control()
        data = await application.body(request, 4096)
        browser_id = str(data.get("browser_id") or "")
        record = application.store.get("browser_connections", browser_id)
        if not record or record.get("revoked"):
            raise HTTPException(404, "Browser not found")
        _manager.default_browser = browser_id
        application.store.put("browser_preferences", "default", {"browser_id": browser_id})
        return {"default_browser": browser_id, "effective_from": "next_run"}

    @router.get("/models")
    async def models(request: Request):
        await asyncio.to_thread(authenticate, request)
        import model_profiles
        root = Path(__file__).resolve().parents[2]
        return {"profiles": [model_profiles.public_profile(profile) for profile in model_profiles.sorted_profiles(root)
                             if model_profiles.is_usable_profile(profile)]}

    @router.get("/workspaces")
    async def workspaces(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        application = control()
        result, _ = await application.service.execute(principal, "session.list", {})
        from agent_harness import WORK_DIR
        default = str(WORK_DIR)
        paths = [default, *[str(row.get("work_dir") or default) for row in result["sessions"]]]
        unique = list(dict.fromkeys(paths))
        return {"default_work_dir": default, "workspaces": [{"path": path, "name": Path(path).name or path} for path in unique]}

    @router.post("/workspaces/pick")
    async def pick_workspace(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        application = control()
        data = await application.body(request, 4096)
        sid = str(data.get("session_id") or "")
        if sid:
            await asyncio.to_thread(authorize_session, principal, "session.update", sid)
        else:
            application.service.authorize(principal, "session.create", {})
        from path_picker_util import pick_native_path
        from agent_harness import WORK_DIR
        initial = str(data.get("initial") or WORK_DIR)
        try:
            path = await asyncio.to_thread(pick_native_path, "directory", initial, False)
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error
        return {"cancelled": not bool(path), "path": str(path or "")}

    @router.post("/workspaces/validate")
    async def validate_workspace(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        application = control()
        application.service.authorize(principal, "session.create", {})
        data = await application.body(request, 4096)
        path = Path(str(data.get("path") or "")).expanduser()
        if not path.is_absolute() or not await asyncio.to_thread(path.is_dir):
            raise HTTPException(422, "请选择已存在的绝对目录")
        from session_control.errors import ControlError
        try:
            application.service.check_workspace(principal, str(path))
        except ControlError as error:
            raise HTTPException(error.status, error.message) from error
        return {"path": str(path.resolve())}

    @router.get("/plugins")
    async def sidebar_plugins(request: Request):
        await asyncio.to_thread(authenticate, request)
        from agent_extensions import plugin_catalog_snapshot
        snapshot = await asyncio.to_thread(plugin_catalog_snapshot)
        rows = []
        for row in snapshot.get("plugins", []):
            identity = row.get("plugin_id") or row.get("id")
            section = next((item for item in snapshot.get("ui_contributions", []) if item.get("plugin_id") == identity and item.get("slot") == "settings.section"), None)
            rows.append({"id": identity, "name": row.get("name") or identity, "description": str(row.get("description") or ""),
                "enabled": bool(row.get("enabled")), "loaded": bool(row.get("loaded")),
                "settings_section": "plugin:" + str(identity) + ":" + str(section["id"]) if section else "plugins"})
        return {"plugins": rows}

    @router.get("/skills")
    async def sidebar_skills(request: Request):
        await asyncio.to_thread(authenticate, request)
        from agent_tools import discover_skills
        skills = await asyncio.to_thread(discover_skills, include_disabled=True)
        return {"skills": [{"name": str(skill.get("name") or ""), "description": str(skill.get("description") or ""),
                            "enabled": skill.get("enabled") is not False} for skill in skills if str(skill.get("name") or "").strip()]}

    @router.post("/uploads")
    async def uploads(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        application = control()
        await asyncio.to_thread(authorize_session, principal, "session.send", request.query_params.get("session_id"))
        form = await request.form()
        files = form.getlist("files")
        if not files or len(files) > 32 or any(not hasattr(item, "read") for item in files):
            raise HTTPException(422, "Expected uploaded files")
        # Reuse the same bounded image/file admission as the main UI. This is a
        # trusted in-process call; the external identity was checked above.
        from webui import upload_chat_files
        response = await upload_chat_files(files, request=None)
        data = json.loads(response.body)
        if response.status_code != 200:
            return response
        from attachments import get_attachment_store
        from attachments.registry import AttachmentRegistry
        from agent_harness import WORK_DIR
        store = get_attachment_store(WORK_DIR)
        result = []
        for item in data["files"]:
            identity = uuid.uuid4().hex
            application.store.put("message_uploads", identity, {**item, "owner": principal.id, "created_at": time.time()})
            if item.get("attachment"):
                AttachmentRegistry(store).grant(principal.id, [item["attachment"]["attachmentId"]])
            result.append({"id": identity, "name": item["name"], "size": item["size"]})
        return {"files": result}

    @router.post("/approvals/analyze")
    async def analyze(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        application = control()
        data = await application.body(request, 4096)
        await asyncio.to_thread(authorize_session, principal, "approval.list", data.get("session_id"))
        # The host route owns the reviewer and stores/publishes its analysis.
        from webui import analyze_session_approval
        return await analyze_session_approval(data["session_id"], data["approval_id"])

    @router.post("/messages")
    async def browser_message(request: Request):
        principal, record = await asyncio.to_thread(authenticate, request)
        application = control()
        try:
            data = await application.body(request)
            allowed = {"session_id", "message", "ui_message", "attachments", "selected_skills", "mode", "browser_context", "automatic", "idempotency_key", "composer", "edit_operation_id"}
            if set(data) - allowed or data.get("mode", "queue") not in {"queue", "pending", "append", "interrupt"}:
                raise ValueError("Unsupported browser message fields")
            await asyncio.to_thread(authorize_session, principal, "session.send", data.get("session_id"))
            message = data.get("message")
            if not isinstance(message, str) or not message.strip():
                raise ValueError("message must be non-empty text")
            ui_message = data.get("ui_message", message)
            if not isinstance(ui_message, str):
                raise ValueError("ui_message must be text")
            requested = data.get("selected_skills", [])
            if not isinstance(requested, list) or len(requested) > 32 or any(not isinstance(name, str) or not name.strip() or len(name) > 512 for name in requested):
                raise ValueError("请选择有效的 Skill，一次最多 32 个")
            requested = list(dict.fromkeys(name.strip() for name in requested))
            from .pending import composer_snapshot
            draft=composer_snapshot(data,requested) if data.get('mode')=='pending' else None
            if requested:
                from webui import _valid_selected_skill_names, _build_agent_message_with_selected_skills, _build_ui_message_with_selected_skills
                selected = await asyncio.to_thread(_valid_selected_skill_names, requested)
                if selected != requested:
                    raise HTTPException(409, "所选 Skill 已停用或不可用，请重新选择：" + ", ".join(name for name in requested if name not in selected))
                message = _build_agent_message_with_selected_skills(message, selected)
                ui_message = _build_ui_message_with_selected_skills(ui_message, selected)
            key = data.get("idempotency_key")
            if not isinstance(key, str) or not 1 <= len(key) <= 128:
                raise ValueError("A browser message idempotency key is required")
            captured = normalize_context(data.get("browser_context"), record["id"], data.get("automatic", True))
            if not _manager or not _manager.enabled():
                raise HTTPException(404, "Browser plugin is unavailable")
            from session_control.public import register_source_lifecycle, transport_service
            _manager.control_service = application.service
            register_source_lifecycle("browser-use", before=_manager.begin_input, after=_manager.finish_input)
            params = {"session_id": data["session_id"], "message": with_page_reference(message, captured),
                      "ui_message": ui_message, "mode": "queue" if draft is not None else data.get("mode", "queue"),
                      "_browser_context": captured, "_source_lifecycle": True}
            if draft is not None:params.update(_browser_pending=True,_browser_draft=draft,_browser_client_id=key)
            if "attachments" in data:
                params["attachments"] = data["attachments"]
            if 'edit_operation_id' in data:
                if draft is None or not isinstance(data['edit_operation_id'],str) or not data['edit_operation_id'].strip():raise ValueError('Only pending messages can be edited')
                from session_control.attachments import prepare_message_attachments
                from .pending import edit_pending
                changes=await asyncio.to_thread(prepare_message_attachments,principal,params,application.store)
                # An empty attachment list must also clear an earlier admitted
                # canonical payload, otherwise the old text would be executed.
                changes.setdefault('_legacy_user_content',None)
                operation=await asyncio.to_thread(edit_pending,application,principal,data['session_id'],data['edit_operation_id'],changes)
                await asyncio.to_thread(application.identities.remote.audit,principal_id=principal.id,action='browser.pending.edit',target=data['session_id'],outcome='ok')
                return {'ok':True,'data':application.service.receipt(operation)}
            await application.service.start()
            result, _ = await transport_service("browser-use").execute(principal, "session.send", params, idempotency_key=key)
            if draft is not None:
                from .pending import pending_item
                result['pending_item']=await asyncio.to_thread(pending_item,application,principal,application.store.get_operation(result['operation_id']))
            return {"ok": True, "data": result}
        except HTTPException:
            raise
        except Exception as error:
            return application.error(error)

    @router.post("/steers")
    async def sidebar_steers(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        data = await control().body(request, 4096)
        sid = data.get("session_id")
        await asyncio.to_thread(authorize_session, principal, "session.history", sid)
        from agent_loop import list_session_steers
        result = await asyncio.to_thread(list_session_steers, sid, include_terminal=True)
        await asyncio.to_thread(authorize_session, principal, "session.history", sid)
        # Do not expose expanded Skill prompts, attachment paths or model input.
        fields = {"id", "client_id", "ui_content", "ui_attachments", "state", "version", "consumed_by", "error", "mode"}
        rows = [{key: value for key, value in row.items() if key in fields}
                for row in result.get("items", []) if row.get("mode") in {"append","interrupt"} and not row.get("after_turn")]
        from .pending import pending_messages,started_pending_turns
        pending=await asyncio.to_thread(pending_messages,control(),principal,sid)
        started=await asyncio.to_thread(started_pending_turns,control(),principal,sid)
        await asyncio.to_thread(authorize_session, principal,"session.history",sid)
        return {"ok": True, "items": rows[-128:], "pending":pending,"started_pending":started}

    @router.post('/pending/cancel')
    async def cancel_pending_message(request:Request):
        principal,_=await asyncio.to_thread(authenticate, request)
        data=await control().body(request,4096)
        if set(data)-{'session_id','operation_id'}:raise HTTPException(400,'Invalid pending action')
        sid=data.get('session_id');identity=data.get('operation_id')
        if not isinstance(identity,str) or not identity or not isinstance(sid,str) or not sid:raise HTTPException(400,'Missing pending message')
        await asyncio.to_thread(authorize_session, principal,'session.send',sid)
        from .pending import cancel_pending
        result=await asyncio.to_thread(cancel_pending,control(),principal,sid,identity)
        await asyncio.to_thread(control().identities.remote.audit,principal_id=principal.id,action='browser.pending.cancel',target=sid,outcome='ok')
        return result

    @router.post("/session-state")
    async def sidebar_state(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        data = await control().body(request, 4096)
        sid = str(data.get("session_id") or "")
        if sid:
            await asyncio.to_thread(authorize_session, principal, "session.get", sid)
        from security import security_status_for_session
        tokens, token_error = None, ""
        if sid:
            try:
                from webui import get_session_context_tokens
                response = await get_session_context_tokens(sid)
                result = json.loads(response.body)
                if response.status_code >= 400 or not result.get("ok", True):
                    token_error = str(result.get("error") or "上下文用量暂不可用")
                else:
                    tokens = result
            except Exception:
                token_error = "上下文用量暂不可用"
        # Token estimation can be slow; read the global mode just before the
        # response so a change made in the main app during estimation is kept.
        permissions = await asyncio.to_thread(security_status_for_session, sid)
        permissions["can_change"] = bool(sid) and principal.permits("session.update") and all(
            policy.get("scope") == "all" for policy in [principal.policy, *principal.delegated_policies])
        return {"permissions": permissions, "context_tokens": tokens, "context_error": token_error}

    @router.post("/permissions")
    async def sidebar_permissions(request: Request):
        principal, _ = await asyncio.to_thread(authenticate, request)
        data = await control().body(request, 4096)
        sid = str(data.get("session_id") or "")
        if not sid:
            raise HTTPException(422, "请先打开会话再修改权限")
        if not principal.permits("session.update") or not all(
                policy.get("scope") == "all" for policy in [principal.policy, *principal.delegated_policies]):
            raise HTTPException(403, "当前连接不能修改全局权限")
        if sid:
            await asyncio.to_thread(authorize_session, principal, "session.update", sid)
        mode = data.get("mode")
        if mode not in {"ask_for_approval", "approve_for_me", "full_access"}:
            raise HTTPException(422, "无效的权限模式")
        if mode == "full_access" and data.get("confirmed_full_access") is not True:
            raise HTTPException(409, "请先确认完全访问对所有会话生效")
        from security import security_status_for_session
        status = await asyncio.to_thread(security_status_for_session, sid)
        if not status.get("available_modes", {}).get(mode):
            raise HTTPException(409, "当前安全设置不允许切换此权限模式")
        from webui import _apply_session_permission_mode
        return {"permissions": {**await _apply_session_permission_mode(sid, mode), "can_change": True}}

    @router.get("/files")
    async def sidebar_file(request: Request, session_id: str, rel: str = "", attachment_id: str = ""):
        principal, _ = await asyncio.to_thread(authenticate, request)
        application = control()
        await asyncio.to_thread(authorize_session, principal, "session.history", session_id)
        from fastapi.responses import Response
        from urllib.parse import quote
        root = None
        if attachment_id:
            from attachments import get_attachment_store
            from agent_harness import WORK_DIR
            store = get_attachment_store(WORK_DIR)
            ref = await history_reference(principal, session_id, lambda value: value.get("attachmentId") == attachment_id and value.get("name"))
            if not ref:
                raise HTTPException(404, "文件不在此会话中")
            try:
                path = await asyncio.to_thread(store.image_host_path if ref.get("mediaType") else store.file_host_path, ref)
                path = Path(path)
            except Exception:
                raise HTTPException(404, "文件不存在") from None
        else:
            from urllib.parse import unquote
            info = await application.service._read(principal, "session.get", {"session_id": session_id, "include_runtime": True})
            root = Path(info["session"]["work_dir"]).resolve()
            raw = unquote(rel).strip()
            if not raw or len(raw) > 4096:
                raise HTTPException(422, "无效的文件路径")
            path = (root / raw).resolve()
            if not path.is_relative_to(root):
                def matches(value):
                    if value.get("type") != "local_file":
                        return False
                    local = value.get("local_file")
                    source = local.get("path") if isinstance(local, dict) else local or value.get("path")
                    return isinstance(source, str) and Path(source).resolve() == path
                if not await history_reference(principal, session_id, matches):
                    raise HTTPException(403, "文件不在当前工作区或会话附件中")
        if path.is_dir():
            import os
            from fastapi.responses import JSONResponse
            def listing():
                entries = []
                with os.scandir(path) as source:
                    for entry in source:
                        entries.append({"name": entry.name, "type": "directory" if entry.is_dir(follow_symlinks=False) else "file"})
                        if len(entries) > 200:
                            break
                truncated = len(entries) > 200
                entries = sorted(entries[:200], key=lambda entry: (entry["type"] != "directory", entry["name"].casefold()))
                parent = str(path.parent) if root is not None and path != root and path.parent.is_relative_to(root) else None
                return {"name": path.name, "path": str(path), "parent": parent, "entries": entries, "truncated": truncated}
            try:
                content = await asyncio.to_thread(listing)
            except PermissionError:
                raise HTTPException(403, "没有权限读取此文件夹") from None
            except OSError:
                raise HTTPException(404, "文件夹不可用") from None
            return JSONResponse(content, headers={"Cache-Control":"no-store", "X-Resource-Type":"directory"})
        if not path.is_file():
            raise HTTPException(404, "文件不存在")
        # Render text in the extension; never execute a local HTML document.
        def read():
            with path.open("rb") as source:
                return source.read(2_000_001)
        content = await asyncio.to_thread(read)
        if len(content) > 2_000_000:
            raise HTTPException(413, "文件大于 2 MB，请在主程序打开")
        import mimetypes
        return Response(content, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-File-Name": quote(path.name)})

    @router.get("/media")
    async def media(request: Request, session_id: str, attachment_id: str = "", rel: str = ""):
        principal, _ = await asyncio.to_thread(authenticate, request)
        application = control()
        await asyncio.to_thread(authorize_session, principal, "session.history", session_id)
        if attachment_id:
            from attachments import get_attachment_store
            from attachments.registry import AttachmentRegistry
            from attachments.errors import AttachmentError
            from agent_harness import WORK_DIR
            from fastapi.responses import Response
            store = get_attachment_store(WORK_DIR)
            try:
                permitted = await asyncio.to_thread(AttachmentRegistry(store).allowed, principal.id, attachment_id)
                # A shared conversation may contain images uploaded in the main
                # application. Require an actual reference in its authorized history.
                def references(value):
                    if isinstance(value, dict):
                        return value.get("attachmentId") == attachment_id or any(references(item) for item in value.values())
                    return isinstance(value, list) and any(references(item) for item in value)
                before = None
                while not permitted:
                    page = await application.service._read(principal, "session.history", {"session_id": session_id, "limit": 500, "before_index": before})
                    permitted = references(page.get("events", []))
                    if permitted or not page.get("has_older"):
                        break
                    next_before = page.get("range_start")
                    if next_before is None or next_before == before:
                        break
                    before = next_before
                if not permitted:
                    raise HTTPException(404, "Image not found in this conversation")
                ref = await asyncio.to_thread(store.ref_by_id, attachment_id)
                stored = await store.read_image(ref)
            except (AttachmentError, ValueError):
                raise HTTPException(404, "Image not found") from None
            return Response(stored.data, media_type=ref["mediaType"], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        if not rel or len(rel) > 4096:
            raise HTTPException(422, "Expected an image reference")
        info = await application.service._read(principal, "session.get", {"session_id": session_id, "include_runtime": True})
        from webui import _workspace_media_response, _VIEWABLE_IMAGE_SUFFIXES
        return await _workspace_media_response(rel, allowed_suffixes=_VIEWABLE_IMAGE_SUFFIXES,
            kind_label="image", work_root=Path(info["session"]["work_dir"]))

    @router.websocket("/ws")
    async def websocket(socket: WebSocket):
        from remote_control.gateway import _is_direct_loopback_request
        if not _is_direct_loopback_request(socket) or socket.headers.get("origin", "").rstrip("/") != extension_origin() or not _manager or not _manager.enabled():
            await socket.close(code=4403)
            return
        await socket.accept()
        async def close_socket(code, reason):
            from starlette.websockets import WebSocketState
            if socket.application_state == WebSocketState.DISCONNECTED:
                return
            try:
                await socket.close(code=code, reason=reason)
            except (RuntimeError, WebSocketDisconnect):
                pass  # A sender or another watcher may already have closed it.
        forwarder = None
        outgoing = asyncio.Queue(maxsize=1000)
        async def send():
            try:
                while True:
                    await socket.send_text(json.dumps(await outgoing.get(),ensure_ascii=False,default=str,allow_nan=False))
            except asyncio.CancelledError:
                raise
            except Exception:
                await close_socket(1011, "Session delivery failed; reconnect to recover")
        sender = asyncio.create_task(send())
        application = control()
        authenticated = False
        selected_session = ""
        metadata_task = None
        metadata_listener = None
        recovery_task = None
        presence_keys = set()
        presence_prefix = "browser-sidebar:" + uuid.uuid4().hex + ":"
        try:
            hello = await asyncio.wait_for(socket.receive_json(), 15)
            principal = application.identities.authenticate(str(hello.get("token") or ""))
            record = application.store.get("browser_connections", principal.id)
            if hello.get("type") != "hello" or not record or record.get("revoked"):
                raise PermissionError("Invalid browser identity")
            application.service.authorize(principal, "system.health", {})
            authenticated = True
            runtime = await _manager.service.call(_manager.ensure, record)
            if hello.get("browser_id") != record["id"]:
                raise PermissionError("Browser binding mismatch")
            metadata_changed = asyncio.Event()
            loop = asyncio.get_running_loop()
            def changed(sid, fields):
                if selected_session and (not sid or sid == selected_session) and fields & {"name", "created", "deleted", "pinned", "archived", "work_dir"}:
                    if not loop.is_closed():
                        loop.call_soon_threadsafe(metadata_changed.set)
            metadata_listener = changed
            application.service.manager.add_session_state_listener(changed)
            async def metadata_updates():
                from session_control.errors import ControlError
                while True:
                    await metadata_changed.wait()
                    metadata_changed.clear()
                    target = selected_session
                    if not target:
                        continue
                    try:
                        application.service.authorize(principal, "session.get", {"session_id": target})
                        result = await application.service._read(principal, "session.get", {"session_id": target})
                        summary = {key: value for key, value in result["session"].items() if key in {"id", "name", "updated_at", "last_activity_at", "created_at", "pinned", "archived", "is_subagent", "parent_session_id"}}
                        if selected_session == target:
                            await outgoing.put({"type": "session.metadata", "session_id": target, "session": summary})
                    except ControlError as error:
                        if error.code == "session_not_found":
                            await outgoing.put({"type": "session.metadata", "session_id": target, "deleted": True})
                        else:
                            await close_socket(websocket_close_code(error), "Session authorization unavailable")
                            return
            metadata_task = asyncio.create_task(metadata_updates())
            async def recover_executions(target):
                from runtime_v2.execution_journal import ExecutionJournal
                from session_control.errors import ControlError
                try:
                    application.service.authorize(principal, "session.history", {"session_id": target})
                    page = await application.service._read(principal, "session.history", {"session_id": target, "turns": 15})
                    seqs = [int(event["runtime_seq"]) for event in page.get("events", []) if event.get("runtime_seq")]
                    journal = ExecutionJournal(application.service.manager.sessions_dir,
                                               path_resolver=application.service.manager._resolve_session_path)
                    recovery = await asyncio.to_thread(journal.read, target, min_runtime_seq=min(seqs) if seqs else None)
                    application.service.authorize(principal, "session.history", {"session_id": target})
                    if selected_session != target:
                        return
                    records = [row for row in recovery["execution_records"] if row.get("kind") == "tool"
                               or row.get("kind") in {"reasoning", "response"} and not row.get("ui_committed")][-512:]
                    if not application.service.deps.is_stream_active(target):
                        for row in records:
                            if row.get("status") in {"running", "generating", "waiting_execution"}:
                                row["status"] = "unknown" if row.get("executed") else "interrupted"
                    if records:
                        await outgoing.put({"type": "session.executions", "session_id": target, "records": records})
                except ControlError as error:
                    if error.code != "session_not_found":
                        await close_socket(websocket_close_code(error), "Session authorization unavailable")
                except Exception:
                    if selected_session == target:
                        await outgoing.put({"type": "session.error", "session_id": target, "message": "执行记录恢复失败，请重新打开会话；实时连接仍可接收新事件。"})
            await outgoing.put({"type": "ready", "browser_id": record["id"], "relay_url": runtime.relay_url()})
            async def forward(session_id):
                from session_event_bus import SessionStreamOverflow, subscribe_session_events
                from session_control.errors import ControlError
                try:
                    application.service.authorize(principal, "session.attach", {"session_id": session_id})
                    async for event in subscribe_session_events(session_id, replay_recent=True, persistent=True, fail_on_overflow=True):
                        if event is None:
                            break
                        actual_session = str(event.get("session_id") or session_id)
                        if actual_session != session_id and str(event.get("type") or "").startswith(("interaction_", "approval_")):
                            try:
                                await asyncio.to_thread(authorize_session, principal, "session.history", actual_session)
                            except HTTPException as error:
                                if error.status_code in {403, 404}:
                                    continue
                                raise
                        if outgoing.full():
                            raise SessionStreamOverflow("Browser socket buffer overflowed")
                        outgoing.put_nowait({"type": "session.event", "session_id": session_id, "event": event})
                    await close_socket(1012, "Session subscription ended; reconnect to recover")
                except asyncio.CancelledError:
                    raise
                except SessionStreamOverflow:
                    await close_socket(4429, "Reload history after reconnect")
                except ControlError as error:
                    await close_socket(websocket_close_code(error), "Session authorization unavailable")
                except Exception:
                    await close_socket(1011, "Session subscription failed; reconnect to recover")
            while True:
                message = await asyncio.wait_for(socket.receive_json(), 45)
                application.service.authorize(principal, "system.health", {})
                if not _manager or not _manager.enabled():
                    from session_control.errors import ControlError
                    raise ControlError("source_disabled", "Browser plugin was disabled", status=403)
                kind = message.get("type")
                if kind == "ping":
                    await outgoing.put({"type": "pong"})
                elif kind == "ui.presence":
                    identity = str(message.get("id") or "")
                    if not identity or len(identity) > 100:
                        raise ValueError("Invalid sidebar identity")
                    from webui import update_ui_attention_surface
                    key = presence_prefix + identity
                    active = message.get("active") is True
                    if active:
                        if key not in presence_keys and len(presence_keys) >= 16:
                            raise ValueError("Too many sidebar surfaces")
                        presence_keys.add(key)
                    else:
                        presence_keys.discard(key)
                    update_ui_attention_surface(key, active)
                elif kind == "relay.request":
                    await outgoing.put({"type": "relay", "url": runtime.relay_url()})
                elif kind == "subscribe":
                    if recovery_task:
                        recovery_task.cancel()
                        await asyncio.gather(recovery_task, return_exceptions=True)
                    if forwarder:
                        forwarder.cancel()
                        await asyncio.gather(forwarder, return_exceptions=True)
                    session_id = str(message.get("session_id") or "")
                    selected_session = ""
                    if session_id:
                        from session_control.errors import ControlError
                        try:
                            application.service.authorize(principal, "session.attach", {"session_id": session_id})
                        except ControlError as error:
                            if error.code in {"unauthorized", "source_disabled", "authorization_revoked"}:
                                raise
                            await outgoing.put({"type": "session.error", "session_id": session_id, "code": error.code, "message": error.message})
                            continue
                        _manager.bindings[session_id] = record["id"]
                        forwarder = asyncio.create_task(forward(session_id))
                        # Run the generator through subscriber registration before
                        # acknowledging. The client fetches history only after this.
                        await asyncio.sleep(0)
                    await outgoing.put({"type": "subscribed", "session_id": session_id})
                    selected_session = session_id
                    if session_id:
                        metadata_changed.set()
                        recovery_task = asyncio.create_task(recover_executions(session_id))
                elif kind == "pause":
                    await _manager.service.call(runtime.request, "pause", {"paused": bool(message.get("paused"))})
                    if not message.get("paused"):
                        await outgoing.put({"type": "relay", "url": runtime.relay_url()})
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass
        except Exception as error:
            from session_control.errors import ControlError
            code = websocket_close_code(error)
            if code == 1011:
                try:
                    await socket.send_json({"type": "error", "code": "browser_runtime_unavailable", "message": str(error)[:500]})
                except (RuntimeError, WebSocketDisconnect):
                    pass
            await close_socket(code, "Browser authorization unavailable" if code == 4401 else "Browser connection temporarily unavailable")
        finally:
            if presence_keys:
                from webui import update_ui_attention_surface
                for key in presence_keys:
                    update_ui_attention_surface(key, False)
            if metadata_listener is not None:
                application.service.manager.remove_session_state_listener(metadata_listener)
            sender.cancel()
            if forwarder:
                forwarder.cancel()
            if metadata_task:
                metadata_task.cancel()
            if recovery_task:
                recovery_task.cancel()
            await asyncio.gather(sender, *([forwarder] if forwarder else []), *([metadata_task] if metadata_task else []), *([recovery_task] if recovery_task else []), return_exceptions=True)

    paths = {route.path for route in router.routes}
    app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", "") not in paths]
    app.include_router(router)
    app.openapi_schema = None


async def start(context, plugin):
    global _manager
    from execution_services import execution_service
    from session_event_bus import add_event_listener
    service = execution_service(context["session_manager"])
    _manager = BrowserManager(service)
    _manager.control_service = control().service
    from session_control.public import register_source_lifecycle, source_state
    add_event_listener(_manager.on_event)
    service.register_shutdown_callback(_manager.close)
    application = control()
    source_state("browser-use", True, app=application)
    await asyncio.to_thread(restore_pairing_grants, application)
    for record in application.store.list("browser_connections"):
        if not record.get("revoked"):
            try:
                await service.call(_manager.ensure, record)
            except (RuntimeError, OSError):
                pass  # Settings remain available to diagnose missing optional Node dependencies.
    selected = application.store.get("browser_preferences", "default") or {}
    if selected.get("browser_id") in _manager.runtimes:
        _manager.default_browser = selected["browser_id"]
    register_source_lifecycle("browser-use", before=_manager.begin_input, after=_manager.finish_input)


async def stop(context, plugin):
    global _manager
    if _manager:
        service = getattr(_manager, "control_service", None)
        for name, callback in (("source_before_run", _manager.begin_input), ("source_after_run", _manager.finish_input)):
            registry = service.callbacks.get(name, {}) if service else {}
            if registry.get("browser-use") == callback:
                registry.pop("browser-use", None)
        from session_event_bus import remove_event_listener
        remove_event_listener(_manager.on_event)
        _manager.service.unregister_shutdown_callback(_manager.close)
        await _manager.service.call(_manager.close)
        _manager = None
