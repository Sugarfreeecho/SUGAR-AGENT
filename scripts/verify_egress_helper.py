#!/usr/bin/env python3
"""Self-test the bundled helper with a real outbound socket attempt."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from security.egress_guard import prepare_egress_launch, sandbox_health
from security.models import (
    CapabilityRequest,
    DecisionOutcome,
    PERMISSION_PRESETS,
    PermissionMode,
    SecurityDecision,
)


def main() -> int:
    health = sandbox_health(refresh=True)
    print(f"health={health.level} backend={health.backend} reason={health.reason}")
    if not health.available:
        return 2
    command_text = "socket egress self-test"
    child = [
        sys.executable,
        "-c",
        "import socket; socket.create_connection(('1.1.1.1', 443), 3); print('UNEXPECTED_CONNECTION')",
    ]
    request = CapabilityRequest.create(
        action="process.exec",
        resource=command_text,
        effect="workspace_write",
        arguments={"command": command_text},
        metadata={"egress_intent": "none", "destinations": []},
    )
    decision = SecurityDecision(DecisionOutcome.ALLOW, "self-test", "helper.self_test", request.digest(4))
    active = {
        "session_id": "egress-helper-self-test",
        "context": PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL],
        "request": request,
        "decision": decision,
        "workspace": ROOT,
    }
    prepared = prepare_egress_launch(child, os.environ, command=command_text, active_context=active)
    result = subprocess.run(prepared.argv, env=prepared.env, capture_output=True, text=True, timeout=15)
    combined = (result.stdout + result.stderr).strip()
    if "UNEXPECTED_CONNECTION" in combined or result.returncode == 0:
        print("FAIL: isolated child reached the network")
        return 1
    print(f"PASS: isolated child network attempt was blocked (exit={result.returncode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
