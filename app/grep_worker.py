"""Minimal, killable Python-regex worker. No agent/runtime imports at startup."""
from __future__ import annotations

import fnmatch
import io
import json
import os
import re
import sys
from pathlib import Path


def requires_isolation(pattern):
    """Keep only non-repeating, non-asserting regexes on the in-process path.

    This is deliberately conservative. All repeats, lookarounds and references
    run in the child, including nested/grouped variants. A thread timeout cannot
    interrupt Python re while it holds the GIL.
    """
    import sre_parse
    simple = {sre_parse.LITERAL, sre_parse.NOT_LITERAL, sre_parse.ANY,
              sre_parse.IN, sre_parse.AT, sre_parse.CATEGORY}

    def safe(items):
        for op, arg in items:
            if op in simple:
                continue
            if op == sre_parse.SUBPATTERN and safe(arg[-1]):
                continue
            if op == sre_parse.BRANCH and all(safe(branch) for branch in arg[1]):
                continue
            return False
        return True
    return not safe(sre_parse.parse(pattern))


def scan_file(path, regex, file_cap, line_cap, emit, check=lambda: None,
              *, skip_binary=True, decode_errors="replace"):
    check()
    try:
        if path.stat().st_size > file_cap:
            return 1
        with path.open("rb") as raw:
            if skip_binary and b"\0" in raw.read(8192):
                return 0
            raw.seek(0)
            with io.TextIOWrapper(raw, encoding="utf-8", errors=decode_errors) as text:
                for number, line in enumerate(text, 1):
                    check()
                    if regex.search(line):
                        line = line.rstrip()
                        if len(line) > line_cap:
                            line = line[:line_cap] + f"... [truncated, {len(line)} chars total]"
                        if emit({"file": str(path), "line": number, "text": line}):
                            return 0
    except OSError as exc:
        emit({"error": f"Error reading {path}: {exc}"})
    return 0


def walk_files(request):
    target = Path(request["target"])
    excluded = set(request["excluded_dirs"])
    for root, dirs, files in os.walk(target, followlinks=False):
        dirs[:] = [d for d in dirs if d not in excluded
                   and (request["include_hidden"] or not d.startswith("."))]
        for name in files:
            path = Path(root) / name
            if name.lower() in request["protected_names"]:
                continue
            if path.is_symlink() or (not request["include_hidden"] and name.startswith(".")):
                continue
            rel = path.relative_to(target).as_posix()
            matches = lambda p: fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p)
            if request["include"] and not any(map(matches, request["include"])):
                continue
            if any(map(matches, request["exclude"])):
                continue
            yield path
        if not request["recursive"]:
            return


def main():
    request = json.loads(sys.stdin.readline())
    regex = re.compile(request["pattern"], request["flags"])
    skipped = 0
    count = 0

    def emit(row):
        nonlocal count
        print(json.dumps(row, ensure_ascii=True), flush=True)
        count += 1
        return count >= request["max_results"]

    paths = map(Path, request["files"]) if request["files"] is not None else walk_files(request)
    for path in paths:
        skipped += scan_file(path, regex, request["file_cap"], request["line_cap"], emit,
                             skip_binary=request["skip_binary"], decode_errors=request["decode_errors"])
        if count >= request["max_results"]:
            break
    print(json.dumps({"skipped_large_files": skipped}), flush=True)


if __name__ == "__main__":
    main()
