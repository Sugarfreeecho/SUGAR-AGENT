import asyncio
from pathlib import Path

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


def test_runtime_only_presents_verified_system_sleep_as_resume():
    source = (Path(__file__).resolve().parents[1] / "app" / "agent_loop.py").read_text(encoding="utf-8")

    assert 'if resume.cause != "system_sleep":' in source
    assert "runtime_watchdog_delay_suppressed" in source
    assert "_wait_for_local_network_recovery" in source
    assert "_executor_endpoint_reachable" not in source
    assert "LocalNetworkUnavailableError" in source


def test_monitor_stop_does_not_wait_for_poll_sleep(monkeypatch):
    async def scenario():
        monitor = runtime_power.RuntimeSuspensionMonitor()
        ready = asyncio.Event()
        loop = asyncio.get_running_loop()
        original = monitor._watch
        def watch(output):
            loop.call_soon_threadsafe(ready.set)
            original(output)
        monitor._watch = watch
        sleeping = []
        async def blocked_poll_sleep(delay):
            sleeping.append(delay)
            await asyncio.Event().wait()
        monkeypatch.setattr(runtime_power.asyncio, "sleep", blocked_poll_sleep)
        async def on_resume(event):
            pytest.fail("unexpected resume")
        task = asyncio.create_task(monitor.run(on_resume))
        try:
            await asyncio.wait_for(ready.wait(), 1)
            monitor.stop()
            await asyncio.wait_for(task, 1)
            assert sleeping == []
            assert monitor._thread is None
        finally:
            monitor.stop()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


def test_monitor_cancellation_stops_native_watchdog():
    async def scenario():
        monitor = runtime_power.RuntimeSuspensionMonitor()
        ready = asyncio.Event()
        loop = asyncio.get_running_loop()
        original = monitor._watch
        def watch(output):
            loop.call_soon_threadsafe(ready.set)
            original(output)
        monitor._watch = watch
        task = asyncio.create_task(monitor.run(lambda event: None))
        await asyncio.wait_for(ready.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert monitor._thread_stop.is_set()
        assert monitor._thread is None
    asyncio.run(scenario())


def test_new_subscriber_during_old_cleanup_keeps_its_watchdog(monkeypatch):
    async def scenario():
        detectors = []
        class Detector:
            def __init__(self):
                self.stopping = asyncio.Event()
                self.release = asyncio.Event()
                self.callback = None
                detectors.append(self)
            async def run(self, callback):
                self.callback = callback
                await self.release.wait()
            def stop(self):
                self.stopping.set()
        monkeypatch.setattr(runtime_power, "RuntimeSuspensionMonitor", Detector)
        broker = runtime_power._RuntimeSuspensionBroker()
        monitor = type("Monitor", (), {"accumulated_suspend_seconds": 0.0,
                                       "_suspend_since_progress_seconds": 0.0})()
        seen = []
        async def callback(event):
            seen.append(event)
        first = await broker.subscribe(monitor, callback)
        await asyncio.sleep(0)
        old = detectors[0]
        cleanup = asyncio.create_task(broker.unsubscribe(first))
        try:
            await old.stopping.wait()
            second = await broker.subscribe(monitor, callback)
            new_task, new_detector = broker.task, broker.detector
            await asyncio.sleep(0)
            old.release.set()
            await cleanup
            assert broker.task is new_task and broker.detector is new_detector
            assert not new_task.done()
            event = runtime_power.RuntimeResume(20, 2, 18, 100, "system_sleep")
            await old.callback(event)
            assert seen == []
            await new_detector.callback(event)
            assert seen == [event]
            final_cleanup = asyncio.create_task(broker.unsubscribe(second))
            await new_detector.stopping.wait()
            new_detector.release.set()
            await final_cleanup
        finally:
            for detector in detectors:
                detector.release.set()
            await asyncio.gather(cleanup, return_exceptions=True)
            if broker.task is not None:
                await broker.task
    asyncio.run(scenario())
