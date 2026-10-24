"""Atomic, process-locked credentials outside the source tree.

Windows encrypts the entire record with current-user DPAPI. Unix uses an
owner-only directory and files. Never put OAuth credentials in model profiles.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
import uuid


def default_directory() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "SugarAgent/plugins/chatgpt-subscription"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sugaragent/plugins/chatgpt-subscription"


class Vault:
    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory or default_directory())
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            self.directory.chmod(0o700)
        self.path = self.directory / "credentials.json"
        self.mutex = threading.RLock()

    @contextmanager
    def locked(self):
        # Hold this lock through refresh and save to serialize rotating tokens
        # even if two SugarAgent processes use the same registration.
        with self.mutex:
            fd = os.open(self.directory / "credentials.lock", os.O_CREAT | os.O_RDWR, 0o600)
            try:
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"\0")
                os.lseek(fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    import msvcrt
                    deadline = time.monotonic() + 120
                    while True:
                        try:
                            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            if time.monotonic() >= deadline:
                                raise TimeoutError("Credential store is busy") from None
                            time.sleep(0.05)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def read(self) -> dict:
        if not self.path.exists():
            return {"host_id": "urn:uuid:" + str(uuid.uuid4()),
                    "proxy_key": secrets.token_urlsafe(32), "port": 0, "accounts": {}}
        raw = self.path.read_bytes()
        if os.name == "nt":
            import win32crypt
            envelope = json.loads(raw)
            if envelope.get("protection") != "windows-dpapi":
                raise ValueError("Invalid credential protection format")
            raw = win32crypt.CryptUnprotectData(base64.b64decode(envelope["data"]), None, None, None, 1)[1]
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("accounts"), dict):
            raise ValueError("Invalid credential record")
        return value

    def write(self, value: dict):
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        if os.name == "nt":
            import win32crypt
            encrypted = win32crypt.CryptProtectData(raw, "SugarAgent ChatGPT", None, None, None, 1)
            raw = json.dumps({"protection": "windows-dpapi", "data": base64.b64encode(encrypted).decode("ascii")}).encode()
        fd, filename = tempfile.mkstemp(prefix=".credentials-", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as target:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
            os.replace(filename, self.path)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
