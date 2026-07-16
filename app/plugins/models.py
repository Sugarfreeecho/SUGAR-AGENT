"""Data models shared by MyAgent's declarative plugin subsystem."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple


COMPATIBILITY_STATUSES = {"native", "compatible", "partial", "unsupported"}


@dataclass(frozen=True)
class PluginCompatibilityReport:
    """Describes how faithfully a plugin can run in MyAgent."""

    status: str
    warnings: Tuple[str, ...] = ()
    supported_components: Tuple[str, ...] = ()
    unsupported_components: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in COMPATIBILITY_STATUSES:
            raise ValueError(f"Invalid plugin compatibility status: {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "warnings": list(self.warnings),
            "supported_components": list(self.supported_components),
            "unsupported_components": list(self.unsupported_components),
        }


@dataclass(frozen=True)
class PluginResource:
    """A path-based plugin resource with a collision-free public name."""

    plugin_id: str
    kind: str
    local_name: str
    qualified_name: str
    path: Path
    plugin_root: Path

    def to_dict(self) -> Dict[str, str]:
        return {
            "plugin_id": self.plugin_id,
            "kind": self.kind,
            "local_name": self.local_name,
            "qualified_name": self.qualified_name,
            "path": str(self.path),
            "plugin_root": str(self.plugin_root),
        }


@dataclass(frozen=True)
class PluginDefinition:
    """The host-neutral representation produced by all plugin adapters."""

    plugin_id: str
    name: str
    namespace: str
    version: str
    description: str
    author: Mapping[str, Any]
    root: Path
    manifest_path: Path
    source_format: str
    skills: Tuple[Path, ...] = ()
    hooks: Tuple[Path, ...] = ()
    mcp_sources: Tuple[Path, ...] = ()
    agents: Tuple[Path, ...] = ()
    prompts: Tuple[Path, ...] = ()
    mcp_servers: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    permissions: Mapping[str, Any] = field(default_factory=dict)
    content_signature: str = ""
    compatibility: PluginCompatibilityReport = field(
        default_factory=lambda: PluginCompatibilityReport("unsupported")
    )
    raw_manifest: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def id(self) -> str:
        """Alias used by manifest-oriented callers."""

        return self.plugin_id

    @property
    def format(self) -> str:
        """Compatibility alias for ``source_format``."""

        return self.source_format

    @property
    def components(self) -> Mapping[str, Any]:
        return {
            "skills": self.skills,
            "hooks": self.hooks,
            "mcp_servers": self.mcp_servers,
            "agents": self.agents,
            "prompts": self.prompts,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.plugin_id,
            "name": self.name,
            "namespace": self.namespace,
            "version": self.version,
            "description": self.description,
            "author": dict(self.author),
            "root": str(self.root),
            "manifest_path": str(self.manifest_path),
            "source_format": self.source_format,
            "components": {
                "skills": [str(path) for path in self.skills],
                "hooks": [str(path) for path in self.hooks],
                "mcp_sources": [str(path) for path in self.mcp_sources],
                "mcp_servers": sorted(self.mcp_servers),
                "agents": [str(path) for path in self.agents],
                "prompts": [str(path) for path in self.prompts],
            },
            "permissions": dict(self.permissions),
            "content_signature": self.content_signature,
            "compatibility": self.compatibility.to_dict(),
        }


@dataclass(frozen=True)
class PluginDiscoveryResult:
    plugins: Tuple[PluginDefinition, ...] = ()
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugins": [plugin.to_dict() for plugin in self.plugins],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PluginLoadResult:
    """All enabled plugin resources ready to merge into host registries."""

    plugins: Tuple[PluginDefinition, ...] = ()
    skill_directories: Mapping[str, Path] = field(default_factory=dict)
    hook_sources: Tuple[PluginResource, ...] = ()
    mcp_servers: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    agent_directories: Mapping[str, Path] = field(default_factory=dict)
    prompt_directories: Mapping[str, Path] = field(default_factory=dict)
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    globally_enabled: bool = True

    @property
    def enabled(self) -> bool:
        return self.globally_enabled

    @property
    def skills(self) -> Mapping[str, Path]:
        return self.skill_directories

    @property
    def hooks(self) -> Tuple[PluginResource, ...]:
        return self.hook_sources

    @property
    def hook_paths(self) -> Tuple[Path, ...]:
        return tuple(source.path for source in self.hook_sources)

    @property
    def hook_source_specs(self) -> Tuple[Dict[str, Any], ...]:
        """Mappings accepted directly by ``hooks.HookManager``."""

        return tuple(
            {
                "source_id": source.qualified_name,
                "plugin_id": source.plugin_id,
                "root": source.plugin_root,
                "config_path": source.path,
            }
            for source in self.hook_sources
        )

    @property
    def agents(self) -> Mapping[str, Path]:
        return self.agent_directories

    @property
    def prompts(self) -> Mapping[str, Path]:
        return self.prompt_directories

    @property
    def mcp_config(self) -> Dict[str, Any]:
        return {"servers": dict(self.mcp_servers)}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "globally_enabled": self.globally_enabled,
            "plugins": [plugin.to_dict() for plugin in self.plugins],
            "skill_directories": {
                name: str(path) for name, path in self.skill_directories.items()
            },
            "hook_sources": [source.to_dict() for source in self.hook_sources],
            "mcp_servers": dict(self.mcp_servers),
            "agent_directories": {
                name: str(path) for name, path in self.agent_directories.items()
            },
            "prompt_directories": {
                name: str(path) for name, path in self.prompt_directories.items()
            },
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PluginChangeSet:
    """Result of comparing the latest enabled plugins with the last load."""

    added: Tuple[str, ...] = ()
    changed: Tuple[str, ...] = ()
    removed: Tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.changed or self.removed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "added": list(self.added),
            "changed": list(self.changed),
            "removed": list(self.removed),
            "has_changes": self.has_changes,
        }


@dataclass(frozen=True)
class PluginReloadResult:
    changes: PluginChangeSet
    loaded: PluginLoadResult

    @property
    def has_changes(self) -> bool:
        return self.changes.has_changes

    def to_dict(self) -> Dict[str, Any]:
        return {"changes": self.changes.to_dict(), "loaded": self.loaded.to_dict()}
