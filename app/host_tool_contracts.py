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


__all__ = ["register", "tool_contract", "unregister"]
