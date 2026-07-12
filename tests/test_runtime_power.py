import asyncio

import pytest

from app import runtime_power


def test_effective_idle_excludes_detected_suspend(monkeypatch):
    ticks = iter([100.0, 140.0])
    monitor = runtime_power.RuntimeSuspensionMonitor(interval_seconds=2, threshold_seconds=15, clock=lambda: next(ticks))
    monitor._suspend_since_progress_seconds = 35.0
    assert monitor.effective_idle_seconds() == pytest.approx(5.0)


def test_monitor_classifies_process_suspension_without_sleep_clock_gap():
    monitor = runtime_power.RuntimeSuspensionMonitor(
        interval_seconds=2,
        threshold_seconds=15,
    )
    event = monitor._classify_gap(20.0, 20.0, 30.0)
    assert event is not None
    assert event.cause == "process_suspended"
    assert event.suspended_seconds == pytest.approx(18.0)


def test_monitor_classifies_windows_sleep_from_excluded_uptime():
    monitor = runtime_power.RuntimeSuspensionMonitor(interval_seconds=2, threshold_seconds=15)
    event = monitor._classify_gap(22.0, 2.0, 30.0)
    assert event is not None
    assert event.cause == "system_sleep"
    assert event.suspended_seconds == pytest.approx(20.0)


def test_monitor_ignores_normal_watchdog_ticks():
    monitor = runtime_power.RuntimeSuspensionMonitor(interval_seconds=2, threshold_seconds=15)
    assert monitor._classify_gap(2.5, 2.5, 30.0) is None


def test_sleep_inhibitor_is_noop_off_windows(monkeypatch):
    monkeypatch.setattr(runtime_power.os, "name", "posix")
    request = runtime_power.WindowsSleepInhibitor.acquire()
    assert request.active is False
    runtime_power.WindowsSleepInhibitor.release(request)
    assert request.closed is True
