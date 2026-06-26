from __future__ import annotations

import os


def runtime_version() -> int:
    raw = os.getenv("RUNTIME_VERSION")
    if raw is None or str(raw).strip() == "":
        raw = os.getenv("RUNTIME_version")
    if raw is not None and str(raw).strip() != "":
        return 2 if str(raw).strip() == "2" else 1
    legacy = os.getenv("RUNTIME_V2_ENABLED")
    if legacy is None:
        return 1
    return 1 if str(legacy).strip().lower() in {"0", "false", "no", "off"} else 2


def runtime_v2_primary() -> bool:
    return runtime_version() == 2


def runtime_v1_primary() -> bool:
    return runtime_version() == 1


def runtime_v2_enabled() -> bool:
    return runtime_v2_primary()


def runtime_v2_strict() -> bool:
    return os.getenv("RUNTIME_V2_STRICT", "0").strip().lower() in {"1", "true", "yes", "on"}
