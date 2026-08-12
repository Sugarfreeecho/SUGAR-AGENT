from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import PermissionMode, SandboxHealth


PROTOCOL_VERSION = 1
HELPER_ENV = "SUGAR_AGENT_EGRESS_HELPER"
HELPER_ENABLED_ENV = "EGRESS_HELPER_ENABLED"
_SESSION_KEY = secrets.token_bytes(32)
_HEALTH_LOCK = threading.Lock()
_HEALTH_CACHE: tuple[float, SandboxHealth, str] | None = None


def egress_helper_enabled(source: Mapping[str, str] | None = None) -> bool:
    env = os.environ if source is None else source
    raw = str(env.get(HELPER_ENABLED_ENV, "1") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class PreparedLaunch:
    argv: tuple[str, ...]
    env: dict[str, str]
    health: SandboxHealth
    enforcement_level: str
    ticket_id: str = ""


def _helper_path() -> str:
    configured = str(os.getenv(HELPER_ENV) or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
        return shutil.which(configured) or ""
    name = "sugaragent-egress-helper.exe" if os.name == "nt" else "sugaragent-egress-helper"
    bundled = Path(__file__).resolve().parents[1] / "native" / name
    if bundled.is_file() and (os.name == "nt" or os.access(bundled, os.X_OK)):
        return str(bundled)
    script = bundled.parent / "sugaragent-egress-helper.py"
    return str(script) if script.is_file() else (shutil.which(name) or "")


def _helper_argv(helper: str) -> tuple[str, ...]:
    if helper.lower().endswith(".py"):
        return (os.getenv("SUGAR_AGENT_EGRESS_HELPER_PYTHON") or os.sys.executable, helper)
    return (helper,)


def sandbox_health(*, refresh: bool = False) -> SandboxHealth:
    global _HEALTH_CACHE
    if not egress_helper_enabled():
        return SandboxHealth("disabled", "none", False, "Egress helper is disabled by EGRESS_HELPER_ENABLED=0.")
    helper = _helper_path()
    now = time.monotonic()
    with _HEALTH_LOCK:
        if not refresh and _HEALTH_CACHE and _HEALTH_CACHE[2] == helper and now - _HEALTH_CACHE[0] < 5.0:
            return _HEALTH_CACHE[1]
        if not helper:
            health = SandboxHealth("degraded", "application-policy", False, "Native egress helper is not installed.")
        else:
            try:
                proc = subprocess.run(
                    [*_helper_argv(helper), "health", "--json"], capture_output=True, text=True, timeout=5.0,
                    creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
                )
                payload = json.loads(proc.stdout or "{}")
                enforcement = str(payload.get("enforcement") or "")
                valid = (
                    proc.returncode == 0
                    and int(payload.get("protocol") or 0) == PROTOCOL_VERSION
                    and enforcement in {"strong", "partial"}
                )
                health = SandboxHealth(
                    enforcement if valid else "degraded",
                    str(payload.get("backend") or platform.system().lower() or "native-helper"),
                    valid,
                    str(payload.get("reason") or "").strip() if valid else str(payload.get("reason") or proc.stderr or "Native helper health check failed.").strip(),
                    tuple(str(item) for item in (payload.get("capabilities") or []) if str(item)),
                )
            except Exception as exc:
                health = SandboxHealth("degraded", "application-policy", False, f"Native helper unavailable: {type(exc).__name__}")
        _HEALTH_CACHE = (now, health, helper)
        return health


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _ticket_for(command: str, request: Any, decision: Any, session_id: str) -> tuple[str, str]:
    metadata = dict(getattr(request, "metadata", {}) or {})
    destinations = list(metadata.get("destinations") or [])
    intent = str(metadata.get("egress_intent") or "none")
    payload = {
        "version": PROTOCOL_VERSION,
        "ticket_id": secrets.token_hex(16),
        "session_id": str(session_id or ""),
        "request_digest": str(getattr(decision, "request_digest", "") or ""),
        "command_digest": hashlib.sha256(str(command or "").encode("utf-8")).hexdigest(),
        "network": "deny" if intent == "none" else "allow",
        "intent": intent,
        "destinations": destinations,
        "wildcard": intent in {"unknown", "interactive"} or not destinations,
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + 120,
        "nonce": secrets.token_hex(16),
    }
    envelope = {"payload": payload, "signature": hmac.new(_SESSION_KEY, _canonical(payload), hashlib.sha256).hexdigest()}
    return base64.urlsafe_b64encode(_canonical(envelope)).decode("ascii"), str(payload["ticket_id"])


def prepare_egress_launch(
    argv: Sequence[str], env: Mapping[str, str], *, command: str,
    active_context: Mapping[str, Any] | None,
) -> PreparedLaunch:
    child_env = dict(env)
    if not egress_helper_enabled():
        health = SandboxHealth("disabled", "none", False, "Egress helper is disabled by configuration.")
        return PreparedLaunch(tuple(argv), child_env, health, "disabled")
    if not active_context:
        health = SandboxHealth("disabled", "none", False, "No active security context.")
        return PreparedLaunch(tuple(argv), child_env, health, "disabled")
    context = active_context.get("context")
    if getattr(context, "mode", None) == PermissionMode.FULL_ACCESS:
        health = SandboxHealth("disabled", "none", False, "Full access mode bypasses egress isolation.")
        return PreparedLaunch(tuple(argv), child_env, health, "disabled")
    health = sandbox_health()
    request = active_context.get("request")
    intent = str(getattr(request, "metadata", {}).get("egress_intent") or "none")
    child_env["SUGAR_AGENT_EGRESS_INTENT"] = intent
    child_env["SUGAR_AGENT_EGRESS_ENFORCEMENT"] = health.level
    if not health.available:
        try:
            from .runtime import security_store

            security_store().audit(
                session_id=str(active_context.get("session_id") or ""),
                event_type="egress_enforcement",
                request_digest=str(getattr(active_context.get("decision"), "request_digest", "") or ""),
                outcome="degraded",
                payload={"backend": health.backend, "reason": health.reason, "intent": intent},
            )
        except Exception:
            pass
        return PreparedLaunch(tuple(argv), child_env, health, "degraded")
    ticket, ticket_id = _ticket_for(command, request, active_context.get("decision"), str(active_context.get("session_id") or ""))
    child_env["SUGAR_AGENT_EGRESS_SESSION_KEY"] = base64.urlsafe_b64encode(_SESSION_KEY).decode("ascii")
    child_env["SUGAR_AGENT_EGRESS_COMMAND_DIGEST"] = hashlib.sha256(str(command or "").encode("utf-8")).hexdigest()
    helper = _helper_path()
    return PreparedLaunch(
        (*_helper_argv(helper), "launch", "--ticket", ticket, "--", *tuple(argv)),
        child_env,
        health,
        health.level,
        ticket_id,
    )
