"""Path and content-integrity helpers for declarative plugins."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections import OrderedDict
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

# Hot-reload checks ask for a plugin signature on every discovery pass. Reading
# every byte each time costs seconds for asset-heavy plugins (the Remotion tree
# alone is ~126 MB), so reuse a signature while a stat-only fingerprint of the
# tree is unchanged. Bounded and process-local: a restart re-reads once.
_SIGNATURE_CACHE_LOCK = threading.Lock()
_SIGNATURE_CACHE: "OrderedDict[str, tuple[str, str]]" = OrderedDict()
_SIGNATURE_CACHE_LIMIT = 64
_SIGNATURE_CACHE_FILE = "plugin-signatures.json"
_signature_cache_loaded = False


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
    """Yield every regular plugin file without following escaping symlinks.

    Only links are resolved. Resolving every entry cost ~2 ms per file on
    Windows (GetFinalPathName), which made a 1,900-file skill tree take
    seconds on every scan.
    """

    resolved_root = root.resolve(strict=True)
    for current, dir_names, file_names in os.walk(resolved_root, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for name in sorted(dir_names):
            if name in _SIGNATURE_IGNORED_DIRS:
                continue
            child = current_path / name
            if not child.is_symlink():
                kept_dirs.append(name)
                continue
            try:
                resolved = child.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise PluginSecurityError(f"Broken plugin directory link: {child}") from exc
            if not is_path_within(resolved, resolved_root):
                raise PluginSecurityError(
                    f"Plugin directory symlink escapes its root: {child}"
                )
            # A validated link is still not descended into, matching os.walk's
            # followlinks=False contract.
        dir_names[:] = kept_dirs
        for name in sorted(file_names):
            child = current_path / name
            if not child.is_symlink():
                try:
                    if child.is_file():
                        yield child
                except OSError:
                    continue
                continue
            try:
                resolved = child.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise PluginSecurityError(f"Broken plugin file link: {child}") from exc
            if not is_path_within(resolved, resolved_root):
                raise PluginSecurityError(f"Plugin file symlink escapes its root: {child}")
            if resolved.is_file():
                yield child


def _plugin_tree_fingerprint(resolved_root: Path) -> str:
    """Summarise file names, sizes and mtimes without reading plugin bytes."""

    rows: list[tuple[str, str, int, int]] = []
    pending = [resolved_root]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    relative = path.relative_to(resolved_root).as_posix()
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in _SIGNATURE_IGNORED_DIRS:
                            pending.append(path)
                        continue
                    if entry.is_symlink():
                        try:
                            target = os.readlink(path)
                            resolved = path.resolve(strict=True)
                        except (OSError, RuntimeError) as exc:
                            raise PluginSecurityError(
                                f"Broken plugin symlink: {path}"
                            ) from exc
                        if not is_path_within(resolved, resolved_root):
                            raise PluginSecurityError(
                                f"Plugin symlink escapes its root: {path}"
                            )
                        rows.append((relative, "L", len(target), 0))
                        continue
                    try:
                        stat_result = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        raise PluginValidationError(
                            f"Cannot read plugin content: {path}"
                        ) from exc
                    rows.append(
                        (relative, "F", int(stat_result.st_size),
                         int(stat_result.st_mtime_ns))
                    )
        except OSError as exc:
            raise PluginValidationError(
                f"Cannot scan plugin content: {current}"
            ) from exc

    digest = hashlib.sha256()
    for relative, kind, size, mtime_ns in sorted(rows):
        digest.update(kind.encode("ascii"))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(size.to_bytes(8, "big", signed=False))
        digest.update(mtime_ns.to_bytes(8, "big", signed=False))
    return digest.hexdigest()


def _read_plugin_content_digest(resolved_root: Path) -> str:
    """Hash relative names and bytes; only runs when the tree fingerprint moved."""

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


def _signature_cache_path() -> Path | None:
    """Keep the cache in per-user state so a cold start avoids full re-reads."""

    try:
        from plugins.manager import _user_data_root

        return _user_data_root() / "cache" / _SIGNATURE_CACHE_FILE
    except Exception:
        return None


def _load_signature_cache() -> None:
    global _signature_cache_loaded
    if _signature_cache_loaded:
        return
    _signature_cache_loaded = True
    path = _signature_cache_path()
    if path is None:
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    rows = raw.get("plugins") if isinstance(raw, dict) else None
    if not isinstance(rows, dict):
        return
    for key, row in rows.items():
        if not isinstance(row, dict):
            continue
        fingerprint = row.get("fingerprint")
        signature = row.get("signature")
        if isinstance(fingerprint, str) and isinstance(signature, str):
            _SIGNATURE_CACHE[str(key)] = (fingerprint, signature)


def _save_signature_cache() -> None:
    path = _signature_cache_path()
    if path is None:
        return
    payload = {
        "version": 1,
        "plugins": {
            key: {"fingerprint": value[0], "signature": value[1]}
            for key, value in _SIGNATURE_CACHE.items()
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        os.replace(temporary, path)
    except OSError:
        pass  # The cache only saves work; never fail a load because of it.


def plugin_content_signature(root: Path) -> str:
    """Hash relative names and bytes for deterministic hot-reload detection."""

    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PluginValidationError(f"Plugin root does not exist: {root}") from exc
    cache_key = os.path.normcase(str(resolved_root))
    fingerprint = _plugin_tree_fingerprint(resolved_root)
    with _SIGNATURE_CACHE_LOCK:
        _load_signature_cache()
        cached = _SIGNATURE_CACHE.get(cache_key)
        if cached is not None and cached[0] == fingerprint:
            _SIGNATURE_CACHE.move_to_end(cache_key)
            return cached[1]
    signature = _read_plugin_content_digest(resolved_root)
    with _SIGNATURE_CACHE_LOCK:
        _SIGNATURE_CACHE[cache_key] = (fingerprint, signature)
        _SIGNATURE_CACHE.move_to_end(cache_key)
        while len(_SIGNATURE_CACHE) > _SIGNATURE_CACHE_LIMIT:
            _SIGNATURE_CACHE.popitem(last=False)
        _save_signature_cache()
    return signature
