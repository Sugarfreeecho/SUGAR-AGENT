"""Source-agnostic tool registration and invocation result contracts.

The registry deliberately stores model-facing JSON definitions separately from
the implementation that will execute them.  Agent orchestration can therefore
resolve a tool by descriptor instead of inferring its owner from name prefixes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional


class ToolRegistryError(ValueError):
    """Base error for invalid or conflicting registrations."""


class DuplicateToolError(ToolRegistryError):
    """Raised when two capabilities attempt to register the same model name."""


class ToolInvocationKind(str, Enum):
    """Executor selected by the host after normal authorization and hooks."""

    HOST = "host"
    HOST_SERVICE = "host_service"
    MCP = "mcp"
    PLUGIN = "plugin"
    UNAVAILABLE = "unavailable"


class ToolOutcomeKind(str, Enum):
    """Source-independent terminal or suspended tool invocation state."""

    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"
    INTERACTION = "interaction"


def _definition_name(definition: Mapping[str, Any]) -> str:
    if not isinstance(definition, Mapping):
        return ""
    function = definition.get("function")
    if not isinstance(function, Mapping):
        return ""
    return str(function.get("name") or "").strip()


@dataclass(frozen=True)
class ToolDescriptor:
    """Immutable registry entry for one model-visible tool capability."""

    name: str
    invocation_kind: ToolInvocationKind
    owner: str
    _definition_json: str = field(repr=False)
    executable: bool = True
    effect: str = ""
    required_permissions: tuple[str, ...] = ()
    invoker_id: str = ""
    emit_pending: bool = True
    parallel_safe: bool = False
    pressure_limited: bool = False
    interactive: bool = False
    early_stream_safe: bool = True
    interruptibility: str = "non_interruptible"

    @classmethod
    def from_openai_definition(
        cls,
        definition: Mapping[str, Any],
        *,
        invocation_kind: ToolInvocationKind | str,
        owner: str,
        executable: Optional[bool] = None,
        effect: str = "",
        required_permissions: Iterable[str] = (),
        invoker_id: str = "",
        emit_pending: bool = True,
        parallel_safe: bool = False,
        pressure_limited: bool = False,
        interactive: bool = False,
        early_stream_safe: bool = True,
        interruptibility: str = "non_interruptible",
    ) -> "ToolDescriptor":
        name = _definition_name(definition)
        if not name:
            raise ToolRegistryError(
                "Tool definition must contain a non-empty function.name"
            )
        try:
            kind = ToolInvocationKind(invocation_kind)
        except ValueError as exc:
            raise ToolRegistryError(
                f"Unsupported tool invocation kind: {invocation_kind!r}"
            ) from exc
        owner_id = str(owner or "").strip()
        if not owner_id:
            raise ToolRegistryError(f"Tool {name!r} must declare an owner")
        try:
            serialized = json.dumps(
                dict(definition),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ToolRegistryError(
                f"Tool definition for {name!r} must be JSON serializable"
            ) from exc
        permissions = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in required_permissions
                if str(item).strip()
            )
        )
        can_execute = kind is not ToolInvocationKind.UNAVAILABLE
        if executable is not None:
            can_execute = bool(executable)
        if kind is ToolInvocationKind.UNAVAILABLE and can_execute:
            raise ToolRegistryError(
                f"Unavailable tool {name!r} cannot be marked executable"
            )
        return cls(
            name=name,
            invocation_kind=kind,
            owner=owner_id,
            _definition_json=serialized,
            executable=can_execute,
            effect=str(effect or "").strip().lower(),
            required_permissions=permissions,
            invoker_id=str(invoker_id or "").strip(),
            emit_pending=bool(emit_pending),
            parallel_safe=bool(parallel_safe),
            pressure_limited=bool(pressure_limited),
            interactive=bool(interactive),
            early_stream_safe=bool(early_stream_safe),
            interruptibility=str(interruptibility or "non_interruptible").strip(),
        )

    def openai_definition(self) -> Dict[str, Any]:
        """Return a fresh copy so callers cannot mutate registry state."""

        value = json.loads(self._definition_json)
        if not isinstance(value, dict):  # pragma: no cover - constructor guarantees this
            raise ToolRegistryError(f"Invalid stored definition for {self.name!r}")
        return value


class ToolRegistry:
    """Ordered, conflict-detecting registry for one Agent request catalog."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ToolDescriptor] = {}

    def register(self, descriptor: ToolDescriptor) -> ToolDescriptor:
        if not isinstance(descriptor, ToolDescriptor):
            raise TypeError("descriptor must be a ToolDescriptor")
        existing = self._descriptors.get(descriptor.name)
        if existing is not None:
            raise DuplicateToolError(
                f"Tool {descriptor.name!r} is already registered by "
                f"{existing.owner!r}; cannot register owner {descriptor.owner!r}"
            )
        self._descriptors[descriptor.name] = descriptor
        return descriptor

    def register_definition(
        self,
        definition: Mapping[str, Any],
        *,
        invocation_kind: ToolInvocationKind | str,
        owner: str,
        executable: Optional[bool] = None,
        effect: str = "",
        required_permissions: Iterable[str] = (),
        invoker_id: str = "",
        emit_pending: bool = True,
        parallel_safe: bool = False,
        pressure_limited: bool = False,
        interactive: bool = False,
        early_stream_safe: bool = True,
        interruptibility: str = "non_interruptible",
    ) -> ToolDescriptor:
        return self.register(
            ToolDescriptor.from_openai_definition(
                definition,
                invocation_kind=invocation_kind,
                owner=owner,
                executable=executable,
                effect=effect,
                required_permissions=required_permissions,
                invoker_id=invoker_id,
                emit_pending=emit_pending,
                parallel_safe=parallel_safe,
                pressure_limited=pressure_limited,
                interactive=interactive,
                early_stream_safe=early_stream_safe,
                interruptibility=interruptibility,
            )
        )

    def resolve(self, name: str) -> Optional[ToolDescriptor]:
        return self._descriptors.get(str(name or "").strip())

    def require(self, name: str) -> ToolDescriptor:
        descriptor = self.resolve(name)
        if descriptor is None:
            raise ToolRegistryError(f"Unknown tool: {name}")
        return descriptor

    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(self._descriptors.values())

    def definitions(self) -> list[Dict[str, Any]]:
        return [item.openai_definition() for item in self._descriptors.values()]

    def names(self, *, executable_only: bool = False) -> frozenset[str]:
        return frozenset(
            name
            for name, descriptor in self._descriptors.items()
            if not executable_only or descriptor.executable
        )

    def __len__(self) -> int:
        return len(self._descriptors)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._descriptors


