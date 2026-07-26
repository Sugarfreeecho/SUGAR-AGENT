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
    "PluginValidationError",
    "default_discovery_dirs",
    "default_state_path",
    "discover_plugins",
    "get_plugin_manager",
    "get_plugin_runtime_registry",
    "load_enabled_plugins",
    "load_plugin",
    "normalize_namespace",
    "path_resources",
    "plugin_content_signature",
    "plugins_enabled",
    "runtime_tool_name",
    "safe_plugin_path",
    "skill_resources",
]
