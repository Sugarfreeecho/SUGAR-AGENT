from __future__ import annotations


def _config(**overrides):
    from cpu_pressure import CpuPressureConfig

    values = {
        "enabled": True,
        "busy_percent": 60.0,
        "high_percent": 90.0,
        "composite_percent": 80.0,
        "recovery_percent": 65.0,
        "sample_seconds": 1.0,
        "window_samples": 1,
        "enter_samples": 3,
        "recovery_seconds": 10.0,
        "tool_concurrency": 2,
    }
    values.update(overrides)
    return CpuPressureConfig(**values)


def test_busy_cpu_keeps_streaming_and_sustained_severe_pressure_degrades():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(_config(), sampler=lambda: 0.0, clock=lambda: 0.0)

    assert monitor.observe(74.0, now=1.0).mode == "normal"
    assert monitor.observe(74.0, now=2.0).mode == "normal"
    busy = monitor.observe(74.0, now=3.0)
    assert busy.mode == "busy"
    assert busy.degraded is False
    assert "cpu_busy" in busy.trigger

    monitor.observe(95.0, now=4.0)
    monitor.observe(95.0, now=5.0)
    severe = monitor.observe(95.0, now=6.0)
    assert severe.mode == "severe"
    assert severe.degraded is True
    assert severe.reason == "system_pressure"


def test_slow_tuning_requires_twelve_samples_and_two_minute_recovery():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(
        _config(enter_samples=12, recovery_seconds=120.0),
        sampler=lambda: 0.0,
        clock=lambda: 0.0,
    )
    for now in range(10, 120, 10):
        assert monitor.observe(95.0, now=now).mode == "normal"
    assert monitor.observe(95.0, now=120.0).mode == "severe"

    assert monitor.observe(20.0, now=130.0).mode == "severe"
    assert monitor.observe(20.0, now=249.9).mode == "severe"
    assert monitor.observe(20.0, now=250.0).mode == "normal"


def test_stable_recovery_first_restores_streaming_then_returns_normal():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(
        _config(enter_samples=1, recovery_seconds=10.0),
        sampler=lambda: 0.0,
        clock=lambda: 0.0,
    )
    assert monitor.observe(95.0, now=1.0).mode == "severe"

    assert monitor.observe(74.0, now=2.0).mode == "severe"
    assert monitor.observe(74.0, now=11.9).mode == "severe"
    restored_stream = monitor.observe(74.0, now=12.0)
    assert restored_stream.mode == "busy"
    assert restored_stream.degraded is False

    assert monitor.observe(50.0, now=13.0).mode == "busy"
    returned_normal = monitor.observe(50.0, now=23.0)
    assert returned_normal.mode == "normal"


def test_spikes_and_incomplete_recovery_do_not_flap_mode():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(_config(), sampler=lambda: 0.0, clock=lambda: 0.0)
    monitor.observe(95.0, now=1.0)
    monitor.observe(40.0, now=2.0)
    monitor.observe(95.0, now=3.0)
    assert monitor.snapshot().mode == "normal"

    monitor.observe(95.0, now=4.0)
    assert monitor.observe(95.0, now=5.0).mode == "severe"
    monitor.observe(50.0, now=6.0)
    monitor.observe(95.0, now=10.0)
    assert monitor.observe(50.0, now=20.0).mode == "severe"


def test_composite_cpu_and_event_loop_lag_can_enter_severe_mode():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(_config(), sampler=lambda: 0.0, clock=lambda: 0.0)
    for now in (1.0, 2.0):
        assert monitor.observe(82.0, now=now, event_loop_lag_ms=600.0).degraded is False
    severe = monitor.observe(82.0, now=3.0, event_loop_lag_ms=600.0)
    assert severe.degraded is True
    assert "cpu_and_event_loop" in severe.trigger


def test_memory_pressure_is_part_of_classification():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(
        _config(enter_samples=1), sampler=lambda: 0.0, clock=lambda: 0.0
    )
    busy = monitor.observe(20.0, now=1.0, memory_percent=88.0, available_memory_gb=4.0)
    assert busy.mode == "busy"
    severe = monitor.observe(20.0, now=2.0, memory_percent=94.0, available_memory_gb=0.8)
    assert severe.mode == "severe"
    assert "memory_severe" in severe.trigger


def test_pressure_caps_tool_parallelism_only_while_severe():
    from cpu_pressure import CpuPressureMonitor

    monitor = CpuPressureMonitor(
        _config(enter_samples=1, recovery_seconds=0.0, tool_concurrency=2),
        sampler=lambda: 0.0,
        clock=lambda: 0.0,
    )
    assert monitor.tool_parallelism(10) == 10
    monitor.observe(74.0, now=1.0)
    assert monitor.snapshot().mode == "busy"
    assert monitor.tool_parallelism(10) == 10
    monitor.observe(99.0, now=2.0)
    assert monitor.tool_parallelism(10) == 2
    monitor.observe(10.0, now=3.0)
    assert monitor.tool_parallelism(10) == 10


