from pathlib import Path
import json
import subprocess

from security.egress_guard import egress_helper_enabled, prepare_egress_launch, sandbox_health
from security.models import (
    CapabilityRequest,
    DecisionOutcome,
    PERMISSION_PRESETS,
    PermissionMode,
    SecurityDecision,
)


def _active(mode=PermissionMode.ASK_FOR_APPROVAL, intent="none"):
    request = CapabilityRequest.create(
        action="process.exec",
        resource="echo ok",
        effect="workspace_write",
        arguments={"command": "echo ok"},
        metadata={"egress_intent": intent, "destinations": []},
    )
    decision = SecurityDecision(
        DecisionOutcome.ALLOW,
        "allowed",
        "test",
        request.digest(4),
    )
    return {
        "session_id": "session",
        "context": PERMISSION_PRESETS[mode],
        "request": request,
        "decision": decision,
        "workspace": Path.cwd(),
    }


def test_missing_helper_is_explicit_degraded(monkeypatch):
    monkeypatch.setenv("SUGAR_AGENT_EGRESS_HELPER", "definitely-missing-egress-helper")
    health = sandbox_health(refresh=True)
    assert health.available is False
    assert health.level == "degraded"
    prepared = prepare_egress_launch(
        ["echo", "ok"],
        {},
        command="echo ok",
        active_context=_active(),
    )
    assert prepared.argv == ("echo", "ok")
    assert prepared.enforcement_level == "degraded"
    assert prepared.env["SUGAR_AGENT_EGRESS_INTENT"] == "none"


def test_full_access_bypasses_helper(monkeypatch):
    monkeypatch.setenv("SUGAR_AGENT_EGRESS_HELPER", "definitely-missing-egress-helper")
    prepared = prepare_egress_launch(
        ["echo", "ok"],
        {},
        command="echo ok",
        active_context=_active(PermissionMode.FULL_ACCESS),
    )
    assert prepared.enforcement_level == "disabled"
    assert prepared.argv == ("echo", "ok")


def test_helper_switch_disables_discovery_and_wrapping(monkeypatch):
    monkeypatch.setenv("EGRESS_HELPER_ENABLED", "0")
    assert egress_helper_enabled() is False
    health = sandbox_health(refresh=True)
    assert health.level == "disabled"
    prepared = prepare_egress_launch(
        ["echo", "ok"],
        {},
        command="echo ok",
        active_context=_active(intent="none"),
    )
    assert prepared.argv == ("echo", "ok")
    assert prepared.enforcement_level == "disabled"
    assert "SUGAR_AGENT_EGRESS_SESSION_KEY" not in prepared.env


def test_partial_helper_is_accepted_and_reports_actual_level(monkeypatch):
    import security.egress_guard as guard

    monkeypatch.setattr(guard, "_helper_path", lambda: "native-helper")
    monkeypatch.setattr(
        guard,
        "sandbox_health",
        lambda refresh=False: guard.SandboxHealth(
            "partial", "test-native", True, "approved connections are broad", ("deny-network",)
        ),
    )
    prepared = guard.prepare_egress_launch(
        ["shell", "-c", "echo ok"],
        {},
        command="echo ok",
        active_context=_active(intent="none"),
    )
    assert prepared.enforcement_level == "partial"
    assert prepared.argv[:3] == ("native-helper", "launch", "--ticket")
    assert "SUGAR_AGENT_EGRESS_COMMAND_DIGEST" in prepared.env


def test_strong_helper_wraps_launch_with_signed_ticket(monkeypatch):
    import security.egress_guard as guard

    monkeypatch.setattr(guard, "_helper_path", lambda: "native-helper")
    monkeypatch.setattr(
        guard,
        "sandbox_health",
        lambda refresh=False: guard.SandboxHealth("strong", "test-native", True, ""),
    )
    prepared = guard.prepare_egress_launch(
        ["shell", "-c", "echo ok"],
        {},
        command="echo ok",
        active_context=_active(intent="read"),
    )
    assert prepared.argv[:3] == ("native-helper", "launch", "--ticket")
    assert prepared.argv[-4:] == ("--", "shell", "-c", "echo ok")
    assert prepared.ticket_id
    assert prepared.enforcement_level == "strong"
    assert "SUGAR_AGENT_EGRESS_SESSION_KEY" in prepared.env


def test_bundled_helper_health_contract_when_available():
    import security.egress_guard as guard

    helper = guard._helper_path()
    assert helper
    proc = subprocess.run(
        [*guard._helper_argv(helper), "health", "--json"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    payload = json.loads(proc.stdout)
    assert payload["protocol"] == 1
    assert payload["enforcement"] in {"strong", "partial", "degraded"}
    assert isinstance(payload.get("capabilities"), list)


def test_bundled_helper_launches_local_command_when_enforcement_available():
    import os

    health = sandbox_health(refresh=True)
    if not health.available:
        import pytest

        pytest.skip(health.reason)
    command = ["cmd.exe", "/d", "/c", "echo", "helper-launch-ok"] if os.name == "nt" else ["sh", "-c", "printf helper-launch-ok"]
    prepared = prepare_egress_launch(command, os.environ, command="echo helper-launch-ok", active_context=_active(intent="none"))
    proc = subprocess.run(prepared.argv, env=prepared.env, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "helper-launch-ok" in proc.stdout


def test_bundled_helper_rejects_ticket_reuse_when_enforcement_available(tmp_path):
    import os

    health = sandbox_health(refresh=True)
    if not health.available:
        import pytest

        pytest.skip(health.reason)
    command = ["cmd.exe", "/d", "/c", "echo", "nonce-ok"] if os.name == "nt" else ["sh", "-c", "printf nonce-ok"]
    active = _active(intent="read")
    active["session_id"] = "nonce-" + tmp_path.name
    prepared = prepare_egress_launch(command, os.environ, command="echo nonce-ok", active_context=active)
    first = subprocess.run(prepared.argv, env=prepared.env, capture_output=True, timeout=15)
    second = subprocess.run(prepared.argv, env=prepared.env, capture_output=True, timeout=15)
    assert first.returncode == 0, first.stderr.decode("utf-8", "replace")
    assert second.returncode != 0
    assert "already used" in second.stderr.decode("utf-8", "replace")


def test_windows_bundled_helper_launches_powershell_backend():
    import os
    if os.name != "nt":
        import pytest
        pytest.skip("Windows-only integration")
    from agent_tools import _windows_powershell_executable

    powershell = _windows_powershell_executable()
    assert powershell
    prepared = prepare_egress_launch(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", "Write-Output actual-shell-ok"],
        os.environ,
        command="printf actual-shell-ok",
        active_context=_active(intent="none"),
    )
    proc = subprocess.run(prepared.argv, env=prepared.env, capture_output=True, timeout=15)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert b"actual-shell-ok" in proc.stdout


def test_windows_helper_switch_selects_appcontainer_compatible_shell(monkeypatch):
    import os
    if os.name != "nt":
        import pytest
        pytest.skip("Windows-only shell selection")
    import agent_tools

    monkeypatch.setattr(agent_tools, "_windows_bash_executable", lambda: r"D:\\Git\\bin\\bash.exe")
    monkeypatch.setenv("EGRESS_HELPER_ENABLED", "1")
    assert agent_tools._run_cli_should_use_bash_on_windows() is False
    monkeypatch.setenv("EGRESS_HELPER_ENABLED", "0")
    assert agent_tools._run_cli_should_use_bash_on_windows() is True
