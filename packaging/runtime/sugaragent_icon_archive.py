"""Read the desktop PPT icon library without expanding it at startup."""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile


INDEX_NAME = "icon-archive.json"
ARCHIVE_NAME = "icons.zip"


@lru_cache(maxsize=16)
def _index(root: str, modified: int) -> dict:
    return json.loads((Path(root) / INDEX_NAME).read_text(encoding="utf-8"))


def _load_index(root: Path) -> dict:
    index = root / INDEX_NAME
    return _index(str(root), index.stat().st_mtime_ns)


def _write_icon(destination: Path, data: bytes) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    # An existing icon may be a user customization. Never overwrite it.
    if destination.is_file():
        return destination
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        if destination.is_file():
            return destination
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def materialize_icon(path: Path) -> Path:
    """Return a real path for one icon, honoring loose/project-local icons first."""
    path = Path(path)
    if path.is_file():
        return path
    for root in path.parents:
        if not (root / INDEX_NAME).is_file():
            continue
        entry = path.relative_to(root).as_posix()
        parts = PurePosixPath(entry).parts
        if ".." in parts or "\\" in entry or ":" in entry or not entry.endswith(".svg"):
            return path
        index = _load_index(root)
        if index.get("schemaVersion") != 1 or entry not in index["entries"]:
            return path
        digest = index["sha256"]
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("Invalid icon archive identity")
        with zipfile.ZipFile(root / ARCHIVE_NAME) as archive:
            data = archive.read(entry)
        try:
            return _write_icon(path, data)
        except OSError:
            # Direct use of a read-only runtime still works, without expanding
            # the complete library or relying on network downloads.
            cache = Path(tempfile.gettempdir()) / "sugaragent-icons" / digest
            return _write_icon(cache.joinpath(*parts), data)
    return path


def list_icons(root: Path, library: str = "", query: str = "") -> list[str]:
    """Search all bundled names, including icons that have never been extracted."""
    if (root / INDEX_NAME).is_file():
        entries = _load_index(root)["entries"]
    else:
        entries = [path.relative_to(root).as_posix() for path in root.rglob("*.svg")]
    return sorted(entry[:-4] for entry in entries
                  if (not library or entry.startswith(library + "/"))
                  and query.casefold() in entry.casefold())


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the complete bundled PPT icon library")
    parser.add_argument("command", choices=["list"])
    parser.add_argument("--library", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--icons-dir", type=Path,
                        default=Path(__file__).resolve().parent.parent / "templates" / "icons")
    args = parser.parse_args()
    for name in list_icons(args.icons_dir, args.library, args.query):
        print(name)


if __name__ == "__main__":
    main()
