"""Per-call grep budgets, cancellable processes and payload-free diagnostics."""
from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import logging
import math
import os
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass

_current = ContextVar("grep_search_run", default=None)
logger = logging.getLogger("agent_harness")
EXCLUDED_DIRS = (
    "venv", ".venv", "__pycache__", ".git", "node_modules", "sessions",
    "logs", ".trash", ".tool_results", "TempOutput", "truncate_backups",
)


class SearchStopped(Exception):
    pass


class SearchRun:
    def __init__(self, **metadata):
        self.started = time.perf_counter()
        try:
            configured_timeout = float(os.getenv("GREP_TIMEOUT_SEC", "30"))
        except ValueError:
            configured_timeout = 30.0
        self.timeout = max(1.0, configured_timeout) if math.isfinite(configured_timeout) else 30.0
        self.deadline = self.started + self.timeout
        self.cancel = threading.Event()
        self._stop_lock = threading.Lock()
        self.metadata = metadata
        self.rows = []
        self.backend = "validation"
        self.fallback_reason = ""
        self.stop_reason = ""
        self.worker_ms = None
        self.admission_ms = None
        self.queue_outcome = "waiting_capacity"
        self.first_hit_ms = None
        self.result_count = 0
        self.candidate_count = None

    def request_stop(self, reason):
        with self._stop_lock:
            if not self.stop_reason:
                self.stop_reason = reason
            self.cancel.set()

    def check(self):
        if self.cancel.is_set():
            self.request_stop("cancelled")
        elif time.perf_counter() >= self.deadline:
            self.request_stop("timeout")
        if self.stop_reason:
            raise SearchStopped(self.stop_reason)

    def error(self, backend):
        if self.stop_reason == "cancelled":
            return "Error: grep cancelled; search incomplete."
        return (f"Error: {backend} timed out after {self.timeout:g} seconds "
                "(GREP_TIMEOUT_SEC total budget); search incomplete.")

    def log(self):
        try:
            logger.info("grep_timing %s", json.dumps({
                **self.metadata, "elapsed_ms": round((time.perf_counter() - self.started) * 1000, 3),
                "worker_queue_ms": self.worker_ms, "backend": self.backend,
                "admission_ms": self.admission_ms, "queue_outcome": self.queue_outcome,
                "first_hit_ms": self.first_hit_ms, "result_count": self.result_count,
                "candidate_count": self.candidate_count,
                "fallback_reason": self.fallback_reason, "stop_reason": self.stop_reason,
                "processes": self.rows,
            }, separators=(",", ":")))
        except Exception:
            pass


@contextmanager
def bind(run):
    token = _current.set(run)
    try:
        yield run
    finally:
        _current.reset(token)


def current():
    return _current.get()


def search_entry(function):
    @functools.wraps(function)
    def call(*args, **kwargs):
        owned = current() is None
        run = current() or SearchRun()
        with bind(run):
            if run.worker_ms is None:
                run.worker_ms = round((time.perf_counter() - run.started) * 1000, 3)
                run.queue_outcome = "direct"
            try:
                run.check()
                return function(*args, **kwargs)
            except SearchStopped:
                return run.error(run.backend)
            finally:
                if owned:
                    run.log()
    return call


class _SearchJob:
    def __init__(self, run):
        self.run = run
        self._lock = threading.Lock()
        self._state = "queued"

    def abandon(self):
        with self._lock:
            if self._state != "queued":
                return False
            self._state = "abandoned"
            self.run.queue_outcome = "abandoned_before_start"
            return True

    def execute(self, context, function, kwargs):
        with self._lock:
            if self._state == "abandoned":
                return None
            self._state = "running"
            self.run.queue_outcome = "started"
            self.run.worker_ms = round((time.perf_counter() - self.run.started) * 1000, 3)
        try:
            # The gate precedes entering the copied security/tool context. A
            # cancelled queued job can never execute later, even after return.
            self.run.check()
            return context.run(function, **kwargs)
        except SearchStopped:
            return self.run.error(self.run.backend)
        finally:
            with self._lock:
                self._state = "finished"
                self.run.queue_outcome = "finished"


