"""Synchronous CLI transport with no backend imports or implicit service launch."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .errors import ControlError


def base_url(explicit=None):
    value = explicit or os.getenv("MYAGENT_SESSION_BASE_URL") or "http://127.0.0.1:" + os.getenv("MYAGENT_SERVER_PORT", "8192")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ControlError("invalid_url", "base-url must be an HTTP(S) origin without embedded credentials")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ControlError("invalid_url", "Non-loopback connections require HTTPS")
    return value.rstrip("/")


def credential_path(url):
    root = os.getenv("MYAGENT_SESSION_CREDENTIAL_DIR")
    if not root:
        if os.name == "nt":
            root = str(Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "SugarAgent" / "session-control")
        else:
            root = str(Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "sugaragent" / "session-control")
    return Path(root) / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")


def save_credentials(url, value):
    path = credential_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="credential-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False)
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class ControlClient:
    def __init__(self, url, *, transport=None):
        self.url = base_url(url)
        self.path = credential_path(self.url)
        # A host-issued execution token always wins over personal credentials.
        self.token = os.getenv("MYAGENT_CONTROL_TOKEN", "")
        if not self.token and not os.getenv("MYAGENT_CONTROL_TASK"):
            try:
                self.token = json.loads(self.path.read_text(encoding="utf-8"))["token"]
            except FileNotFoundError:
                pass
            except (ValueError, KeyError, TypeError) as exc:
                raise ControlError("unauthorized", "Stored credential is invalid; run auth login", status=401) from exc
        self.http = httpx.Client(base_url=self.url, timeout=httpx.Timeout(30, read=310), trust_env=False,
                                 follow_redirects=False, transport=transport)

    def close(self):
        self.http.close()

    def headers(self):
        if not self.token:
            raise ControlError("unauthorized", "Run auth login or supply a host-issued MYAGENT_CONTROL_TOKEN", status=401)
        return {"Authorization": "Bearer " + self.token}

    @staticmethod
    def decode(response):
        try:
            value = response.json()
        except ValueError as exc:
            raise ControlError("backend_protocol_error", "Backend did not return control protocol JSON", status=502) from exc
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ControlError("backend_protocol_error", "Unsupported control protocol response", status=502)
        if not value.get("ok"):
            error = value.get("error") or {}
            raise ControlError(error.get("code", "request_failed"), error.get("message", "Request failed"), status=response.status_code, details=error.get("details"))
        return value

    def rpc(self, method, params=None, *, key=None, request_id=None):
        try:
            response = self.http.post("/api/control/v1/rpc", headers=self.headers(), json={
                "request_id": request_id or str(uuid.uuid4()), "method": method, "params": params or {},
                "idempotency_key": key or str(uuid.uuid4())})
            return self.decode(response)
        except httpx.HTTPError as exc:
            raise ControlError("backend_unavailable", "Cannot reach the SugarAgent backend", status=503) from exc

    def login(self, payload):
        if os.getenv("MYAGENT_CONTROL_TASK") or os.getenv("MYAGENT_CONTROL_TOKEN"):
            raise ControlError("forbidden", "Task processes cannot replace their host-issued identity", status=403)
        try:
            value = self.decode(self.http.post("/api/control/v1/auth/claim", json=payload))["data"]
        except httpx.HTTPError as exc:
            raise ControlError("backend_unavailable", "Cannot reach the SugarAgent backend", status=503) from exc
        save_credentials(self.url, value)
        self.token = value["token"]
        return {"authenticated": True, "principal": value["principal"]}

    def logout(self):
        try:
            value = self.decode(self.http.post("/api/control/v1/auth/logout", headers=self.headers()))
        except httpx.HTTPError as exc:
            raise ControlError("backend_unavailable", "Cannot reach the SugarAgent backend", status=503) from exc
        if not os.getenv("MYAGENT_CONTROL_TASK") and self.path.exists():
            self.path.unlink()
        self.token = ""
        return value

    def export_archive(self, operation_id, destination):
        path = Path(destination).expanduser().resolve()
        if path.exists():
            raise ControlError("output_exists", "Output file already exists", status=409)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="session-export-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle, self.http.stream("GET", "/api/control/v1/archives/" + operation_id, headers=self.headers()) as response:
                if response.status_code != 200:
                    response.read()
                    self.decode(response)
                for chunk in response.iter_bytes():
                    handle.write(chunk)
            os.replace(temporary, path)
            return str(path)
        except httpx.HTTPError as exc:
            raise ControlError("backend_unavailable", "Archive download interrupted; retry using the export operation ID", status=503, details={"operation_id": operation_id}) from exc
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def import_archive(self, source, *, key=None):
        path = Path(source).expanduser()
        if not path.is_file():
            raise ControlError("invalid_arguments", "--archive requires a local archive file")
        try:
            def chunks():
                with path.open("rb") as handle:
                    while chunk := handle.read(65536):
                        yield chunk
            response = self.http.post("/api/control/v1/archives", content=chunks(), headers={**self.headers(),
                "Content-Type": "application/zip", "Idempotency-Key": key or str(uuid.uuid4())})
            return self.decode(response)
        except httpx.HTTPError as exc:
            raise ControlError("backend_unavailable", "Archive upload interrupted; retry with the same idempotency key", status=503) from exc

    def follow(self, sid, *, cursor=None, generation=None):
        params = {"session_id": sid}
        if cursor is not None:
            params["cursor"] = cursor
        if generation:
            params["generation"] = generation
        try:
            with self.http.stream("GET", "/api/control/v1/events", params=params, headers=self.headers()) as response:
                if response.status_code != 200:
                    response.read()
                    self.decode(response)
                for line in response.iter_lines():
                    if line:
                        yield json.loads(line)
        except httpx.HTTPError as exc:
            raise ControlError("backend_unavailable", "Event connection interrupted; reconnect with its cursor", status=503) from exc
