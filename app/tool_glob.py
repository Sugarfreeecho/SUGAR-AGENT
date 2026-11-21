"""Scandir traversal for a leading recursive glob, with pathlib fallbacks."""
from __future__ import annotations

import errno
import fnmatch
import os
import stat
import time
from pathlib import Path
from typing import Iterable, Optional

from tool_cancel import current_cancel_event

# Dependency, VCS and cache trees are pruned by default.  A code search must
# never walk node_modules: pnpm links packages with directory junctions, and
# some peer-dependency pairs form real cycles (browserslist <->
# update-browserslist-db), so following those links never terminates.
PRUNED_DIR_NAMES = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "bower_components", "jspm_packages",
    ".venv", "venv", "virtualenv",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
})

_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class GlobScanStopped(Exception):
    """Raised when a glob hits its entry budget, deadline or cancellation."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _scan_budget() -> int:
    try:
        return max(1, int(os.getenv("GLOB_MAX_SCAN_ENTRIES", "200000")))
    except ValueError:
        return 200000


def _scan_timeout() -> float:
    try:
        value = float(os.getenv("GLOB_TIMEOUT_SEC", "60"))
    except ValueError:
        return 60.0
    return value if value > 0 else 60.0


def _is_link_like(entry: os.DirEntry) -> bool:
    """True for symlinks and Windows junctions/reparse points.

    ``DirEntry.is_dir(follow_symlinks=False)`` reports ``True`` for NTFS
    junctions on CPython 3.10, so it cannot be used to stop recursive descent.
    """
    try:
        if entry.is_symlink():
            return True
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attributes & _REPARSE_POINT)


def recursive_glob(
    root: Path,
    pattern: str,
    *,
    max_entries: Optional[int] = None,
    timeout_sec: Optional[float] = None,
    cancel_event=None,
    prune_dirs: Optional[Iterable[str]] = None,
):
    """Return an iterator for **/suffix, or None for other pathlib patterns.

    Scan each recursive directory once. In particular, a literal suffix such
    as .config/plugins*.json must not stat .config under every directory.
    TempOutput is always pruned, dependency/VCS/cache trees are pruned unless
    ``GLOB_INCLUDE_IGNORED=1``, and directory links are never followed.
    """
    parts = Path(pattern).parts
    if (not parts or parts[0] != '**' or len(parts) < 2
            or any(p in {'**', '..'} for p in parts[1:])):
        return None
    directory_only = pattern.endswith(('/', os.sep))
    suffix = parts[1:]
    matchers = [re_match(part) for part in suffix]

    pruned = {name.lower() for name in (PRUNED_DIR_NAMES if prune_dirs is None else prune_dirs)}
    if _env_flag("GLOB_INCLUDE_IGNORED"):
        pruned = set()

    budget = max_entries if max_entries and max_entries > 0 else _scan_budget()
    timeout = timeout_sec if timeout_sec and timeout_sec > 0 else _scan_timeout()
    cancel = cancel_event if cancel_event is not None else current_cancel_event()
    deadline = time.monotonic() + timeout
    scanned = 0

    def check_stop() -> None:
        if cancel is not None and cancel.is_set():
            raise GlobScanStopped("cancelled")
        if time.monotonic() >= deadline:
            raise GlobScanStopped("timeout")
        if scanned >= budget:
            raise GlobScanStopped("entries")

    def entries_at(directory):
        nonlocal scanned
        check_stop()
        try:
            with os.scandir(directory) as iterator:
                entries = [
                    entry for entry in iterator
                    if entry.name.lower() not in pruned
                    and entry.name.lower() != 'tempoutput'
                ]
        except OSError as exc:
            if _ignorable(exc):
                return []
            raise
        scanned += len(entries)
        if scanned > budget:
            raise GlobScanStopped("entries")
        return entries

    def select(directory, entries, position):
        final = position == len(suffix) - 1
        for entry in entries:
            if not matchers[position](os.path.normcase(entry.name)):
                continue
            try:
                if final:
                    literal = not any(c in suffix[position] for c in '*?[')
                    if (not directory_only or entry.is_dir()) and (
                        not literal or not _is_link_like(entry) or (directory / entry.name).exists()
                    ):
                        yield directory / entry.name
                elif entry.is_dir(follow_symlinks=False) and not _is_link_like(entry):
                    child = directory / entry.name
                    yield from select(child, entries_at(child), position + 1)
            except OSError as exc:
                if not _ignorable(exc):
                    raise

    def walk():
        stack = [root]
        while stack:
            directory = stack.pop()
            entries = entries_at(directory)
            yield from select(directory, entries, 0)
            children = []
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False) and not _is_link_like(entry):
                        children.append(directory / entry.name)
                except OSError as exc:
                    if not _ignorable(exc):
                        raise
            stack.extend(reversed(children))

    return walk()


def re_match(pattern):
    import re

    return re.compile(fnmatch.translate(os.path.normcase(pattern))).match


def _ignorable(exc):
    # Do not turn unexpected disk failures into an apparently empty result.
    return (isinstance(exc, PermissionError)
            or exc.errno in {errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP}
            or getattr(exc, 'winerror', None) in {21, 123, 1921})
