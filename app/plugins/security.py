"""Path and content-integrity helpers for declarative plugins."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from typing import Iterator


class PluginError(ValueError):
    """Base error for plugin discovery, validation, and state operations."""


class PluginValidationError(PluginError):
    pass


class PluginSecurityError(PluginValidationError):
    pass


class PluginStateError(PluginError):
    pass


_SAFE_NAMESPACE = re.compile(r"[^a-z0-9._-]+")
_SIGNATURE_IGNORED_DIRS = frozenset(
    {".git", ".myagent-runtime", "__pycache__", "node_modules"}
)


def normalize_namespace(value: object) -> str:
    """Return a stable, filesystem-independent plugin namespace."""

    normalized = _SAFE_NAMESPACE.sub("-", str(value or "").strip().lower())
    normalized = re.sub(r"[-_.]{2,}", "-", normalized).strip("-._")
    if not normalized:
        raise PluginValidationError("Plugin name must contain a letter or number")
    if len(normalized) > 80:
        normalized = normalized[:80].rstrip("-._")
    return normalized


def _lexical_parts(raw_path: object) -> tuple[str, ...]:
    text = str(raw_path or "").strip()
    if not text:
        raise PluginValidationError("Plugin component path cannot be empty")
    if "\x00" in text:
        raise PluginSecurityError("Plugin component path contains a NUL byte")
    # Treat both slash styles as separators, even when tests run off Windows.
    return PurePosixPath(text.replace("\\", "/")).parts


def is_path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_plugin_path(
    root: Path,
    raw_path: object,
    *,
    must_exist: bool = True,
    expected: str = "any",
) -> Path:
    """Resolve a manifest path and forbid traversal or symlink escape."""

    try:
        root_resolved = root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginValidationError(f"Plugin root does not exist: {root}") from exc
    parts = _lexical_parts(raw_path)
    if ".." in parts:
        raise PluginSecurityError(f"Plugin path traversal is forbidden: {raw_path}")
    candidate = Path(str(raw_path)).expanduser()
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    try:
        resolved = candidate.resolve(strict=must_exist)
    except (OSError, RuntimeError) as exc:
        raise PluginValidationError(f"Plugin component does not exist: {raw_path}") from exc
    if not is_path_within(resolved, root_resolved):
        raise PluginSecurityError(
            f"Plugin path escapes its root (including through a symlink): {raw_path}"
        )
    if must_exist and expected == "file" and not resolved.is_file():
        raise PluginValidationError(f"Plugin component must be a file: {raw_path}")
    if must_exist and expected == "dir" and not resolved.is_dir():
        raise PluginValidationError(f"Plugin component must be a directory: {raw_path}")
    return resolved


def iter_safe_plugin_files(root: Path) -> Iterator[Path]:
    """Yield every regular plugin file without following escaping symlinks."""

    resolved_root = root.resolve(strict=True)
    for current, dir_names, file_names in os.walk(resolved_root, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for name in sorted(dir_names):
            if name in _SIGNATURE_IGNORED_DIRS:
                continue
            child = current_path / name
            try:
                resolved = child.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise PluginSecurityError(f"Broken plugin directory link: {child}") from exc
            if not is_path_within(resolved, resolved_root):
                raise PluginSecurityError(
                    f"Plugin directory symlink escapes its root: {child}"
                )
            # os.walk(followlinks=False) will not descend into directory symlinks.
            if not child.is_symlink():
                kept_dirs.append(name)
        dir_names[:] = kept_dirs
        for name in sorted(file_names):
            child = current_path / name
            try:
                resolved = child.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise PluginSecurityError(f"Broken plugin file link: {child}") from exc
            if not is_path_within(resolved, resolved_root):
                raise PluginSecurityError(f"Plugin file symlink escapes its root: {child}")
            if resolved.is_file():
                yield child


def plugin_content_signature(root: Path) -> str:
    """Hash relative names and bytes for deterministic hot-reload detection."""

    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginValidationError(f"Plugin root does not exist: {root}") from exc
    digest = hashlib.sha256()
    links = []
    for current, dir_names, file_names in os.walk(resolved_root, followlinks=False):
        current_path = Path(current)
        dir_names[:] = [
            name for name in dir_names if name not in _SIGNATURE_IGNORED_DIRS
        ]
        for name in tuple(dir_names) + tuple(file_names):
            child = current_path / name
            if not child.is_symlink():
                continue
            try:
                target = child.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise PluginSecurityError(f"Broken plugin symlink: {child}") from exc
            if not is_path_within(target, resolved_root):
                raise PluginSecurityError(f"Plugin symlink escapes its root: {child}")
            links.append(child)
    for path in sorted(links, key=lambda item: item.as_posix()):
        relative = path.relative_to(resolved_root).as_posix().encode("utf-8")
        try:
            target = os.readlink(path).encode("utf-8")
        except OSError as exc:
            raise PluginSecurityError(f"Cannot read plugin symlink: {path}") from exc
        digest.update(b"L")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(target).to_bytes(8, "big"))
        digest.update(target)
    for path in sorted(iter_safe_plugin_files(resolved_root), key=lambda p: p.as_posix()):
        relative = path.relative_to(resolved_root).as_posix().encode("utf-8")
        digest.update(b"F")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError as exc:
            raise PluginValidationError(f"Cannot read plugin content: {path}") from exc
    return digest.hexdigest()
