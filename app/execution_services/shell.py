"""Bridge the existing authorized shell preparation to owned process jobs."""
from __future__ import annotations

import asyncio
import inspect
import time


def jobs_enabled():
    from plugins.host import bundled_host_plugin_enabled
    return bundled_host_plugin_enabled("execution-tools")


async def execute_prepared(prepared, cwd, spawn_kw, command, timeout, background,
                           cleanup_paths, active, sink=None, interrupt_check=None):
    from .jobs import execution_service, JobLimitReached
    from agent_tools import (_decode_cli_subprocess_bytes, _truncate_output,
        _summarize_shell_stream_if_binary_like, _run_cli_stderr_hints,
        redact_sensitive_tool_text, _RunShellProgressPublisher, _run_shell_stream_max_chars,
        _run_shell_state_sink)

    service = execution_service()
    owner = str(active["session_id"])
    spec = {"argv": list(prepared.argv), "env": dict(prepared.env), "cwd": str(cwd),
            "spawn_kw": spawn_kw, "label": command,
            "permission_mode": str(active["context"].mode),
            "cleanup_paths": [str(p) for p in cleanup_paths]}
    # The service owns temporary scripts until the process actually settles.
    try:
        identifier = await service.call(service.spawn_process, owner, spec, visible=background)
    except JobLimitReached:
        if background:
            raise
        # DSH falls back to ordinary bounded foreground execution when its
        # jobs registry cannot admit another operation. Nothing was spawned.
        return None
    cleanup_paths.clear()
    began = time.monotonic()
    async def report(status, result, snapshot):
        sink = _run_shell_state_sink.get()
        if sink is None:
            return
        payload = {"status": status, "result": result, "executed": True,
            "process_state": "stopped" if snapshot["done"] else "running",
            "exit_code": snapshot["job"]["exit_code"], "job_id": identifier,
            "duration_ms": int((time.monotonic() - began) * 1000),
            **{name: redact_sensitive_tool_text(_decode_cli_subprocess_bytes(snapshot[name]))
               for name in ("stdout", "stderr")}}
        outcome = sink(payload)
        if inspect.isawaitable(outcome):
            await outcome
    deadline = time.monotonic() + timeout
    publisher = _RunShellProgressPublisher(sink, max_chars=_run_shell_stream_max_chars())
    emitted = {"stdout": b"", "stderr": b""}
    emitted_text = {"stdout": "", "stderr": ""}
    try:
        snapshot = await service.call(service.foreground_snapshot, identifier)
        if background:
            text = f"started background job {identifier}\nCollect with job_output(job_id=\"{identifier}\")."
            await report("running" if not snapshot["done"] else snapshot["job"]["status"], text, snapshot)
            return text
        await report("running", "", snapshot)
        while True:
            snapshot = await service.call(service.foreground_snapshot, identifier)
            if sink:
                for name in emitted:
                    raw = snapshot[name]
                    previous = emitted[name]
                    delta = raw[len(previous):] if raw.startswith(previous) else raw
                    if delta:
                        prev_text = emitted_text[name]
                        # 优先解码“整段累计字节”再取新增文本差：避免按任意字节切片解码把多字节字符劈开；
                        # 超过 1MB 的巨量输出退回按片解码，控制每轮快照的解码开销。
                        full_text = (
                            _decode_cli_subprocess_bytes(raw) if len(raw) <= 1048576 else None
                        )
                        if full_text is not None and full_text.startswith(prev_text):
                            piece = full_text[len(prev_text):]
                            emitted_text[name] = full_text
                        else:
                            piece = _decode_cli_subprocess_bytes(delta)
                            emitted_text[name] = prev_text + piece
                        if piece:
                            await publisher.push(name, piece)
                    emitted[name] = raw
            if snapshot["done"]:
                break
            if interrupt_check and interrupt_check():
                await service.call(service.foreground_snapshot, identifier, promote=True)
                await service.call(service.kill, owner, identifier, "run interrupted")
                raise asyncio.CancelledError()
            if time.monotonic() >= deadline:
                snapshot = await service.call(service.foreground_snapshot, identifier, promote=True)
                text = f"Command still running; promoted to background job {identifier}\nCollect with job_output(job_id=\"{identifier}\")."
                await report("running" if not snapshot["done"] else snapshot["job"]["status"], text, snapshot)
                return text
            await asyncio.sleep(.1)
    except BaseException as exc:
        await service.call(service.foreground_snapshot, identifier, promote=True)
        await service.call(service.kill, owner, identifier, "foreground call interrupted")
        snapshot = await service.call(service.foreground_snapshot, identifier)
        await report("interrupted" if isinstance(exc, asyncio.CancelledError) else "failed",
            redact_sensitive_tool_text(_decode_cli_subprocess_bytes(snapshot["stdout"]) +
                _decode_cli_subprocess_bytes(snapshot["stderr"])), snapshot)
        raise
    finally:
        await publisher.close()
    parts = []
    for name in ("stdout", "stderr"):
        raw = snapshot[name]
        text = _truncate_output(_summarize_shell_stream_if_binary_like(
            _decode_cli_subprocess_bytes(raw), raw, name))
        if text.strip():
            if snapshot["truncated"][name]:
                text = "[output truncated; earlier bytes unavailable]\n" + text
            parts.append(("STDERR:\n" if name == "stderr" else "") + text)
    job = snapshot["job"]
    if job["status"] == "failed":
        parts.append("Error executing command: " + job["detail"])
    parts.append(f"Exit code: {job['exit_code']}")
    hint = _run_cli_stderr_hints(command, _decode_cli_subprocess_bytes(snapshot["stderr"]), job["exit_code"] or 0)
    if hint:
        parts.append(hint)
    result = redact_sensitive_tool_text("\n".join(parts))
    await report("completed" if job["exit_code"] == 0 else "failed", result, snapshot)
    await service.call(service.release_foreground, identifier)
    return result
