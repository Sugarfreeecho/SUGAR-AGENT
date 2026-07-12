from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


logger = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
POWER_REQUEST_CONTEXT_VERSION = 0
POWER_REQUEST_CONTEXT_SIMPLE_STRING = 0x1
POWER_REQUEST_SYSTEM_REQUIRED = 0


class _ReasonContextUnion(ctypes.Union):
    _fields_ = [("simple_reason_string", ctypes.c_wchar_p)]


class _ReasonContext(ctypes.Structure):
    _anonymous_ = ("reason",)
    _fields_ = [
        ("version", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("reason", _ReasonContextUnion),
    ]


@dataclass
class WindowsPowerRequest:
    handle: Optional[int] = None
    fallback_thread_state: bool = False
    closed: bool = False

    @property
    def active(self) -> bool:
        return not self.closed and bool(self.handle or self.fallback_thread_state)

    def close(self) -> None:
        WindowsSleepInhibitor.release(self)

    def __del__(self):
        try:
            self.close()
        except Exception:
            # Interpreter shutdown may already have torn ctypes/logging down.
            pass


class WindowsSleepInhibitor:
    """Create one kernel power-request handle per agent run.

    Handles are process-owned and automatically closed by Windows on process
    termination. This avoids mixing process-wide reference counting with the
    thread-local SetThreadExecutionState API.
    """

    @classmethod
    def acquire(cls, reason: str = "MyAgent is running an active task") -> WindowsPowerRequest:
        if os.name != "nt":
            return WindowsPowerRequest()
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            context = _ReasonContext(
                version=POWER_REQUEST_CONTEXT_VERSION,
                flags=POWER_REQUEST_CONTEXT_SIMPLE_STRING,
                simple_reason_string=str(reason or "MyAgent active task"),
            )
            kernel32.PowerCreateRequest.argtypes = [ctypes.POINTER(_ReasonContext)]
            kernel32.PowerCreateRequest.restype = ctypes.c_void_p
            kernel32.PowerSetRequest.argtypes = [ctypes.c_void_p, ctypes.c_int]
            kernel32.PowerSetRequest.restype = ctypes.c_bool
            handle = kernel32.PowerCreateRequest(ctypes.byref(context))
            invalid_handle = ctypes.c_void_p(-1).value
            if not handle or int(handle) == int(invalid_handle):
                raise OSError(ctypes.get_last_error(), "PowerCreateRequest failed")
            if not kernel32.PowerSetRequest(handle, POWER_REQUEST_SYSTEM_REQUIRED):
                error = ctypes.get_last_error()
                kernel32.CloseHandle(ctypes.c_void_p(handle))
                raise OSError(error, "PowerSetRequest failed")
            logger.info("power_request_acquired handle=%s", int(handle))
            return WindowsPowerRequest(handle=int(handle))
        except Exception:
            logger.warning("PowerCreateRequest unavailable; using thread-state fallback", exc_info=True)
            try:
                active = bool(ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED
                ))
                return WindowsPowerRequest(fallback_thread_state=active)
            except Exception:
                logger.warning("Windows sleep inhibition fallback failed", exc_info=True)
                return WindowsPowerRequest()

    @classmethod
    def release(cls, request: Optional[WindowsPowerRequest]) -> None:
        if request is None or request.closed:
            return
        request.closed = True
        if os.name != "nt":
            return
        if request.handle:
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.PowerClearRequest.argtypes = [ctypes.c_void_p, ctypes.c_int]
                kernel32.PowerClearRequest.restype = ctypes.c_bool
                kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel32.CloseHandle.restype = ctypes.c_bool
                handle = ctypes.c_void_p(request.handle)
                if not kernel32.PowerClearRequest(handle, POWER_REQUEST_SYSTEM_REQUIRED):
                    logger.warning("PowerClearRequest failed handle=%s error=%s", request.handle, ctypes.get_last_error())
                kernel32.CloseHandle(handle)
                logger.info("power_request_released handle=%s", request.handle)
            except Exception:
                logger.warning("Windows power request release failed", exc_info=True)
            return
        if request.fallback_thread_state:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except Exception:
                logger.warning("Windows sleep inhibition fallback release failed", exc_info=True)


@dataclass(frozen=True)
class RuntimeResume:
    gap_seconds: float
    expected_interval_seconds: float
    suspended_seconds: float
    detected_monotonic: float
    cause: str = "process_suspended"


def _windows_unbiased_seconds() -> Optional[float]:
    """Return Windows uptime excluding sleep, or None when unavailable."""
    if os.name != "nt":
        return None
    try:
        value = ctypes.c_ulonglong()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        query = kernel32.QueryUnbiasedInterruptTime
        query.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
        query.restype = ctypes.c_bool
        if not query(ctypes.byref(value)):
            return None
        return float(value.value) / 10_000_000.0
    except Exception:
        logger.debug("QueryUnbiasedInterruptTime unavailable", exc_info=True)
        return None


