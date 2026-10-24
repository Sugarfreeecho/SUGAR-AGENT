"""Scandir traversal for a leading recursive glob, with pathlib fallbacks."""
from __future__ import annotations

import fnmatch
import errno
import os
from pathlib import Path


def recursive_glob(root: Path, pattern: str):
    """Return an iterator for **/suffix, or None for other pathlib patterns.

    Scan each recursive directory once. In particular, a literal suffix such
    as .config/plugins*.json must not stat .config under every directory.
    Only TempOutput is pruned: it is already excluded by the tool contract.
    Recursive descent does not follow directory links, just like Path.glob.
    """
    parts = Path(pattern).parts
    if (not parts or parts[0] != '**' or len(parts) < 2
            or any(p in {'**', '..'} for p in parts[1:])):
        return None
    directory_only = pattern.endswith(('/', os.sep))
    suffix = parts[1:]
    matchers = [re_match(part) for part in suffix]

    def entries_at(directory):
        try:
            with os.scandir(directory) as iterator:
                return [entry for entry in iterator if entry.name.lower() != 'tempoutput']
        except OSError as exc:
            if _ignorable(exc):
                return []
            raise

    def select(directory, entries, position):
        final = position == len(suffix) - 1
        for entry in entries:
            if not matchers[position](os.path.normcase(entry.name)):
                continue
            try:
                if final:
                    literal = not any(c in suffix[position] for c in '*?[')
                    if (not directory_only or entry.is_dir()) and (
                        not literal or not entry.is_symlink() or (directory / entry.name).exists()
                    ):
                        yield directory / entry.name
                elif entry.is_dir():
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
                    if entry.is_dir(follow_symlinks=False):
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
