# -*- coding: utf-8 -*-
"""Plugin-declared tray menu entries for the Windows tray launcher.

A plugin opts in from its manifest (``capabilities.ui.tray``)::

    "capabilities": {
      "ui": {
        "tray": [
          {"id": "shield", "label": "\u62a4\u5c4f\u6a21\u5f0f",
           "command": ["{pythonw}", "scripts/mode.py", "set", "shield"],
           "check": {"file": "{state}/power-mode.json", "key": "mode", "equals": "shield"}},
          {"id": "power", "label": "\u7535\u6e90\u6a21\u5f0f",
           "items": [ ...leaf rows... ]}
        ]
      }
    }

Contract:

* **Best effort.** A malformed manifest, a missing script or a broken JSON
  file only removes that one entry; the tray menu must still open.
* **No shell.** ``command`` is an argv list executed with ``shell=False``;
  strings are never parsed by cmd.exe or PowerShell.
* **Contained paths.** Relative path-looking tokens are resolved inside the
  plugin root, and anything that escapes it invalidates the entry.
* **Enablement mirrors the backend.** ``PLUGIN_<ID>_ENABLED`` env override,
  then ``.config/plugins-state.json``, then the tier default
  (``standalone`` ships disabled, everything else defaults on).
* **Placeholders.** ``{python}``, ``{pythonw}``, ``{powershell}``,
  ``{plugin}``, ``{root}`` and ``{state}`` expand at menu build time.
* **Checked state** is read from the plugin's own state file on every popup, so
  a menu can show which mode is active without the tray owning that state.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

try:  # package import (tests, backend) vs flat import (tray script)
    from .tray_slot import MAX_TRAY_ROWS, parse_tray_rows
except ImportError:  # pragma: no cover - flat import fallback
    from tray_slot import MAX_TRAY_ROWS, parse_tray_rows  # type: ignore[no-redef]

MANIFEST_DIR = ".myagent-plugin"
MANIFEST_NAME = "plugin.json"
MAX_TRAY_ACTIONS = MAX_TRAY_ROWS

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}

#: Tokens that look like a file are resolved against the plugin root.
_PATH_SUFFIXES = (
    ".py", ".pyw", ".ps1", ".exe", ".bat", ".cmd", ".vbs", ".js", ".cjs", ".mjs",
)


@dataclass(frozen=True)
class TrayAction:
    """One clickable leaf entry owned by a plugin."""

    plugin_id: str
    item_id: str
    label: str
    argv: Tuple[str, ...]
    cwd: Path
    windowless: bool = True
    checked: bool = False


@dataclass(frozen=True)
class TrayGroup:
    """A submenu whose children are leaf actions."""

    plugin_id: str
    item_id: str
    label: str
    children: Tuple[TrayAction, ...]


TrayEntry = Union[TrayAction, TrayGroup]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        return None


def _tier_table(app_dir: Path) -> Dict[str, str]:
    raw = _load_json(app_dir / "plugins" / "tiers.json")
    table: Dict[str, str] = {}
    tiers = raw.get("tiers") if isinstance(raw, Mapping) else None
    if isinstance(tiers, Mapping):
        for tier, plugin_ids in tiers.items():
            if not isinstance(plugin_ids, list):
                continue
            for plugin_id in plugin_ids:
                key = str(plugin_id or "").strip().lower()
                if key:
                    table.setdefault(key, str(tier))
    return table


def _state_table(config_dir: Path) -> Dict[str, bool]:
    raw = _load_json(config_dir / "plugins-state.json")
    plugins = raw.get("plugins") if isinstance(raw, Mapping) else None
    table: Dict[str, bool] = {}
    if isinstance(plugins, Mapping):
        for plugin_id, entry in plugins.items():
            if isinstance(entry, Mapping) and isinstance(entry.get("enabled"), bool):
                table[str(plugin_id).strip().lower()] = bool(entry["enabled"])
    return table


def _env_override(plugin_id: str) -> Optional[bool]:
    key = "".join(ch if ch.isalnum() else "_" for ch in plugin_id.upper())
    raw = (os.getenv(f"PLUGIN_{key}_ENABLED") or "").strip().lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    return None


def _is_enabled(plugin_id: str, tiers: Mapping[str, str], state: Mapping[str, bool]) -> bool:
    override = _env_override(plugin_id)
    if override is not None:
        return override
    if plugin_id in state:
        return state[plugin_id]
    return tiers.get(plugin_id) != "standalone"


def _plugin_roots(project_root: Path) -> List[Path]:
    """Mirror ``plugins.manager.default_discovery_dirs`` without importing it."""

    raw_dirs = (os.getenv("PLUGINS_DIRS") or "").strip()
    if raw_dirs:
        candidates = [item for item in raw_dirs.split(os.pathsep) if item.strip()]
    else:
        single = (os.getenv("PLUGINS_DIR") or "").strip()
        if single:
            candidates = [single]
        else:
            local_app_data = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
            candidates = [
                str(project_root / "plugins"),
                str(Path(local_app_data) / "SugarAgent" / "plugins"),
            ]
    roots: List[Path] = []
    for candidate in candidates:
        path = Path(candidate).expanduser()
        path = (path if path.is_absolute() else project_root / path).resolve()
        if path.is_dir() and path not in roots:
            roots.append(path)
    return roots


def default_state_dir() -> Path:
    """Per-user state directory shared with plugins that persist a mode."""

    local_app_data = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / "SugarAgent" / "state"


def _default_powershell() -> str:
    system_root = os.getenv("SystemRoot") or r"C:\Windows"
    return str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")


def _looks_like_path(token: str) -> bool:
    return ("/" in token) or ("\\" in token) or token.lower().endswith(_PATH_SUFFIXES)


def _resolve_token(token: str, plugin_root: Path) -> str:
    """Resolve a plugin-relative path and refuse anything outside the plugin."""

    candidate = Path(token).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (plugin_root / candidate).resolve()
    if resolved != plugin_root and plugin_root not in resolved.parents:
        raise ValueError(f"path escapes plugin root: {token}")
    return str(resolved)


def _expand_token(token: str, context: Mapping[str, str], plugin_root: Path) -> str:
    expanded = token
    for name, value in context.items():
        expanded = expanded.replace("{" + name + "}", value)
    if Path(expanded).is_absolute():
        return expanded
    if _looks_like_path(expanded):
        return _resolve_token(expanded, plugin_root)
    return expanded


def _tray_rows(manifest: Mapping[str, Any]) -> Sequence[Dict[str, Any]]:
    """Validated rows from the shared parser; warnings are surfaced by the loader."""

    capabilities = manifest.get("capabilities")
    ui = capabilities.get("ui") if isinstance(capabilities, Mapping) else None
    if not isinstance(ui, Mapping):
        return ()
    rows, _warnings = parse_tray_rows(ui.get("tray"))
    return rows


def _checked(spec: Any, plugin_root: Path, context: Mapping[str, str]) -> bool:
    if not isinstance(spec, Mapping):
        return False
    raw_file = spec.get("file")
    key = spec.get("key")
    if not isinstance(raw_file, str) or not raw_file.strip():
        return False
    try:
        path = Path(_expand_token(raw_file.strip(), context, plugin_root))
    except (OSError, ValueError):
        return False
    if not path.is_absolute():
        path = (plugin_root / path).resolve()
    data = _load_json(path)
    if not isinstance(data, Mapping):
        return False
    value = data.get(key) if isinstance(key, str) and key else data
    expected = spec.get("equals")
    if expected is None:
        return bool(value)
    return str(value) == str(expected)


def _build_action(
    plugin_id: str,
    plugin_root: Path,
    row: Dict[str, Any],
    context: Mapping[str, str],
) -> Optional[TrayAction]:
    """Resolve a validated action row into something the tray can execute."""

    item_id = str(row.get("id") or "").strip()
    label = str(row.get("label") or "").strip()
    argv: List[str] = []
    try:
        for raw_token in row.get("command") or ():
            argv.append(_expand_token(str(raw_token), context, plugin_root))
    except (OSError, ValueError):
        return None
    if not argv or not Path(argv[0]).is_absolute():
        return None
    if not Path(argv[0]).exists():
        return None
    if not item_id or not label:
        return None
    return TrayAction(
        plugin_id=plugin_id,
        item_id=item_id,
        label=label,
        argv=tuple(argv),
        cwd=plugin_root,
        windowless=bool(row.get("windowless", True)),
        checked=_checked(row.get("check"), plugin_root, context),
    )


def _build_group(
    plugin_id: str,
    plugin_root: Path,
    row: Dict[str, Any],
    context: Mapping[str, str],
    budget: int,
) -> Optional[TrayGroup]:
    item_id = str(row.get("id") or "").strip()
    label = str(row.get("label") or "").strip()
    if not item_id or not label:
        return None
    children: List[TrayAction] = []
    for child_row in (row.get("items") or ())[:budget]:
        if not isinstance(child_row, Mapping):
            continue
        action = _build_action(plugin_id, plugin_root, dict(child_row), context)
        if action is not None:
            children.append(action)
    if not children:
        return None
    return TrayGroup(plugin_id=plugin_id, item_id=item_id, label=label, children=tuple(children))


def discover_tray_menu(
    project_root: Path,
    *,
    app_dir: Optional[Path] = None,
    config_dir: Optional[Path] = None,
    python_exe: Optional[str] = None,
    pythonw_exe: Optional[str] = None,
    powershell_exe: Optional[str] = None,
    state_dir: Optional[Path] = None,
) -> List[TrayEntry]:
    """Return every enabled plugin's tray entries (groups included), in order."""

    project_root = Path(project_root).resolve()
    app_dir = Path(app_dir).resolve() if app_dir else project_root / "app"
    config_dir = Path(config_dir).resolve() if config_dir else project_root / ".config"
    tiers = _tier_table(app_dir)
    state = _state_table(config_dir)
    context = {
        "python": str(python_exe or ""),
        "pythonw": str(pythonw_exe or python_exe or ""),
        "powershell": str(powershell_exe or _default_powershell()),
        "plugin": "",
        "root": str(project_root),
        "state": str(Path(state_dir) if state_dir else default_state_dir()),
    }

    entries: List[TrayEntry] = []
    seen: set[Tuple[str, str]] = set()
    leaves = 0
    for search_root in _plugin_roots(project_root):
        try:
            children = sorted(search_root.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            manifest_path = child / MANIFEST_DIR / MANIFEST_NAME
            if not manifest_path.is_file():
                continue
            manifest = _load_json(manifest_path)
            if not isinstance(manifest, Mapping):
                continue
            plugin_id = str(manifest.get("id") or child.name).strip().lower()
            if not plugin_id or not _is_enabled(plugin_id, tiers, state):
                continue
            plugin_context = dict(context)
            plugin_context["plugin"] = str(child)
            for row in _tray_rows(manifest):
                budget = MAX_TRAY_ACTIONS - leaves
                if budget <= 0:
                    return entries
                try:
                    if row.get("kind") == "group":
                        entry: Optional[TrayEntry] = _build_group(
                            plugin_id, child, row, plugin_context, budget
                        )
                    else:
                        entry = _build_action(plugin_id, child, dict(row), plugin_context)
                except (OSError, ValueError):
                    entry = None
                if entry is None:
                    continue
                key = (entry.plugin_id, entry.item_id)
                if key in seen:
                    continue
                seen.add(key)
                entries.append(entry)
                leaves += len(entry.children) if isinstance(entry, TrayGroup) else 1
    return entries


def discover_tray_actions(project_root: Path, **kwargs: Any) -> List[TrayAction]:
    """Flattened convenience view used by tests and simple callers."""

    flat: List[TrayAction] = []
    for entry in discover_tray_menu(project_root, **kwargs):
        if isinstance(entry, TrayGroup):
            flat.extend(entry.children)
        else:
            flat.append(entry)
    return flat


def launch(action: TrayAction) -> subprocess.Popen:
    """Start one tray action detached from the tray's own lifetime."""

    creationflags = 0
    if os.name == "nt" and action.windowless:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    return subprocess.Popen(
        list(action.argv),
        cwd=str(action.cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )


__all__ = [
    "MAX_TRAY_ACTIONS",
    "TrayAction",
    "TrayEntry",
    "TrayGroup",
    "default_state_dir",
    "discover_tray_actions",
    "discover_tray_menu",
    "launch",
]