class RuntimeSuspensionMonitor:
    """Detect system sleep/process suspension without treating loop stalls as sleep.

    Sampling happens on a dedicated native thread.  A synchronous tool may block
    asyncio for a long time, but the watchdog keeps ticking and therefore does not
    produce a false resume event.
    """

    def __init__(
        self,
        interval_seconds: float = 2.0,
        threshold_seconds: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
        unbiased_clock: Optional[Callable[[], Optional[float]]] = _windows_unbiased_seconds,
    ):
        self.interval_seconds = max(0.05, float(interval_seconds))
        self.threshold_seconds = max(self.interval_seconds * 2.0, float(threshold_seconds))
        self._clock = clock
        self._unbiased_clock = unbiased_clock
        self.accumulated_suspend_seconds = 0.0
        self._suspend_since_progress_seconds = 0.0
        self.last_progress_monotonic = self._clock()
        self._last_tick = self.last_progress_monotonic
        self._stop = asyncio.Event()
        self._thread_stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def mark_progress(self) -> None:
        self.last_progress_monotonic = self._clock()
        self._suspend_since_progress_seconds = 0.0

    def effective_idle_seconds(self, now: Optional[float] = None) -> float:
        current = self._clock() if now is None else float(now)
        return max(0.0, current - self.last_progress_monotonic - self._suspend_since_progress_seconds)

    def stop(self) -> None:
        self._stop.set()
        self._thread_stop.set()

    def _classify_gap(
        self,
        gap: float,
        unbiased_gap: Optional[float],
        detected_monotonic: float,
    ) -> Optional[RuntimeResume]:
        if gap < self.threshold_seconds:
            return None
        suspended = max(0.0, gap - self.interval_seconds)
        cause = "process_suspended"
        if unbiased_gap is not None:
            sleep_seconds = max(0.0, gap - unbiased_gap)
            # Allow for timer jitter while requiring meaningful excluded uptime.
            if sleep_seconds >= min(2.0, self.threshold_seconds / 2.0):
                suspended = sleep_seconds
                cause = "system_sleep"
        return RuntimeResume(gap, self.interval_seconds, suspended, detected_monotonic, cause)

    def _watch(self, output: "queue.Queue[RuntimeResume]") -> None:
        last_tick = self._clock()
        last_unbiased = self._unbiased_clock() if self._unbiased_clock else None
        while not self._thread_stop.wait(self.interval_seconds):
            now = self._clock()
            current_unbiased = self._unbiased_clock() if self._unbiased_clock else None
            gap = max(0.0, now - last_tick)
            unbiased_gap = None
            if current_unbiased is not None and last_unbiased is not None:
                unbiased_gap = max(0.0, current_unbiased - last_unbiased)
            event = self._classify_gap(gap, unbiased_gap, now)
            if event is not None:
                output.put(event)
            last_tick = now
            last_unbiased = current_unbiased

    async def run(self, on_resume: Callable[[RuntimeResume], Awaitable[None]]) -> None:
        output: "queue.Queue[RuntimeResume]" = queue.Queue()
        self._thread_stop.clear()
        self._thread = threading.Thread(
            target=self._watch,
            args=(output,),
            name="myagent-runtime-watchdog",
            daemon=True,
        )
        self._thread.start()
        while not self._stop.is_set():
            await asyncio.sleep(min(self.interval_seconds, 0.25))
            while True:
                try:
                    event = output.get_nowait()
                except queue.Empty:
                    break
                self.accumulated_suspend_seconds += event.suspended_seconds
                self._suspend_since_progress_seconds += event.suspended_seconds
                await on_resume(event)
        self._thread_stop.set()
        if self._thread is not None:
            await asyncio.to_thread(self._thread.join, max(1.0, self.interval_seconds * 2.0))
            self._thread = None


class AgentRunPowerGuard:
    def __init__(self, monitor: Optional[RuntimeSuspensionMonitor] = None):
        self.monitor = monitor or RuntimeSuspensionMonitor()
        self.sleep_inhibited = False
        self._power_request: Optional[WindowsPowerRequest] = None
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self, on_resume: Callable[[RuntimeResume], Awaitable[None]]) -> None:
        self._power_request = WindowsSleepInhibitor.acquire()
        self.sleep_inhibited = self._power_request.active
        self._monitor_task = asyncio.create_task(self.monitor.run(on_resume))

    async def close(self) -> None:
        self.monitor.stop()
        if self._monitor_task is not None:
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        WindowsSleepInhibitor.release(self._power_request)
        self._power_request = None
