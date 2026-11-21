import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plugin_bus  # noqa: E402


def setup_function(_):
    plugin_bus.reset()


def test_call_requires_declared_permission():
    async def handler(caller, method, params):
        return {"ok": True}

    plugin_bus.register("browser-use", "browser", handler, methods={"send_text"})
    plugin_bus.note_plugin("sugar-assistant", {"services": []})
    try:
        asyncio.run(plugin_bus.call("sugar-assistant", "browser", "send_text", {}))
    except PermissionError as exc:
        assert "未声明" in str(exc)
    else:
        raise AssertionError("应当拒绝未声明权限的调用")


def test_call_rejects_method_outside_whitelist():
    async def handler(caller, method, params):
        return {"ok": True}

    plugin_bus.register("browser-use", "browser", handler, methods={"send_text"})
    plugin_bus.note_plugin("sugar-assistant", {"services": ["browser"]})
    try:
        asyncio.run(plugin_bus.call("sugar-assistant", "browser", "read_all_tabs", {}))
    except PermissionError as exc:
        assert "白名单" in str(exc)
    else:
        raise AssertionError("应当拒绝白名单外的方法")


def test_call_passes_and_audits():
    async def handler(caller, method, params):
        return {"echo": params.get("text")}

    plugin_bus.register("browser-use", "browser", handler, methods={"send_text"})
    plugin_bus.note_plugin("sugar-assistant", {"services": ["browser"]})
    result = asyncio.run(plugin_bus.call("sugar-assistant", "browser", "send_text", {"text": "hi"}))
    assert result == {"echo": "hi"}
    assert plugin_bus.audit()[-1]["method"] == "send_text"
