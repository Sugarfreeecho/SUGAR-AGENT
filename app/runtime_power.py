from __future__ import annotations

import asyncio
import ctypes
import logging
import os
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


class RuntimeSuspensionMonitor:
    """Detect event-loop scheduling gaps caused by sleep or process suspension."""

    def __init__(
        self,
        interval_seconds: float = 2.0,
        threshold_seconds: float = 15.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.interval_seconds = max(0.05, float(interval_seconds))
        self.threshold_seconds = max(self.interval_seconds * 2.0, float(threshold_seconds))
        self._clock = clock
        self.accumulated_suspend_seconds = 0.0
        self._suspend_since_progress_seconds = 0.0
        self.last_progress_monotonic = self._clock()
        self._last_tick = self.last_progress_monotonic
        self._stop = asyncio.Event()

    def mark_progress(self) -> None:
        self.last_progress_monotonic = self._clock()
        self._suspend_since_progress_seconds = 0.0

    def effective_idle_seconds(self, now: Optional[float] = None) -> float:
        current = self._clock() if now is None else float(now)
        return max(0.0, current - self.last_progress_monotonic - self._suspend_since_progress_seconds)

    def stop(self) -> None:
        self._stop.set()

    async def run(self, on_resume: Callable[[RuntimeResume], Awaitable[None]]) -> None:
        self._last_tick = self._clock()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
                break
            except asyncio.TimeoutError:
                pass
            now = self._clock()
            gap = max(0.0, now - self._last_tick)
            self._last_tick = now
            if gap < self.threshold_seconds:
                continue
            suspended = max(0.0, gap - self.interval_seconds)
            self.accumulated_suspend_seconds += suspended
            self._suspend_since_progress_seconds += suspended
            await on_resume(RuntimeResume(gap, self.interval_seconds, suspended, now))


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
