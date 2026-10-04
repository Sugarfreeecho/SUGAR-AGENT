"""Computer Use settings and catalog adapter."""
from fastapi import APIRouter, HTTPException, Request

from execution_services import execution_service
from execution_services.computer import computer_manager


def tool_definitions(context, plugin):
    if not context["is_enabled"](plugin.plugin_id):
        return []
    manager = computer_manager()
    return list(manager.catalog) if manager.state == "ready" else []


def install(app, context, plugin):
    router = APIRouter()

    @router.get("/api/computer-use")
    async def status():
        from plugins.host import bundled_host_plugin_enabled
        manager = computer_manager(execution_service(context["session_manager"]))
        import agent_mcp
        configs, _error = agent_mcp._load_servers_dict_from_config()
        return {**manager.status(), "plugin_enabled": bundled_host_plugin_enabled(plugin.plugin_id),
                "mcp_servers": [alias for alias, cfg in (configs or {}).items()
                                if isinstance(cfg, dict) and cfg.get("command") and not cfg.get("url")]}

    @router.post("/api/computer-use")
    async def configure(request: Request):
        from plugins.host import bundled_host_plugin_enabled
        from plugin_web_gateway import validate_plugin_write_origin, PluginWebError
        if not bundled_host_plugin_enabled(plugin.plugin_id):
            raise HTTPException(404, "computer-use plugin is disabled")
        try:
            validate_plugin_write_origin(request.method, origin=request.headers.get("origin", ""),
                scheme=request.url.scheme, host=request.headers.get("host", ""),
                fetch_site=request.headers.get("sec-fetch-site", ""), require_origin=True)
        except PluginWebError as exc:
            raise HTTPException(exc.status, str(exc)) from exc
        try:
            data = await request.json()
        except ValueError as exc:
            raise HTTPException(400, "invalid JSON") from exc
        if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):
            raise HTTPException(422, "enabled must be a boolean")
        service = execution_service(context["session_manager"])
        manager = computer_manager(service)
        try:
            return await service.call(manager.configure, data["enabled"],
                data.get("provider", "native"), data.get("server_alias", "cua-driver-mcp"))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    app.include_router(router)


async def start(context, plugin):
    service = execution_service(context["session_manager"])
    manager = computer_manager(service)
    settings = manager.settings()
    if settings.get("enabled"):
        try:
            await service.call(manager.configure, settings["enabled"], settings.get("provider", "native"),
                settings.get("server_alias", "cua-driver-mcp"), save=False)
        except (ValueError, RuntimeError) as exc:
            manager.state, manager.error = "error", str(exc)


async def stop(context, plugin):
    service = execution_service(context["session_manager"])
    manager = computer_manager(service)
    if service._thread and service._thread.is_alive() and not service._closing:
        await service.call(manager.stop)
