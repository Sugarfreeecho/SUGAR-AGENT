import asyncio

import pytest

from app import runtime_power


def test_effective_idle_excludes_detected_suspend(monkeypatch):
    ticks = iter([100.0, 140.0])
    monitor = runtime_power.RuntimeSuspensionMonitor(interval_seconds=2, threshold_seconds=15, clock=lambda: next(ticks))
    monitor._suspend_since_progress_seconds = 35.0
    assert monitor.effective_idle_seconds() == pytest.approx(5.0)


def test_monitor_reports_scheduler_gap(monkeypatch):
    samples = iter([10.0, 10.0, 10.5])
    monitor = runtime_power.RuntimeSuspensionMonitor(
        interval_seconds=0.01,
        threshold_seconds=0.02,
        clock=lambda: next(samples),
    )
    seen = []

    async def fake_wait_for(_awaitable, timeout):
        _awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(runtime_power.asyncio, "wait_for", fake_wait_for)

    async def on_resume(event):
        seen.append(event)
        monitor.stop()

    asyncio.run(monitor.run(on_resume))
    assert len(seen) == 1
    assert seen[0].gap_seconds == pytest.approx(0.5)
    assert seen[0].suspended_seconds == pytest.approx(0.45)


def test_sleep_inhibitor_is_noop_off_windows(monkeypatch):
    monkeypatch.setattr(runtime_power.os, "name", "posix")
    request = runtime_power.WindowsSleepInhibitor.acquire()
    assert request.active is False
    runtime_power.WindowsSleepInhibitor.release(request)
    assert request.closed is True
