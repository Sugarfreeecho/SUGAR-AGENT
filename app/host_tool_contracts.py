"""Contracts for host tools whose implementation lives in a plugin.

Security classification needs to know the effect of a host tool before the
plugin's own module is imported. Plugins register a provider while they are
running and unregister it on stop; with no provider the lookup is empty and
the tool falls through to the generic branches.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

Provider = Callable[[str], Optional[Dict[str, Any]]]

_LOCK = threading.RLock()
_PROVIDERS: list[Provider] = []


def register(provider: Provider) -> None:
    if not callable(provider):
        raise TypeError("tool contract provider must be callable")
    with _LOCK:
        if provider not in _PROVIDERS:
            _PROVIDERS.append(provider)


def unregister(provider: Provider) -> None:
    with _LOCK:
        try:
            _PROVIDERS.remove(provider)
        except ValueError:
            pass


def tool_contract(name: str) -> Dict[str, Any]:
    """Return the first non-empty contract for ``name`` (newest first)."""

    key = str(name or "").strip()
    if not key:
        return {}
    with _LOCK:
        providers = list(reversed(_PROVIDERS))
    for provider in providers:
        try:
            row = provider(key)
        except Exception:
            continue
        if isinstance(row, dict) and row:
            return dict(row)
    return {}


def filter_preferred_mcp_tools(registry, resolve_identity) -> list[str]:
    """Apply trusted host transport preferences before tool disclosure.

    Compare MCP source-local names, never the shortened model-facing alias.
    Only an available host descriptor owned by the declaring provider can
    replace a family. Removing the alternative from the execution registry
    also prevents search/call bridges from silently selecting that transport.
    """
    from tool_registry import ToolInvocationKind

    prefixes = set()
    for descriptor in registry.descriptors():
        if descriptor.invocation_kind is not ToolInvocationKind.HOST_SERVICE or not descriptor.executable:
            continue
        contract = tool_contract(descriptor.execution_name)
        if contract.get("managed_by") != descriptor.owner:
            continue
        families=contract.get("preferred_mcp_families", ())
        if not isinstance(families, (tuple,list)):
            continue
        for prefix in families:
            if isinstance(prefix, str) and prefix and descriptor.execution_name.startswith(prefix):
                prefixes.add(prefix)
    if not prefixes:
        return []
    removed = []
    for descriptor in registry.descriptors():
        if descriptor.invocation_kind is not ToolInvocationKind.MCP:
            continue
        identity = resolve_identity(descriptor.execution_name)
        if identity and any(identity[1].startswith(prefix) for prefix in prefixes):
            registry._descriptors.pop(descriptor.name, None)
            removed.append(descriptor.name)
    return removed


__all__ = ["register", "tool_contract", "unregister", "filter_preferred_mcp_tools"]
