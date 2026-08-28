"""Versioned registry for trusted LLM transport and diagnostic providers."""
from __future__ import annotations

import inspect
import re
import threading
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional


ProviderFactory = Callable[..., Any]
_PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,79}$")


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    factory: ProviderFactory
    source: str
    api_version: int = 1
    dialect: str = "standard"
    tokenizer: Optional[Callable[..., int]] = None
    discover: Optional[Callable[..., Any]] = None
    probe: Optional[Callable[..., Any]] = None
    capabilities: Mapping[str, bool] = field(
        default_factory=lambda: MappingProxyType({})
    )


class ProviderRegistry:
    """Fail-closed provider catalog shared by core and bundled extensions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers: dict[str, ProviderDescriptor] = {}

    @staticmethod
    def _key(value: Any) -> str:
        key = str(getattr(value, "value", value) or "").strip().lower()
        if not _PROVIDER_ID_RE.fullmatch(key):
            raise ValueError("provider_id must be a lowercase dotted identifier")
        return key

    def register(
        self,
        provider_id: str,
        factory: ProviderFactory,
        *,
        source: str,
        api_version: int = 1,
        dialect: str = "standard",
        tokenizer: Optional[Callable[..., int]] = None,
        discover: Optional[Callable[..., Any]] = None,
        probe: Optional[Callable[..., Any]] = None,
        capabilities: Optional[Mapping[str, bool]] = None,
        replace: bool = False,
    ) -> ProviderDescriptor:
        key = self._key(provider_id)
        owner = str(source or "").strip()
        if not owner:
            raise ValueError("provider source is required")
        if not callable(factory):
            raise TypeError("provider factory must be callable")
        for label, callback in (
            ("tokenizer", tokenizer),
            ("discover", discover),
            ("probe", probe),
        ):
            if callback is not None and not callable(callback):
                raise TypeError(f"provider {label} must be callable")
        normalized_dialect = str(dialect or "standard").strip().lower()
        if not _PROVIDER_ID_RE.fullmatch(normalized_dialect):
            raise ValueError("provider dialect must be a lowercase dotted identifier")
        descriptor = ProviderDescriptor(
            provider_id=key,
            factory=factory,
            source=owner,
            api_version=int(api_version),
            dialect=normalized_dialect,
            tokenizer=tokenizer,
            discover=discover,
            probe=probe,
            capabilities=MappingProxyType(
                {
                    str(key): bool(value)
                    for key, value in dict(capabilities or {}).items()
                }
            ),
        )
        if descriptor.api_version != 1:
            raise ValueError("unsupported provider API version")
        with self._lock:
            if key in self._providers and not replace:
                raise ValueError(f"provider is already registered: {key}")
            self._providers[key] = descriptor
        return descriptor

    def resolve(self, provider_id: Any) -> ProviderDescriptor:
        key = self._key(provider_id)
        with self._lock:
            descriptor = self._providers.get(key)
        if descriptor is None:
            raise ValueError(f"unregistered LLM provider: {key}")
        return descriptor

    def build(self, provider_id: Any, profile: Mapping[str, Any], **services: Any) -> Any:
        descriptor = self.resolve(provider_id)
        return descriptor.factory(dict(profile or {}), **services)

    async def run_diagnostic(
        self, provider_id: Any, operation: str, **arguments: Any
    ) -> Any:
        descriptor = self.resolve(provider_id)
        normalized_operation = str(operation or "").strip().lower()
        if normalized_operation not in {"discover", "probe"}:
            raise ValueError(f"unsupported provider diagnostic: {operation}")
        callback = (
            descriptor.discover
            if normalized_operation == "discover"
            else descriptor.probe
        )
        if callback is None:
            raise ValueError(
                f"provider {descriptor.provider_id!r} does not support {normalized_operation}"
            )
        value = callback(**arguments)
        return await value if inspect.isawaitable(value) else value

    def snapshot(self) -> Mapping[str, Mapping[str, Any]]:
        with self._lock:
            rows = {
                key: MappingProxyType(
                    {
                        "provider_id": item.provider_id,
                        "source": item.source,
                        "api_version": item.api_version,
                        "dialect": item.dialect,
                        "has_tokenizer": callable(item.tokenizer),
                        "can_discover": callable(item.discover),
                        "can_probe": callable(item.probe),
                        "capabilities": item.capabilities,
                    }
                )
                for key, item in self._providers.items()
            }
        return MappingProxyType(rows)


provider_registry = ProviderRegistry()


__all__ = ["ProviderDescriptor", "ProviderRegistry", "provider_registry"]
