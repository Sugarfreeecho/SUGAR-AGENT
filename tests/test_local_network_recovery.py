from __future__ import annotations

import asyncio
import inspect
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
    # 连接抖动先同模型重试（默认 10 次太慢，压到 1 次验证重试→切换次序）
    monkeypatch.setenv("LLM_CANDIDATE_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("LLM_CANDIDATE_RETRY_BACKOFF_SEC", "0")

    result = completions.create(messages=[], max_tokens=10)

    assert result == {"ok": True}
    assert calls == ["primary", "primary", "backup"]
    assert len(statuses) == 1
    assert statuses[0]["model_switch"] is True
    assert statuses[0]["network_error"] is True


def test_offline_machine_still_uses_backup_for_non_network_errors(monkeypatch):
    import agent_harness

    calls = []
    primary = _Completions(calls, "primary", error=ValueError("invalid provider response"))
    backup = _Completions(calls, "backup", result={"ok": True})
    statuses = []
    completions = agent_harness._FallbackCompletions(
        [_candidate("primary", primary), _candidate("backup", backup)],
        statuses.append,
    )
    monkeypatch.setattr(agent_harness, "machine_network_available", lambda: False)

    result = completions.create(messages=[], max_tokens=10)

    assert result == {"ok": True}
    assert calls == ["primary", "backup"]
    assert len(statuses) == 1
    assert statuses[0]["model_switch"] is True
    assert statuses[0]["network_error"] is False


def test_non_windows_network_probe_is_conservative(monkeypatch):
    import agent_harness

    monkeypatch.setattr(agent_harness.os, "name", "posix")
    assert agent_harness.machine_network_available() is True


@pytest.mark.parametrize(("probe_result", "expected"), [(True, True), (False, False)])
def test_windows_offline_hint_is_confirmed_by_active_probe(
    monkeypatch, probe_result, expected
):
    import agent_harness

    class _Wininet:
        @staticmethod
        def InternetGetConnectedState(_flags, _reserved):
            return 0

    class _Windll:
        wininet = _Wininet()

    monkeypatch.setattr(agent_harness.os, "name", "nt")
    monkeypatch.setattr(agent_harness.ctypes, "windll", _Windll())
    monkeypatch.setattr(
        agent_harness,
        "_probe_network_connectivity",
        lambda: probe_result,
    )

    assert agent_harness.machine_network_available() is expected


def test_network_probe_uses_configured_targets(monkeypatch):
    import agent_harness

    calls = []

    class _Connection:
        def close(self):
            calls.append("closed")

    def connect(endpoint, timeout):
        calls.append((endpoint, timeout))
        if endpoint[0] == "unreachable.test":
            raise OSError("unreachable")
        return _Connection()

    monkeypatch.setenv(
        "LOCAL_NETWORK_PROBE_TARGETS",
        "unreachable.test:443,reachable.test:8443",
    )
    monkeypatch.setattr(agent_harness.socket, "create_connection", connect)

    assert agent_harness._probe_network_connectivity(timeout=0.2) is True
    assert calls == [
        (("unreachable.test", 443), 0.2),
        (("reachable.test", 8443), 0.2),
        "closed",
    ]


def test_local_network_sleep_resumes_without_probing_a_provider(monkeypatch):
    import agent_loop

    availability = iter([False, True])
    events = []

    monkeypatch.setattr(agent_loop, "machine_network_available", lambda: next(availability))
    monkeypatch.setattr(agent_loop.session_manager, "is_interrupt_requested", lambda _sid: False)

    async def no_steer(*_args, **_kwargs):
        return None

    async def no_delay(*_args, **_kwargs):
        return True

    async def emit(event):
        events.append(event)

    monkeypatch.setattr(agent_loop, "_raise_if_steer_requested", no_steer)
    monkeypatch.setattr(agent_loop, "_await_retry_delay_or_interrupt", no_delay)
    state = {"session_id": "offline", "stream_events": []}

    recovered = asyncio.run(
        agent_loop._wait_for_local_network_recovery(state, emit, poll_seconds=0.01)
    )

    assert recovered is True
    assert state["_runtime_stage"] == "react"
    assert any(event.get("local_network_offline") for event in events)
    assert events[-1]["network_recovered"] is True


def test_online_provider_failure_never_enters_an_unbounded_endpoint_wait():
    import agent_loop

    source = inspect.getsource(agent_loop)
    react_source = inspect.getsource(agent_loop._react_node_once)
    network_branch = react_source.split('if _cls.get("code") == "NET":', 1)[1].split(
        "import json as _json", 1
    )[0]

    assert "_executor_endpoint_reachable" not in source
    assert "_wait_for_network_recovery" not in source
    assert network_branch.count("_wait_for_local_network_recovery(") == 1
    assert network_branch.index("if local_network_offline:") < network_branch.index(
        "_wait_for_local_network_recovery("
    )
    assert "if attempt <= NETWORK_RECONNECT_MAX_ATTEMPTS:" in network_branch
    webui_source = (APP_DIR / "webui.py").read_text(encoding="utf-8")
    assert "本机离线时等待网络恢复，其他错误达到上限后进入常规模型回退" in webui_source
