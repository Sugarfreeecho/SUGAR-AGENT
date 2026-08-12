"""Process-wide resource pressure detection for adaptive runtime behavior.

The public module name remains ``cpu_pressure`` for compatibility, but the
monitor deliberately combines host CPU, memory, this process' CPU share and
asyncio event-loop responsiveness.  It exposes three stable modes:

``normal``
    Full streaming and normal local-tool parallelism.
``busy``
    Keep streaming. Existing delta coalescing and deferred observability
    writes absorb background overhead without a visible UX downgrade.
``severe``
    Use whole-response LLM output and cap local resource-heavy tool work.

Transitions require sustained observations and recovery uses a lower threshold
plus a stability window, so a short spike cannot make output modes flap.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Optional, Tuple, Union


logger = logging.getLogger(__name__)
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_MODE_RANK = {"normal": 0, "busy": 1, "severe": 2}


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


def _clamp_percent(value: float) -> float:
    return min(100.0, max(0.0, float(value)))


@dataclass(frozen=True)
class CpuPressureConfig:
    enabled: bool = True
    # PCManager-inspired warning/severe split. Busy never disables streaming.
    busy_percent: float = 60.0
    high_percent: float = 90.0
    composite_percent: float = 80.0
    recovery_percent: float = 65.0
    sample_seconds: float = 10.0
    window_samples: int = 5
    enter_samples: int = 12
    recovery_seconds: float = 120.0
    memory_busy_percent: float = 85.0
    memory_severe_percent: float = 93.0
    memory_recovery_percent: float = 80.0
    memory_min_available_gb: float = 1.0
    process_busy_percent: float = 35.0
    loop_busy_ms: float = 200.0
    loop_composite_ms: float = 500.0
    loop_severe_ms: float = 1000.0
    loop_recovery_ms: float = 100.0
    loop_probe_seconds: float = 10.0
    tool_concurrency: int = 2

    @classmethod
    def from_env(cls) -> "CpuPressureConfig":
        # CPU_PRESSURE_HIGH_PERCENT remains a backwards-compatible alias.
        severe_default = _env_float("CPU_PRESSURE_HIGH_PERCENT", 90.0)
        severe = _clamp_percent(_env_float("CPU_PRESSURE_SEVERE_PERCENT", severe_default))
        busy = min(severe, max(1.0, _env_float("CPU_PRESSURE_BUSY_PERCENT", 60.0)))
        recovery = min(busy, max(0.0, _env_float("CPU_PRESSURE_RECOVERY_PERCENT", 65.0)))
        return cls(
            enabled=_env_bool("CPU_PRESSURE_ENABLED", True),
            busy_percent=busy,
            high_percent=severe,
            recovery_percent=recovery,
            sample_seconds=max(0.1, _env_float("CPU_PRESSURE_SAMPLE_SECONDS", 10.0)),
            enter_samples=max(1, _env_int("CPU_PRESSURE_ENTER_SAMPLES", 12)),
            recovery_seconds=max(0.0, _env_float("CPU_PRESSURE_RECOVERY_SECONDS", 120.0)),
            tool_concurrency=max(1, _env_int("CPU_PRESSURE_TOOL_CONCURRENCY", 2)),
        )


@dataclass(frozen=True)
class PressureObservation:
    cpu_percent: float
    memory_percent: Optional[float] = None
    available_memory_gb: Optional[float] = None
    process_cpu_percent: Optional[float] = None
    event_loop_lag_ms: Optional[float] = None


@dataclass(frozen=True)
class CpuPressureSnapshot:
    # Keep the first five fields compatible with earlier positional callers.
    degraded: bool
    mode: str
    cpu_percent: Optional[float]
    changed_monotonic: float
    reason: str = ""
    cpu_average_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    available_memory_gb: Optional[float] = None
    process_cpu_percent: Optional[float] = None
    event_loop_lag_ms: Optional[float] = None
    trigger: str = ""

    @property
    def busy(self) -> bool:
        return self.mode in {"busy", "severe", "degraded"}


class CpuPressureMonitor:
    """Sample host pressure on one daemon thread and expose a safe snapshot."""

    def __init__(
        self,
        config: Optional[CpuPressureConfig] = None,
        *,
        sampler: Optional[Callable[[], Union[float, PressureObservation]]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or CpuPressureConfig.from_env()
        self._sampler = sampler
        self._clock = clock
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._mode = "normal"
        self._cpu_percent: Optional[float] = None
        self._cpu_average_percent: Optional[float] = None
        self._cpu_window: Deque[float] = deque(maxlen=self.config.window_samples)
        self._memory_percent: Optional[float] = None
        self._available_memory_gb: Optional[float] = None
        self._process_cpu_percent: Optional[float] = None
        self._event_loop_lag_ms: Optional[float] = None
        self._event_loop_lag_updated: Optional[float] = None
        self._busy_samples = 0
        self._severe_samples = 0
        self._recovery_since: Optional[float] = None
        self._changed_monotonic = self._clock()
        self._mode_trigger = ""
        self._unavailable_logged = False
        self._process = None
        self._logical_cpu_count = 1

    def _default_sample(self) -> PressureObservation:
        try:
            import psutil
        except ImportError as exc:
            raise RuntimeError("psutil is not installed") from exc

        if self._process is None:
            self._process = psutil.Process()
            self._logical_cpu_count = max(1, int(psutil.cpu_count(logical=True) or 1))
            # Prime psutil's non-blocking process counter.
            self._process.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        raw_process_cpu = float(self._process.cpu_percent(interval=None))
        process_cpu = _clamp_percent(raw_process_cpu / self._logical_cpu_count)
        return PressureObservation(
            cpu_percent=float(psutil.cpu_percent(interval=None)),
            memory_percent=float(memory.percent),
            available_memory_gb=float(memory.available) / (1024.0 ** 3),
            process_cpu_percent=process_cpu,
            # The probe writes lag directly with its own timestamp. Leaving
            # this unset prevents the 1s resource sampler from refreshing a
            # stale lag value after the asyncio loop stops reporting.
            event_loop_lag_ms=None,
        )

    def _fresh_event_loop_lag_unlocked(self, now: float) -> Optional[float]:
        if self._event_loop_lag_updated is None:
            return None
        max_age = max(2.0, self.config.sample_seconds * 3.0)
        if now - self._event_loop_lag_updated > max_age:
            return None
        return self._event_loop_lag_ms

    def record_event_loop_lag(self, lag_ms: float, *, now: Optional[float] = None) -> None:
        """Record one lightweight asyncio scheduling-latency observation."""
        current = self._clock() if now is None else float(now)
        with self._lock:
            self._event_loop_lag_ms = max(0.0, float(lag_ms))
            self._event_loop_lag_updated = current

    def _coerce_observation(
        self,
        observation: Union[float, PressureObservation],
        *,
        memory_percent: Optional[float],
        available_memory_gb: Optional[float],
        process_cpu_percent: Optional[float],
        event_loop_lag_ms: Optional[float],
    ) -> PressureObservation:
        if isinstance(observation, PressureObservation):
            return observation
        return PressureObservation(
            cpu_percent=float(observation),
            memory_percent=memory_percent,
            available_memory_gb=available_memory_gb,
            process_cpu_percent=process_cpu_percent,
            event_loop_lag_ms=event_loop_lag_ms,
        )

    def _classify_unlocked(self) -> Tuple[str, str]:
        cpu = self._cpu_average_percent or 0.0
        memory = self._memory_percent
        available = self._available_memory_gb
        process_cpu = self._process_cpu_percent
        lag = self._event_loop_lag_ms

        severe_reasons = []
        if cpu >= self.config.high_percent:
            severe_reasons.append("cpu_severe")
        if memory is not None and memory >= self.config.memory_severe_percent:
            severe_reasons.append("memory_severe")
        if (
            available is not None
            and self.config.memory_min_available_gb > 0
            and available <= self.config.memory_min_available_gb
        ):
            severe_reasons.append("memory_available_low")
        if lag is not None and lag >= self.config.loop_severe_ms:
            severe_reasons.append("event_loop_severe")
        if (
            cpu >= self.config.composite_percent
            and lag is not None
            and lag >= self.config.loop_composite_ms
        ):
            severe_reasons.append("cpu_and_event_loop")
        if (
            process_cpu is not None
            and process_cpu >= self.config.process_busy_percent
            and lag is not None
            and lag >= self.config.loop_composite_ms
        ):
            severe_reasons.append("process_cpu_and_event_loop")
        if severe_reasons:
            return "severe", ",".join(severe_reasons)

        busy_reasons = []
        if cpu >= self.config.busy_percent:
            busy_reasons.append("cpu_busy")
        if memory is not None and memory >= self.config.memory_busy_percent:
            busy_reasons.append("memory_busy")
        if process_cpu is not None and process_cpu >= self.config.process_busy_percent:
            busy_reasons.append("process_cpu_busy")
        if lag is not None and lag >= self.config.loop_busy_ms:
            busy_reasons.append("event_loop_busy")
        if busy_reasons:
            return "busy", ",".join(busy_reasons)
        return "normal", ""

    def _healthy_for_normal_unlocked(self) -> bool:
        cpu_ok = (self._cpu_average_percent or 0.0) <= self.config.recovery_percent
        memory_ok = (
            self._memory_percent is None
            or self._memory_percent <= self.config.memory_recovery_percent
        )
        lag_ok = (
            self._event_loop_lag_ms is None
            or self._event_loop_lag_ms <= self.config.loop_recovery_ms
        )
        return cpu_ok and memory_ok and lag_ok

    def _set_mode_unlocked(self, mode: str, trigger: str, now: float) -> str:
        previous = self._mode
        if previous == mode:
            if trigger:
                self._mode_trigger = trigger
            return ""
        self._mode = mode
        self._changed_monotonic = now
        self._mode_trigger = trigger if mode != "normal" else ""
        self._recovery_since = None
        return f"{previous} -> {mode}"

    def observe(
        self,
        observation: Union[float, PressureObservation],
        *,
        now: Optional[float] = None,
        memory_percent: Optional[float] = None,
        available_memory_gb: Optional[float] = None,
        process_cpu_percent: Optional[float] = None,
        event_loop_lag_ms: Optional[float] = None,
    ) -> CpuPressureSnapshot:
        """Apply one observation. Public for deterministic tests/diagnostics."""
        current = self._clock() if now is None else float(now)
        sample = self._coerce_observation(
            observation,
            memory_percent=memory_percent,
            available_memory_gb=available_memory_gb,
            process_cpu_percent=process_cpu_percent,
            event_loop_lag_ms=event_loop_lag_ms,
        )
        transition = ""
        with self._lock:
            self._cpu_percent = _clamp_percent(sample.cpu_percent)
            self._cpu_window.append(self._cpu_percent)
            self._cpu_average_percent = sum(self._cpu_window) / len(self._cpu_window)
            self._memory_percent = (
                None if sample.memory_percent is None else _clamp_percent(sample.memory_percent)
            )
            self._available_memory_gb = (
                None
                if sample.available_memory_gb is None
                else max(0.0, float(sample.available_memory_gb))
            )
            self._process_cpu_percent = (
                None
                if sample.process_cpu_percent is None
                else _clamp_percent(sample.process_cpu_percent)
            )
            if sample.event_loop_lag_ms is not None:
                self._event_loop_lag_ms = max(0.0, float(sample.event_loop_lag_ms))
                self._event_loop_lag_updated = current
            elif self._fresh_event_loop_lag_unlocked(current) is None:
                self._event_loop_lag_ms = None

            if not self.config.enabled:
                return self._snapshot_unlocked()

            target_mode, trigger = self._classify_unlocked()
            target_rank = _MODE_RANK[target_mode]
            current_rank = _MODE_RANK[self._mode]
            self._busy_samples = self._busy_samples + 1 if target_rank >= 1 else 0
            self._severe_samples = self._severe_samples + 1 if target_rank >= 2 else 0

            if target_rank > current_rank:
                self._recovery_since = None
                if target_mode == "severe" and self._severe_samples >= self.config.enter_samples:
                    transition = self._set_mode_unlocked("severe", trigger, current)
                elif self._mode == "normal" and self._busy_samples >= self.config.enter_samples:
                    transition = self._set_mode_unlocked("busy", trigger, current)
            elif target_rank < current_rank:
                # Severe only needs a stable non-severe window to restore
                # streaming. Busy requires all lower recovery thresholds.
                can_recover = self._mode == "severe" or self._healthy_for_normal_unlocked()
                if can_recover:
                    if self._recovery_since is None:
                        self._recovery_since = current
                    if current - self._recovery_since >= self.config.recovery_seconds:
                        transition = self._set_mode_unlocked(target_mode, trigger, current)
                        self._busy_samples = 0 if target_mode == "normal" else self._busy_samples
                        self._severe_samples = 0
                else:
                    self._recovery_since = None
            else:
                self._recovery_since = None
                if trigger:
                    self._mode_trigger = trigger

            snapshot = self._snapshot_unlocked()
        if transition:
            logger.warning(
                "cpu_pressure_mode_changed %s cpu=%.1f%% avg=%.1f%% memory=%s%% "
                "process_cpu=%s%% loop_lag=%sms trigger=%s",
                transition,
                self._cpu_percent,
                self._cpu_average_percent,
                "n/a" if self._memory_percent is None else f"{self._memory_percent:.1f}",
                "n/a" if self._process_cpu_percent is None else f"{self._process_cpu_percent:.1f}",
                "n/a" if self._event_loop_lag_ms is None else f"{self._event_loop_lag_ms:.0f}",
                self._mode_trigger or "recovered",
            )
        return snapshot

    def _snapshot_unlocked(self) -> CpuPressureSnapshot:
        degraded = bool(self.config.enabled and self._mode == "severe")
        return CpuPressureSnapshot(
            degraded=degraded,
            mode=self._mode if self.config.enabled else "normal",
            cpu_percent=self._cpu_percent,
            changed_monotonic=self._changed_monotonic,
            reason="system_pressure" if degraded else "",
            cpu_average_percent=self._cpu_average_percent,
            memory_percent=self._memory_percent,
            available_memory_gb=self._available_memory_gb,
            process_cpu_percent=self._process_cpu_percent,
            event_loop_lag_ms=self._event_loop_lag_ms,
            trigger=self._mode_trigger if self.config.enabled else "",
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
                        "Resource pressure sampling unavailable; adaptive degradation is inactive: %s",
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
                name="myagent-resource-pressure",
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
            if self.config.enabled and self._mode == "severe":
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


def record_event_loop_lag(lag_ms: float) -> None:
    _get_monitor().record_event_loop_lag(lag_ms)


async def event_loop_lag_probe() -> None:
    """Continuously measure scheduling lag; cancellation cleanly stops it."""
    monitor = _get_monitor()
    interval = monitor.config.loop_probe_seconds
    while True:
        started = time.monotonic()
        await asyncio.sleep(interval)
        elapsed = time.monotonic() - started
        monitor.record_event_loop_lag(max(0.0, (elapsed - interval) * 1000.0))


def tool_parallelism(normal_limit: int) -> int:
    monitor = _get_monitor()
    monitor.start()
    return monitor.tool_parallelism(normal_limit)
