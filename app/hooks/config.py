"""hooks.json loading and validation."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .models import (
    FAILURE_POLICIES,
    SUPPORTED_HOOK_EVENT_SET,
    CommandSpec,
    HookConfigurationError,
    HookDefinition,
    HookLoadResult,
    HookSource,
)


SourceLike = Union[HookSource, str, Path, Mapping[str, Any]]


def _as_path(value: Any, base: Path) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else base / path


def _normalize_source(source: SourceLike, project_root: Path, index: int) -> HookSource:
    if isinstance(source, HookSource):
        return source
    if isinstance(source, (str, Path)):
        path = _as_path(source, project_root).resolve()
        return HookSource(source_id=f"plugin:{path.stem}:{index}", root=path.parent, config_path=path)
    if not isinstance(source, Mapping):
        raise HookConfigurationError(f"Plugin hook source #{index} must be a path or object.")

    plugin_id = str(source.get("plugin_id") or source.get("id") or "").strip() or None
    source_id = str(source.get("source_id") or (f"plugin:{plugin_id}" if plugin_id else f"plugin:{index}"))
    root = _as_path(source.get("root") or project_root, project_root).resolve()
    raw_config = source.get("config")
    config: Optional[Mapping[str, Any]] = raw_config if isinstance(raw_config, Mapping) else None
    raw_path = source.get("config_path") or source.get("path")
    config_path = _as_path(raw_path, root).resolve() if raw_path else None
    if config is None and config_path is None and "hooks" in source:
        config = source
    if config is None and config_path is None:
        raise HookConfigurationError(f"Hook source {source_id!r} has neither config nor config_path.")
    return HookSource(
        source_id=source_id,
        root=root,
        config_path=config_path,
        config=config,
        plugin_id=plugin_id,
    )


def _read_source(source: HookSource) -> Mapping[str, Any]:
    if source.config is not None:
        return source.config
    assert source.config_path is not None
    try:
        parsed = json.loads(source.config_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise HookConfigurationError(f"Hook config not found: {source.config_path}") from exc
    except json.JSONDecodeError as exc:
        raise HookConfigurationError(
            f"Invalid JSON in {source.config_path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise HookConfigurationError(f"Cannot read hook config {source.config_path}: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise HookConfigurationError(f"Hook config {source.config_path} must contain a JSON object.")
    return parsed


def _string(value: Any, field: str, *, allow_empty: bool = True) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HookConfigurationError(f"{field} must be a string.")
    value = value.strip()
    if not value and not allow_empty:
        raise HookConfigurationError(f"{field} cannot be empty.")
    return value


def _platform_value(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        value = value.get("command")
    return _string(value, field)


def _parse_command(entry: Mapping[str, Any], inherited: Mapping[str, Any]) -> CommandSpec:
    raw_command = entry.get("command")
    default_command: Optional[str]
    windows_command: Optional[str] = None
    unix_command: Optional[str] = None
    if isinstance(raw_command, Mapping):
        default_command = _platform_value(raw_command.get("default"), "command.default")
        windows_command = _platform_value(raw_command.get("windows"), "command.windows")
        unix_command = _platform_value(raw_command.get("unix") or raw_command.get("posix"), "command.unix")
    else:
        default_command = _platform_value(raw_command, "command")

    windows_command = _platform_value(
        entry.get("windows_command", entry.get("command_windows", entry.get("windows"))),
        "windows_command",
    ) or windows_command
    unix_command = _platform_value(
        entry.get("unix_command", entry.get("command_unix", entry.get("unix"))),
        "unix_command",
    ) or unix_command
    if not any((default_command, windows_command, unix_command)):
        raise HookConfigurationError("A command hook requires command, windows_command, or unix_command.")

    raw_timeout = entry.get("timeout_seconds", entry.get("timeout", inherited.get("timeout_seconds", 10.0)))
    try:
        timeout = float(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise HookConfigurationError("timeout_seconds must be a number.") from exc
    if timeout <= 0:
        raise HookConfigurationError("timeout_seconds must be greater than zero.")

    raw_limit = entry.get("max_output_bytes", inherited.get("max_output_bytes", 1024 * 1024))
    try:
        max_output = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise HookConfigurationError("max_output_bytes must be an integer.") from exc
    if max_output < 1024:
        raise HookConfigurationError("max_output_bytes must be at least 1024.")

    raw_allowlist = entry.get(
        "env_allowlist",
        entry.get("environment", inherited.get("env_allowlist", inherited.get("environment", ()))),
    )
    if raw_allowlist is None:
        raw_allowlist = ()
    if not isinstance(raw_allowlist, (list, tuple)) or any(not isinstance(item, str) for item in raw_allowlist):
        raise HookConfigurationError("env_allowlist must be an array of environment variable names.")
    allowlist = tuple(dict.fromkeys(item.strip() for item in raw_allowlist if item.strip()))

    raw_env = entry.get("env", inherited.get("env", {})) or {}
    if not isinstance(raw_env, Mapping):
        raise HookConfigurationError("env must be an object containing literal values.")
    env: Dict[str, str] = {}
    for key, value in raw_env.items():
        if not isinstance(key, str) or not key.strip() or isinstance(value, (dict, list)):
            raise HookConfigurationError("env keys must be non-empty strings and values must be scalar.")
        env[key.strip()] = "" if value is None else str(value)

    cwd = _string(entry.get("cwd", inherited.get("cwd")), "cwd")
    return CommandSpec(
        command=default_command,
        windows_command=windows_command,
        unix_command=unix_command,
        cwd=cwd,
        timeout_seconds=timeout,
        env_allowlist=allowlist,
        env=env,
        max_output_bytes=max_output,
    )


def _parse_document(source: HookSource, document: Mapping[str, Any], order_start: int) -> List[HookDefinition]:
    raw_version = document.get("version", document.get("schema_version", 1))
    if raw_version != 1:
        raise HookConfigurationError(f"Unsupported hook schema version {raw_version!r} in {source.source_id}.")
    hooks = document.get("hooks", {})
    if not isinstance(hooks, Mapping):
        raise HookConfigurationError(f"hooks in {source.source_id} must be an object keyed by event name.")

    definitions: List[HookDefinition] = []
    order = order_start
    for event, raw_entries in hooks.items():
        if event not in SUPPORTED_HOOK_EVENT_SET:
            raise HookConfigurationError(f"Unsupported hook event {event!r} in {source.source_id}.")
        if not isinstance(raw_entries, list):
            raise HookConfigurationError(f"hooks.{event} must be an array.")
        for group_index, raw_group in enumerate(raw_entries):
            if not isinstance(raw_group, Mapping):
                raise HookConfigurationError(f"hooks.{event}[{group_index}] must be an object.")
            if raw_group.get("enabled") is False:
                continue
            nested = raw_group.get("hooks")
            if nested is not None and "type" not in raw_group and "command" not in raw_group:
                if not isinstance(nested, list):
                    raise HookConfigurationError(f"hooks.{event}[{group_index}].hooks must be an array.")
                handler_entries = nested
                inherited = raw_group
            else:
                handler_entries = [raw_group]
                inherited = {}

            for handler_index, raw_handler in enumerate(handler_entries):
                if not isinstance(raw_handler, Mapping):
                    raise HookConfigurationError(
                        f"hooks.{event}[{group_index}].hooks[{handler_index}] must be an object."
                    )
                if raw_handler.get("enabled") is False:
                    continue
                handler_type = str(raw_handler.get("type", "command")).strip().lower()
                if handler_type != "command":
                    raise HookConfigurationError(
                        f"Hook type {handler_type!r} is not supported by the command-hook runtime."
                    )
                matcher = _string(raw_handler.get("matcher", inherited.get("matcher", "")), "matcher") or ""
                try:
                    re.compile(".*" if matcher == "*" else matcher)
                except re.error as exc:
                    raise HookConfigurationError(f"Invalid matcher regex {matcher!r}: {exc}") from exc
                policy = str(
                    raw_handler.get("failure_policy", inherited.get("failure_policy", "warn"))
                ).strip().lower()
                if policy not in FAILURE_POLICIES:
                    raise HookConfigurationError(
                        f"failure_policy must be one of {sorted(FAILURE_POLICIES)}, got {policy!r}."
                    )
                raw_priority = raw_handler.get("priority", inherited.get("priority", 100))
                if isinstance(raw_priority, bool):
                    raise HookConfigurationError("priority must be an integer.")
                try:
                    priority = int(raw_priority)
                except (TypeError, ValueError) as exc:
                    raise HookConfigurationError("priority must be an integer.") from exc
                hook_id = str(
                    raw_handler.get("id")
                    or f"{source.source_id}:{event}:{group_index}:{handler_index}"
                ).strip()
                if not hook_id:
                    raise HookConfigurationError("Hook id cannot be empty.")
                definitions.append(
                    HookDefinition(
                        id=hook_id,
                        event=event,
                        command=_parse_command(raw_handler, inherited),
                        matcher=matcher,
                        handler_type=handler_type,
                        failure_policy=policy,
                        priority=priority,
                        source_id=source.source_id,
                        source_root=source.root,
                        plugin_id=source.plugin_id,
                        order=order,
                    )
                )
                order += 1
    return definitions


def load_hook_sources(
    project_root: Union[str, Path],
    *,
    config_path: Optional[Union[str, Path]] = None,
    plugin_sources: Optional[Sequence[SourceLike]] = None,
    include_project: bool = True,
    strict: bool = False,
) -> HookLoadResult:
    """Load project and plugin hook sources into validated definitions.

    Project hooks default to ``<project_root>/hooks.json``. A missing default
    file is normal; an explicitly supplied missing file is a configuration
    error. Plugin sources may be paths, :class:`HookSource` values, or mappings
    containing ``config``/``config_path``, ``root``, and ``plugin_id``.
    """

    root = Path(project_root).expanduser().resolve()
    sources: List[HookSource] = []
    explicit_project_path = config_path is not None
    if include_project:
        path = _as_path(config_path or "hooks.json", root).resolve()
        if path.is_file() or explicit_project_path:
            sources.append(HookSource("project", root, config_path=path))
    errors: List[str] = []
    for index, raw_source in enumerate(plugin_sources or ()):
        try:
            sources.append(_normalize_source(raw_source, root, index))
        except HookConfigurationError as exc:
            if strict:
                raise
            errors.append(str(exc))

    definitions: List[HookDefinition] = []
    loaded: List[str] = []
    for source in sources:
        try:
            document = _read_source(source)
            definitions.extend(_parse_document(source, document, len(definitions)))
            loaded.append(source.source_id)
        except HookConfigurationError as exc:
            if strict:
                raise
            errors.append(str(exc))
    definitions.sort(key=lambda item: (item.priority, item.order, item.source_id, item.id))
    return HookLoadResult(tuple(definitions), tuple(errors), tuple(loaded))


def load_hook_definitions(
    project_root: Union[str, Path],
    *,
    config_path: Optional[Union[str, Path]] = None,
    plugin_sources: Optional[Sequence[SourceLike]] = None,
    include_project: bool = True,
) -> Tuple[HookDefinition, ...]:
    """Strict convenience API returning only hook definitions."""

    return load_hook_sources(
        project_root,
        config_path=config_path,
        plugin_sources=plugin_sources,
        include_project=include_project,
        strict=True,
    ).definitions
