"""DSH-style jobs with a dedicated loop, bounded output and trusted ownership."""
from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import ctypes
import logging
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)
ACTIVE = {"running", "stopping"}
OUTPUT_LIMIT = 256 * 1024
LOG_LIMIT = 32 * 1024 * 1024


class JobLimitReached(RuntimeError):
    pass


class OutputBuffer:
    """Absolute byte cursors distinguish an empty read from overwritten output."""

    def __init__(self, limit: int = OUTPUT_LIMIT):
        self.limit = limit
        self.data = bytearray()
        self.end = 0
        self.cursor = 0

    @property
    def begin(self):
        return self.end - len(self.data)

    def append(self, value: bytes):
        self.end += len(value)
        self.data.extend(value)
        if len(self.data) > self.limit:
            del self.data[:-self.limit]

    def read_at(self, offset: int):
        offset = max(0, min(int(offset), self.end))
        gap = offset < self.begin
        raw = bytes(self.data[max(offset, self.begin) - self.begin:])
        return raw, self.end, gap

    def read(self):
        raw, self.cursor, gap = self.read_at(self.cursor)
        return raw, gap


@dataclass
class Job:
    id: str
    owner: str
    kind: str
    label: str
    visible: bool = True
    status: str = "running"
    detail: str = ""
    exit_code: int | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    output: OutputBuffer = field(default_factory=OutputBuffer)
    stdout: OutputBuffer = field(default_factory=OutputBuffer)
    stderr: OutputBuffer = field(default_factory=OutputBuffer)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    cancel: Callable | None = None
    task: asyncio.Task | None = None
    startup_done: asyncio.Event | None = None
    pid: int | None = None
    process_created: float | None = None
    notice_pending: bool = False
    notice_suppressed: bool = False
    waiters: int = 0
    permission_mode: str = ""
    result: dict | None = None
    result_pending: bool = False

    def public(self):
        return {"id": self.id, "kind": self.kind, "label": self.label,
                "status": self.status, "detail": self.detail, "exit_code": self.exit_code,
                "started_at": self.started_at, "finished_at": self.finished_at,
                "outputOffset": self.output.end, "outputBegin": self.output.begin,
                "pid": self.pid}


