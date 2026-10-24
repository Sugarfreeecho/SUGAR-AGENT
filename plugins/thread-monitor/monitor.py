"""Read-only OS-thread and concurrency sampler for the Agent host process.

The sampler answers two questions that must not be conflated:

* **OS threads** - how many operating-system threads this process really owns
  right now, grouped by creation reason.  A thread pool that grows on every run
  shows up as a number instead of a hunch.
* **Agent concurrency** - how many logical units of work are alive right now
  (root runs, subagents, background jobs, PTY terminals, team sessions).

Everything here is read-only: it inspects registries the runtime already
maintains and never mutates agent state.  Sampling is driven by a daemon thread
so the HTTP layer only ever reads a pre-built snapshot.

The sampler also never *creates* host state.  It looks services up in
``sys.modules`` and only reads objects the application has already built, so a
sample can never trigger a cold start - importing ``agent_harness`` for the
first time, for instance, scans the whole session directory and takes seconds.

Two host-side shortcuts are deliberate:

* Session names come from ``session_manager.index`` (already in memory).
  ``list_sessions()`` would trigger a full disk rescan and stale-archive sweep,
  which costs seconds on a large session directory.
* Background jobs are counted from the execution service's job table instead of
  awaiting ``list_jobs()``, which is bound to the service's own event loop.
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
from collections import Counter, deque
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple


def _env_float(name: str, default: float, minimum: float) -> float:
    try:
        return max(minimum, float(os.getenv(name, "") or default))
    except (TypeError, ValueError):
        return max(minimum, float(default))


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, "") or default))
    except (TypeError, ValueError):
        return max(minimum, int(default))


SAMPLE_INTERVAL_SEC = _env_float("THREAD_MONITOR_INTERVAL_SEC", 1.0, 0.25)
HISTORY_LIMIT = _env_int("THREAD_MONITOR_HISTORY", 600, 60)
MAX_THREAD_DETAIL = _env_int("THREAD_MONITOR_MAX_THREADS", 200, 20)
LEAK_SUSPECT_SEC = _env_float("THREAD_MONITOR_LEAK_SEC", 300.0, 30.0)


@lru_cache(maxsize=1)
def _windows_thread_api():
    import ctypes
    from ctypes import wintypes

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                    ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD)]

    # WinDLL releases the GIL for each OS call. psutil's thread enumeration on
    # Windows can retain it throughout the scan, stalling unrelated HTTP work.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Thread32First", "Thread32Next"):
        func = getattr(kernel, name)
        func.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
        func.restype = wintypes.BOOL
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.GetThreadTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetThreadTimes.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return ctypes, wintypes, kernel, ThreadEntry


def _windows_threads(pid: int):
    ctypes, wintypes, kernel, ThreadEntry = _windows_thread_api()
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows = []
    try:
        entry = ThreadEntry()
        entry.dwSize = ctypes.sizeof(entry)
        present = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while present:
            if entry.th32OwnerProcessID == pid:
                tid = int(entry.th32ThreadID)
                user = system = 0.0
                handle = kernel.OpenThread(0x0800, False, tid)  # QUERY_LIMITED_INFORMATION
                if handle:
                    try:
                        created, exited, cpu_kernel, cpu_user = (wintypes.FILETIME() for _ in range(4))
                        if kernel.GetThreadTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                                 ctypes.byref(cpu_kernel), ctypes.byref(cpu_user)):
                            system = ((cpu_kernel.dwHighDateTime << 32) | cpu_kernel.dwLowDateTime) / 10000000
                            user = ((cpu_user.dwHighDateTime << 32) | cpu_user.dwLowDateTime) / 10000000
                    finally:
                        kernel.CloseHandle(handle)
                # Threads can exit between enumeration and OpenThread. Keep
                # the snapshot identity with zero CPU when no handle remains.
                rows.append(SimpleNamespace(id=tid, user_time=user, system_time=system))
            present = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(snapshot)
    return rows


def _read_os_threads():
    if sys.platform == "win32":
        try:
            return _windows_threads(os.getpid())
        except (OSError, AttributeError):
            pass
    import psutil
    return psutil.Process(os.getpid()).threads()


def _sampling_interval(elapsed: float) -> float:
    # Diagnostic sampling should use roughly <=5% of a worker's time. Back off
    # under load and avoid an immediate retry loop after a very slow sample.
    return max(SAMPLE_INTERVAL_SEC, min(10.0, elapsed * 20.0), elapsed + SAMPLE_INTERVAL_SEC)

_ACTIVE_JOB_STATES = frozenset({"running", "stopping"})
# "myagent-llm-request_3" / "selftest-worker-11" -> "<head>_*" / "<head>-*".
# Only a trailing run of digits is folded: random hex suffixes and names such
# as "pending-counts" must keep their identity.
_TRAILING_INDEX = re.compile(r"^(?P<head>.+[-_])(?P<index>\d+)$")


def _now() -> float:
    return time.time()


def group_thread_name(name: str) -> str:
    """Fold volatile ids so pool threads collapse into one comparable group.

    ``myagent-llm-request_3`` and ``selftest-worker-2`` both lose their numeric
    suffix, while names without digits (``MainThread``, ``pending-counts``)
    stay untouched.
    """

    text = str(name or "").strip() or "unnamed"
    match = _TRAILING_INDEX.match(text)
    if match is None:
        return text
    return f"{match.group('head')}*"


def python_thread_index() -> Dict[int, Dict[str, Any]]:
    """Map native OS thread ids to the Python thread that owns them.

    ``psutil`` reports OS thread ids and ``threading.Thread.native_id`` lives in
    the same id space, so the two can be joined.  Threads created outside Python
    (native libraries, the OpenSSL pool) simply have no entry.
    """

    result: Dict[int, Dict[str, Any]] = {}
    try:
        threads = threading.enumerate()
    except Exception:  # pragma: no cover - defensive
        return result
    for thread in threads:
        native_id = getattr(thread, "native_id", None)
        if native_id is None:
            continue
        try:
            key = int(native_id)
        except (TypeError, ValueError):
            continue
        result[key] = {
            "name": str(getattr(thread, "name", "") or ""),
            "daemon": bool(getattr(thread, "daemon", False)),
        }
    return result


def _active_root_runs() -> Tuple[List[Dict[str, str]], List[str]]:
    """Return root runs that own a live task, plus any probe errors."""

    errors: List[str] = []
    names: Dict[str, str] = {}
    candidates: List[str] = []
    # ``agent_harness`` is always imported by the app before a run can exist.
    # Touching it here would force a cold import (and a full session scan) in a
    # process that has no runs to report, so only use an already-loaded module.
    harness = sys.modules.get("agent_harness")
    if harness is not None:
        try:
            manager = getattr(harness, "session_manager", None)
            for row in list(getattr(manager, "index", None) or []):
                if not isinstance(row, dict):
                    continue
                sid = str(row.get("id") or "").strip()
                if not sid:
                    continue
                candidates.append(sid)
                names[sid] = str(row.get("name") or sid)
        except Exception as exc:
            errors.append(f"session index probe failed: {exc}")

    # ``session_lifecycle`` is imported by the runtime before it can register a
    # run, so an absent module means there is nothing to report.
    lifecycle = sys.modules.get("session_lifecycle")
    if lifecycle is None:
        return [], errors
    try:
        # Sessions holding a live task are the authoritative active set; the
        # index is only used for display names.
        for sid in list(getattr(lifecycle, "_run_tasks", None) or {}):
            sid = str(sid or "").strip()
            if sid and sid not in names:
                candidates.append(sid)
    except Exception as exc:
        errors.append(f"run registry probe failed: {exc}")

    is_run_active = getattr(lifecycle, "is_run_active", None)
    if not callable(is_run_active):
        errors.append("run probe unavailable")
        return [], errors

    active: List[Dict[str, str]] = []
    seen = set()
    for sid in candidates:
        if sid in seen:
            continue
        seen.add(sid)
        try:
            if is_run_active(sid):
                active.append({"session_id": sid, "name": names.get(sid, sid), "kind": "session"})
        except Exception:
            continue
    return active, errors


def _running_subagents() -> Dict[str, str]:
    module = sys.modules.get("agent_subagent")
    if module is None:
        return {}
    try:
        running = module.subagent_registry.running_runs()
        if isinstance(running, dict):
            return {str(k): str(v or "") for k, v in running.items()}
    except Exception:
        return {}
    return {}


def _count_jobs(service: Any) -> int:
    try:
        jobs = service.jobs
        snapshot = list(jobs.values())
    except Exception:
        return 0
    return sum(
        1
        for job in snapshot
        if str(getattr(job, "status", "") or "") in _ACTIVE_JOB_STATES
        and bool(getattr(job, "visible", True))
    )


def _count_terminals(service: Any) -> int:
    try:
        sessions = getattr(getattr(service, "terminals", None), "sessions", None) or {}
        snapshot = list(sessions.values())
    except Exception:
        return 0
    return sum(1 for row in snapshot if str(getattr(row, "status", "") or "") == "running")


def _count_pending_interactions() -> int:
    """Count queued questions and approvals from the sidebar's warm cache."""

    module = sys.modules.get("human_interaction")
    if module is None:
        return 0
    try:
        cache = getattr(module.get_human_interaction_service(), "_pending_counts_cache", None)
        if not isinstance(cache, dict):
            return 0
        total = 0
        for entry in list(cache.values()):
            counts = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else entry
            if isinstance(counts, dict):
                total += max(0, int(counts.get("total") or 0))
        return total
    except Exception:
        return 0


