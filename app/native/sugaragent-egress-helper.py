#!/usr/bin/env python3
"""SugarAgent egress launcher.

This executable is deliberately dependency-free so it can be installed next to
the application.  Linux and macOS use operating-system process sandboxes for a
deny-network ticket.  Network-bearing tickets are launched normally because
the stock OS tools cannot safely express a per-process destination allow-list;
health therefore reports ``partial`` rather than pretending this is strong
target-scoped isolation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROTOCOL_VERSION = 1
SESSION_KEY_ENV = "SUGAR_AGENT_EGRESS_SESSION_KEY"
COMMAND_DIGEST_ENV = "SUGAR_AGENT_EGRESS_COMMAND_DIGEST"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _decode_ticket(raw: str) -> dict:
    try:
        padded = raw + "=" * (-len(raw) % 4)
        envelope = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        payload = envelope["payload"]
        signature = str(envelope["signature"])
        key = base64.urlsafe_b64decode(os.environ[SESSION_KEY_ENV].encode("ascii"))
    except Exception as exc:
        raise ValueError("invalid ticket envelope") from exc
    expected = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("ticket signature mismatch")
    if int(payload.get("version") or 0) != PROTOCOL_VERSION:
        raise ValueError("unsupported ticket protocol")
    now = int(time.time())
    if now < int(payload.get("issued_at") or 0) - 30 or now > int(payload.get("expires_at") or 0):
        raise ValueError("ticket expired or not active")
    command_digest = str(os.environ.get(COMMAND_DIGEST_ENV) or "")
    if not command_digest or not hmac.compare_digest(str(payload.get("command_digest") or ""), command_digest):
        raise ValueError("command digest mismatch")
    if not str(payload.get("ticket_id") or "") or not str(payload.get("nonce") or ""):
        raise ValueError("ticket identity is missing")
    return payload


def _claim_nonce(payload: dict) -> None:
    nonce = str(payload["nonce"])
    session = str(payload.get("session_id") or "anonymous")
    root = Path(tempfile.gettempdir()) / "sugaragent-egress-nonces" / hashlib.sha256(session.encode()).hexdigest()[:24]
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in root.glob("*.used"):
        try:
            if now - old.stat().st_mtime > 600:
                old.unlink()
        except OSError:
            pass
    marker = root / (hashlib.sha256(nonce.encode()).hexdigest() + ".used")
    try:
        fd = os.open(str(marker), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("ticket nonce was already used") from exc
    with os.fdopen(fd, "w", encoding="ascii") as stream:
        stream.write(str(payload.get("expires_at") or ""))


def _backend() -> tuple[str, str, list[str], str]:
    if sys.platform.startswith("linux"):
        unshare = shutil.which("unshare")
        if not unshare:
            return "degraded", "application-policy", [], "unshare is not installed"
        probe = subprocess.run(
            [unshare, "--user", "--map-root-user", "--net", "--", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        if probe.returncode != 0:
            return "degraded", "application-policy", [], "unprivileged user/network namespaces are unavailable"
        return "partial", "linux-network-namespace", ["deny-network", "process-tree", "ipv4", "ipv6", "dns"], "Approved network commands are not destination-limited"
    if sys.platform == "darwin":
        sandbox = shutil.which("sandbox-exec")
        if not sandbox:
            return "degraded", "application-policy", [], "sandbox-exec is unavailable; install the signed Network Extension for strong enforcement"
        return "partial", "macos-sandbox-profile", ["deny-network", "process-tree", "ipv4", "ipv6", "dns"], "Approved network commands are not destination-limited"
    if os.name == "nt":
        return "degraded", "application-policy", [], "The signed Windows WFP service is not installed"
    return "degraded", "application-policy", [], "unsupported operating system"


def _health() -> int:
    level, backend, capabilities, reason = _backend()
    print(json.dumps({
        "protocol": PROTOCOL_VERSION,
        "enforcement": level,
        "backend": backend,
        "capabilities": capabilities,
        "reason": reason,
    }, separators=(",", ":")))
    return 0 if level in {"partial", "strong"} else 1


def _launch(args: list[str]) -> int:
    try:
        marker = args.index("--")
        ticket_index = args.index("--ticket")
        ticket = args[ticket_index + 1]
        command = args[marker + 1 :]
        if not command:
            raise ValueError("missing command")
        payload = _decode_ticket(ticket)
        _claim_nonce(payload)
    except (ValueError, IndexError) as exc:
        print(f"egress helper: {exc}", file=sys.stderr)
        return 64

    level, _backend_name, _capabilities, reason = _backend()
    if level not in {"partial", "strong"}:
        print(f"egress helper: enforcement unavailable: {reason}", file=sys.stderr)
        return 69

    child_env = dict(os.environ)
    child_env.pop(SESSION_KEY_ENV, None)
    child_env.pop(COMMAND_DIGEST_ENV, None)
    network = str(payload.get("network") or "deny")
    if network == "deny" and sys.platform.startswith("linux"):
        command = [shutil.which("unshare") or "unshare", "--user", "--map-root-user", "--net", "--", *command]
    elif network == "deny" and sys.platform == "darwin":
        profile = "(version 1) (allow default) (deny network*)"
        command = [shutil.which("sandbox-exec") or "/usr/bin/sandbox-exec", "-p", profile, *command]

    try:
        return subprocess.call(command, env=child_env)
    except FileNotFoundError:
        print(f"egress helper: executable not found: {command[0]}", file=sys.stderr)
        return 127
    except OSError as exc:
        print(f"egress helper: launch failed: {exc}", file=sys.stderr)
        return 126


def main(argv: list[str]) -> int:
    if argv == ["health", "--json"]:
        return _health()
    if argv and argv[0] == "launch":
        return _launch(argv[1:])
    print("usage: sugaragent-egress-helper health --json | launch --ticket TICKET -- command ...", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
