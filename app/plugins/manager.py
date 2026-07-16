"""Lifecycle manager for discovered declarative plugins."""
from __future__ import annotations

import copy
import os
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from .loader import discover_plugins, path_resources, skill_resources
from .models import (
    PluginChangeSet,
    PluginDefinition,
    PluginDiscoveryResult,
    PluginLoadResult,
    PluginReloadResult,
    PluginResource,
)
from .security import (
    PluginError,
    PluginSecurityError,
    PluginValidationError,
    normalize_namespace,
    safe_plugin_path,
)
from .state import PluginStateStore


_FALSE_VALUES = {"0", "false", "no", "off"}


def plugins_enabled() -> bool:
    """Global feature switch.  Plugins are enabled by default."""

    return os.getenv("PLUGINS_ENABLED", "1").strip().lower() not in _FALSE_VALUES


def default_discovery_dirs() -> tuple[Path, ...]:
    """Resolve configurable project and user plugin search roots."""

    configured = os.getenv("PLUGINS_DIRS", "").strip()
    if configured:
        return tuple(
            Path(item).expanduser()
            for item in configured.split(os.pathsep)
            if item.strip()
        )
    single = os.getenv("PLUGINS_DIR", "").strip()
    if single:
        return (Path(single).expanduser(),)
    project_root = Path(__file__).resolve().parents[2]
    return (project_root / "plugins", Path.home() / ".myagent" / "plugins")


