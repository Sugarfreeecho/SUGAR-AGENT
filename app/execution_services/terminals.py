"""True PTY sessions with owner isolation and DSH send/read semantics."""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import shutil
import signal
import platform
import re
import time
import uuid
from dataclasses import dataclass, field

from .jobs import OutputBuffer, OUTPUT_LIMIT, terminate_process

PROMPT_MARKER = "\x1b]133;D\x07"


@dataclass
class TerminalSession:
    id: str
    owner: str
    name: str
    cwd: str
    actor: str
    backend: object
    dialect: str
    screen: object
    parser: object
    prompt_marker: str = PROMPT_MARKER
    status: str = "running"
    output: OutputBuffer = field(default_factory=lambda: OutputBuffer(2 * 1024 * 1024))
    started_at: float = field(default_factory=time.time)
    reader: asyncio.Task | None = None
    send_task: asyncio.Task | None = None
    send_job: object | None = None
    last_output: float = field(default_factory=time.monotonic)
    prompt_count: int = 0
    cwd_ready: bool = False
    marker_tail: str = ""
    connection: str = ""
    permission_mode: str = ""
    detail: str = ""
    exit_code: int | None = None
    pid: int | None = None
    process_created: float | None = None
    interruption: dict | None = None

    def working_directory(self):
        """Read the live shell's directory, never infer it from prior input."""
        import psutil
        try:
            if (self.status != "running" or not self.cwd_ready or not self.pid
                or not self.process_created
                or (self.send_task is not None and not self.send_task.done())
                or not TerminalManager._foreground_ready(self)):
                return None
            process = psutil.Process(self.pid)
            if abs(process.create_time() - self.process_created) >= .01:
                return None
            cwd = process.cwd()
            if not os.path.isabs(cwd) or not os.path.isdir(cwd):
                return None
            self.cwd = cwd
            return cwd
        except (psutil.Error, OSError, ValueError):
            return None

    def public(self):
        return {"id": self.id, "type": "shell", "name": self.name, "cwd": self.cwd,
                "status": self.status, "actor": self.actor, "dialect": self.dialect,
                "startedAt": self.started_at, "pid": self.pid, "detail": self.detail,
                "exit_code": self.exit_code}


