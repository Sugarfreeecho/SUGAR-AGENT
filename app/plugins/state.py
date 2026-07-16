"""Atomic persistence for per-plugin enable/disable state."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .security import PluginStateError, normalize_namespace


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class PluginStateStore:
    """A tiny state database with atomic replacement and in-process locking."""

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        self._lock = threading.RLock()

    def _read_unlocked(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {"version": 1, "plugins": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginStateError(f"Cannot read plugin state {self.path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("version") != 1:
            raise PluginStateError("Plugin state must be a version 1 JSON object")
        plugins = raw.get("plugins")
        if not isinstance(plugins, dict):
            raise PluginStateError("Plugin state 'plugins' must be an object")
        for plugin_id, entry in plugins.items():
            if not isinstance(plugin_id, str) or not isinstance(entry, dict):
                raise PluginStateError("Plugin state contains an invalid entry")
            if not isinstance(entry.get("enabled"), bool):
                raise PluginStateError(f"Plugin state for {plugin_id!r} lacks boolean enabled")
        return raw

    def read(self) -> Dict[str, Any]:
        with self._lock:
            return self._read_unlocked()

    def is_enabled(self, plugin_id: str, default: bool = True) -> bool:
        plugin_id = normalize_namespace(plugin_id)
        data = self.read()
        entry = data["plugins"].get(plugin_id)
        return default if not isinstance(entry, dict) else bool(entry["enabled"])

    def set_enabled(self, plugin_id: str, enabled: bool) -> Dict[str, Any]:
        plugin_id = normalize_namespace(plugin_id)
        if not isinstance(enabled, bool):
            raise PluginStateError("Plugin enabled state must be a boolean")
        with self._lock:
            data = self._read_unlocked()
            data["plugins"][plugin_id] = {
                "enabled": enabled,
                "updated_at": _now_iso(),
            }
            self._write_unlocked(data)
            return dict(data["plugins"][plugin_id])

    def _write_unlocked(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        tmp = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            with tmp.open("wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise PluginStateError(f"Cannot write plugin state {self.path}: {exc}") from exc
