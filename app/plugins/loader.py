"""Manifest adapters and safe discovery for MyAgent plugins.

The loader is deliberately declarative.  It reads JSON and resource files but
never imports or executes Python (or any other plugin code).
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .models import (
    PluginCompatibilityReport,
    PluginDefinition,
    PluginDiscoveryResult,
    PluginResource,
)
from .security import (
    PluginSecurityError,
    PluginValidationError,
    is_path_within,
    normalize_namespace,
    plugin_content_signature,
    safe_plugin_path,
)


MANIFEST_MARKERS: Tuple[Tuple[str, str], ...] = (
    (".myagent-plugin", "native"),
    (".claude-plugin", "claude"),
    (".codex-plugin", "codex"),
)
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_MCP_CONFIG_BYTES = 4 * 1024 * 1024

_COMMON_FIELDS = {
    "$schema",
    "schema_version",
    "schemaVersion",
    "name",
    "id",
    "display_name",
    "displayName",
    "version",
    "description",
    "author",
    "authors",
    "homepage",
    "repository",
    "license",
    "keywords",
    "metadata",
    "permissions",
    "components",
    "skills",
    "hooks",
    "mcp_servers",
    "mcpServers",
    "agents",
    "prompts",
}
_UNSUPPORTED_COMPONENT_KEYS = {
    "commands",
    "slash_commands",
    "lsp",
    "lspServers",
    "apps",
    "ui",
    "themes",
    "outputStyles",
}
_FORBIDDEN_CODE_KEYS = {
    "main",
    "module",
    "python",
    "python_module",
    "entrypoint",
    "entry_point",
    "activationEvents",
}
_SKILL_NAME_RE = re.compile(r"(?mi)^name\s*:\s*([^\r\n#]+)")


def _read_json_file(path: Path, max_bytes: int, label: str) -> Mapping[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise PluginValidationError(f"Cannot stat {label} {path}: {exc}") from exc
    if size > max_bytes:
        raise PluginValidationError(f"{label} is too large: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PluginValidationError(f"Cannot parse {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PluginValidationError(f"{label} root must be a JSON object: {path}")
    return data


def _manifest_from_path(path: Path | str) -> tuple[Path, Path, str, tuple[str, ...]]:
    supplied = Path(path).expanduser()
    warnings: List[str] = []
    if supplied.is_file():
        manifest = supplied.resolve(strict=True)
        parent_name = manifest.parent.name
        formats = {marker: source_format for marker, source_format in MANIFEST_MARKERS}
        if manifest.name != "plugin.json" or parent_name not in formats:
            raise PluginValidationError(
                "Plugin manifest must be .myagent-plugin/plugin.json, "
                ".claude-plugin/plugin.json, or .codex-plugin/plugin.json"
            )
        return manifest.parent.parent.resolve(strict=True), manifest, formats[parent_name], ()
    try:
        root = supplied.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginValidationError(f"Plugin directory does not exist: {supplied}") from exc
    if not root.is_dir():
        raise PluginValidationError(f"Plugin root must be a directory: {root}")
    matches: List[tuple[Path, str]] = []
    for marker, source_format in MANIFEST_MARKERS:
        candidate = root / marker / "plugin.json"
        if candidate.is_file():
            matches.append((candidate.resolve(strict=True), source_format))
    if not matches:
        raise PluginValidationError(f"No supported plugin manifest under {root}")
    manifest, source_format = matches[0]
    if not is_path_within(manifest, root):
        raise PluginSecurityError("Plugin manifest symlink escapes its root")
    if len(matches) > 1:
        warnings.append(
            "Multiple plugin manifests found; selected "
            f"{manifest.parent.name}/plugin.json by adapter priority"
        )
    return root, manifest, source_format, tuple(warnings)


def _component_container(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    components = manifest.get("components")
    return components if isinstance(components, dict) else {}


def _component_value(manifest: Mapping[str, Any], *keys: str) -> Any:
    components = _component_container(manifest)
    for key in keys:
        if key in manifest:
            return manifest[key]
        if key in components:
            return components[key]
    return None


def _path_values(value: Any, component: str) -> tuple[list[str], list[str]]:
    """Return declared paths and non-fatal adapter warnings."""

    if value is None:
        return [], []
    values = value if isinstance(value, list) else [value]
    paths: List[str] = []
    warnings: List[str] = []
    for item in values:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            paths.append(item["path"])
        else:
            warnings.append(f"Ignored unsupported inline {component} declaration")
    return paths, warnings


def _resolve_declared_paths(
    root: Path,
    manifest: Mapping[str, Any],
    component: str,
    aliases: Sequence[str],
    *,
    expected: str = "any",
) -> tuple[list[Path], list[str], bool]:
    value = _component_value(manifest, *aliases)
    raw_paths, warnings = _path_values(value, component)
    resolved = [safe_plugin_path(root, item, expected=expected) for item in raw_paths]
    return resolved, warnings, value is not None


def _append_conventional(paths: List[Path], candidate: Path, root: Path, expected: str) -> None:
    if not candidate.exists():
        return
    resolved = safe_plugin_path(root, candidate, expected=expected)
    if resolved not in paths:
        paths.append(resolved)


def _normalise_author(value: Any) -> Mapping[str, Any]:
    if isinstance(value, str):
        return {"name": value}
    if isinstance(value, dict):
        return {str(key): copy.deepcopy(item) for key, item in value.items()}
    if isinstance(value, list):
        return {"authors": copy.deepcopy(value)}
    return {}


def _normalise_permissions(value: Any, warnings: List[str]) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return {item: True for item in value}
    warnings.append("Ignored invalid permissions declaration; permissions grant no authority")
    return {}


def _replace_root_tokens(value: Any, root: Path) -> Any:
    if isinstance(value, str):
        root_text = str(root)
        for token in (
            "${MYAGENT_PLUGIN_ROOT}",
            "${CLAUDE_PLUGIN_ROOT}",
            "${CODEX_PLUGIN_ROOT}",
        ):
            value = value.replace(token, root_text)
        return value
    if isinstance(value, list):
        return [_replace_root_tokens(item, root) for item in value]
    if isinstance(value, dict):
        return {str(key): _replace_root_tokens(item, root) for key, item in value.items()}
    return copy.deepcopy(value)


def _secure_mcp_server_config(root: Path, alias: str, raw: Any) -> Mapping[str, Any]:
    if not isinstance(raw, dict):
        raise PluginValidationError(f"MCP server {alias!r} must be an object")
    config = _replace_root_tokens(raw, root)
    for key in ("cwd", "workingDirectory"):
        cwd = config.get(key)
        if isinstance(cwd, str) and cwd.strip():
            config[key] = str(safe_plugin_path(root, cwd, expected="dir"))
    # A command name such as `python` or `npx` is allowed.  Explicit command
    # paths are plugin resources and therefore cannot escape the plugin root.
    command = config.get("command")
    if isinstance(command, str) and command.strip():
        looks_like_path = command.startswith((".", "/", "\\")) or "/" in command or "\\" in command
        if looks_like_path:
            config["command"] = str(safe_plugin_path(root, command, expected="file"))
    return config


def _extract_server_object(data: Mapping[str, Any], source: str) -> Mapping[str, Any]:
    if data.get("enabled") is False:
        return {}
    if isinstance(data.get("mcpServers"), dict):
        return data["mcpServers"]
    if isinstance(data.get("servers"), dict):
        return data["servers"]
    ignored = {"enabled", "version", "schema_version", "$schema"}
    direct = {key: value for key, value in data.items() if key not in ignored}
    if direct and all(isinstance(value, dict) for value in direct.values()):
        return direct
    raise PluginValidationError(f"MCP config has no server object: {source}")


def _mcp_declarations(
    root: Path,
    manifest: Mapping[str, Any],
) -> tuple[list[Path], Mapping[str, Any], list[str], bool]:
    value = _component_value(manifest, "mcp_servers", "mcpServers")
    paths: List[Path] = []
    inline: Mapping[str, Any] = {}
    warnings: List[str] = []
    declared = value is not None
    if isinstance(value, str):
        paths.append(safe_plugin_path(root, value, expected="file"))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                paths.append(safe_plugin_path(root, item, expected="file"))
            elif isinstance(item, dict) and isinstance(item.get("path"), str):
                paths.append(safe_plugin_path(root, item["path"], expected="file"))
            else:
                warnings.append("Ignored unsupported MCP declaration")
    elif isinstance(value, dict):
        if isinstance(value.get("path"), str):
            paths.append(safe_plugin_path(root, value["path"], expected="file"))
        else:
            inline = _extract_server_object(value, "manifest")
    elif value is not None:
        warnings.append("Ignored invalid MCP declaration")
    return paths, inline, warnings, declared


def _load_mcp_servers(
    root: Path,
    namespace: str,
    sources: Iterable[Path],
    inline: Mapping[str, Any],
) -> tuple[Mapping[str, Mapping[str, Any]], list[str]]:
    merged: Dict[str, Mapping[str, Any]] = {}
    warnings: List[str] = []
    groups: List[tuple[str, Mapping[str, Any]]] = []
    if inline:
        groups.append(("manifest", inline))
    for path in sources:
        data = _read_json_file(path, MAX_MCP_CONFIG_BYTES, "MCP config")
        groups.append((str(path), _extract_server_object(data, str(path))))
    for source, servers in groups:
        for raw_alias, raw_config in servers.items():
            local_alias = normalize_namespace(raw_alias)
            qualified = f"{namespace}/{local_alias}"
            if qualified in merged:
                warnings.append(f"Duplicate MCP server {qualified!r} ignored from {source}")
                continue
            merged[qualified] = _secure_mcp_server_config(root, str(raw_alias), raw_config)
    return merged, warnings


def _supported_component_names(
    skills: Sequence[Path],
    hooks: Sequence[Path],
    mcp_servers: Mapping[str, Any],
    agents: Sequence[Path],
    prompts: Sequence[Path],
) -> list[str]:
    return [
        name
        for name, present in (
            ("skills", bool(skills)),
            ("hooks", bool(hooks)),
            ("mcp_servers", bool(mcp_servers)),
            ("agents", bool(agents)),
            ("prompts", bool(prompts)),
        )
        if present
    ]


def load_plugin(path: Path | str) -> PluginDefinition:
    """Parse one native, Claude, or Codex plugin into a unified definition."""

    root, manifest_path, source_format, initial_warnings = _manifest_from_path(path)
    manifest = _read_json_file(manifest_path, MAX_MANIFEST_BYTES, "plugin manifest")
    warnings: List[str] = list(initial_warnings)

    raw_id = manifest.get("id") or manifest.get("name") or root.name
    namespace = normalize_namespace(raw_id)
    name = str(
        manifest.get("display_name")
        or manifest.get("displayName")
        or manifest.get("name")
        or raw_id
    ).strip()
    if not name:
        raise PluginValidationError("Plugin name is required")
    version = str(manifest.get("version") or "0.0.0").strip()
    description = str(manifest.get("description") or "").strip()

    skills, component_warnings, skills_declared = _resolve_declared_paths(
        root, manifest, "skills", ("skills",)
    )
    warnings.extend(component_warnings)
    hooks, component_warnings, hooks_declared = _resolve_declared_paths(
        root, manifest, "hooks", ("hooks",), expected="file"
    )
    warnings.extend(component_warnings)
    agents, component_warnings, agents_declared = _resolve_declared_paths(
        root, manifest, "agents", ("agents",)
    )
    warnings.extend(component_warnings)
    prompts, component_warnings, prompts_declared = _resolve_declared_paths(
        root, manifest, "prompts", ("prompts",)
    )
    warnings.extend(component_warnings)
    mcp_sources, inline_mcp, component_warnings, mcp_declared = _mcp_declarations(root, manifest)
    warnings.extend(component_warnings)

    # Claude and Codex manifests conventionally discover these directories;
    # native plugins accept the same defaults for a low-friction authoring path.
    if not skills_declared:
        _append_conventional(skills, root / "skills", root, "dir")
    if not hooks_declared:
        _append_conventional(hooks, root / "hooks" / "hooks.json", root, "file")
    if not agents_declared:
        _append_conventional(agents, root / "agents", root, "dir")
    if not prompts_declared:
        _append_conventional(prompts, root / "prompts", root, "dir")
    if not mcp_declared:
        _append_conventional(mcp_sources, root / ".mcp.json", root, "file")
        _append_conventional(mcp_sources, root / "mcp" / "servers.json", root, "file")

    mcp_servers, mcp_warnings = _load_mcp_servers(
        root, namespace, mcp_sources, inline_mcp
    )
    warnings.extend(mcp_warnings)

    permissions = _normalise_permissions(manifest.get("permissions"), warnings)
    supported = _supported_component_names(skills, hooks, mcp_servers, agents, prompts)
    manifest_components = _component_container(manifest)
    unsupported = sorted(
        key
        for key in _UNSUPPORTED_COMPONENT_KEYS
        if key in manifest or key in manifest_components
    )
    forbidden = sorted(
        key for key in _FORBIDDEN_CODE_KEYS if key in manifest or key in manifest_components
    )
    if forbidden:
        unsupported.extend(forbidden)
        warnings.append(
            "Executable host entrypoints are unsupported and were not loaded: "
            + ", ".join(forbidden)
        )
    if unsupported:
        warnings.append("Unsupported plugin components: " + ", ".join(sorted(set(unsupported))))

    unknown = sorted(
        key
        for key in manifest
        if key not in _COMMON_FIELDS
        and key not in _UNSUPPORTED_COMPONENT_KEYS
        and key not in _FORBIDDEN_CODE_KEYS
    )
    if unknown:
        warnings.append("Unrecognized manifest fields were ignored: " + ", ".join(unknown))

    unsupported = sorted(set(unsupported))
    if source_format == "native" and not unsupported:
        compatibility_status = "native"
    elif supported and unsupported:
        compatibility_status = "partial"
    elif supported:
        compatibility_status = "compatible"
    else:
        compatibility_status = "unsupported"
        warnings.append("Plugin has no supported declarative components")

    compatibility = PluginCompatibilityReport(
        status=compatibility_status,
        warnings=tuple(dict.fromkeys(warnings)),
        supported_components=tuple(supported),
        unsupported_components=tuple(unsupported),
    )
    return PluginDefinition(
        plugin_id=namespace,
        name=name,
        namespace=namespace,
        version=version,
        description=description,
        author=_normalise_author(manifest.get("author") or manifest.get("authors")),
        root=root,
        manifest_path=manifest_path,
        source_format=source_format,
        skills=tuple(skills),
        hooks=tuple(hooks),
        mcp_sources=tuple(mcp_sources),
        agents=tuple(agents),
        prompts=tuple(prompts),
        mcp_servers=mcp_servers,
        permissions=permissions,
        content_signature=plugin_content_signature(root),
        compatibility=compatibility,
        raw_manifest=copy.deepcopy(manifest),
    )


def _manifest_candidates(discovery_root: Path) -> list[Path]:
    try:
        root = discovery_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return []
    if not root.is_dir():
        return []
    if any((root / marker / "plugin.json").is_file() for marker, _ in MANIFEST_MARKERS):
        return [root]
    candidates: Dict[str, Path] = {}
    for manifest in root.rglob("plugin.json"):
        if manifest.parent.name not in {marker for marker, _ in MANIFEST_MARKERS}:
            continue
        try:
            plugin_root = manifest.parent.parent.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not is_path_within(plugin_root, root):
            continue
        candidates[str(plugin_root).casefold()] = plugin_root
    return [candidates[key] for key in sorted(candidates)]


def discover_plugins(
    discovery_dirs: Iterable[Path | str] | Path | str,
) -> PluginDiscoveryResult:
    """Discover plugins, isolating invalid packages from healthy packages."""

    plugins: List[PluginDefinition] = []
    errors: List[str] = []
    warnings: List[str] = []
    seen_roots: set[str] = set()
    seen_ids: Dict[str, Path] = {}
    roots = (
        (discovery_dirs,)
        if isinstance(discovery_dirs, (str, Path))
        else discovery_dirs
    )
    for discovery_dir in roots:
        for candidate in _manifest_candidates(Path(discovery_dir)):
            root_key = str(candidate).casefold()
            if root_key in seen_roots:
                continue
            seen_roots.add(root_key)
            try:
                plugin = load_plugin(candidate)
            except (PluginValidationError, PluginSecurityError) as exc:
                errors.append(f"{candidate}: {exc}")
                continue
            previous = seen_ids.get(plugin.plugin_id)
            if previous is not None:
                warnings.append(
                    f"Duplicate plugin namespace {plugin.plugin_id!r} at {candidate}; "
                    f"keeping earlier plugin at {previous}"
                )
                continue
            seen_ids[plugin.plugin_id] = plugin.root
            plugins.append(plugin)
    plugins.sort(key=lambda item: (item.plugin_id, str(item.root).casefold()))
    return PluginDiscoveryResult(
        plugins=tuple(plugins), errors=tuple(errors), warnings=tuple(warnings)
    )


def _safe_resource_files(root: Path, configured: Path, file_names: Optional[set[str]] = None) -> list[Path]:
    configured = safe_plugin_path(root, configured)
    if configured.is_file():
        if file_names is None or configured.name in file_names:
            return [configured]
        return []
    found: List[Path] = []
    for candidate in configured.rglob("*"):
        safe = safe_plugin_path(root, candidate)
        if not safe.is_file():
            continue
        if file_names is not None and safe.name not in file_names:
            continue
        found.append(safe)
    return sorted(set(found), key=lambda item: item.as_posix())


def skill_resources(plugin: PluginDefinition) -> tuple[PluginResource, ...]:
    resources: List[PluginResource] = []
    seen: set[str] = set()
    for configured in plugin.skills:
        for skill_file in _safe_resource_files(plugin.root, configured, {"SKILL.md"}):
            local_name = skill_file.parent.name
            try:
                text = skill_file.read_text(encoding="utf-8")[:16384]
                if text.startswith("---"):
                    end = text.find("---", 3)
                    header = text[3:end] if end >= 0 else ""
                    match = _SKILL_NAME_RE.search(header)
                    if match:
                        local_name = match.group(1).strip().strip("'\"")
            except (OSError, UnicodeError):
                pass
            local_name = normalize_namespace(local_name)
            qualified = f"{plugin.namespace}:{local_name}"
            if qualified in seen:
                continue
            seen.add(qualified)
            resources.append(
                PluginResource(
                    plugin_id=plugin.plugin_id,
                    kind="skill",
                    local_name=local_name,
                    qualified_name=qualified,
                    path=skill_file.parent,
                    plugin_root=plugin.root,
                )
            )
    return tuple(resources)


def path_resources(plugin: PluginDefinition, kind: str, paths: Iterable[Path]) -> tuple[PluginResource, ...]:
    resources: List[PluginResource] = []
    seen: set[str] = set()
    for configured in paths:
        for candidate in (configured,):
            local_name = normalize_namespace(candidate.stem if candidate.is_file() else candidate.name)
            qualified = f"{plugin.namespace}:{local_name}"
            if qualified in seen:
                suffix = 2
                while f"{qualified}-{suffix}" in seen:
                    suffix += 1
                qualified = f"{qualified}-{suffix}"
            seen.add(qualified)
            resources.append(
                PluginResource(
                    plugin_id=plugin.plugin_id,
                    kind=kind,
                    local_name=local_name,
                    qualified_name=qualified,
                    path=safe_plugin_path(plugin.root, candidate),
                    plugin_root=plugin.root,
                )
            )
    return tuple(resources)
