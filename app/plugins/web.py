"""Validated static Web capability declarations for plugins."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional

from .models import PluginDefinition
from .security import PluginSecurityError


@dataclass(frozen=True)
class PluginWebManifest:
    plugin_id: str
    entry: Optional[Path]
    assets: Optional[Path]
    api: bool


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _declared_path(
    plugin: PluginDefinition,
    raw: Any,
    *,
    kind: str,
    require_file: bool,
) -> Optional[Path]:
    value = str(raw or "").strip().replace("\\", "/")
    if not value:
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise PluginSecurityError(
            f"Plugin {plugin.plugin_id!r} Web {kind} must stay inside its package"
        )
    root = plugin.root.resolve(strict=True)
    candidate = (root / Path(*relative.parts)).resolve(strict=True)
    if not _inside(candidate, root):
        raise PluginSecurityError(
            f"Plugin {plugin.plugin_id!r} Web {kind} escapes its package"
        )
    expected = candidate.is_file() if require_file else candidate.is_dir()
    if not expected:
        expected_kind = "file" if require_file else "directory"
        raise PluginSecurityError(
            f"Plugin {plugin.plugin_id!r} Web {kind} is not a {expected_kind}"
        )
    return candidate


def plugin_web_manifest(plugin: PluginDefinition) -> Optional[PluginWebManifest]:
    capabilities = plugin.raw_manifest.get("capabilities")
    raw_web = capabilities.get("web") if isinstance(capabilities, Mapping) else None
    if raw_web is True:
        raw_web = {}
    if not isinstance(raw_web, Mapping):
        return None
    entry = _declared_path(
        plugin,
        raw_web.get("entry"),
        kind="entry",
        require_file=True,
    )
    assets = _declared_path(
        plugin,
        raw_web.get("assets"),
        kind="assets",
        require_file=False,
    )
    return PluginWebManifest(
        plugin_id=plugin.plugin_id,
        entry=entry,
        assets=assets,
        api=bool(raw_web.get("api")),
    )


def resolve_plugin_asset(plugin: PluginDefinition, asset_path: str) -> Path:
    manifest = plugin_web_manifest(plugin)
    if manifest is None or manifest.assets is None:
        raise PluginSecurityError(
            f"Plugin {plugin.plugin_id!r} has no static asset capability"
        )
    raw = str(asset_path or "").strip().replace("\\", "/")
    relative = PurePosixPath(raw)
    if not raw or relative.is_absolute() or ".." in relative.parts:
        raise PluginSecurityError("Plugin asset path is invalid")
    candidate = (manifest.assets / Path(*relative.parts)).resolve(strict=True)
    if not _inside(candidate, manifest.assets) or not candidate.is_file():
        raise PluginSecurityError("Plugin asset path escapes its declared directory")
    return candidate


__all__ = [
    "PluginWebManifest",
    "plugin_web_manifest",
    "resolve_plugin_asset",
]
