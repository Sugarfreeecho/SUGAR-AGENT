"""Persistent JSON-RPC-style process worker for Python plugins.

The host exchanges newline-delimited JSON requests and responses over stdio.
Plugin stdout is redirected to stderr so it cannot corrupt the protocol
channel.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib.util
import inspect
import json
import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

from myagent_plugin_sdk import PLUGIN_API_VERSION, Plugin


def _load_module(root: Path, entrypoint: Path) -> ModuleType:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    module_name = f"_myagent_plugin_{abs(hash(str(entrypoint)))}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        entrypoint,
        submodule_search_locations=[str(root)]
        if entrypoint.name == "__init__.py"
        else None,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load plugin entrypoint: {entrypoint}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_HERMES_HOOK_MAP = {
    "pre_tool_call": "PreToolUse",
    "post_tool_call": "PostToolUse",
    "on_session_start": "SessionStart",
    "on_session_end": "SessionEnd",
    "on_session_finalize": "SessionEnd",
    "subagent_start": "SubagentStart",
    "subagent_stop": "SubagentStop",
    "pre_verify": "Stop",
}


async def _call_with_supported_kwargs(callback: Any, kwargs: Mapping[str, Any]) -> Any:
    try:
        signature = inspect.signature(callback)
        accepts_all = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        selected = dict(kwargs) if accepts_all else {
            name: value for name, value in kwargs.items() if name in signature.parameters
        }
    except (TypeError, ValueError):
        selected = dict(kwargs)
    result = callback(**selected)
    return await result if inspect.isawaitable(result) else result


def _normalise_hermes_hook_result(hook_name: str, result: Any) -> Any:
    if not isinstance(result, Mapping):
        return {} if result is None else {"additional_context": str(result)}
    output = dict(result)
    if hook_name == "pre_verify":
        action = str(output.get("action") or "").lower()
        decision = str(output.get("decision") or "").lower()
        if action == "continue" or decision == "block":
            return {
                "decision": "deny",
                "reason": str(output.get("message") or output.get("reason") or ""),
                "additional_context": str(output.get("message") or ""),
            }
    action = str(output.get("action") or "").lower()
    if output.get("block") is True or action in {"block", "deny", "skip"}:
        output["decision"] = "deny"
    if "updated_args" in output and "updated_input" not in output:
        output["updated_input"] = output["updated_args"]
    return output


class _HermesPluginContext:
    """Subset adapter for Hermes standalone tools, hooks, and commands."""

    def __init__(self, registry: Plugin) -> None:
        self.registry = registry
        self._hook_counts: dict[str, int] = {}

    def register_tool(
        self,
        name: str,
        toolset: str = "",
        schema: Optional[Mapping[str, Any]] = None,
        handler: Any = None,
        check_fn: Any = None,
        requires_env: Any = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
        override: bool = False,
    ) -> None:
        _ = toolset, check_fn, requires_env, is_async, emoji, override
        raw_schema = dict(schema or {})
        parameters = raw_schema.get("parameters", raw_schema)
        tool_description = description or str(raw_schema.get("description") or "")

        def wrapped(**arguments: Any) -> Any:
            return handler(dict(arguments))

        self.registry.register_tool(
            name,
            wrapped,
            description=tool_description,
            input_schema=parameters,
        )

    def register_hook(self, hook_name: str, callback: Any) -> None:
        event = _HERMES_HOOK_MAP.get(str(hook_name or ""))
        if event is None:
            return
        count = self._hook_counts.get(hook_name, 0) + 1
        self._hook_counts[hook_name] = count

        async def wrapped(payload: Mapping[str, Any]) -> Any:
            kwargs = dict(payload)
            if isinstance(payload.get("tool_input"), Mapping):
                kwargs.setdefault("args", dict(payload["tool_input"]))
            if "tool_output" in payload:
                kwargs.setdefault("result", payload.get("tool_output"))
            result = await _call_with_supported_kwargs(callback, kwargs)
            return _normalise_hermes_hook_result(hook_name, result)

        self.registry.register_hook(
            event,
            wrapped,
            hook_id=f"hermes-{hook_name.replace('_', '-')}-{count}",
        )

    def register_command(
        self,
        name: str,
        handler: Any,
        description: str = "",
        args_hint: str = "",
    ) -> None:
        async def wrapped(arguments: str, context: Mapping[str, Any]) -> Any:
            _ = context
            result = handler(arguments)
            result = await result if inspect.isawaitable(result) else result
            return str(result or arguments)

        self.registry.register_command(
            str(name or "").lstrip("/").replace(" ", "-"),
            wrapped,
            description=description,
            usage=args_hint,
        )

    def register_cli_command(self, *args: Any, **kwargs: Any) -> None:
        _ = args, kwargs


def _load_registry(root: Path, entrypoint: Path, adapter: str = "native") -> Plugin:
    with contextlib.redirect_stdout(sys.stderr):
        module = _load_module(root, entrypoint)
        if adapter == "hermes":
            register = getattr(module, "register", None)
            if not callable(register):
                raise RuntimeError("Hermes plugin entrypoint must expose register(ctx)")
            registry = Plugin()
            configured = register(_HermesPluginContext(registry))
            return configured if isinstance(configured, Plugin) else registry
        exported = getattr(module, "plugin", None)
        if isinstance(exported, Plugin):
            return exported
        setup = getattr(module, "setup", None)
        if not callable(setup):
            raise RuntimeError(
                "Plugin entrypoint must expose `plugin = Plugin()` or `setup(plugin)`"
            )
        registry = Plugin()
        configured = setup(registry)
        if isinstance(configured, Plugin):
            registry = configured
        return registry


async def _handle(registry: Plugin, request: Mapping[str, Any]) -> Any:
    method = str(request.get("method") or "")
    if method == "plugin.describe":
        return {
            "api_version": PLUGIN_API_VERSION,
            "tools": registry.describe_tools(),
            "hooks": registry.describe_hooks(),
            "commands": registry.describe_commands(),
            "deferred_results": registry.supports_deferred_results,
            "http": registry.supports_http,
            "background_services": registry.describe_background_services(),
        }
    if method == "plugin.ping":
        return {"api_version": PLUGIN_API_VERSION, "status": "ready"}
    if method == "plugin.shutdown":
        return {"status": "stopping"}
    if method == "background.status":
        return {"services": registry.background_service_status()}
    if method == "tool.call":
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise ValueError("tool.call params must be an object")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, Mapping):
            raise ValueError("tool.call arguments must be an object")
        context = params.get("context")
        if context is None:
            context = {}
        if not isinstance(context, Mapping):
            raise ValueError("tool.call context must be an object")
        with contextlib.redirect_stdout(sys.stderr):
            return await registry.invoke_tool(
                str(params.get("name") or ""),
                arguments,
                context,
            )
    if method == "hook.call":
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise ValueError("hook.call params must be an object")
        payload = params.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise ValueError("hook.call payload must be an object")
        with contextlib.redirect_stdout(sys.stderr):
            return await registry.invoke_hook(
                str(params.get("event") or ""),
                str(params.get("hook_id") or ""),
                payload,
            )
    if method == "command.call":
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise ValueError("command.call params must be an object")
        context = params.get("context")
        if context is None:
            context = {}
        if not isinstance(context, Mapping):
            raise ValueError("command.call context must be an object")
        with contextlib.redirect_stdout(sys.stderr):
            return await registry.invoke_command(
                str(params.get("name") or ""),
                str(params.get("arguments") or ""),
                context,
            )
    if method in {"deferred.poll", "deferred.cancel"}:
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise ValueError(f"{method} params must be an object")
        context = params.get("context")
        if context is None:
            context = {}
        if not isinstance(context, Mapping):
            raise ValueError(f"{method} context must be an object")
        token = str(params.get("token") or "")
        if not token:
            raise ValueError(f"{method} token must not be empty")
        with contextlib.redirect_stdout(sys.stderr):
            if method == "deferred.poll":
                return await registry.poll_deferred(token, context)
            return await registry.cancel_deferred(
                token,
                str(params.get("reason") or "cancelled"),
                context,
            )
    if method == "http.handle":
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise ValueError("http.handle params must be an object")
        http_request = params.get("request")
        if not isinstance(http_request, Mapping):
            raise ValueError("http.handle request must be an object")
        context = params.get("context")
        if context is None:
            context = {}
        if not isinstance(context, Mapping):
            raise ValueError("http.handle context must be an object")
        with contextlib.redirect_stdout(sys.stderr):
            return await registry.handle_http(http_request, context)
    raise ValueError(f"Unknown worker method: {method}")


def _write_response(payload: Mapping[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


async def _serve(
    plugin_root: str,
    entrypoint_path: str,
    adapter: str,
    host_context: Mapping[str, Any] | None = None,
) -> int:
    """Serve every request on one event loop for the worker's lifetime."""
    request_id: Any = None
    registry: Plugin | None = None
    try:
        root = Path(plugin_root).expanduser().resolve(strict=True)
        entrypoint = Path(entrypoint_path).expanduser().resolve(strict=True)
        if root not in entrypoint.parents:
            raise ValueError("Plugin entrypoint must stay inside the plugin root")
        registry = _load_registry(root, entrypoint, str(adapter or "native"))
        activation_context = {
            "plugin_root": str(root),
            "entrypoint": str(entrypoint),
            **dict(host_context or {}),
        }
        with contextlib.redirect_stdout(sys.stderr):
            await registry.activate(activation_context)
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            request_id = None
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("Worker request must be a JSON object")
                request_id = request.get("id")
                result = await _handle(registry, request)
                _write_response({"id": request_id, "ok": True, "result": result})
                if str(request.get("method") or "") == "plugin.shutdown":
                    break
            except Exception as exc:
                _write_response(
                    {
                        "id": request_id,
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "traceback": traceback.format_exc(limit=8),
                        },
                    }
                )
        return 0
    except Exception as exc:
        _write_response(
            {
                "id": request_id,
                "ok": False,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(limit=8),
                },
            }
        )
        return 1
    finally:
        if registry is not None:
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    await registry.deactivate(
                        {**dict(host_context or {}), "reason": "worker_exit"}
                    )
            except Exception:
                traceback.print_exc(file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--adapter", default="native")
    parser.add_argument("--plugin-id", required=True)
    parser.add_argument("--plugin-data-dir", required=True)
    parser.add_argument("--plugin-cache-dir", required=True)
    parser.add_argument("--plugin-temp-dir", required=True)
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--background-services-enabled", default="0")
    args = parser.parse_args()
    return asyncio.run(
        _serve(
            args.plugin_root,
            args.entrypoint,
            str(args.adapter or "native"),
            {
                "plugin_id": str(args.plugin_id or ""),
                "plugin_data_dir": str(args.plugin_data_dir or ""),
                "plugin_cache_dir": str(args.plugin_cache_dir or ""),
                "plugin_temp_dir": str(args.plugin_temp_dir or ""),
                "workspace_root": str(args.workspace_root or ""),
                "background_services_enabled": str(
                    args.background_services_enabled or "0"
                ).strip().lower()
                in {"1", "true", "yes", "on"},
            },
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
