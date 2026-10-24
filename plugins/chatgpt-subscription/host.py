"""SugarAgent's bundled-host entry; all implementation stays in this plugin."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import re
import threading
from urllib.parse import urlsplit
import webbrowser

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

# Host entries are loaded under unique module names, not as import packages.
_package = __name__ + "_plan"
_spec = importlib.util.spec_from_file_location(_package, Path(__file__).parent / "chatgpt_plan/__init__.py",
    submodule_search_locations=[str(Path(__file__).parent / "chatgpt_plan")])
_module = importlib.util.module_from_spec(_spec)
sys.modules[_package] = _module
_spec.loader.exec_module(_module)
Runtime = importlib.import_module(_package + ".adapter").Runtime
PlanError = importlib.import_module(_package + ".auth").PlanError
_runtime = None
_lock = threading.RLock()


def _enabled():
    from plugins.host import bundled_host_plugin_enabled
    return bundled_host_plugin_enabled("chatgpt-subscription")


def _get_runtime():
    global _runtime
    with _lock:
        if _runtime is None:
            _runtime = Runtime(enabled=_enabled)
        return _runtime


def install(app, context, _plugin):
    router = APIRouter(prefix="/api/chatgpt-subscription")

    def guard(request):
        if not _enabled():
            raise HTTPException(404, "ChatGPT subscription plugin is disabled")
        # Account actions are only available from a local SugarAgent browser.
        if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
            raise HTTPException(403, "Please use SugarAgent on this computer")
        if request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise HTTPException(403, "Invalid local Host")
        origin = request.headers.get("origin", "")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme != request.url.scheme or parsed.netloc != request.headers.get("host"):
                raise HTTPException(403, "Cross-origin access denied")
        if request.method != "GET":
            from plugin_web_gateway import validate_plugin_write_origin, PluginWebError
            try:
                validate_plugin_write_origin(request.method, origin=origin, scheme=request.url.scheme,
                    host=request.headers.get("host", ""), fetch_site=request.headers.get("sec-fetch-site", ""),
                    require_origin=True)
            except PluginWebError as exc:
                raise HTTPException(exc.status, str(exc)) from None

    async def call(function, *args):
        try:
            return await run_in_threadpool(function, *args)
        except PlanError as exc:
            raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None
        except Exception:
            raise HTTPException(500, "插件运行失败，请检查插件依赖或凭据存储权限。") from None

    async def payload(request):
        try:
            value = await request.json()
        except ValueError:
            raise HTTPException(400, "Invalid JSON") from None
        if not isinstance(value, dict):
            raise HTTPException(400, "Expected a JSON object")
        if any(not isinstance(value.get(key, ""), str) for key in ("account_id", "model", "name")):
            raise HTTPException(422, "account_id, model and name must be strings")
        if len(value.get("name", "").strip()) > 80:
            raise HTTPException(422, "配置名称最多 80 个字符。")
        return value

    def connection_status():
        from model_profiles import load_store
        result = _get_runtime().accounts.public_status()
        known = {row["id"] for row in result["accounts"]}
        result["profiles"] = []
        for row in load_store(Path(context["project_root"])).get("profiles", []):
            if not isinstance(row, dict):
                continue
            try:
                base = urlsplit(str(row.get("base_url") or ""))
            except ValueError:
                continue
            match = re.fullmatch(r"/accounts/([a-f0-9]{24})/v1/?", base.path)
            if base.hostname != "127.0.0.1" or not match or match[1] not in known:
                continue
            if not str(row.get("id", "")).startswith("chatgpt-" + match[1] + "-"):
                continue
            result["profiles"].append({"id": row["id"], "account_id": match[1],
                "name": str(row.get("name") or row.get("model") or ""),
                "model": str(row.get("model") or ""), "enabled": row.get("enabled") is not False})
        return result

    @router.get("/status")
    async def status(request: Request):
        guard(request)
        return await call(connection_status)

    @router.post("/notice")
    async def notice(request: Request):
        guard(request)
        await call(lambda: _get_runtime().accounts.acknowledge_plan_notice())
        return {"ok": True}

    @router.post("/login")
    async def login(request: Request):
        guard(request)
        data = await payload(request)
        url = await call(lambda: _get_runtime().sign_in(data.get("account_id", "")))
        try:
            opened = await run_in_threadpool(webbrowser.open, url)
        except Exception:
            opened = False
        # No ID-token hints or other tokens are ever included in this URL.
        return {"authorization_url": url, "browser_opened": bool(opened)}

    @router.post("/cancel")
    async def cancel(request: Request):
        guard(request)
        await call(lambda: _get_runtime().accounts.cancel())
        return {"ok": True}

    @router.post("/logout")
    async def logout(request: Request):
        guard(request)
        data = await payload(request)
        return await call(lambda: _get_runtime().accounts.sign_out(data.get("account_id", "")))

    @router.get("/models")
    async def models(request: Request, account_id: str):
        guard(request)
        return {"models": await call(lambda: _get_runtime().models(account_id))}

    @router.post("/test")
    async def test_model(request: Request):
        guard(request)
        data = await payload(request)
        return await call(lambda: _get_runtime().test_model(data.get("account_id", ""), data.get("model", "")))

    @router.post("/profiles")
    async def profiles(request: Request):
        guard(request)
        data = await payload(request)

        def save():
            from model_profiles import public_profile, upsert_profile
            runtime = _get_runtime()
            profile = runtime.profile(data.get("account_id", ""), data.get("model", ""), data.get("name", "").strip())
            public = public_profile(upsert_profile(Path(context["project_root"]), profile))
            public.pop("api_key", None)
            public.pop("headers", None)
            return {"profile": public}

        return await call(save)

    # A content-signature reload creates a new module. Replace this plugin's
    # routes so requests do not keep reaching the previous module's runtime.
    prefix = router.prefix
    app.router.routes[:] = [route for route in app.router.routes
                           if getattr(route, "path", "") != prefix
                           and not getattr(route, "path", "").startswith(prefix + "/")]
    app.include_router(router)
    app.openapi_schema = None


async def start(_context, _plugin):
    # Bind lazily on fresh installations; restore the stable port for saved
    # model profiles after a host restart. Failure does not block SugarAgent.
    def restore():
        runtime = _get_runtime()
        with runtime.vault.locked():
            port = runtime.vault.read().get("port")
        if port:
            try:
                runtime.start()
            except PlanError:
                pass  # Login/profile actions report an actionable port error.
    await asyncio.to_thread(restore)


async def stop(_context, _plugin):
    global _runtime
    with _lock:
        runtime, _runtime = _runtime, None
    if runtime:
        await asyncio.to_thread(runtime.stop)
