"""Registry contract for optional public-web search providers."""
from __future__ import annotations

import inspect
import re
import threading
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Awaitable, Callable, Mapping


SearchCallback = Callable[[str, int], str | Awaitable[str]]
_PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,79}$")


@dataclass(frozen=True)
class SearchProviderDescriptor:
    provider_id: str
    callback: SearchCallback
    source: str
    api_version: int = 1


class SearchProviderRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers: dict[str, SearchProviderDescriptor] = {}

    @staticmethod
    def _key(value: Any) -> str:
        key = str(value or "").strip().lower()
        if not _PROVIDER_ID_RE.fullmatch(key):
            raise ValueError("search provider_id must be a lowercase dotted identifier")
        return key

    def register(
        self,
        provider_id: str,
        callback: SearchCallback,
        *,
        source: str,
        api_version: int = 1,
        replace: bool = False,
    ) -> SearchProviderDescriptor:
        key = self._key(provider_id)
        owner = str(source or "").strip()
        if not owner:
            raise ValueError("search provider source is required")
        if not callable(callback):
            raise TypeError("search provider callback must be callable")
        if int(api_version) != 1:
            raise ValueError("unsupported search provider API version")
        descriptor = SearchProviderDescriptor(key, callback, owner, int(api_version))
        with self._lock:
            if key in self._providers and not replace:
                raise ValueError(f"search provider is already registered: {key}")
            self._providers[key] = descriptor
        return descriptor

    def clear(self) -> None:
        with self._lock:
            self._providers.clear()

    async def search(self, provider_id: Any, query: str, count: int) -> str:
        key = self._key(provider_id)
        with self._lock:
            descriptor = self._providers.get(key)
        if descriptor is None:
            raise ValueError(f"unregistered search provider: {key}")
        value = descriptor.callback(str(query or ""), max(1, int(count)))
        result = await value if inspect.isawaitable(value) else value
        return str(result)

    def snapshot(self) -> Mapping[str, Mapping[str, Any]]:
        with self._lock:
            rows = {
                key: MappingProxyType(
                    {
                        "provider_id": item.provider_id,
                        "source": item.source,
                        "api_version": item.api_version,
                    }
                )
                for key, item in self._providers.items()
            }
        return MappingProxyType(rows)


search_provider_registry = SearchProviderRegistry()


__all__ = [
    "SearchProviderDescriptor",
    "SearchProviderRegistry",
    "search_provider_registry",
]