class ExecutionService:
    def __init__(self, session_manager=None, *, max_concurrent: int = 10):
        self.manager = session_manager
        self.max_concurrent = max_concurrent
        self.jobs: dict[str, Job] = {}
        self._loop = None
        self._thread = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._closing = False
        self._recovered: set[str] = set()
        self._log_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self.suppressed: set[str] = set()
        self.closed_owners: set[str] = set()
        self.boot_id = uuid.uuid4().hex
        self.terminals = None

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._ready.clear()
            self._closing = False
            def run():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(
                    max_workers=64, thread_name_prefix="execution-io"))
                self._loop = loop
                self._ready.set()
                loop.run_forever()
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()
            self._thread = threading.Thread(target=run, name="execution-services", daemon=True)
            self._thread.start()
        if not self._ready.wait(10):
            raise RuntimeError("execution service did not start")

    async def call(self, operation, *args, **kwargs):
        self.start()
        if self._closing:
            raise RuntimeError("execution service is shutting down")
        if asyncio.get_running_loop() is self._loop:
            return await operation(*args, **kwargs)
        # Do not carry a live Agent state or ContextVar authorization into the
        # long-lived service. Each operation receives its explicit trusted spec.
        def submit():
            return asyncio.run_coroutine_threadsafe(operation(*args, **kwargs), self._loop)
        future = contextvars.Context().run(submit)
        return await asyncio.wrap_future(future)

    def _store(self):
        if self.manager is None:
            return None
        from runtime_v2.extension_state import SessionExtensionStateStore
        return SessionExtensionStateStore(self.manager.repository.sessions_dir,
            path_resolver=self.manager._resolve_session_path)

    def _path(self, owner, resource_id):
        if self.manager is None:
            return None
        if not re.fullmatch(r"[a-f0-9]{32}", str(resource_id)):
            raise ValueError("invalid execution resource id")
        root = Path(self.manager._resolve_session_path(owner))
        if not root.is_dir():
            raise ValueError("session not found")
        return root / "execution" / resource_id

    async def persist(self, owner, namespace, value):
        store = self._store()
        if store:
            await asyncio.to_thread(store.set_latest, owner, "execution-tools", namespace, value=value)

    async def _persist_job(self, job):
        import psutil
        await self.persist(job.owner, "job." + job.id,
            {**job.public(), "owner": job.owner, "boot_id": self.boot_id,
             "host_pid": os.getpid(), "host_created": psutil.Process().create_time(),
             "process_created": job.process_created, "visible": job.visible,
             "notice_pending": job.notice_pending,
             "notice_suppressed": job.notice_suppressed,
             "permission_mode": job.permission_mode, "model_cursor": job.output.cursor,
             "result": job.result, "result_pending": job.result_pending})

    async def recover(self, owner):
        if owner in self._recovered:
            return
        store = self._store()
        if not store:
            self._recovered.add(owner)
            return
        extensions = await asyncio.to_thread(store.read_all_lightweight, owner)
        for namespace, row in (extensions.get("execution-tools") or {}).items():
            value = row.get("value") or {}
            if value.get("owner") != owner or value.get("boot_id") == self.boot_id:
                continue
            if namespace.startswith("job."):
                job = Job(str(value["id"]), owner, value.get("kind", "process"),
                    value.get("label", ""), visible=value.get("visible", True))
                job.status = value.get("status", "failed")
                job.started_at = value.get("started_at", time.time())
                job.finished_at = value.get("finished_at")
                job.exit_code = value.get("exit_code")
                job.detail = value.get("detail", "")
                job.result = value.get("result")
                job.result_pending = bool(value.get("result_pending"))
                if job.status in ACTIVE:
                    job.status, job.detail = "failed", "host_restarted: execution was interrupted; command was not replayed"
                    job.finished_at = time.time()
                    await asyncio.to_thread(self._cleanup_previous_process, value)
                job.notice_suppressed = True
                path = self._path(owner, job.id)
                if path and (path / "output.bin").is_file():
                    def tail():
                        with (path / "output.bin").open("rb") as stream:
                            stream.seek(0, 2)
                            size = stream.tell()
                            stream.seek(max(0, size - OUTPUT_LIMIT))
                            raw = stream.read(OUTPUT_LIMIT)
                        try:
                            end = int((path / "output.offset").read_text())
                        except (OSError, ValueError):
                            end = int(value.get("outputOffset") or 0)
                        return raw, max(size, end)
                    raw, end = await asyncio.to_thread(tail)
                    job.output.append(raw)
                    job.output.end = end
                job.output.cursor = min(job.output.end, max(0, int(value.get("model_cursor") or 0)))
                job.done.set()
                self.jobs[job.id] = job
                await self._persist_job(job)
            elif namespace.startswith("terminal.") and value.get("status") == "running":
                value.update(status="closed", detail="host_restarted: shell was not restored")
                await asyncio.to_thread(self._cleanup_previous_process, value)
                await self.persist(owner, namespace, value)
        self._recovered.add(owner)

    @staticmethod
    def _cleanup_previous_process(value):
        # A forked/copied record is not authority to kill a process. Identity
        # must also match this controller's previous process lifetime.
        import psutil
        try:
            parent = psutil.Process(int(value.get("host_pid") or 0))
            if parent.is_running() and abs(parent.create_time() - float(value.get("host_created") or 0)) < .01:
                return
        except (psutil.Error, ValueError):
            pass
        if not value.get("process_created") or not value.get("host_created"):
            return
        try:
            child = psutil.Process(int(value.get("pid") or 0))
            if abs(child.create_time() - float(value["process_created"])) >= .01:
                return
            for process in reversed(child.children(recursive=True)):
                process.kill()
            child.kill()
        except (psutil.Error, ValueError):
            pass

    async def admit(self, owner, kind, label, *, visible=True, permission_mode=""):
        if not owner:
            raise ValueError("background execution requires a trusted owner")
        await self.recover(owner)
        if permission_mode and self.manager is not None:
            from security.runtime import session_permission_mode
            if str(session_permission_mode(owner)) != permission_mode:
                raise PermissionError("permission mode changed before execution; request authorization again")
        if self._closing or owner in self.suppressed:
            raise RuntimeError("session execution is stopped")
        if sum(j.owner == owner and j.status in ACTIVE for j in self.jobs.values()) >= self.max_concurrent:
            raise JobLimitReached(f"background job limit reached ({self.max_concurrent} per Agent)")
        job = Job(uuid.uuid4().hex, owner, kind, str(label)[:1000], visible=visible,
                  permission_mode=permission_mode)
        self.jobs[job.id] = job
        try:
            if visible:
                await self._persist_job(job)
        except BaseException:
            self.jobs.pop(job.id, None)
            raise
        return job

    def owned(self, owner, job_id):
        job = self.jobs.get(str(job_id))
        if job is None or job.owner != owner or not job.visible:
            raise ValueError("job not found for this Agent")
        return job

    async def append(self, job, raw, stream="stdout"):
        job.output.append(raw)
        getattr(job, stream).append(raw)
        if self.manager and job.visible:
            await self.write_log(job.owner, job.id, raw)

    async def write_log(self, owner, identifier, raw):
        if self.manager:
            path = self._path(owner, identifier)
            def write():
                path.mkdir(parents=True, exist_ok=True)
                target = path / "output.bin"
                offset_file = path / "output.offset"
                size = target.stat().st_size if target.exists() else 0
                try:
                    end = max(size, int(offset_file.read_text()))
                except (OSError, ValueError):
                    end = size
                with target.open("ab") as file:
                    file.write(raw)
                if target.stat().st_size > LOG_LIMIT:
                    with target.open("rb") as file:
                        file.seek(-LOG_LIMIT // 2, 2)
                        tail = file.read()
                    target.write_bytes(tail)
                temporary = path / "output.offset.tmp"
                temporary.write_text(str(end + len(raw)), encoding="ascii")
                temporary.replace(offset_file)
            # stdout and stderr readers may both append concurrently. Keep the
            # persisted stream and its derived absolute offset in one order.
            key = (str(owner), str(identifier))
            async with self._log_locks.setdefault(key, asyncio.Lock()):
                await asyncio.to_thread(write)

    async def settle(self, job, status="completed", detail="", exit_code=None, result=None):
        if job.done.is_set():
            return
        job.status = "killed" if job.status == "stopping" else status
        job.detail, job.exit_code, job.finished_at = detail, exit_code, time.time()
        job.result, job.result_pending = result, result is not None
        job.notice_pending = bool(job.visible and not job.notice_suppressed
                                  and job.owner not in self.suppressed)
        job.done.set()
        if job.visible:
            await self._persist_job(job)

    async def list_jobs(self, owner):
        await self.recover(owner)
        return [j.public() for j in self.jobs.values() if j.owner == owner and j.visible]

    async def output(self, owner, job_id, wait=False, timeout_ms=30000, *, offset=None):
        await self.recover(owner)
        job = self.owned(owner, job_id)
        if wait and not job.done.is_set():
            job.waiters += 1
            try:
                await asyncio.wait_for(job.done.wait(), max(.001, min(float(timeout_ms), 600000) / 1000))
            except asyncio.TimeoutError:
                pass
            finally:
                job.waiters -= 1
        if offset is None:
            raw, gap = job.output.read()
            result = job.result if job.result_pending else None
            job.result_pending = False
            if job.done.is_set():
                job.notice_pending = False
                job.output.limit = 16 * 1024
                if len(job.output.data) > job.output.limit:
                    del job.output.data[:-job.output.limit]
            await self._persist_job(job)
            cursor = job.output.cursor
        else:
            raw, cursor, gap = job.output.read_at(offset)
            result = job.result
        from agent_tools import redact_sensitive_tool_text, _decode_cli_subprocess_bytes
        text = redact_sensitive_tool_text(_decode_cli_subprocess_bytes(raw))
        return {"text": ("[output truncated; earlier bytes are unavailable]\n" if gap else "") + text,
                "job": job.public(), "offset": cursor, "truncated": gap, "result": result}

    async def kill(self, owner, job_id, reason="", *, suppress=True):
        job = self.owned(owner, job_id)
        if job.status not in ACTIVE:
            return {"outcome": "already-finished", "job": job.public()}
        job.notice_suppressed = job.notice_suppressed or suppress
        job.notice_pending = False
        if job.status != "stopping":
            job.status = "stopping"
            job.detail = reason or "cancellation requested"
            if job.cancel:
                await job.cancel()
        await self._persist_job(job)
        return {"outcome": "cancellation-requested", "job": job.public()}

    async def stop_owner(self, owner, *, close_terminals=False, reason="user_stop"):
        self.suppressed.add(owner)
        if close_terminals:
            self.closed_owners.add(owner)
        for job in tuple(self.jobs.values()):
            if job.owner != owner:
                continue
            job.notice_pending, job.notice_suppressed = False, True
            if job.status in ACTIVE:
                job.status = "stopping"
                job.detail = reason
                if job.cancel:
                    await job.cancel()
            if job.visible:
                await self._persist_job(job)
        if self.terminals:
            await self.terminals.stop_owner(owner, close=close_terminals)
        owned = [j for j in self.jobs.values() if j.owner == owner]
        for job in owned:
            if job.startup_done and not job.startup_done.is_set():
                await asyncio.wait_for(job.startup_done.wait(), 8)
                if job.cancel and not job.done.is_set():
                    await job.cancel()
        tasks = [j.task for j in owned if j.task and not j.task.done()]
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=8)
            if pending:
                raise RuntimeError("execution cleanup timed out; resources may still be stopping")

    async def resume_owner(self, owner):
        self.suppressed.discard(owner)
        self.closed_owners.discard(owner)

    async def pending_owners(self):
        return sorted({j.owner for j in self.jobs.values()
                       if j.notice_pending and not j.waiters and j.owner not in self.suppressed})

    async def notices(self, owner):
        jobs = [j for j in self.jobs.values() if j.owner == owner and j.notice_pending and not j.waiters
                and owner not in self.suppressed]
        return [{"id": j.id, "text": f"[background job {j.id}] {j.kind} finished: {j.status}. {j.detail} Read its output with job_output."}
                for j in jobs]

    async def acknowledge(self, owner, ids):
        for identifier in ids:
            job = self.owned(owner, identifier)
            job.notice_pending = False
            await self._persist_job(job)

    async def spawn_process(self, owner, spec, *, visible):
        job = await self.admit(owner, "process", spec["label"], visible=visible,
                               permission_mode=spec.get("permission_mode", ""))
        job.startup_done = asyncio.Event()
        paths = list(spec.get("cleanup_paths") or ())
        process = None
        handle = None
        try:
            def start():
                from agent_tools import _assign_windows_run_shell_job
                kw = dict(spec.get("spawn_kw") or {})
                kw.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=spec["cwd"], env=spec["env"])
                if os.name == "nt":
                    kw["creationflags"] = int(kw.get("creationflags", 0)) | 4  # CREATE_SUSPENDED
                else:
                    kw["start_new_session"] = True
                if owner in self.suppressed or self._closing or job.status != "running":
                    raise RuntimeError("execution cancelled before process start")
                child = subprocess.Popen(spec["argv"], **kw)
                job_handle = None
                try:
                    job_handle = _assign_windows_run_shell_job(child.pid)
                    if os.name == "nt":
                        if not job_handle:
                            raise RuntimeError("could not contain suspended process in a Windows Job Object")
                        if owner in self.suppressed or self._closing or job.status != "running":
                            raise RuntimeError("execution cancelled before target command was resumed")
                        resume = ctypes.WinDLL("ntdll").NtResumeProcess
                        resume.argtypes, resume.restype = [ctypes.c_void_p], ctypes.c_long
                        if resume(int(child._handle)) != 0:
                            raise RuntimeError("could not resume contained process")
                    return child, job_handle
                except BaseException:
                    child.kill()
                    child.wait()
                    from agent_tools import _close_windows_run_shell_job
                    _close_windows_run_shell_job(job_handle)
                    raise
            starter = asyncio.create_task(asyncio.to_thread(start))
            try:
                process, handle = await asyncio.shield(starter)
            except asyncio.CancelledError:
                process, handle = await starter
                raise
            job.pid = process.pid
            import psutil
            try:
                job.process_created = psutil.Process(process.pid).create_time()
            except psutil.Error:
                pass
            async def cancel():
                await asyncio.to_thread(terminate_process, process, job.process_created)
            job.cancel = cancel
            if job.status == "stopping" or owner in self.suppressed:
                await cancel()
            if visible:
                await self._persist_job(job)
            async def monitor():
                # Blocking pipe readers must not occupy the management pool:
                # cancellation and persistence still need workers under load.
                io_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3,
                    thread_name_prefix="job-io")
                loop = asyncio.get_running_loop()
                status, detail, code = "completed", "", None
                try:
                    async def pump(pipe, name):
                        while True:
                            raw = await loop.run_in_executor(io_pool, pipe.read1, 8192)
                            if not raw:
                                break
                            await self.append(job, raw, name)
                    readers = asyncio.gather(pump(process.stdout, "stdout"), pump(process.stderr, "stderr"))
                    code = await loop.run_in_executor(io_pool, process.wait)
                    try:
                        await asyncio.wait_for(readers, 3)
                    except asyncio.TimeoutError:
                        # Descendants inheriting the pipes must not retain the
                        # job forever after the command's main process exits.
                        await cancel()
                    detail = f"Exit code: {code}"
                except BaseException as exc:
                    await cancel()
                    status, detail = "failed", str(exc)
                finally:
                    from agent_tools import _close_windows_run_shell_job, _unlink_run_shell_temp
                    _close_windows_run_shell_job(handle)
                    _unlink_run_shell_temp([Path(p) for p in paths])
                    for pipe in (process.stdout, process.stderr):
                        pipe.close()
                    io_pool.shutdown(wait=False, cancel_futures=True)
                await self.settle(job, status, detail, exit_code=code)
            job.task = asyncio.create_task(monitor())
            job.startup_done.set()
            return job.id
        except BaseException as exc:
            if process:
                await asyncio.to_thread(terminate_process, process, job.process_created)
            from agent_tools import _close_windows_run_shell_job, _unlink_run_shell_temp
            _close_windows_run_shell_job(handle)
            _unlink_run_shell_temp([Path(p) for p in paths])
            job.notice_suppressed = True
            await self.settle(job, "failed", str(exc))
            raise
        finally:
            job.startup_done.set()

    async def foreground_snapshot(self, job_id, *, promote=False):
        job = self.jobs[job_id]
        if promote and not job.visible:
            key = (job.owner, job.id)
            async with self._log_locks.setdefault(key, asyncio.Lock()):
                # Publish at the snapshot boundary. Later appends queue behind
                # this initial log write rather than racing an overwrite.
                raw, end = bytes(job.output.data), job.output.end
                job.visible = True
                if job.done.is_set():
                    job.notice_pending = not job.notice_suppressed
                path = self._path(job.owner, job.id)
                if path:
                    await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
                    await asyncio.to_thread((path / "output.bin").write_bytes, raw)
                    await asyncio.to_thread((path / "output.offset").write_text, str(end), encoding="ascii")
            await self._persist_job(job)
        return {"done": job.done.is_set(), "job": job.public(),
                "stdout": bytes(job.stdout.data), "stderr": bytes(job.stderr.data),
                "truncated": {"stdout": job.stdout.begin > 0, "stderr": job.stderr.begin > 0}}

    async def release_foreground(self, identifier):
        job = self.jobs.get(identifier)
        if job and job.done.is_set() and not job.visible:
            self.jobs.pop(identifier, None)

    async def shutdown(self):
        if not self._thread or not self._thread.is_alive():
            return
        async def clean():
            from .computer import _MANAGER
            if _MANAGER is not None and _MANAGER.service is self:
                await _MANAGER.stop()
            self._closing = True
            for owner in {j.owner for j in self.jobs.values()}:
                await self.stop_owner(owner, close_terminals=True, reason="host_shutdown")
            if self.terminals:
                await self.terminals.shutdown()
            tasks = [j.task for j in self.jobs.values() if j.task and not j.task.done()]
            if tasks:
                await asyncio.wait(tasks, timeout=8)
        await self.call(clean)
        self._loop.call_soon_threadsafe(self._loop.stop)
        await asyncio.to_thread(self._thread.join, 10)


def terminate_process(process, created=None):
    import psutil
    from agent_tools import _agent_protected_process_ids
    protected = _agent_protected_process_ids()
    try:
        root = psutil.Process(process.pid)
        if created and abs(root.create_time() - created) >= .01:
            return
        children = root.children(recursive=True)
        for child in reversed(children):
            if child.pid not in protected:
                try:
                    child.kill()
                except psutil.Error:
                    pass
        if root.pid not in protected:
            root.kill()
    except psutil.Error:
        pass
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass


_SERVICE = None
_SERVICE_LOCK = threading.Lock()


def execution_service(session_manager=None):
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            if session_manager is None:
                from agent_harness import session_manager as default_manager
                session_manager = default_manager
            _SERVICE = ExecutionService(session_manager)
        elif session_manager is not None and _SERVICE.manager is not session_manager:
            raise RuntimeError("execution service is already bound to another session manager")
        return _SERVICE