class _SearchExecutor:
    """Isolate searches, bounding running work plus queued placeholders."""
    def __init__(self, max_workers=4, capacity=16):
        self._slots = threading.BoundedSemaphore(capacity)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="myagent-grep")

    def try_submit(self, job, context, function, kwargs):
        if not self._slots.acquire(blocking=False):
            return None
        release_lock = threading.Lock()
        released = False

        def release():
            nonlocal released
            with release_lock:
                if not released:
                    released = True
                    self._slots.release()

        def execute():
            try:
                return job.execute(context, function, kwargs)
            finally:
                release()

        try:
            return self._executor.submit(execute)
        except BaseException:
            if job.abandon():
                release()
            raise

    def shutdown(self):
        # Do not cancel Futures: cancelled ThreadPoolExecutor work items stay
        # queued, and releasing their slots early permits unbounded buildup.
        self._executor.shutdown(wait=True)


_executor = None
_executor_lock = threading.Lock()


def _search_executor():
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = _SearchExecutor()
        return _executor


async def invoke(function, kwargs, metadata):
    """Queue deadlines return promptly; running searches settle child cleanup."""
    run = SearchRun(**metadata)
    job = _SearchJob(run)
    future = None
    cancellation = None
    with bind(run):
        try:
            context = contextvars.copy_context()
            executor = _search_executor()
            while future is None:
                run.check()
                submitted = executor.try_submit(job, context, function, kwargs)
                if submitted is not None:
                    run.admission_ms = round((time.perf_counter() - run.started) * 1000, 3)
                    future = asyncio.wrap_future(submitted)
                    # Abandoned placeholders may finish after this task exits.
                    future.add_done_callback(lambda done: None if done.cancelled() else done.exception())
                else:
                    await asyncio.sleep(min(.01, max(0, run.deadline - time.perf_counter())))
            while not future.done():
                try:
                    remaining = run.deadline - time.perf_counter()
                    if remaining <= 0:
                        run.request_stop("timeout")
                        if job.abandon():
                            return run.error("grep")
                        # Running work must reap/close its processes before return.
                        await asyncio.shield(future)
                    else:
                        await asyncio.wait((future,), timeout=remaining)
                except asyncio.CancelledError as exc:
                    cancellation = cancellation or exc
                    run.request_stop("cancelled")
                    if job.abandon():
                        raise cancellation
            if cancellation is not None:
                raise cancellation
            return future.result()
        except asyncio.CancelledError:
            run.request_stop("cancelled")
            job.abandon()
            raise
        except SearchStopped:
            job.abandon()
            return run.error("grep")
        except BaseException:
            if cancellation is not None:
                raise cancellation
            raise
        finally:
            run.log()


def normalize_globs(value, name):
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"grep {name} must be a string or an array of strings")
    return [item.strip() for item in value if item.strip()]


def scope_args(*, recursive, include, exclude, include_hidden, include_ignored):
    args = []
    if include_hidden:
        args.append("--hidden")
    if include_ignored:
        args.append("--no-ignore")
    for pattern in include:
        args.extend(("--glob", pattern))
    for pattern in exclude:
        args.extend(("--glob", "!" + pattern.lstrip("!")))
    # The target itself remains searchable, even when its name is excluded.
    # These globs apply only to descendants, at every depth.
    for name in EXCLUDED_DIRS:
        args.extend(("--glob", f"!{name}/"))
    if not recursive:
        args.extend(("--max-depth", "1"))
    return args


@dataclass
class ProcessResult:
    returncode: int
    stderr: str
    stopped: bool


def _records(stream, separator):
    if separator == "\n":
        yield from stream
        return
    pending = ""
    while True:
        chunk = stream.read(4096)
        if not chunk:
            if pending:
                yield pending
            return
        parts = (pending + chunk).split(separator)
        yield from parts[:-1]
        pending = parts[-1]


