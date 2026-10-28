"""Public, allowlisted runtime assets shared by isolated plugin pages."""
from pathlib import Path

from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

STATIC = Path(__file__).resolve().parent / "templates" / "static"
PAGE_ASSETS = {
    "plugin-page-bridge.js": "application/javascript",
    "plugin-page.css": "text/css",
    "workflow-console.js": "application/javascript",
    "workflow-console.css": "text/css",
}
ASSET_ROUTE = "/plugin-assets/{plugin_id}/{asset_path:path}"


async def serve_plugin_asset(plugin_id: str, asset_path: str):
    from plugin_web_gateway import PluginWebError, plugin_asset
    try:
        path = await run_in_threadpool(plugin_asset, plugin_id, asset_path)
    except PluginWebError as exc:
        return JSONResponse({"ok": False, "error": exc.code, "message": str(exc)}, status_code=exc.status)
    suffix = path.suffix.lower()
    media_type = {".js": "application/javascript", ".mjs": "application/javascript", ".css": "text/css"}.get(suffix)
    return FileResponse(str(path), media_type=media_type,
                        headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})


def install_plugin_page_assets(app):
    """Also repairs an already-running host when bundled plugins are reloaded."""
    paths = {"/static/" + name for name in PAGE_ASSETS}
    replace_asset_route = any(isinstance(route, APIRoute) and route.path == ASSET_ROUTE for route in app.router.routes)
    if replace_asset_route:
        paths.add(ASSET_ROUTE)
    app.router.routes[:] = [route for route in app.router.routes
                            if not isinstance(route, APIRoute) or route.path not in paths]

    def endpoint(name, media_type):
        async def serve():
            return FileResponse(str(STATIC / name), media_type=media_type,
                                headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})
        return serve

    for name, media_type in PAGE_ASSETS.items():
        app.add_api_route("/static/" + name, endpoint(name, media_type), methods=["GET"],
                          name="plugin_page_asset:" + name, include_in_schema=False)
    if replace_asset_route:
        app.add_api_route(ASSET_ROUTE, serve_plugin_asset, methods=["GET"], name="plugin_web_asset", include_in_schema=False)
    app.openapi_schema = None
