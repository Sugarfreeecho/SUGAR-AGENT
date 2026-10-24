"""Bundled voice plugin: own HTTP routes and release providers on disable."""
import importlib.util
from pathlib import Path
import sys


def _runtime():
    name = "sugaragent_voice_input"
    if name not in sys.modules:
        root = Path(__file__).parent / "speech_input"
        spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    from importlib import import_module
    return import_module(name + ".api")


def install(app, context, plugin):
    if getattr(app.state, "voice_input_service", None) is not None:
        return
    from plugins.host import bundled_host_plugin_enabled
    app.state.voice_input_service = _runtime().register_speech_api(
        app, context["work_dir"], lambda: getattr(app.state, "remote_control_gateway", None),
        enabled_resolver=lambda: bundled_host_plugin_enabled(plugin.plugin_id),
    )


async def start(context, plugin):
    service = getattr(context["app"].state, "voice_input_service", None)
    if service is not None:
        service._closed = False


async def stop(context, plugin):
    service = getattr(context["app"].state, "voice_input_service", None)
    if service is not None:
        await service.close()