@dataclass(frozen=True)
class ToolOutcome:
    """Uniform result envelope returned by future source-specific invokers."""

    kind: ToolOutcomeKind
    content: Any = None
    code: str = ""
    message: str = ""
    retryable: bool = False
    token: str = ""
    deadline_seconds: float = 0.0
    request_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", ToolOutcomeKind(self.kind))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))
        if self.kind is ToolOutcomeKind.FAILED and not str(self.code or "").strip():
            raise ToolRegistryError("Failed ToolOutcome requires an error code")
        if self.kind is ToolOutcomeKind.DEFERRED:
            if not str(self.token or "").strip():
                raise ToolRegistryError("Deferred ToolOutcome requires a token")
            if float(self.deadline_seconds or 0.0) <= 0:
                raise ToolRegistryError(
                    "Deferred ToolOutcome requires a positive deadline_seconds"
                )
        if self.kind is ToolOutcomeKind.INTERACTION and not str(
            self.request_id or ""
        ).strip():
            raise ToolRegistryError(
                "Interaction ToolOutcome requires a request_id"
            )

    @classmethod
    def completed(
        cls, content: Any, *, metadata: Optional[Mapping[str, Any]] = None
    ) -> "ToolOutcome":
        return cls(
            kind=ToolOutcomeKind.COMPLETED,
            content=content,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def failed(
        cls,
        code: str,
        message: str,
        *,
        content: Any = None,
        retryable: bool = False,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "ToolOutcome":
        return cls(
            kind=ToolOutcomeKind.FAILED,
            code=str(code or "").strip(),
            message=str(message or ""),
            content=content,
            retryable=bool(retryable),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def deferred(
        cls,
        token: str,
        deadline_seconds: float,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "ToolOutcome":
        return cls(
            kind=ToolOutcomeKind.DEFERRED,
            token=str(token or "").strip(),
            deadline_seconds=float(deadline_seconds),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def interaction(
        cls,
        request_id: str,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "ToolOutcome":
        return cls(
            kind=ToolOutcomeKind.INTERACTION,
            request_id=str(request_id or "").strip(),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"type": self.kind.value}
        if self.kind is ToolOutcomeKind.COMPLETED:
            result["content"] = self.content
        elif self.kind is ToolOutcomeKind.FAILED:
            result.update(
                {
                    "code": self.code,
                    "message": self.message,
                    "retryable": self.retryable,
                }
            )
            if self.content is not None:
                result["content"] = self.content
        elif self.kind is ToolOutcomeKind.DEFERRED:
            result.update(
                {
                    "token": self.token,
                    "deadline_seconds": self.deadline_seconds,
                }
            )
        else:
            result["request_id"] = self.request_id
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


__all__ = [
    "DuplicateToolError",
    "ToolDescriptor",
    "ToolInvocationKind",
    "ToolOutcome",
    "ToolOutcomeKind",
    "ToolRegistry",
    "ToolRegistryError",
]
