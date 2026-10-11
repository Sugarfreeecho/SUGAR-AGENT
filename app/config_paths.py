"""Local state paths, with an in-place migration from the old directory name."""
from __future__ import annotations

import logging
import threading
from pathlib import Path


logger = logging.getLogger(__name__)
CONFIG_DIR_NAME = ".config"
LEGACY_CONFIG_DIR_NAME = ".sugaragent"
_migration_lock = threading.RLock()
_migrated_roots: set[Path] = set()


def _move_missing(source: Path, target: Path) -> None:
    """Merge missing entries while leaving conflicting old files untouched."""
    if not target.exists() and not target.is_symlink():
        source.rename(target)
        return
    if (source.is_dir() and target.is_dir()
            and not source.is_symlink() and not target.is_symlink()):
        for child in source.iterdir():
            _move_missing(child, target / child.name)
        # Conflicting entries remain as a backup in the old directory.
        if not any(source.iterdir()):
            source.rmdir()


def config_dir(root: Path | str) -> Path:
    """Rename .sugaragent once per root, without overwriting newer config."""
    root = Path(root).resolve()
    target = root / CONFIG_DIR_NAME
    legacy = root / LEGACY_CONFIG_DIR_NAME
    with _migration_lock:
        if root not in _migrated_roots:
            if legacy.is_dir() and not legacy.is_symlink():
                try:
                    _move_missing(legacy, target)
                    logger.info("Migrated local state directory %s -> %s", legacy, target)
                except OSError:
                    # A locked/read-only directory must not reset user state.
                    logger.warning("Could not finish migrating %s -> %s", legacy, target,
                                   exc_info=True)
            _migrated_roots.add(root)
    return target


def config_path(root: Path | str, *parts: str) -> Path:
    """Use the new path, or retain an unmoved legacy entry after a failed move."""
    directory = config_dir(root)
    target = directory.joinpath(*parts)
    legacy = directory.parent.joinpath(LEGACY_CONFIG_DIR_NAME, *parts)
    if not target.exists() and legacy.exists():
        return legacy
    return target


def resolve_legacy_config_path(path: Path, root: Path | str) -> Path:
    """Keep saved attachment/Markdown paths working after the rename."""
    root = Path(root).resolve()
    path = Path(path).resolve()
    try:
        relative = path.relative_to(root / LEGACY_CONFIG_DIR_NAME)
    except ValueError:
        return path
    target = config_path(root, *relative.parts)
    # Prefer an existing old file if a conflicting copy was retained.
    if path.exists():
        return path
    return target if target.exists() else path
