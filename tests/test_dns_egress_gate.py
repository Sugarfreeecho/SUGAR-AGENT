"""本机 DNS 故障必须暂停候选链，而不是把整条链打到死解析器上。

现场（2026-11-08 22:44）::

    getaddrinfo failed -> Connection error. x3 -> 四个候选全灭
    -> NET 错误卡 -> 5 次快速重连

WinINet 与 TCP 直连探测都报"在线"，因为 DNS 属于独立的一层；旧逻辑于是
把解析失败当成端点抖动，同模型重试后逐跳切换。这里锁定修复后的判定：
环境级解析故障 -> LocalDnsUnavailableError（沉睡等待）；仅单域名故障 ->
跳过同模型重试直接换候选。
"""

from __future__ import annotations

import asyncio
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


def _candidate(name, completions, host=""):
    return {
        "model": name,
        "host": host,
        "client": _Client(completions),
        "max_output_tokens": 100,
        "temperature": 0,
    }


def _reset_dns_cache(agent_harness) -> None:
    agent_harness._DNS_PROBE_CACHE.clear()


def test_dead_resolver_pauses_chain_instead_of_switching(monkeypatch):
    import agent_harness

    calls = []
    primary = _Completions(
        calls,
        "primary",
        error=ConnectionError("[Errno 11001] getaddrinfo failed"),
    )
    backup = _Completions(calls, "backup", result={"ok": True})
    completions = agent_harness._FallbackCompletions(
        [
            _candidate("primary", primary, host="api.commandcode.ai"),
            _candidate("backup", backup, host="api.deepseek.com"),
        ],
        [].append,
    )
    monkeypatch.setattr(agent_harness, "machine_network_available", lambda: True)
    monkeypatch.setattr(
        agent_harness, "local_dns_available", lambda **_kwargs: False
    )
    monkeypatch.setattr(
        agent_harness,
        "_resolve_host_cached",
        lambda host, timeout, **_kwargs: False,
    )

    with pytest.raises(agent_harness.LocalDnsUnavailableError):
        completions.create(messages=[], max_tokens=10)

    # 关键：一次调用后立刻停手，绝不挨个候选重试
    assert calls == ["primary"]


def test_single_host_dns_failure_skips_retries_and_switches(monkeypatch):
    import agent_harness

    calls = []
    primary = _Completions(
        calls,
        "primary",
        error=ConnectionError("[Errno 11001] getaddrinfo failed"),
    )
    backup = _Completions(calls, "backup", result={"ok": True})
    statuses = []
    completions = agent_harness._FallbackCompletions(
        [
            _candidate("primary", primary, host="broken.example.invalid"),
            _candidate("backup", backup, host="api.deepseek.com"),
        ],
        statuses.append,
    )
    monkeypatch.setattr(agent_harness, "machine_network_available", lambda: True)
    monkeypatch.setattr(agent_harness, "local_dns_available", lambda **_kwargs: True)
    monkeypatch.setattr(
        agent_harness,
        "_resolve_host_cached",
        lambda host, timeout, **_kwargs: host == "api.deepseek.com",
    )

    result = completions.create(messages=[], max_tokens=10)

    assert result == {"ok": True}
    # 该域名解析失败，本机 DNS 正常 —— 直接换候选，不浪费同模型重试
    assert calls == ["primary", "backup"]
    assert not [s for s in statuses if s.get("alert_id") == "LLM-RETRY"]


def test_generic_connect_error_with_unresolvable_host_switches_immediately(monkeypatch):
    import agent_harness

    calls = []
    primary = _Completions(calls, "primary", error=ConnectionError("Connection error."))
    backup = _Completions(calls, "backup", result={"ok": True})
    completions = agent_harness._FallbackCompletions(
        [
            _candidate("primary", primary, host="vanished.example.invalid"),
            _candidate("backup", backup, host="api.deepseek.com"),
        ],
        [].append,
    )
    monkeypatch.setattr(agent_harness, "machine_network_available", lambda: True)
    monkeypatch.setattr(agent_harness, "local_dns_available", lambda **_kwargs: True)
    monkeypatch.setattr(
        agent_harness,
        "_resolve_host_cached",
        lambda host, timeout, **_kwargs: host == "api.deepseek.com",
    )
    monkeypatch.setenv("LLM_CANDIDATE_RETRY_ATTEMPTS", "10")
    monkeypatch.setenv("LLM_CANDIDATE_RETRY_BACKOFF_SEC", "0")

    result = completions.create(messages=[], max_tokens=10)

    assert result == {"ok": True}
    assert calls == ["primary", "backup"]