def run_process(args, *, popen, subprocess_module, stdio, consume, backend,
                input_text=None, separator="\n"):
    """Drain stderr concurrently; retain at most 8 KiB while counting all bytes.

    stdout remains streaming so the caller can stop immediately at its cap.
    The shared deadline also covers preceding backend attempts and enumeration.
    """
    run = current() or SearchRun()
    run.check()
    started = time.perf_counter()
    row = {"backend": backend, "spawn_ms": 0, "first_output_ms": None,
           "stderr_bytes": 0, "cap_hit": False, "consume_ms": 0}
    process = None
    stderr_parts = []
    retained = 0
    finished = threading.Event()
    threads = []
    timer = None

    def kill():
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    def timeout():
        if not finished.is_set():
            run.request_stop("timeout")
            kill()

    def watch_cancel():
        while not finished.wait(.025):
            if run.cancel.is_set():
                run.request_stop("cancelled")
                kill()
                return

    def drain():
        nonlocal retained
        try:
            while True:
                stream = getattr(process.stderr, "buffer", process.stderr)
                chunk = stream.read(4096)
                if not chunk:
                    return
                raw = chunk if isinstance(chunk, bytes) else chunk.encode("utf-8", errors="replace")
                row["stderr_bytes"] += len(raw)
                if retained < 8192:
                    kept = raw[:8192 - retained]
                    stderr_parts.append(kept)
                    retained += len(kept)
        except (OSError, ValueError):
            pass

    def write_input():
        try:
            process.stdin.write(input_text)
            process.stdin.close()
        except (OSError, ValueError):
            pass

    try:
        kwargs = dict(stdio)
        if input_text is not None:
            kwargs["stdin"] = subprocess_module.PIPE
        process = popen(args, stdout=subprocess_module.PIPE, stderr=subprocess_module.PIPE,
                        text=True, encoding="utf-8", errors="replace", **kwargs)
        row["spawn_ms"] = round((time.perf_counter() - started) * 1000, 3)
        # Popen cannot be interrupted portably; check its time against the same
        # deadline immediately after it returns, before consuming any output.
        run.check()
        timer = threading.Timer(max(0, run.deadline - time.perf_counter()), timeout)
        timer.daemon = True
        timer.start()
        for target in (drain, watch_cancel, *([write_input] if input_text is not None else [])):
            thread = threading.Thread(target=target, daemon=True, name="grep-io")
            threads.append(thread)
            thread.start()
        for raw in _records(process.stdout, separator):
            run.check()
            if row["first_output_ms"] is None:
                row["first_output_ms"] = round((time.perf_counter() - started) * 1000, 3)
            consume_started = time.perf_counter()
            try:
                stop = consume(raw)
            finally:
                row["consume_ms"] += (time.perf_counter() - consume_started) * 1000
            if stop:
                row["cap_hit"] = True
                try:
                    process.terminate()
                except OSError:
                    pass
                break
        read_done = time.perf_counter()
        row["read_ms"] = round((read_done - started) * 1000, 3)
        try:
            returncode = process.wait(timeout=min(1.0, max(.001, run.deadline - read_done)))
        except subprocess_module.TimeoutExpired:
            kill()
            returncode = process.wait(timeout=1)
        result = ProcessResult(returncode, "", row["cap_hit"])
        return result
    finally:
        cleanup = time.perf_counter()
        kill()
        if process is not None:
            try:
                process.wait(timeout=1)
            except subprocess_module.TimeoutExpired:
                kill()
                process.wait(timeout=1)
            # Once the child is reaped, readers/writer reach EOF/broken pipe.
            finished.set()
            if timer is not None:
                timer.cancel()
            for thread in threads:
                thread.join(timeout=1)
            for name in ("stdout", "stderr", "stdin"):
                stream = getattr(process, name, None)
                if stream is not None:
                    stream.close()
        row["cleanup_ms"] = round((time.perf_counter() - cleanup) * 1000, 3)
        row["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        row["stop_reason"] = run.stop_reason
        row["consume_ms"] = round(row["consume_ms"], 3)
        row["exit_code"] = process.poll() if process is not None else None
        run.rows.append(row)
        if "result" in locals():
            result.stderr = b"".join(stderr_parts).decode("utf-8", errors="replace")
