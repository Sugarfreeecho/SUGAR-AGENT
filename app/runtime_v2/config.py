from __future__ import annotations

import os


def runtime_v2_enabled() -> bool:
    return os.getenv("RUNTIME_V2_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def runtime_v2_strict() -> bool:
    return os.getenv("RUNTIME_V2_STRICT", "0").strip().lower() in {"1", "true", "yes", "on"}