def test_loopback_candidates_never_probe_dns(monkeypatch):
    import agent_harness

    calls = []
    primary = _Completions(calls, "primary", error=ConnectionError("connect failed"))
    backup = _Completions(calls, "backup", result={"ok": True})
    completions = agent_harness._FallbackCompletions(
        [
            _candidate("primary", primary, host="127.0.0.1"),
            _candidate("backup", backup, host="localhost"),
        ],
        [].append,
    )

    def _explode(*_args, **_kwargs):
        raise AssertionError("loopback endpoints must not trigger DNS probing")

    monkeypatch.setattr(agent_harness, "machine_network_available", lambda: True)
    monkeypatch.setattr(agent_harness, "local_dns_available", _explode)
    monkeypatch.setattr(agent_harness, "_resolve_host_cached", _explode)
    monkeypatch.setenv("LLM_CANDIDATE_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("LLM_CANDIDATE_RETRY_BACKOFF_SEC", "0")

    result = completions.create(messages=[], max_tokens=10)

    assert result == {"ok": True}
    assert calls == ["primary", "primary", "backup"]


def test_is_dns_resolution_error_reads_the_cause_chain():
    import agent_harness

    wrapped = ConnectionError("Connection error.")
    wrapped.__cause__ = OSError(11001, "getaddrinfo failed")
    assert agent_harness.is_dns_resolution_error(wrapped) is True
    assert agent_harness.is_dns_resolution_error(ConnectionError("connect failed")) is False
    assert agent_harness.is_dns_resolution_error(RuntimeError("502 bad gateway")) is False


def test_local_dns_available_accepts_any_probe_host(monkeypatch):
    import agent_harness

    _reset_dns_cache(agent_harness)
    monkeypatch.setenv("LOCAL_DNS_PROBE_HOSTS", "dead.test,live.test")
    monkeypatch.setenv("LOCAL_DNS_PROBE_TIMEOUT_SEC", "0.2")

    def _getaddrinfo(host, *_args, **_kwargs):
        if host == "dead.test":
            raise OSError(11001, "getaddrinfo failed")
        return [(0, 0, 0, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(agent_harness.socket, "getaddrinfo", _getaddrinfo)

    assert agent_harness.local_dns_available() is True

    monkeypatch.setattr(
        agent_harness.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(11001, "getaddrinfo failed")),
    )
    _reset_dns_cache(agent_harness)
    assert agent_harness.local_dns_available() is False


def test_sleep_wait_requires_dns_before_resuming(monkeypatch):
    import agent_loop

    dns_states = iter([False, True])
    events = []

    monkeypatch.setattr(agent_loop, "machine_network_available", lambda: True)
    monkeypatch.setattr(agent_loop, "local_dns_available", lambda **_kwargs: next(dns_states))
    monkeypatch.setattr(
        agent_loop.session_manager,
        "is_interrupt_requested",
        lambda _sid, _run_id="": False,
    )

    async def no_steer(*_args, **_kwargs):
        return None

    async def no_delay(*_args, **_kwargs):
        return True

    async def emit(event):
        events.append(event)

    monkeypatch.setattr(agent_loop, "_raise_if_steer_requested", no_steer)
    monkeypatch.setattr(agent_loop, "_await_retry_delay_or_interrupt", no_delay)
    state = {"session_id": "dns-outage", "stream_events": []}

    recovered = asyncio.run(
        agent_loop._wait_for_local_network_recovery(
            state, emit, poll_seconds=0.01, require_dns=True
        )
    )

    assert recovered is True
    assert state["_runtime_stage"] == "react"
    assert events[-1]["network_recovered"] is True
    assert events[-1]["dns_unavailable"] is False


def test_profile_candidate_carries_endpoint_host():
    import agent_harness

    assert (
        agent_harness._profile_request_host({"base_url": "https://api.commandcode.ai/provider/v1"})
        == "api.commandcode.ai"
    )
    assert agent_harness._profile_request_host({"base_url": "http://127.0.0.1:8787/v1"}) == "127.0.0.1"
    assert agent_harness._profile_request_host({"base_url": ""}) == ""
