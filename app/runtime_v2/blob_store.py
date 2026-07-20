from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path


class BlobStore:
    """Content-addressed store for large text payloads."""

    def __init__(self, session_dir: str | Path):
        self.session_dir = Path(session_dir)

    def put_text(self, text: str, suffix: str = ".txt") -> dict:
        data = str(text or "").encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        suffix = suffix if suffix.startswith(".") else f".{suffix}"
        rel = Path("blobs") / f"{digest}{suffix}"
        path = self.session_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_name(
                f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            try:
                with tmp.open("wb") as fh:
                    fh.write(data)
                    fh.flush()
                    os.fsync(fh.fileno())
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
        return {
            "blob_ref": rel.as_posix(),
            "sha256": digest,
            "bytes": len(data),
        }

    def read_text(self, blob_ref: str) -> str:
        rel = Path(str(blob_ref or ""))
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("invalid blob_ref")
        path = self.session_dir / rel
        data = path.read_bytes()
        expected = path.stem.lower()
        if len(expected) == 64 and all(char in "0123456789abcdef" for char in expected):
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                raise RuntimeError(
                    f"Runtime V2 blob checksum mismatch for {rel.as_posix()}: "
                    f"expected {expected}, got {actual}"
                )
        return data.decode("utf-8")
