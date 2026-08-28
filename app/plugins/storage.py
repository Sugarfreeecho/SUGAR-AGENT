"""Host-owned storage layout for executable plugins.

Plugin package roots are treated as source and may be read-only.  Persistent,
rebuildable, and temporary runtime files are allocated below a separate host
root and exposed to workers only as trusted context.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from .security import PluginSecurityError, normalize_namespace


def default_workspace_root() -> Path:
    """Resolve WORK_DIR with the same project-relative convention as the host."""

    project_root = Path(__file__).resolve().parents[2]
    raw = str(os.getenv("WORK_DIR") or "").strip()
    candidate = Path(raw).expanduser() if raw else project_root / "workspace"
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def default_plugin_storage_root() -> Path:
    configured = str(
        os.getenv("PLUGIN_STORAGE_DIR")
        or os.getenv("MYAGENT_PLUGIN_STORAGE_DIR")
        or ""
    ).strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = default_workspace_root() / candidate
        return candidate.resolve()
    return (default_workspace_root() / ".sugaragent" / "plugins").resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class PluginStorageLayout:
    plugin_id: str
    root: Path
    data_dir: Path
    cache_dir: Path
    temp_dir: Path

    def reset_temp_dir(self) -> None:
        """Remove contents from the host-owned temporary directory safely."""

        for entry in self.temp_dir.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                entry.unlink(missing_ok=True)
            else:
                shutil.rmtree(entry)

    def trusted_context(self, *, workspace_root: str = "") -> Dict[str, str]:
        context = {
            "plugin_id": self.plugin_id,
            "plugin_data_dir": str(self.data_dir),
            "plugin_cache_dir": str(self.cache_dir),
            "plugin_temp_dir": str(self.temp_dir),
        }
        workspace = str(workspace_root or "").strip()
        if workspace:
            context["workspace_root"] = workspace
        return context


def plugin_storage_layout(
    plugin_id: str,
    *,
    storage_root: Path | str | None = None,
    create: bool = True,
) -> PluginStorageLayout:
    """Return a canonical, non-escaping directory layout for one plugin."""

    namespace = normalize_namespace(plugin_id)
    root = Path(storage_root or default_plugin_storage_root()).expanduser()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    try:
        resolved_root = root.resolve(strict=create)
    except (OSError, RuntimeError) as exc:
        raise PluginSecurityError(f"Cannot resolve plugin storage root: {root}") from exc

    plugin_root = resolved_root / namespace
    if create:
        plugin_root.mkdir(parents=False, exist_ok=True)
    try:
        resolved_plugin_root = plugin_root.resolve(strict=create)
    except (OSError, RuntimeError) as exc:
        raise PluginSecurityError(
            f"Cannot resolve storage for plugin {namespace!r}"
        ) from exc
    if not _is_within(resolved_plugin_root, resolved_root):
        raise PluginSecurityError(
            f"Plugin storage escapes the configured root: {namespace!r}"
        )

    children = []
    for name in ("data", "cache", "temp"):
        child = resolved_plugin_root / name
        if create:
            child.mkdir(parents=False, exist_ok=True)
        try:
            resolved_child = child.resolve(strict=create)
        except (OSError, RuntimeError) as exc:
            raise PluginSecurityError(
                f"Cannot resolve {name} storage for plugin {namespace!r}"
            ) from exc
        if not _is_within(resolved_child, resolved_plugin_root):
            raise PluginSecurityError(
                f"Plugin {name} storage escapes its allocated root: {namespace!r}"
            )
        children.append(resolved_child)

    return PluginStorageLayout(
        plugin_id=namespace,
        root=resolved_plugin_root,
        data_dir=children[0],
        cache_dir=children[1],
        temp_dir=children[2],
    )


__all__ = [
    "PluginStorageLayout",
    "default_plugin_storage_root",
    "default_workspace_root",
    "plugin_storage_layout",
]
