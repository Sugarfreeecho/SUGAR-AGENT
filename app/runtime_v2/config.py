from __future__ import annotations

import os
from typing import Optional


def runtime_version() -> int:
    raw = os.getenv("RUNTIME_VERSION")
    if raw is None or str(raw).strip() == "":
        raw = os.getenv("RUNTIME_version")
    if raw is not None and str(raw).strip() != "":
        return 2 if str(raw).strip() == "2" else 1
    legacy = os.getenv("RUNTIME_V2_ENABLED")
    if legacy is None:
        return 2
    return 1 if str(legacy).strip().lower() in {"0", "false", "no", "off"} else 2


def runtime_v2_primary() -> bool:
    return runtime_version() == 2


def runtime_v1_primary() -> bool:
    return runtime_version() == 1


def runtime_v2_enabled() -> bool:
    return runtime_v2_primary()


def runtime_v2_strict() -> bool:
    # Runtime V2 is the default fact source. Silently dropping a failed write
    # makes later projections look valid but incomplete, so fail closed unless
    # an operator explicitly opts into the old diagnostic behavior.
    return os.getenv("RUNTIME_V2_STRICT", "1").strip().lower() in {"1", "true", "yes", "on"}


def runtime_v2_react_transaction_timeout_seconds() -> Optional[float]:
    """Return the online ReAct lock budget; maintenance callers do not use it."""
    raw = os.getenv("RUNTIME_V2_REACT_TRANSACTION_TIMEOUT_SECONDS")
    if raw is None:
        # Compatibility with the first bounded-lock release.
        raw = os.getenv("RUNTIME_V2_TRANSACTION_TIMEOUT_SECONDS", "10")
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        timeout = 10.0
    return timeout if timeout > 0 else None
