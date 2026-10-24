"""Product tiers for plugins: packaging, default state and settings visibility.

Four tiers are declared once in ``tiers.json`` and consumed by both the runtime
and the desktop packaging script:

``system``          系统内置：设置页隐藏、工具常驻、环境变量可控
``system-external`` 系统外置：设置页可见、工具常驻、环境变量可覆盖
``extension``       拓展功能：设置页可见、工具延迟加载、默认启用
``standalone``      独立功能：不随安装包分发、默认停用、工具延迟加载

An unlisted plugin is treated as ``standalone`` on purpose: a new directory must
be registered before it can silently join the installer.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TIERS_PATH = Path(__file__).with_name("tiers.json")
TIER_ORDER = ("system", "system-external", "extension", "standalone")
RESIDENT_TIERS = frozenset({"system", "system-external"})
UNCLASSIFIED_TIER = "unclassified"

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}

_lock = threading.RLock()
_cache: Optional[tuple[Any, Dict[str, str]]] = None


def _table() -> Dict[str, str]:
    global _cache
    try:
        stat = TIERS_PATH.stat()
        signature: Any = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        signature = None
    with _lock:
        if _cache is not None and _cache[0] == signature:
            return _cache[1]
        mapping: Dict[str, str] = {}
        try:
            raw = json.loads(TIERS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Plugin tier table unavailable (%s); every plugin falls back to %s",
                           exc, UNCLASSIFIED_TIER)
            raw = {}
        tiers = raw.get("tiers") if isinstance(raw, dict) else None
        if isinstance(tiers, dict):
            for tier, plugin_ids in tiers.items():
                if tier not in TIER_ORDER or not isinstance(plugin_ids, list):
                    continue
                for plugin_id in plugin_ids:
                    key = str(plugin_id or "").strip().lower()
                    if key:
                        # First declaration wins so a typo cannot silently move
                        # a plugin into a weaker tier.
                        mapping.setdefault(key, tier)
        _cache = (signature, mapping)
        return mapping


def tier_of(plugin_id: str) -> str:
    key = str(plugin_id or "").strip().lower()
    if not key:
        return UNCLASSIFIED_TIER
    return _table().get(key, UNCLASSIFIED_TIER)


def is_registered(plugin_id: str) -> bool:
    return str(plugin_id or "").strip().lower() in _table()


def default_enabled(plugin_id: str) -> bool:
    """Standalone plugins ship disabled and must be switched on by hand.

    An unlisted plugin (typically user-installed) keeps the historical
    "enabled by default" behaviour; packaging still only ships listed tiers.
    """

    return tier_of(plugin_id) != "standalone"


def hidden_in_settings(plugin_id: str) -> bool:
    """Only 系统内置 stays out of the settings list."""

    return tier_of(plugin_id) == "system"


def tools_resident(plugin_id: str) -> bool:
    """系统内置 / 系统外置 own the resident tool slots; others are deferred."""

    return tier_of(plugin_id) in RESIDENT_TIERS


def packaged_by_default(plugin_id: str) -> bool:
    return tier_of(plugin_id) != "standalone"


def env_var_name(plugin_id: str) -> str:
    key = "".join(ch if ch.isalnum() else "_" for ch in str(plugin_id or "").strip().upper())
    return f"PLUGIN_{key}_ENABLED"


def env_override(plugin_id: str) -> Optional[bool]:
    """Per-plugin environment switch; ``None`` means "no opinion"."""

    name = env_var_name(plugin_id)
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return None
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    logger.warning("Ignoring invalid %s=%r (expected 1/0)", name, raw)
    return None


def snapshot() -> Dict[str, Any]:
    table = _table()
    return {
        "path": str(TIERS_PATH),
        "tiers": {
            tier: sorted(plugin_id for plugin_id, value in table.items() if value == tier)
            for tier in TIER_ORDER
        },
    }


__all__ = [
    "RESIDENT_TIERS",
    "TIERS_PATH",
    "TIER_ORDER",
    "UNCLASSIFIED_TIER",
    "default_enabled",
    "env_override",
    "env_var_name",
    "hidden_in_settings",
    "is_registered",
    "packaged_by_default",
    "snapshot",
    "tier_of",
    "tools_resident",
]