def _execution_service_if_started() -> Any:
    """Return the execution service only if the app already created it.

    ``execution_service()`` would build the service (and its own event-loop
    thread) on first call; counting must never be the reason that happens.
    """

    module = sys.modules.get("execution_services.jobs")
    if module is None:
        return None
    return getattr(module, "_SERVICE", None)


class ThreadMonitor:
    """Process-local sampler with a background tick and short history."""

    def __init__(self, *, history: int = HISTORY_LIMIT) -> None:
        self._lock = threading.RLock()
        self._history: Deque[Dict[str, Any]] = deque(maxlen=max(30, int(history)))
        self._first_seen: Dict[int, float] = {}
        self._meta: Dict[int, Dict[str, Any]] = {}
        self._baseline = 0
        self._peak = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_error = ""
        self._started_at = _now()
        self._interval_sec = SAMPLE_INTERVAL_SEC

    # -- lifecycle -----------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="thread-monitor", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    @property
    def running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self.sample()
            except Exception as exc:  # pragma: no cover - defensive
                self._last_error = f"{type(exc).__name__}: {exc}"
            elapsed = max(0.0, time.monotonic() - started)
            self._interval_sec = _sampling_interval(elapsed)
            self._stop.wait(max(0.0, self._interval_sec - elapsed))

    # -- sampling ------------------------------------------------------
    def sample(self) -> Dict[str, Any]:
        errors: List[str] = []
        threads = self._collect_threads(errors)
        concurrency, concurrency_errors = self._collect_concurrency()
        errors.extend(concurrency_errors)
        process = self._collect_process(errors)

        total = len(threads)
        with self._lock:
            if not self._baseline:
                self._baseline = total
            self._peak = max(self._peak, total)
            now = _now()
            for row in threads:
                tid = int(row["thread_id"])
                self._first_seen.setdefault(tid, now)
                self._meta[tid] = {
                    "name": row["name"],
                    "group": row["group"],
                }
            live = {int(row["thread_id"]) for row in threads}
            for tid in list(self._first_seen):
                if tid not in live:
                    self._first_seen.pop(tid, None)
                    self._meta.pop(tid, None)

            previous = self._history[-1] if self._history else None
            row = {
                "timestamp": now,
                "thread_total": total,
                "thread_groups": self._group_rows(threads),
                "threads": threads[:MAX_THREAD_DETAIL],
                "concurrency": concurrency,
                "delta_threads": total - int(previous["thread_total"]) if previous else 0,
                "peak_threads": self._peak,
                "baseline_threads": self._baseline,
                "process": process,
                "errors": errors,
            }
            self._history.append(row)
            return dict(row)

    @staticmethod
    def _group_rows(threads: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        counter: Counter = Counter()
        cpu: Dict[str, float] = {}
        for row in threads:
            group = str(row["group"])
            counter[group] += 1
            cpu[group] = cpu.get(group, 0.0) + float(row.get("cpu_seconds") or 0.0)
        return [
            {
                "group": group,
                "count": count,
                "cpu_seconds": round(cpu.get(group, 0.0), 3),
            }
            for group, count in counter.most_common()
        ]

    @staticmethod
    def _collect_threads(errors: List[str]) -> List[Dict[str, Any]]:
        try:
            raw_threads = _read_os_threads()
        except Exception as exc:
            errors.append(f"thread enumeration failed: {exc}")
            return []

        owners = python_thread_index()
        rows: List[Dict[str, Any]] = []
        for item in raw_threads:
            try:
                tid = int(getattr(item, "id", 0) or 0)
            except (TypeError, ValueError):
                tid = 0
            owner = owners.get(tid) or {}
            name = str(owner.get("name") or f"tid-{tid}")
            try:
                user_time = float(getattr(item, "user_time", 0.0) or 0.0)
                system_time = float(getattr(item, "system_time", 0.0) or 0.0)
            except (TypeError, ValueError):
                user_time = system_time = 0.0
            rows.append(
                {
                    "thread_id": tid,
                    "name": name,
                    "group": group_thread_name(name),
                    "daemon": bool(owner.get("daemon", False)),
                    "cpu_seconds": round(user_time + system_time, 3),
                }
            )
        rows.sort(key=lambda row: (-float(row["cpu_seconds"]), str(row["name"])))
        return rows

    def _collect_concurrency(self) -> Tuple[Dict[str, Any], List[str]]:
        errors: List[str] = []
        result: Dict[str, Any] = {
            "root_runs": 0,
            "subagent_runs": 0,
            "background_jobs": 0,
            "terminals": 0,
            "pending_interactions": 0,
            "active_team_sessions": 0,
            "total": 0,
            "sessions": [],
        }
        if str(os.getenv("THREAD_MONITOR_SKIP_CONCURRENCY", "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            # Escape hatch for isolated profiling runs: the thread view stays
            # usable even when the host registries are not importable.
            result["skipped"] = True
            return result, errors

        subagents = _running_subagents()
        result["subagent_runs"] = len(subagents)

        roots, root_errors = _active_root_runs()
        errors.extend(root_errors)
        # A subagent session also registers a run task; count it once, on the
        # subagent side, so the two groups stay independent.
        roots = [row for row in roots if row["session_id"] not in subagents]
        result["root_runs"] = len(roots)
        result["sessions"] = roots[:50]

        for child_id, run_id in list(subagents.items())[:50]:
            result["sessions"].append(
                {
                    "session_id": child_id,
                    "name": child_id,
                    "kind": "subagent",
                    "run_id": run_id,
                }
            )

        service = _execution_service_if_started()
        if service is not None:
            try:
                result["background_jobs"] = _count_jobs(service)
                result["terminals"] = _count_terminals(service)
            except Exception as exc:
                errors.append(f"execution service probe failed: {exc}")

        team_module = sys.modules.get("agent_team.service")
        if team_module is not None:
            try:
                result["active_team_sessions"] = len(team_module.active_team_session_ids())
            except Exception as exc:
                errors.append(f"team probe failed: {exc}")

        result["pending_interactions"] = _count_pending_interactions()
        result["total"] = (
            int(result["root_runs"])
            + int(result["subagent_runs"])
            + int(result["background_jobs"])
            + int(result["terminals"])
            + int(result["active_team_sessions"])
        )
        return result, errors

    def _collect_process(self, errors: List[str]) -> Dict[str, Any]:
        info: Dict[str, Any] = {"pid": os.getpid()}
        try:
            import psutil

            process = psutil.Process(os.getpid())
            info["num_threads"] = int(process.num_threads())
            info["uptime_seconds"] = round(_now() - float(process.create_time()), 1)
            info["rss_mb"] = round(float(process.memory_info().rss) / (1024 * 1024), 1)
        except Exception as exc:
            errors.append(f"process probe failed: {exc}")
        info["monitor_uptime_seconds"] = round(_now() - self._started_at, 1)
        if self._last_error:
            info["last_error"] = self._last_error
        return info

    # -- queries -------------------------------------------------------
    def latest(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._history[-1]) if self._history else None

    def snapshot(self, *, history: int = 60) -> Dict[str, Any]:
        latest = self.latest()
        if latest is None:
            # The first HTTP hit must never render an empty page.
            latest = self.sample()
        limit = max(1, min(int(history or 60), self._history.maxlen or HISTORY_LIMIT))
        with self._lock:
            rows = list(self._history)[-limit:]
        latest["history"] = [
            {
                "timestamp": round(float(row["timestamp"]), 3),
                "thread_total": int(row["thread_total"]),
                "concurrency_total": int(row["concurrency"].get("total") or 0),
            }
            for row in rows
        ]
        latest["suspected_leaks"] = self.suspected_leaks()
        latest["running"] = self.running
        latest["interval_seconds"] = self._interval_sec
        latest["leak_suspect_seconds"] = LEAK_SUSPECT_SEC
        total_threads = int(latest.get("thread_total") or 0)
        runs = int(latest["concurrency"].get("total") or 0)
        latest["threads_per_run"] = round(total_threads / runs, 2) if runs > 0 else None
        return latest

    def suspected_leaks(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            meta = dict(self._meta)
            first_seen = dict(self._first_seen)
        now = _now()
        rows = []
        for tid, info in meta.items():
            age = now - float(first_seen.get(tid, now))
            if age < LEAK_SUSPECT_SEC:
                continue
            rows.append(
                {
                    "thread_id": int(tid),
                    "name": str(info.get("name") or ""),
                    "group": str(info.get("group") or ""),
                    "alive_seconds": round(age, 1),
                }
            )
        rows.sort(key=lambda row: -float(row["alive_seconds"]))
        return rows[: max(1, limit)]

    def reset_baseline(self) -> Dict[str, Any]:
        """Forget the baseline and peak; monitor-local state only."""

        with self._lock:
            self._baseline = 0
            self._peak = 0
            self._history.clear()
        return self.snapshot()

    def stop_tracking(self) -> None:
        """Drop per-thread bookkeeping without touching agent state."""

        with self._lock:
            self._first_seen.clear()
            self._meta.clear()


__all__ = [
    "ThreadMonitor",
    "group_thread_name",
    "python_thread_index",
    "SAMPLE_INTERVAL_SEC",
    "HISTORY_LIMIT",
    "LEAK_SUSPECT_SEC",
]
