"""Domain-neutral registry for optional session workflow continuations."""
from __future__ import annotations

import threading
import hashlib
import importlib.util
import inspect
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class SessionWorkflow:
    plugin_id: str
    continuation_source: str
    can_continue: Callable[[str], bool]


class SessionWorkflowRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, SessionWorkflow] = {}
        self._callbacks: dict[str, Mapping[str, Callable[..., Any]]] = {}

    def register(self, workflow: SessionWorkflow, *, replace: bool = False) -> None:
        if not workflow.plugin_id or not workflow.continuation_source:
            raise ValueError("workflow identity and continuation source are required")
        with self._lock:
            if workflow.plugin_id in self._items and not replace:
                raise ValueError(f"workflow already registered: {workflow.plugin_id}")
            self._items[workflow.plugin_id] = workflow

    def continuation_source(self, session_id: str) -> str:
        sid = str(session_id or "").strip()
        if not sid:
            return ""
        with self._lock:
            items = tuple(self._items.values())
        for item in items:
            try:
                if item.can_continue(sid):
                    return item.continuation_source
            except Exception:
                continue
        return ""

    def register_callbacks(
        self,
        plugin_id: str,
        callbacks: Mapping[str, Callable[..., Any]],
        *,
        replace: bool = False,
    ) -> None:
        owner = str(plugin_id or "").strip()
        clean = {str(name): value for name, value in callbacks.items() if callable(value)}
        if not owner or not clean:
            raise ValueError("workflow callbacks require an owner and callables")
        with self._lock:
            if owner in self._callbacks and not replace:
                raise ValueError(f"workflow callbacks already registered: {owner}")
            self._callbacks[owner] = clean

    def unregister_callbacks(self, plugin_id: str) -> None:
        owner = str(plugin_id or "").strip()
        if not owner:
            return
        with self._lock:
            self._callbacks.pop(owner, None)

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            callbacks = tuple(self._callbacks.values())
        result = None
        for group in callbacks:
            callback = group.get(name)
            if callback is None:
                continue
            value = callback(*args, **kwargs)
            if value is not None:
                result = value
        return result

    async def call_async(self, name: str, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            callbacks = tuple(self._callbacks.values())
        result = None
        for group in callbacks:
            callback = group.get(name)
            if callback is None:
                continue
            value = callback(*args, **kwargs)
            value = await value if inspect.isawaitable(value) else value
            if value is not None:
                result = value
        return result


session_workflows = SessionWorkflowRegistry()

_ACTIVATED_SIGNATURES: set[tuple[str, str]] = set()
_ACTIVE_CALLBACK_OWNERS: set[str] = set()
_ACTIVATION_LOCK = threading.RLock()
_ACTIVATED = False


def invalidate_bundled_workflow_callbacks() -> None:
    """Drop callback registrations so an explicit plugin reload can rebuild them."""

    global _ACTIVATED
    with _ACTIVATION_LOCK:
        for owner in tuple(_ACTIVE_CALLBACK_OWNERS):
            session_workflows.unregister_callbacks(owner)
        _ACTIVE_CALLBACK_OWNERS.clear()
        _ACTIVATED_SIGNATURES.clear()
        _ACTIVATED = False


def activate_bundled_workflow_callbacks(host_module: Any, *, force: bool = False) -> None:
    """Load callback modules declared by enabled, physically bundled plugins."""

    global _ACTIVATED
    if _ACTIVATED and not force:
        return
    with _ACTIVATION_LOCK:
        if _ACTIVATED and not force:
            return
        if force:
            for owner in tuple(_ACTIVE_CALLBACK_OWNERS):
                session_workflows.unregister_callbacks(owner)
            _ACTIVE_CALLBACK_OWNERS.clear()
            _ACTIVATED_SIGNATURES.clear()

        from agent_extensions import load_plugins
        from plugins.host import is_bundled_trusted_host_plugin

        bundled_root = Path(__file__).resolve().parents[1] / "plugins"
        for plugin in load_plugins().plugins:
            capabilities = plugin.raw_manifest.get("capabilities")
            trusted = capabilities.get("trusted_host") if isinstance(capabilities, Mapping) else None
            entry = str(trusted.get("workflow_runtime") or "").strip() if isinstance(trusted, Mapping) else ""
            if not entry:
                continue
            if not is_bundled_trusted_host_plugin(plugin):
                continue
            root = plugin.root.resolve()
            try:
                root.relative_to(bundled_root.resolve())
            except ValueError:
                continue
            path = (root / entry).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            key = (plugin.plugin_id, plugin.content_signature)
            if key in _ACTIVATED_SIGNATURES or path.suffix.lower() != ".py" or not path.is_file():
                continue
            digest = hashlib.sha256(f"{path}:{plugin.content_signature}".encode()).hexdigest()[:16]
            name = f"myagent_workflow_runtime_{digest}"
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            initialize = getattr(module, "initialize", None)
            callbacks = initialize(host_module) if callable(initialize) else None
            if isinstance(callbacks, Mapping):
                session_workflows.register_callbacks(plugin.plugin_id, callbacks, replace=True)
                _ACTIVE_CALLBACK_OWNERS.add(plugin.plugin_id)
                _ACTIVATED_SIGNATURES.add(key)
        _ACTIVATED = True


__all__ = [
    "SessionWorkflow",
    "SessionWorkflowRegistry",
    "activate_bundled_workflow_callbacks",
    "invalidate_bundled_workflow_callbacks",
    "session_workflows",
]