class TerminalManager:
    def __init__(self, service):
        self.service = service
        self.sessions: dict[str, TerminalSession] = {}
        self.openings: dict[asyncio.Task, tuple[str, str]] = {}

    def owned(self, owner, identifier, actor="model"):
        session = self.sessions.get(str(identifier))
        if not session or session.owner != owner or session.actor != actor:
            raise ValueError("terminal not found for this owner")
        return session

    async def _persist(self, session):
        import psutil
        await self.service.persist(session.owner, "terminal." + session.id,
            {**session.public(), "owner": session.owner, "boot_id": self.service.boot_id,
             "host_pid": os.getpid(), "host_created": psutil.Process().create_time(),
             "process_created": session.process_created})

    async def open(self, owner, **options):
        task = asyncio.current_task()
        self.openings[task] = (owner, options.get("actor", "model"))
        try:
            return await self._open(owner, **options)
        finally:
            self.openings.pop(task, None)

    async def _open(self, owner, *, name="", cwd="", actor="model", shell="", permission_mode=""):
        await self.service.recover(owner)
        if self.service._closing or owner in self.service.closed_owners:
            raise RuntimeError("session execution is closing")
        if actor == "model" and owner in self.service.suppressed:
            raise RuntimeError("session execution is stopped")
        if sum(s.owner == owner and s.actor == actor and s.status == "running"
               for s in self.sessions.values()) >= 8:
            raise RuntimeError("terminal limit reached (8 per owner)")
        import pyte
        from agent_tools import (_subprocess_env_for_shell,
            _run_shell_env_with_prepended_agent_python_dir)
        env = _run_shell_env_with_prepended_agent_python_dir(_subprocess_env_for_shell())
        nonce = uuid.uuid4().hex
        prompt_marker = f"\x1b]133;D;{nonce}\x07"
        if actor == "model":
            # DSH uses a plain model terminal; retain rich rendering for users.
            env.update(TERM="dumb", PAGER="cat", GIT_PAGER="cat", NO_COLOR="1")
            env.pop("COLORTERM", None)
        else:
            env.update(TERM="xterm-256color", COLORTERM="truecolor")
        if not cwd:
            from agent_tools import active_tool_work_dir
            cwd = str(active_tool_work_dir())
        if not os.path.isdir(cwd):
            raise ValueError("terminal working directory does not exist")
        if os.name == "nt":
            from agent_tools import _windows_powershell_executable
            executable = shell or _windows_powershell_executable()
            if not executable:
                raise RuntimeError("PowerShell is not installed")
            base = os.path.basename(executable).lower()
            if base not in {"powershell", "powershell.exe", "pwsh", "pwsh.exe", "cmd", "cmd.exe", "bash", "bash.exe"}:
                raise ValueError("unsupported terminal shell")
            dialect = "pwsh" if "powershell" in base or "pwsh" in base else ("bash" if "bash" in base else "cmd")
            if dialect == "pwsh":
                argv = [executable, "-NoLogo", "-NoProfile", "-NoExit", "-Command",
                    ('Remove-Module PSReadLine -ErrorAction SilentlyContinue; ' if actor == "model" else '') + 'function global:prompt { '
                    # PowerShell's provider location does not normally update
                    # the process cwd. Synchronize it before publishing readiness.
                    'if ((Get-Location).Provider.Name -eq "FileSystem") { '
                    '[Environment]::CurrentDirectory = (Get-Location).ProviderPath }; '
                    f'[Console]::Write([char]27 + "]133;D;{nonce}" + [char]7); "PS " + (Get-Location).Path + "> " }}']
            elif dialect == "bash":
                env["PS1"] = f"\\[\\e]133;D;{nonce}\\a\\]\\w $ "
                argv = [executable, "--noprofile", "--norc", "-i"]
            else:
                argv = [executable, "/Q"]
            from winpty import PtyProcess
            spawn = lambda: PtyProcess.spawn(argv, cwd=cwd, env=env, dimensions=(40, 160))
        else:
            executable = shell or shutil.which("bash")
            if not executable:
                raise RuntimeError("Bash is not installed")
            base = os.path.basename(executable)
            if base not in {"bash", "sh", "zsh", "fish"}:
                raise ValueError("unsupported terminal shell")
            dialect = base
            if base == "bash":
                env["PS1"] = f"\\[\\e]133;D;{nonce}\\a\\]\\w $ "
                argv = [executable, "--noprofile", "--norc", "-i"]
            else:
                argv = [executable, "-i"]
            from ptyprocess import PtyProcessUnicode
            spawn = lambda: PtyProcessUnicode.spawn(argv, cwd=cwd, env=env, dimensions=(40, 160))
        backend = None
        try:
            starter = asyncio.create_task(asyncio.to_thread(spawn))
            try:
                backend = await asyncio.shield(starter)
            except asyncio.CancelledError:
                backend = await starter
                raise
            if (self.service._closing or owner in self.service.closed_owners
                or (actor == "model" and owner in self.service.suppressed)):
                raise RuntimeError("terminal startup was stopped")
            if permission_mode:
                from security.runtime import session_permission_mode
                if str(session_permission_mode(owner)) != permission_mode:
                    raise PermissionError("permission mode changed during terminal startup")
            screen = pyte.HistoryScreen(160, 40, history=10000)
            session = TerminalSession(uuid.uuid4().hex, owner, name or "shell", cwd, actor,
                backend, dialect, screen, pyte.Stream(screen), prompt_marker=prompt_marker, permission_mode=permission_mode,
                pid=backend.pid)
            import psutil
            try:
                session.process_created = psutil.Process(backend.pid).create_time()
            except psutil.Error:
                pass
            self.sessions[session.id] = session
            await self._persist(session)
            session.reader = asyncio.create_task(self._pump(session))
            # Initial startup output is useful, but startup never depends on
            # recognizing a prompt from an arbitrary interactive application.
            deadline = time.monotonic() + (10 if actor == "model" else 3)
            while session.prompt_count == 0 and session.status == "running" and time.monotonic() < deadline:
                await asyncio.sleep(.05)
            return {**session.public(), "motd": self.viewport(session)}
        except BaseException:
            if backend:
                await asyncio.to_thread(backend.close, True)
            raise

    async def _pump(self, session):
        io_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1,
            thread_name_prefix="terminal-io")
        loop = asyncio.get_running_loop()
        detail = "shell exited"
        try:
            while session.status == "running":
                text = await loop.run_in_executor(io_pool, session.backend.read, 8192)
                if not text:
                    # pywinpty returns an empty string for its no-data sentinel,
                    # and raises EOFError on actual EOF. Never close a live shell
                    # merely because a read found no output.
                    if getattr(session.backend, "flag_eof", False) or not await asyncio.to_thread(session.backend.isalive):
                        break
                    await asyncio.sleep(.05)
                    continue
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="replace")
                session.output.append(text.encode("utf-8"))
                await self.service.write_log(session.owner, session.id, text.encode("utf-8"))
                session.parser.feed(text)
                # Conservatively bound retained Unicode cells by their maximum
                # UTF-8 width, in addition to the 10,000-line ceiling.
                keep = max(0, min(10000, (4 * 1024 * 1024) // (session.screen.columns * 4) - session.screen.lines))
                while len(session.screen.history.top) + len(session.screen.history.bottom) > keep:
                    if session.screen.history.top:
                        session.screen.history.top.popleft()
                    else:
                        session.screen.history.bottom.pop()
                marked = session.marker_tail + text
                marker = session.prompt_marker
                prompt_count = marked.count(marker)
                session.prompt_count += prompt_count
                if prompt_count:
                    session.cwd_ready = True
                # Keep only an incomplete marker, never count a full marker twice.
                session.marker_tail = next((marked[-n:] for n in range(len(marker)-1, 0, -1)
                    if marked.endswith(marker[:n])), "")
                session.last_output = time.monotonic()
        except EOFError:
            pass
        except Exception as exc:
            detail = f"terminal read failed: {type(exc).__name__}: {exc}"
        finally:
            io_pool.shutdown(wait=False, cancel_futures=True)
            if session.status == "running":
                try:
                    alive = await asyncio.to_thread(session.backend.isalive)
                except Exception as exc:
                    alive = True
                    detail = f"terminal liveness check failed: {type(exc).__name__}: {exc}"
                if alive and detail == "shell exited":
                    detail = "terminal transport reached EOF while shell was alive; shell cleaned up"
                session.status, session.detail = "closed", detail
                session.exit_code = getattr(session.backend, "exitstatus", None)
                try:
                    if alive:
                        await asyncio.to_thread(terminate_process, session.backend, session.process_created)
                    await asyncio.to_thread(session.backend.close, True)
                finally:
                    await self._persist(session)

    @staticmethod
    def viewport(session):
        from agent_tools import redact_sensitive_tool_text
        return redact_sensitive_tool_text("\n".join(session.screen.display).rstrip())

    @staticmethod
    def _foreground_ready(session):
        if os.name == "nt":
            import psutil
            try:
                return not any(p.is_running() for p in psutil.Process(session.pid).children())
            except psutil.Error:
                return False
        try:
            if os.tcgetpgrp(session.backend.fd) != os.getpgid(session.pid):
                return False
            if platform.system() == "Linux":
                from pathlib import Path
                fields = Path(f"/proc/{session.pid}/syscall").read_text().split()
                read_syscall = 63 if platform.machine().lower() in {"aarch64", "arm64"} else 0
                return len(fields) > 1 and int(fields[0], 0) == read_syscall and int(fields[1], 0) == 0
            return True  # private prompt marker plus POSIX foreground identity
        except (OSError, ValueError):
            return False

    async def _send(self, session, text, submit=True):
        if session.status != "running":
            raise RuntimeError("terminal is closed")
        if len(text.encode("utf-8")) > 64 * 1024:
            raise ValueError("terminal input exceeds 64 KiB")
        before = session.prompt_count
        output_start = session.output.end
        expected_echo = re.sub(r"\s+", "", text)
        def prompt_after_input():
            raw, _, _ = session.output.read_at(output_start)
            received = raw.decode("utf-8", errors="replace").replace(session.prompt_marker, "\x00")
            received = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", received)
            received = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", received)
            received = re.sub(r"\s+", "", received)
            echoed = received.rfind(expected_echo) if expected_echo else 0
            return echoed >= 0 and "\x00" in received[echoed + len(expected_echo):]
        began = time.monotonic()
        try:
            session.cwd_ready = False
            await asyncio.to_thread(session.backend.write, text + ("\r" if submit else ""))
            while True:
                if session.status != "running":
                    reason = "session_exit"
                    break
                elapsed = time.monotonic() - began
                # A previous prompt can still be travelling through ConPTY
                # when this write is accepted. Require an echoed submission
                # followed by its own private prompt, then a quiet read edge.
                if (elapsed >= .15 and session.prompt_count > before
                    and time.monotonic() - session.last_output >= .15
                    and prompt_after_input() and self._foreground_ready(session)):
                    reason = "stdin_read"
                    break
                if elapsed >= 3 and time.monotonic() - session.last_output >= 3:
                    reason = "inferred_idle"
                    break
                if elapsed >= 30:
                    reason = "timeout"
                    break
                await asyncio.sleep(.05)
            session.cwd_ready = reason == "stdin_read"
            return {"kind": "foreground", "viewport": self.viewport(session),
                    "waitReason": reason, "sessionStatus": session.status,
                    "sessionDetail": session.detail, "shellExitCode": session.exit_code,
                    "terminalId": session.id, "completion_scope": "terminal_send",
                    "command_state": {"stdin_read": "shell_ready", "session_exit": "shell_exited"}.get(reason, "unknown"),
                    "truncated": session.output.begin > 0}
        except asyncio.CancelledError:
            if session.status == "running":
                try:
                    session.interruption = await self.signal(session.owner, session.id, "SIGINT", actor=session.actor)
                except Exception as exc:
                    session.interruption = {"delivered": False, "interruptVerified": False, "error": str(exc)}
            raise

    async def send(self, owner, identifier, text, submit=True, background=False):
        session = self.owned(owner, identifier)
        if session.send_task and not session.send_task.done():
            raise RuntimeError("a terminal send is already active")
        if len(text.encode("utf-8")) > 64 * 1024:
            raise ValueError("terminal input exceeds 64 KiB")
        if not background:
            session.send_job = None
            session.send_task = asyncio.create_task(self._send(session, text, submit))
            return await session.send_task
        job = await self.service.admit(owner, "pty-send", f"{identifier}: {text}", permission_mode=session.permission_mode)
        job.terminal_id = identifier
        await self.service._persist_job(job)
        session.send_job = job
        session.interruption = None
        cursor = session.output.end
        session.send_task = asyncio.create_task(self._send(session, text, submit))
        operation = session.send_task
        async def cancel():
            if not operation.done():
                operation.cancel()
        job.cancel = cancel
        async def monitor():
            import pyte
            chunks = []
            class TextScreen(pyte.Screen):
                def __init__(self):
                    super().__init__(160, 40)
                    self.pending = False
                def draw(self, value):
                    self.pending = True
                    super().draw(value)
                    self.pending = True
                def emit_line(self):
                    if self.pending:
                        chunks.append(self.display[self.cursor.y].rstrip() + "\n")
                        self.pending = False
                def linefeed(self):
                    if self.pending:
                        self.emit_line()
                    else:
                        chunks.append("\n")
                    super().linefeed()
                def index(self):
                    # Include automatically wrapped output before it scrolls.
                    self.emit_line()
                    super().index()
            screen = TextScreen()
            parser = pyte.Stream(screen)
            async def flush(final=False):
                nonlocal cursor
                raw, cursor, gap = session.output.read_at(cursor)
                if gap:
                    chunks.append("\n[terminal output truncated]\n")
                parser.feed(raw.decode("utf-8", errors="replace"))
                if final:
                    screen.emit_line()
                if chunks:
                    text = "".join(chunks)
                    chunks.clear()
                    await self.service.append(job, text.encode("utf-8"))
            try:
                while not operation.done():
                    await flush()
                    await asyncio.sleep(.1)
                result = await operation
                await flush(final=True)
                await self.service.settle(job, detail=result["waitReason"], result=result)
            except asyncio.CancelledError:
                await flush(final=True)
                receipt = session.interruption or {"interruptVerified": False}
                await self.service.settle(job, "killed", "terminal send observation cancelled; consult interruption receipt",
                    result={"terminalId": identifier, "completion_scope": "terminal_send",
                            "command_state": "shell_ready" if receipt.get("interruptVerified") else "unknown",
                            "interruption": receipt})
            except Exception as exc:
                await self.service.settle(job, "failed", str(exc))
        job.task = asyncio.create_task(monitor())
        return {"kind": "background", "jobId": job.id, "terminalId": identifier,
                "completion_scope": "terminal_send"}

    async def read(self, owner, identifier, offset=0, count=500, *, actor="model"):
        if identifier not in self.sessions:
            result = await self.history(owner, identifier, actor=actor)
            lines = result["text"].splitlines()
            end = max(0, len(lines) - max(0, int(offset)))
            begin = max(0, end - max(1, min(int(count), 10000)))
            return {**result, "text": "\n".join(lines[begin:end]), "totalLines": len(lines),
                    "lineBegin": begin, "lineEnd": end}
        session = self.owned(owner, identifier, actor)
        history = session.screen.history.top
        plain = ["".join(row.get(col).data if row.get(col) is not None else " "
                         for col in range(session.screen.columns)).rstrip() for row in history]
        plain.extend(session.screen.display)
        while plain and not plain[-1].strip():
            plain.pop()
        total = len(plain)
        end = max(0, total - max(0, int(offset)))
        begin = max(0, end - min(max(1, int(count)), 10000))
        from agent_tools import redact_sensitive_tool_text
        raw = "\n".join(plain[begin:end]).encode("utf-8")
        return {"text": redact_sensitive_tool_text(raw[-OUTPUT_LIMIT:].decode("utf-8", errors="replace")),
                "totalLines": total, "lineBegin": begin, "lineEnd": end,
                "truncated": begin > 0 or len(raw) > OUTPUT_LIMIT}

    async def history(self, owner, identifier, *, actor="user"):
        if actor not in {"user", "model"}:
            raise ValueError("invalid terminal actor")
        session = self.sessions.get(identifier)
        if session:
            return await self.read(owner, identifier, actor=actor)
        store = self.service._store()
        if store is None:
            raise ValueError("terminal not found")
        row = await asyncio.to_thread(store.get, owner, "execution-tools", "terminal." + identifier)
        value = row.get("value") or {}
        if value.get("owner") != owner or value.get("actor") != actor or value.get("id") != identifier:
            raise ValueError("terminal not found")
        path = self.service._path(owner, identifier)
        def tail():
            file = path / "output.bin"
            if not file.is_file():
                return ""
            with file.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - OUTPUT_LIMIT))
                return stream.read(OUTPUT_LIMIT).decode("utf-8", errors="replace")
        import re
        text = await asyncio.to_thread(tail)
        text = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", text)
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        from agent_tools import redact_sensitive_tool_text
        return {"text": redact_sensitive_tool_text(text), "status": value.get("status"), "truncated": True}

    async def signal(self, owner, identifier, name, *, actor="model"):
        session = self.owned(owner, identifier, actor)
        if session.status != "running":
            raise RuntimeError("terminal is closed")
        allowed = {"SIGINT", "SIGTERM", "SIGKILL", "SIGTSTP", "SIGHUP"}
        if name not in allowed:
            raise ValueError("unsupported signal")
        if name == "SIGINT":
            before = session.prompt_count
            children = []
            if os.name == "nt":
                shell = self._windows_shell(session)
                # Capture before Ctrl+C so a later command cannot become the
                # fallback target. Process objects retain creation-time checks.
                children = await asyncio.to_thread(shell.children, recursive=True)
            delivered, delivery_error = True, None
            try:
                await asyncio.to_thread(session.backend.write, "\x03")
            except (OSError, EOFError) as exc:
                delivered, delivery_error = False, str(exc)
            method = "pty_ctrl_c"
            deadline = time.monotonic() + 2
            verified = False
            while session.status == "running" and time.monotonic() < deadline:
                if session.prompt_count > before and self._foreground_ready(session):
                    verified = True
                    session.cwd_ready = True
                    break
                await asyncio.sleep(.05)
            receipt = {"delivered": delivered, "method": method, "interruptVerified": verified,
                       "verification": "shell_ready" if verified else "not_observed",
                       "sessionStatus": session.status}
            if delivery_error:
                receipt["delivery_error"] = delivery_error
            if os.name == "nt" and not verified and session.status == "running":
                self._windows_shell(session)
                if children:
                    fallback = await self._terminate_windows_children(session, children, "SIGTERM")
                    # Exiting the children is not enough to establish shell
                    # readiness. Keep the same shell and require its new prompt.
                    deadline = time.monotonic() + 1
                    while time.monotonic() < deadline and session.status == "running":
                        if session.prompt_count > before and self._foreground_ready(session):
                            verified = fallback["interruptVerified"]
                            if verified:
                                session.cwd_ready = True
                            break
                        await asyncio.sleep(.05)
                    receipt.update(delivered=delivered or fallback["delivered"],
                        method="pty_ctrl_c_then_terminate_owned_children", forced=True,
                        interruptVerified=verified,
                        verification="foreground_processes_exited" if verified else "not_observed",
                        ctrlCVerified=False, fallback=fallback, shellPreserved=fallback["shellPreserved"], sessionStatus=session.status)
                else:
                    receipt.update(reason="no_owned_child_processes", shellPreserved=True,
                        next_action="Observe again or explicitly terminal_close to stop an in-process shell command. No shell termination or replacement was performed.")
            session.interruption = receipt
            return receipt
        if os.name == "nt":
            if name not in {"SIGTERM", "SIGKILL"}:
                raise ValueError(f"{name} is not supported on Windows")
            shell = self._windows_shell(session)
            children = shell.children(recursive=True)
            if not children:
                raise ValueError("shell-targeted signal refused; use terminal_close")
            return await self._terminate_windows_children(session, children, name)
        pgid = os.tcgetpgrp(session.backend.fd)
        if pgid == os.getpgid(session.pid):
            raise ValueError("shell-targeted signal refused; use terminal_close")
        os.killpg(pgid, getattr(signal, name))
        return {"delivered": True, "targetPgid": pgid, "interruptVerified": False,
                "verification": "not_observed", "sessionStatus": session.status}

    @staticmethod
    def _windows_shell(session):
        import psutil
        shell = psutil.Process(session.pid)
        if not session.process_created or abs(shell.create_time() - session.process_created) >= .01:
            raise RuntimeError("terminal process identity changed")
        return shell

    async def _terminate_windows_children(self, session, children, name):
        import psutil
        self._windows_shell(session)
        def terminate():
            errors = []
            for child in reversed(children):
                try:
                    child.kill() if name == "SIGKILL" else child.terminate()
                except psutil.NoSuchProcess:
                    pass
                except psutil.Error as exc:
                    errors.append({"pid": child.pid, "error": str(exc)})
            _, alive = psutil.wait_procs(children, timeout=2)
            return errors, alive
        errors, alive = await asyncio.to_thread(terminate)
        shell = self._windows_shell(session)
        preserved = shell.is_running() and session.status == "running"
        verified = not alive and not errors and preserved
        return {"delivered": not errors, "interruptVerified": verified,
                "verification": "foreground_processes_exited" if verified else "not_observed",
                "method": "terminate_owned_child_process_tree", "forced": True,
                "targetPids": [child.pid for child in children], "errors": errors,
                "shellPreserved": preserved, "sessionStatus": session.status}

    async def close(self, owner, identifier, *, actor="model"):
        session = self.owned(owner, identifier, actor)
        if session.status == "running":
            session.status, session.detail = "closed", "terminal closed"
            if session.send_job and not session.send_job.done.is_set():
                session.send_job.notice_suppressed = True
            if session.send_task and not session.send_task.done():
                session.send_task.cancel()
            await asyncio.to_thread(terminate_process, session.backend, session.process_created)
            await asyncio.to_thread(session.backend.close, True)
            if session.reader:
                try:
                    await asyncio.wait_for(asyncio.shield(session.reader), 3)
                except asyncio.TimeoutError:
                    session.reader.cancel()
            await self._persist(session)
        return session.public()

    async def list(self, owner, *, actor="model"):
        await self.service.recover(owner)
        result = [s.public() for s in self.sessions.values() if s.owner == owner and s.actor == actor]
        store = self.service._store()
        if store:
            state = await asyncio.to_thread(store.read_all_lightweight, owner)
            present = {s["id"] for s in result}
            for key, row in (state.get("execution-tools") or {}).items():
                value = row.get("value") or {}
                if key.startswith("terminal.") and value.get("owner") == owner and value.get("actor") == actor and value.get("id") not in present:
                    result.append(value)
        return result

    async def stream(self, owner, identifier, offset, connection, *, claim=False):
        session = self.owned(owner, identifier, "user")
        if claim:
            session.connection = connection
        raw, next_offset, gap = session.output.read_at(offset)
        return {"text": raw.decode("utf-8", errors="replace"), "offset": next_offset,
                "truncated": gap, "status": session.status,
                "viewport": self.viewport(session) if gap else ""}

    async def input(self, owner, identifier, text, connection):
        session = self.owned(owner, identifier, "user")
        if not connection or session.connection != connection:
            raise PermissionError("this browser connection does not control the terminal")
        if session.status != "running":
            raise RuntimeError("terminal is closed")
        if len(text.encode("utf-8")) > 64 * 1024:
            raise ValueError("terminal input exceeds 64 KiB")
        await asyncio.to_thread(session.backend.write, text)

    async def resize(self, owner, identifier, rows, cols, connection):
        session = self.owned(owner, identifier, "user")
        if not connection or session.connection != connection:
            raise PermissionError("this browser connection does not control the terminal")
        rows, cols = max(2, min(int(rows), 200)), max(20, min(int(cols), 500))
        await asyncio.to_thread(session.backend.setwinsize, rows, cols)
        session.screen.resize(rows, cols)

    async def stop_owner(self, owner, *, close=False):
        openings = [task for task, (sid, actor) in tuple(self.openings.items())
                    if sid == owner and (close or actor == "model")]
        for task in openings:
            task.cancel()
        if openings:
            await asyncio.gather(*openings, return_exceptions=True)
        for session in tuple(self.sessions.values()):
            if session.owner == owner and (close or session.actor == "model"):
                if close:
                    await self.close(owner, session.id, actor=session.actor)
                elif session.send_task and not session.send_task.done():
                    session.send_task.cancel()
                elif session.actor == "model" and session.status == "running":
                    # A send can finish with inferred_idle while its command
                    # remains in the foreground. Stop still interrupts it.
                    await self.signal(owner, session.id, "SIGINT")

    async def shutdown(self):
        openings = list(self.openings)
        for task in openings:
            task.cancel()
        if openings:
            await asyncio.gather(*openings, return_exceptions=True)
        for session in tuple(self.sessions.values()):
            await self.close(session.owner, session.id, actor=session.actor)


def terminal_manager(service):
    if service.terminals is None:
        service.terminals = TerminalManager(service)
    return service.terminals
