from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class _Completions:
    def __init__(self, calls, name, *, result=None, error=None):
        self._calls = calls
        self._name = name
        self._result = result
        self._error = error

    def create(self, **_kwargs):
        self._calls.append(self._name)
        if self._error is not None:
            raise self._error
        return self._result


class _Client:
    def __init__(self, completions):
        self.chat = type("_Chat", (), {"completions": completions})()


def _candidate(name, completions):
    return {
        "model": name,
        "client": _Client(completions),
        "max_output_tokens": 100,
        "temperature": 0,
    }


def test_offline_machine_sleeps_before_switching_models(monkeypatch):
    import agent_harness

    calls = []
    primary = _Completions(calls, "primary", error=ConnectionError("connect failed"))
    backup = _Completions(calls, "backup", result={"ok": True})
    statuses = []
    completions = agent_harness._FallbackCompletions(
        [_candidate("primary", primary), _candidate("backup", backup)],
        statuses.append,
    )
    monkeypatch.setattr(agent_harness, "machine_network_available", lambda: False)

    with pytest.raises(agent_harness.LocalNetworkUnavailableError):
        completions.create(messages=[], max_tokens=10)

    assert calls == ["primary"]
    assert statuses == []


def test_provider_connect_error_uses_backup_when_machine_is_online(monkeypatch):
    import agent_harness

    calls = []
    primary = _Completions(calls, "primary", error=ConnectionError("provider connect failed"))
    backup = _Completions(calls, "backup", result={"ok": True})
    statuses = []
    completions = agent_harness._FallbackCompletions(
        [_candidate("primary", primary), _candidate("backup", backup)],
        statuses.append,
    )
    monkeypatch.setattr(agent_harness, "machine_network_available", lambda: True)

    result = completions.create(messages=[], max_tokens=10)

    assert result == {"ok": True}
    assert calls == ["primary", "backup"]
    assert len(statuses) == 1
    assert statuses[0]["model_switch"] is True
    assert statuses[0]["network_error"] is True


def test_non_windows_network_probe_is_conservative(monkeypatch):
    import agent_harness

    monkeypatch.setattr(agent_harness.os, "name", "posix")
    assert agent_harness.machine_network_available() is True
