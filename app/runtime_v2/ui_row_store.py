"""Immutable, independently addressable UI rows, including compacted baselines."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path


class UiRowStore:
    def __init__(self, directory: Path):
        self.directory = directory

    def write(self, rows: list[dict], *, file_number=0) -> tuple[str, list[list]]:
        self.directory.mkdir(parents=True, exist_ok=True)
        name = f"ui_rows_{uuid.uuid4().hex}.jsonl"
        path = self.directory / name
        locations = []
        try:
            with path.open("xb") as fh:
                for row in rows:
                    encoded = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
                    offset = fh.tell()
                    fh.write(encoded)
                    locations.append([file_number, offset, len(encoded), hashlib.sha256(encoded).hexdigest()])
            return name, locations
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def read(self, files: list[str], locations: list[list]) -> list[dict]:
        handles = {}
        out = []
        try:
            for file_number, offset, length, digest in locations:
                if int(file_number) < 0 or int(offset) < 0 or int(length) <= 0:
                    raise ValueError("invalid UI row location")
                name = files[int(file_number)]
                if Path(name).name != name or not name.startswith("ui_rows_") or not name.endswith(".jsonl"):
                    raise ValueError("invalid UI row segment")
                if name not in handles:
                    handles[name] = (self.directory / name).open("rb")
                fh = handles[name]
                fh.seek(int(offset))
                encoded = fh.read(int(length))
                if hashlib.sha256(encoded).hexdigest() != digest:
                    raise ValueError("UI row segment is corrupt")
                row = json.loads(encoded)
                if not isinstance(row, dict):
                    raise ValueError("invalid UI row")
                out.append(row)
        finally:
            for fh in handles.values():
                fh.close()
        return out

    def cleanup(self, keep: list[str]) -> None:
        # Old readers may still hold the previous index. Allow their requests
        # to finish before collecting unreferenced generations and crash debris.
        deadline = time.time() - 120
        keep_names = set(keep)
        for path in self.directory.glob("ui_rows_*.jsonl"):
            try:
                if path.name not in keep_names and path.stat().st_mtime < deadline:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
