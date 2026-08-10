"""Process-wide CPU pressure detection for adaptive runtime behavior.

The monitor changes mode only after sustained observations and uses a lower
recovery threshold. This hysteresis prevents output-mode flapping around a
single CPU percentage.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional


logger = logging.getLogger(__name__)
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = str(raw).strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class CpuPressureConfig:
    enabled: bool = True
    high_percent: float = 85.0
    recovery_percent: float = 65.0
    sample_seconds: float = 1.0
    enter_samples: int = 3
    recovery_seconds: float = 10.0
    tool_concurrency: int = 2

    @classmethod
    def from_env(cls) -> "CpuPressureConfig":
        high = min(100.0, max(1.0, _env_float("CPU_PRESSURE_HIGH_PERCENT", 85.0)))
        recovery = min(high, max(0.0, _env_float("CPU_PRESSURE_RECOVERY_PERCENT", 65.0)))
        return cls(
            enabled=_env_bool("CPU_PRESSURE_ENABLED", True),
            high_percent=high,
            recovery_percent=recovery,
            sample_seconds=max(0.1, _env_float("CPU_PRESSURE_SAMPLE_SECONDS", 1.0)),
            enter_samples=max(1, _env_int("CPU_PRESSURE_ENTER_SAMPLES", 3)),
            recovery_seconds=max(0.0, _env_float("CPU_PRESSURE_RECOVERY_SECONDS", 10.0)),
            tool_concurrency=max(1, _env_int("CPU_PRESSURE_TOOL_CONCURRENCY", 2)),
        )


@dataclass(frozen=True)
class CpuPressureSnapshot:
    degraded: bool
    mode: str
    cpu_percent: Optional[float]
    changed_monotonic: float
    reason: str = ""


class CpuPressureMonitor:
    """Sample host CPU on one daemon thread and expose a thread-safe snapshot."""

    def __init__(
        self,
        config: Optional[CpuPressureConfig] = None,
        *,
        sampler: Optional[Callable[[], float]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or CpuPressureConfig.from_env()
        self._sampler = sampler
        self._clock = clock
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._degraded = False
        self._cpu_percent: Optional[float] = None
        self._high_samples = 0
        self._recovery_since: Optional[float] = None
        self._changed_monotonic = self._clock()
        self._unavailable_logged = False

    def _default_sample(self) -> float:
        try:
            import psutil
        except ImportError as exc:
            raise RuntimeError("psutil is not installed") from exc
        return float(psutil.cpu_percent(interval=None))

    def observe(self, cpu_percent: float, *, now: Optional[float] = None) -> CpuPressureSnapshot:
        """Apply one observation. Public for deterministic tests and diagnostics."""
        current = self._clock() if now is None else float(now)
        value = min(100.0, max(0.0, float(cpu_percent)))
        transition = ""
        with self._lock:
            self._cpu_percent = value
            if not self.config.enabled:
                return self._snapshot_unlocked()

            if not self._degraded:
                self._high_samples = self._high_samples + 1 if value >= self.config.high_percent else 0
                if self._high_samples >= self.config.enter_samples:
                    self._degraded = True
                    self._changed_monotonic = current
                    self._recovery_since = None
                    transition = "normal -> degraded"
            else:
                if value <= self.config.recovery_percent:
                    if self._recovery_since is None:
                        self._recovery_since = current
                    if current - self._recovery_since >= self.config.recovery_seconds:
                        self._degraded = False
                        self._changed_monotonic = current
                        self._high_samples = 0
                        self._recovery_since = None
                        transition = "degraded -> normal"
                else:
                    self._recovery_since = None

            snapshot = self._snapshot_unlocked()
        if transition:
            logger.warning(
                "cpu_pressure_mode_changed %s cpu=%.1f%% high=%.1f%% recovery=%.1f%%",
                transition,
                value,
                self.config.high_percent,
                self.config.recovery_percent,
            )
        return snapshot

    def _snapshot_unlocked(self) -> CpuPressureSnapshot:
        degraded = bool(self.config.enabled and self._degraded)
        return CpuPressureSnapshot(
            degraded=degraded,
            mode="degraded" if degraded else "normal",
            cpu_percent=self._cpu_percent,
            changed_monotonic=self._changed_monotonic,
            reason="cpu_pressure" if degraded else "",
        )

    def snapshot(self) -> CpuPressureSnapshot:
        with self._lock:
            return self._snapshot_unlocked()

    def _watch(self) -> None:
        sampler = self._sampler or self._default_sample
        while not self._stop.is_set():
            try:
                self.observe(sampler())
            except Exception as exc:
                if not self._unavailable_logged:
                    logger.warning(
                        "CPU pressure sampling unavailable; adaptive degradation is inactive: %s",
                        exc,
                    )
                    self._unavailable_logged = True
            if self._stop.wait(self.config.sample_seconds):
                break

    def start(self) -> None:
        if not self.config.enabled:
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._watch,
                name="myagent-cpu-pressure",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(max(0.0, float(timeout)))

    def tool_parallelism(self, normal_limit: int) -> int:
        limit = max(1, int(normal_limit))
        with self._lock:
            if self.config.enabled and self._degraded:
                return min(limit, self.config.tool_concurrency)
        return limit


_monitor_lock = threading.Lock()
_monitor: Optional[CpuPressureMonitor] = None


def _get_monitor() -> CpuPressureMonitor:
    # The application loads .env while importing agent_harness. Delay config
    # capture until startup/first use so those values are authoritative even if
    # this lightweight module was imported earlier.
    global _monitor
    if _monitor is not None:
        return _monitor
    with _monitor_lock:
        if _monitor is None:
            _monitor = CpuPressureMonitor()
        return _monitor


def start() -> None:
    _get_monitor().start()


def stop() -> None:
    monitor = _monitor
    if monitor is not None:
        monitor.stop()


def snapshot() -> CpuPressureSnapshot:
    # Lazy start also covers direct library/CLI use outside app.main's lifespan.
    monitor = _get_monitor()
    monitor.start()
    return monitor.snapshot()


def tool_parallelism(normal_limit: int) -> int:
    monitor = _get_monitor()
    monitor.start()
    return monitor.tool_parallelism(normal_limit)