def default_state_path() -> Path:
    configured = os.getenv("PLUGINS_STATE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[2] / ".myagent" / "plugins-state.json"


class PluginManager:
    """Discovers, enables, merges, and hot-reloads plugin resources.

    Plugin contents stay declarative: this class never imports a module from a
    plugin.  Hook and MCP executors remain separate trust boundaries.
    """

    def __init__(
        self,
        discovery_dirs: Optional[Iterable[Path | str] | Path | str] = None,
        state_path: Optional[Path | str] = None,
        *,
        enabled: Optional[bool] = None,
    ):
        configured_dirs = default_discovery_dirs() if discovery_dirs is None else discovery_dirs
        if isinstance(configured_dirs, (str, Path)):
            configured_dirs = (configured_dirs,)
        self.discovery_dirs = tuple(Path(item).expanduser() for item in configured_dirs)
        self.state = PluginStateStore(default_state_path() if state_path is None else state_path)
        self._enabled_override = enabled
        self._lock = threading.RLock()
        self._loaded_signatures: Dict[str, str] = {}
        self._last_discovery = PluginDiscoveryResult()
        self._last_load = PluginLoadResult(globally_enabled=self._is_globally_enabled())

    def _is_globally_enabled(self) -> bool:
        return plugins_enabled() if self._enabled_override is None else bool(self._enabled_override)

    @property
    def globally_enabled(self) -> bool:
        return self._is_globally_enabled()

    @property
    def last_discovery(self) -> PluginDiscoveryResult:
        return self._last_discovery

    @property
    def last_load(self) -> PluginLoadResult:
        return self._last_load

    def discover_report(self) -> PluginDiscoveryResult:
        report = discover_plugins(self.discovery_dirs)
        self._last_discovery = report
        return report

    def discover(self) -> tuple[PluginDefinition, ...]:
        """Return valid discovered definitions; details stay in last_discovery."""

        return self.discover_report().plugins

    def is_enabled(self, plugin_id: str) -> bool:
        return self.state.is_enabled(plugin_id, default=True)

    def set_enabled(self, plugin_id: str, enabled: bool) -> Mapping[str, object]:
        namespace = normalize_namespace(plugin_id)
        known = {plugin.plugin_id for plugin in self.discover()}
        if namespace not in known:
            raise PluginValidationError(f"Unknown plugin: {plugin_id}")
        return self.state.set_enabled(namespace, enabled)

    def enable(self, plugin_id: str) -> Mapping[str, object]:
        return self.set_enabled(plugin_id, True)

    def disable(self, plugin_id: str) -> Mapping[str, object]:
        return self.set_enabled(plugin_id, False)

    enable_plugin = enable
    disable_plugin = disable
    set_plugin_enabled = set_enabled

    def _enabled_definitions(
        self, report: PluginDiscoveryResult
    ) -> tuple[list[PluginDefinition], list[str]]:
        enabled: List[PluginDefinition] = []
        errors: List[str] = []
        try:
            states = self.state.read().get("plugins", {})
        except PluginError as exc:
            # Fail closed if enablement state is corrupt; silently treating all
            # third-party code as enabled would violate the user's choices.
            return [], [str(exc)]
        for plugin in report.plugins:
            state = states.get(plugin.plugin_id)
            is_enabled = True if not isinstance(state, dict) else bool(state.get("enabled"))
            if not is_enabled:
                continue
            if plugin.compatibility.status == "unsupported":
                errors.append(
                    f"Plugin {plugin.plugin_id!r} is unsupported and was not loaded"
                )
                continue
            enabled.append(plugin)
        return enabled, errors

    @staticmethod
    def _component_resources(
        plugin: PluginDefinition, kind: str, configured_paths: Iterable[Path]
    ) -> tuple[PluginResource, ...]:
        """Namespace agent/prompt files, retaining empty roots as resources."""

        candidates: List[Path] = []
        seen_paths: set[str] = set()
        for configured in configured_paths:
            configured = safe_plugin_path(plugin.root, configured)
            if configured.is_file():
                configured_candidates = [configured]
            else:
                configured_candidates = []
                for item in configured.rglob("*"):
                    safe_item = safe_plugin_path(plugin.root, item)
                    if safe_item.is_file() and safe_item.suffix.lower() in {
                        ".md",
                        ".json",
                        ".txt",
                    }:
                        configured_candidates.append(safe_item)
                configured_candidates.sort(key=lambda item: item.as_posix())
                if not configured_candidates:
                    configured_candidates = [configured]
            for candidate in configured_candidates:
                path_key = str(candidate).casefold()
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                candidates.append(candidate)
        return path_resources(plugin, kind, candidates)

    def _assemble(self, update_signatures: bool) -> PluginLoadResult:
        if not self._is_globally_enabled():
            result = PluginLoadResult(globally_enabled=False)
            if update_signatures:
                self._loaded_signatures = {}
                self._last_load = result
            return result

        report = self.discover_report()
        enabled_plugins, state_errors = self._enabled_definitions(report)
        loaded_plugins: List[PluginDefinition] = []
        skill_dirs: Dict[str, Path] = {}
        hook_sources: List[PluginResource] = []
        mcp_servers: Dict[str, Mapping[str, object]] = {}
        agent_dirs: Dict[str, Path] = {}
        prompt_dirs: Dict[str, Path] = {}
        errors = list(report.errors) + state_errors
        warnings = list(report.warnings)

        for plugin in enabled_plugins:
            # Build each plugin off to the side so a resource changed into an
            # escaping symlink cannot leave a half-merged plugin behind.
            try:
                plugin_skills = skill_resources(plugin)
                plugin_hooks = path_resources(plugin, "hook", plugin.hooks)
                plugin_agents = self._component_resources(plugin, "agent", plugin.agents)
                plugin_prompts = self._component_resources(plugin, "prompt", plugin.prompts)
            except (PluginValidationError, PluginSecurityError, OSError) as exc:
                errors.append(f"Plugin {plugin.plugin_id!r} failed safe loading: {exc}")
                continue

            loaded_plugins.append(plugin)
            warnings.extend(plugin.compatibility.warnings)
            for resource in plugin_skills:
                if resource.qualified_name in skill_dirs:
                    warnings.append(f"Duplicate skill {resource.qualified_name!r} ignored")
                    continue
                skill_dirs[resource.qualified_name] = resource.path
            hook_sources.extend(plugin_hooks)
            for name, config in plugin.mcp_servers.items():
                if name in mcp_servers:
                    warnings.append(f"Duplicate MCP server {name!r} ignored")
                    continue
                mcp_servers[name] = copy.deepcopy(config)
            for resource in plugin_agents:
                if resource.qualified_name in agent_dirs:
                    warnings.append(f"Duplicate agent {resource.qualified_name!r} ignored")
                    continue
                agent_dirs[resource.qualified_name] = resource.path
            for resource in plugin_prompts:
                if resource.qualified_name in prompt_dirs:
                    warnings.append(f"Duplicate prompt {resource.qualified_name!r} ignored")
                    continue
                prompt_dirs[resource.qualified_name] = resource.path

        result = PluginLoadResult(
            plugins=tuple(loaded_plugins),
            skill_directories=skill_dirs,
            hook_sources=tuple(hook_sources),
            mcp_servers=mcp_servers,
            agent_directories=agent_dirs,
            prompt_directories=prompt_dirs,
            errors=tuple(dict.fromkeys(errors)),
            warnings=tuple(dict.fromkeys(warnings)),
            globally_enabled=True,
        )
        if update_signatures:
            self._loaded_signatures = {
                plugin.plugin_id: plugin.content_signature for plugin in loaded_plugins
            }
            self._last_load = result
        return result

    def load_enabled(self) -> PluginLoadResult:
        with self._lock:
            return self._assemble(update_signatures=True)

    load = load_enabled

    def _changes_for(self, current: PluginLoadResult) -> PluginChangeSet:
        current_signatures = {
            plugin.plugin_id: plugin.content_signature for plugin in current.plugins
        }
        previous_ids = set(self._loaded_signatures)
        current_ids = set(current_signatures)
        return PluginChangeSet(
            added=tuple(sorted(current_ids - previous_ids)),
            changed=tuple(
                sorted(
                    plugin_id
                    for plugin_id in current_ids & previous_ids
                    if current_signatures[plugin_id] != self._loaded_signatures[plugin_id]
                )
            ),
            removed=tuple(sorted(previous_ids - current_ids)),
        )

    def detect_changes(self) -> PluginChangeSet:
        """Compare current enabled plugin signatures without updating baseline."""

        with self._lock:
            return self._changes_for(self._assemble(update_signatures=False))

    def has_changes(self) -> bool:
        return self.detect_changes().has_changes

    def reload_changed(self) -> PluginReloadResult:
        with self._lock:
            loaded = self._assemble(update_signatures=False)
            changes = self._changes_for(loaded)
            self._loaded_signatures = {
                plugin.plugin_id: plugin.content_signature for plugin in loaded.plugins
            }
            self._last_load = loaded
            return PluginReloadResult(changes=changes, loaded=loaded)


_default_manager: Optional[PluginManager] = None
_default_manager_config: Optional[tuple[tuple[str, ...], str]] = None
_default_manager_lock = threading.Lock()


def get_plugin_manager() -> PluginManager:
    """Return the lazy process-wide manager used by host integrations."""

    global _default_manager, _default_manager_config
    with _default_manager_lock:
        dirs = default_discovery_dirs()
        state_path = default_state_path()
        config = (
            tuple(str(path.expanduser().resolve()) for path in dirs),
            str(state_path.expanduser().resolve()),
        )
        if _default_manager is None or _default_manager_config != config:
            _default_manager = PluginManager(dirs, state_path)
            _default_manager_config = config
        return _default_manager


def load_enabled_plugins() -> PluginLoadResult:
    return get_plugin_manager().load_enabled()