def test_process_monitor_reads_three_level_env_lazily(monkeypatch):
    import cpu_pressure

    monkeypatch.setattr(cpu_pressure, "_monitor", None)
    monkeypatch.setenv("CPU_PRESSURE_BUSY_PERCENT", "61")
    monkeypatch.setenv("CPU_PRESSURE_SEVERE_PERCENT", "91")
    monkeypatch.setenv("CPU_PRESSURE_RECOVERY_PERCENT", "55")
    # Advanced composite thresholds are intentionally internal defaults now.
    monkeypatch.setenv("CPU_PRESSURE_WINDOW_SAMPLES", "99")
    monkeypatch.setenv("CPU_PRESSURE_LOOP_SEVERE_MS", "9")
    monitor = cpu_pressure._get_monitor()
    assert monitor.config.busy_percent == 61.0
    assert monitor.config.high_percent == 91.0
    assert monitor.config.recovery_percent == 55.0
    assert monitor.config.window_samples == 5
    assert monitor.config.loop_severe_ms == 1000.0
    assert monitor.config.loop_probe_seconds == 10.0
    monitor.stop()
    monkeypatch.setattr(cpu_pressure, "_monitor", None)


def test_llm_policy_keeps_transport_streaming_and_buffers_severe_output(monkeypatch):
    import agent_loop
    from cpu_pressure import CpuPressureSnapshot

    emit = lambda _event: None
    normal = CpuPressureSnapshot(False, "normal", 30.0, 1.0)
    busy = CpuPressureSnapshot(False, "busy", 74.0, 2.0, cpu_average_percent=72.0)
    severe = CpuPressureSnapshot(
        True,
        "severe",
        94.0,
        3.0,
        "system_pressure",
        cpu_average_percent=92.0,
        trigger="cpu_severe",
    )

    monkeypatch.setattr(agent_loop, "EXECUTOR_STREAM", True)
    monkeypatch.setattr(agent_loop.cpu_pressure, "snapshot", lambda: normal)
    assert agent_loop._llm_runtime_policy(emit)["output_mode"] == "stream"

    monkeypatch.setattr(agent_loop.cpu_pressure, "snapshot", lambda: busy)
    assert agent_loop._llm_runtime_policy(emit)["output_mode"] == "stream"

    monkeypatch.setattr(agent_loop.cpu_pressure, "snapshot", lambda: severe)
    policy = agent_loop._llm_runtime_policy(emit)
    assert policy["use_stream"] is True
    assert policy["emit_deltas"] is False
    assert policy["output_mode"] == "buffered_stream"
    assert policy["reason"] == "system_pressure"

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


def test_cpu_pressure_transition_statuses_are_durable_and_detailed():
    import agent_loop
    from agent_subagent_events import should_persist_ui_event
    from cpu_pressure import CpuPressureSnapshot

    busy_snapshot = CpuPressureSnapshot(
        False,
        "busy",
        74.0,
        1.0,
        cpu_average_percent=71.5,
        memory_percent=60.0,
        event_loop_lag_ms=20.0,
        trigger="cpu_busy",
    )
    severe_snapshot = CpuPressureSnapshot(
        True,
        "severe",
        94.0,
        2.0,
        "system_pressure",
        cpu_average_percent=91.2,
        memory_percent=78.0,
        event_loop_lag_ms=620.0,
        trigger="cpu_and_event_loop",
    )
    normal_snapshot = CpuPressureSnapshot(
        False,
        "normal",
        52.0,
        3.0,
        cpu_average_percent=58.2,
        memory_percent=62.0,
        event_loop_lag_ms=34.0,
    )

    busy = agent_loop._cpu_pressure_transition_event("normal", busy_snapshot)
    severe = agent_loop._cpu_pressure_transition_event("busy", severe_snapshot)
    unchanged = agent_loop._cpu_pressure_transition_event("severe", severe_snapshot)
    recovered = agent_loop._cpu_pressure_transition_event("severe", normal_snapshot)

    assert busy["cpu_pressure_mode"] == "busy"
    assert "继续逐 token 流式输出" in busy["content"]
    assert severe["cpu_pressure_mode"] == "severe"
    assert "CPU 滑动均值 91.2%" in severe["content"]
    assert "整段输出" in severe["content"]
    assert unchanged is None
    assert recovered["cpu_pressure_mode"] == "normal"
    assert "已还原逐 token 流式输出" in recovered["content"]
    for event in (busy, severe, recovered):
        assert "ephemeral" not in event
        assert should_persist_ui_event(event) is True


def test_internal_streaming_completion_buffers_transport_under_pressure(monkeypatch):
    import agent_harness
    from cpu_pressure import CpuPressureSnapshot

    monkeypatch.setattr(
        agent_harness.cpu_pressure,
        "snapshot",
        lambda: CpuPressureSnapshot(
            True, "severe", 95.0, 1.0, "system_pressure", trigger="cpu_severe"
        ),
    )
    worker_args = []

    def fake_stream_worker(sync_q, *_args, **kwargs):
        from types import SimpleNamespace

        worker_args.append(kwargs)
        sync_q.put(("turn", SimpleNamespace(content="whole response")))
        sync_q.put(None)

    monkeypatch.setattr(agent_harness, "run_chat_completion_stream_worker", fake_stream_worker)
    pieces = []
    result = agent_harness.executor_chat_complete_stream(
        [{"role": "user", "content": "summarize"}],
        on_content_delta=pieces.append,
        session_id="s1",
    )
    assert result == "whole response"
    assert pieces == ["whole response"]
    assert worker_args[0]["emit_deltas"] is False
