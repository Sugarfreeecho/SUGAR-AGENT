import importlib.util
import os
import sys
import threading
from pathlib import Path

import pytest


@pytest.fixture
def monitor_module():
    path = Path(__file__).resolve().parents[1] / "plugins/thread-monitor/monitor.py"
    spec = importlib.util.spec_from_file_location("thread_monitor_sampling_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 OS query")
def test_windows_sampler_keeps_real_thread_ids_and_cpu_counters(monitor_module):
    import psutil

    stopped = threading.Event()
    workers = [threading.Thread(target=stopped.wait, name=f"sampler-test-{i}") for i in range(3)]
    for worker in workers:
        worker.start()
    try:
        process = psutil.Process()
        before = {row.id: row for row in process.threads()}
        sampled = {row.id: row for row in monitor_module._windows_threads(os.getpid())}
        after = {row.id: row for row in process.threads()}
        assert all(worker.native_id in sampled for worker in workers)
        assert threading.get_native_id() in sampled
        for tid in before.keys() & sampled.keys() & after.keys():
            old, row, new = before[tid], sampled[tid], after[tid]
            assert old.user_time - .016 <= row.user_time <= new.user_time + .016
            assert old.system_time - .016 <= row.system_time <= new.system_time + .016
    finally:
        stopped.set()
        for worker in workers:
            worker.join(timeout=2)


def test_os_query_failure_preserves_psutil_fallback(monitor_module, monkeypatch):
    import psutil

    monkeypatch.setattr(monitor_module.sys, "platform", "win32")
    def fail(_pid):
        raise OSError("native query unavailable")
    monkeypatch.setattr(monitor_module, "_windows_threads", fail)
    expected = [object()]
    class Process:
        def threads(self):
            return expected
    monkeypatch.setattr(psutil, "Process", lambda _pid: Process())
    assert monitor_module._read_os_threads() is expected


def test_sampler_retreats_after_expensive_sampling(monitor_module):
    fast = monitor_module._sampling_interval(.001)
    slow = monitor_module._sampling_interval(.2)
    stalled = monitor_module._sampling_interval(20)
    assert fast >= monitor_module.SAMPLE_INTERVAL_SEC
    assert slow >= fast
    assert slow >= 4
    assert stalled >= 20 + monitor_module.SAMPLE_INTERVAL_SEC


def test_windows_query_closes_handles_on_cpu_probe_failure(monitor_module, monkeypatch):
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("th32ThreadID", wintypes.DWORD),
                    ("th32OwnerProcessID", wintypes.DWORD)]
    closed = []
    class Kernel:
        def CreateToolhelp32Snapshot(self, _flags, _pid):
            return 101
        def Thread32First(self, _snapshot, pointer):
            pointer._obj.th32OwnerProcessID = os.getpid()
            pointer._obj.th32ThreadID = 42
            return True
        def OpenThread(self, _rights, _inherit, _tid):
            return 303
        def GetThreadTimes(self, *_args):
            raise OSError("thread disappeared")
        def CloseHandle(self, handle):
            closed.append(handle)
    monkeypatch.setattr(monitor_module, "_windows_thread_api", lambda: (ctypes, wintypes, Kernel(), Entry))
    with pytest.raises(OSError, match="thread disappeared"):
        monitor_module._windows_threads(os.getpid())
    assert closed == [303, 101]
