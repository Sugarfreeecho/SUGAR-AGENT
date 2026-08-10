from __future__ import annotations


def _config(**overrides):
    from cpu_pressure import CpuPressureConfig

    values = {
        "enabled": True,
        "high_percent": 85.0,
        "recovery_percent": 65.0,
        "sample_seconds": 1.0,
        "enter_samples": 3,
        "recovery_seconds": 10.0,
        "tool_concurrency": 2,
    }
    values.update(overrides)
    return CpuPressureConfig(**values)


def test_sustained_pressure_degrades_and_stable_recovery_restores_streaming():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(_config(), sampler=lambda: 0.0, clock=lambda: 0.0)

    assert monitor.observe(90.0, now=1.0).degraded is False
    assert monitor.observe(88.0, now=2.0).degraded is False
    entered = monitor.observe(86.0, now=3.0)
    assert entered.degraded is True
    assert entered.reason == "cpu_pressure"

    assert monitor.observe(64.0, now=4.0).degraded is True
    assert monitor.observe(60.0, now=13.9).degraded is True
    recovered = monitor.observe(65.0, now=14.0)
    assert recovered.degraded is False
    assert recovered.mode == "normal"


def test_spikes_and_incomplete_recovery_do_not_flap_mode():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(_config(), sampler=lambda: 0.0, clock=lambda: 0.0)
    monitor.observe(95.0, now=1.0)
    monitor.observe(40.0, now=2.0)
    monitor.observe(95.0, now=3.0)
    assert monitor.snapshot().degraded is False

    monitor.observe(95.0, now=4.0)
    assert monitor.observe(95.0, now=5.0).degraded is True
    monitor.observe(50.0, now=6.0)
    monitor.observe(70.0, now=10.0)
    assert monitor.observe(50.0, now=20.0).degraded is True


def test_pressure_caps_tool_parallelism_only_while_degraded():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(
        _config(enter_samples=1, recovery_seconds=0.0, tool_concurrency=2),
        sampler=lambda: 0.0,
        clock=lambda: 0.0,
    )
    assert monitor.tool_parallelism(10) == 10
    monitor.observe(99.0, now=1.0)
    assert monitor.tool_parallelism(10) == 2
    monitor.observe(10.0, now=2.0)
    assert monitor.tool_parallelism(10) == 10


def test_process_monitor_reads_env_lazily(monkeypatch):
    import cpu_pressure

    monkeypatch.setattr(cpu_pressure, "_monitor", None)
    monkeypatch.setenv("CPU_PRESSURE_HIGH_PERCENT", "91")
    monkeypatch.setenv("CPU_PRESSURE_RECOVERY_PERCENT", "55")
    monitor = cpu_pressure._get_monitor()
    assert monitor.config.high_percent == 91.0
    assert monitor.config.recovery_percent == 55.0


def test_llm_policy_uses_non_stream_mode_during_cpu_pressure(monkeypatch):
    import agent_loop
    from cpu_pressure import CpuPressureSnapshot

    emit = lambda _event: None
    normal = CpuPressureSnapshot(False, "normal", 30.0, 1.0)
    degraded = CpuPressureSnapshot(True, "degraded", 92.0, 2.0, "cpu_pressure")

    monkeypatch.setattr(agent_loop, "EXECUTOR_STREAM", True)
    monkeypatch.setattr(agent_loop.cpu_pressure, "snapshot", lambda: normal)
    assert agent_loop._llm_runtime_policy(emit)["output_mode"] == "stream"

    monkeypatch.setattr(agent_loop.cpu_pressure, "snapshot", lambda: degraded)
    policy = agent_loop._llm_runtime_policy(emit)
    assert policy["use_stream"] is False
    assert policy["output_mode"] == "non_stream"
    assert policy["reason"] == "cpu_pressure"

    monkeypatch.setattr(agent_loop.cpu_pressure, "snapshot", lambda: normal)
    assert agent_loop._llm_runtime_policy(emit)["output_mode"] == "stream"


def test_manual_non_stream_setting_is_not_overridden_by_recovery(monkeypatch):
    import agent_loop
    from cpu_pressure import CpuPressureSnapshot

    monkeypatch.setattr(agent_loop, "EXECUTOR_STREAM", False)
    monkeypatch.setattr(
        agent_loop.cpu_pressure,
        "snapshot",
        lambda: CpuPressureSnapshot(False, "normal", 20.0, 1.0),
    )
    policy = agent_loop._llm_runtime_policy(lambda _event: None)
    assert policy["use_stream"] is False
    assert policy["reason"] == "stream_disabled"


def test_internal_streaming_completion_uses_one_non_stream_callback_under_pressure(monkeypatch):
    import agent_harness
    from cpu_pressure import CpuPressureSnapshot

    monkeypatch.setattr(
        agent_harness.cpu_pressure,
        "snapshot",
        lambda: CpuPressureSnapshot(True, "degraded", 95.0, 1.0, "cpu_pressure"),
    )
    monkeypatch.setattr(
        agent_harness,
        "executor_chat_complete",
        lambda messages, session_id="": "whole response",
    )
    pieces = []
    result = agent_harness.executor_chat_complete_stream(
        [{"role": "user", "content": "summarize"}],
        on_content_delta=pieces.append,
        session_id="s1",
    )
    assert result == "whole response"
    assert pieces == ["whole response"]
