"""Public seam for transports that live outside the core application.

Remote-control transports used to import ``webui`` internals to reach the
session-control dependencies and the gateway's shared service. Optional
transports now live in their own plugins, so they need one stable entry point
that does not depend on private module attributes.

The seam is intentionally tiny: it exposes the same objects the built-in
gateway was registered with, and it is only imported when a transport actually
starts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TransportContext:
    """Everything an out-of-core transport needs to start."""

    dependencies: Any
    gateway_service: Optional[Any]


def transport_context() -> TransportContext:
    """Return the live session-control dependencies and shared gateway service.

    Importing ``webui`` lazily keeps this module importable in contexts that
    only need the type (tests, tooling) and avoids an import cycle at startup.
    """

    import webui

    gateway = getattr(webui, "_remote_control_gateway", None)
    dependencies = getattr(webui, "_control_dependencies", None)
    if dependencies is None:
        raise RuntimeError("remote control dependencies are not initialised")
    return TransportContext(
        dependencies=dependencies,
        gateway_service=getattr(gateway, "service", None),
    )


__all__ = ["TransportContext", "transport_context"]
