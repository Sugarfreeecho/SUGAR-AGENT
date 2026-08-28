"""Declarative resources and executable Plugin API runtimes for MyAgent.

Supported package markers:

* ``.myagent-plugin/plugin.json`` (native)
* ``.claude-plugin/plugin.json`` (compatible adapter)
* ``.codex-plugin/plugin.json`` (compatible adapter)
* ``plugin.yaml`` / ``plugin.yml`` (Hermes compatibility adapter)
* OpenCode plugin ``package.json`` packages

``PLUGINS_ENABLED`` defaults to enabled and accepts ``0``, ``false``, ``no``,
or ``off`` to prevent every plugin resource and runtime from being loaded.
"""
from .loader import MANIFEST_MARKERS, discover_plugins, load_plugin, path_resources, skill_resources
from .manager import (
    PluginManager,
    default_discovery_dirs,
    default_state_path,
    get_plugin_manager,
    load_enabled_plugins,
    plugins_enabled,
)
from .models import (
    COMPATIBILITY_STATUSES,
    PluginChangeSet,
    PluginCommand,
    PluginCompatibilityReport,
    PluginDefinition,
    PluginDiscoveryResult,
    PluginLoadResult,
    PluginReloadResult,
    PluginResource,
    PluginRuntimeSpec,
)
from .security import (
    PluginError,
    PluginSecurityError,
    PluginStateError,
    PluginValidationError,
    normalize_namespace,
    plugin_content_signature,
    safe_plugin_path,
)
from .runtime import (
    PluginRuntimeError,
    PluginRuntimeRegistry,
    RuntimeToolBinding,
    get_plugin_runtime_registry,
    runtime_tool_name,
)
from .installer import PluginInstallError, PluginInstaller
from .state import PluginStateStore
from .ui import plugin_ui_contributions, project_plugin_session_ui
from .storage import (
    PluginStorageLayout,
    default_plugin_storage_root,
    default_workspace_root,
    plugin_storage_layout,
)
from .settings import (
    PluginSettingsStore,
    default_plugin_settings_path,
    plugin_settings_schema,
    public_plugin_settings,
    resolve_plugin_settings_context,
)

__all__ = [
    "COMPATIBILITY_STATUSES",
    "MANIFEST_MARKERS",
    "PluginChangeSet",
    "PluginCommand",
    "PluginCompatibilityReport",
    "PluginDefinition",
    "PluginDiscoveryResult",
    "PluginError",
    "PluginLoadResult",
    "PluginManager",
    "PluginReloadResult",
    "PluginResource",
    "PluginRuntimeSpec",
    "PluginInstallError",
    "PluginInstaller",
    "PluginRuntimeError",
    "PluginRuntimeRegistry",
    "RuntimeToolBinding",
    "PluginSecurityError",
    "PluginStateError",
    "PluginStateStore",
    "PluginStorageLayout",
    "PluginValidationError",
    "default_discovery_dirs",
    "default_plugin_storage_root",
    "default_state_path",
    "default_workspace_root",
    "discover_plugins",
    "get_plugin_manager",
    "get_plugin_runtime_registry",
    "load_enabled_plugins",
    "load_plugin",
    "normalize_namespace",
    "path_resources",
    "plugin_content_signature",
    "plugin_ui_contributions",
    "project_plugin_session_ui",
    "plugins_enabled",
    "plugin_storage_layout",
    "PluginSettingsStore",
    "default_plugin_settings_path",
    "plugin_settings_schema",
    "public_plugin_settings",
    "resolve_plugin_settings_context",
    "runtime_tool_name",
    "safe_plugin_path",
    "skill_resources",
]
