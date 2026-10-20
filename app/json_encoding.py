"""Optional fast encoding for ordinary JSON, with an explicit caller fallback."""
from __future__ import annotations

import math
from typing import Any, Optional

try:
    import orjson as _orjson
except ImportError:
    _orjson = None


def encode_plain_json(payload: Any, *, encoder=None) -> Optional[bytes]:
    encoder = encoder if encoder is not None else _orjson
    if encoder is None:
        return None

    def supported(value: Any, depth: int = 0) -> bool:
        kind = type(value)
        if value is None or kind in (str, bool):
            return True
        if kind is int:
            return -(1 << 63) <= value < (1 << 64)
        if kind is float:
            return math.isfinite(value)
        if depth >= 64:
            return False
        if kind is list:
            return all(supported(item, depth + 1) for item in value)
        if kind is dict:
            return all(type(key) is str and supported(item, depth + 1) for key, item in value.items())
        return False

    if not supported(payload):
        return None
    try:
        return encoder.dumps(payload)
    except (TypeError, ValueError):
        return None
