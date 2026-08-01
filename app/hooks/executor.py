"""Isolated command hook execution."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .models import HOOK_DECISIONS, HookDefinition, HookExecutionError, HookExecutionResult


_BASE_ENV_WINDOWS = (
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
)
_BASE_ENV_POSIX = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "SHELL")


def _replace_roots(value: str, definition: HookDefinition, project_root: Path) -> str:
    plugin_root = str(definition.source_root)
    replacements = {
        "${PLUGIN_ROOT}": plugin_root,
        "$PLUGIN_ROOT": plugin_root,
        "${MYAGENT_PLUGIN_ROOT}": plugin_root,
        "$MYAGENT_PLUGIN_ROOT": plugin_root,
        "${CLAUDE_PLUGIN_ROOT}": plugin_root,
        "$CLAUDE_PLUGIN_ROOT": plugin_root,
        "${CODEX_PLUGIN_ROOT}": plugin_root,
        "$CODEX_PLUGIN_ROOT": plugin_root,
        "${MYAGENT_PROJECT_ROOT}": str(project_root),
        "$MYAGENT_PROJECT_ROOT": str(project_root),
    }
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    return value


def build_hook_environment(
    definition: HookDefinition,
    project_root: Path,
    *,
    source_environment: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Build a minimal, explicit environment for a command hook."""

    source = source_environment if source_environment is not None else os.environ
    names = _BASE_ENV_WINDOWS if os.name == "nt" else _BASE_ENV_POSIX
    if os.name == "nt":
        # ``os.environ`` is case-insensitive on Windows, but callers often pass
        # a plain dict snapshot which is not. Preserve Windows semantics so
        # essentials such as SYSTEMROOT cannot disappear due to key casing.
        lookup = {str(key).upper(): value for key, value in source.items()}

        def source_value(name: str) -> Optional[Any]:
            return lookup.get(name.upper())
    else:
        def source_value(name: str) -> Optional[Any]:
            return source.get(name)

    env: Dict[str, str] = {}
    for name in names:
        value = source_value(name)
        if value is not None:
            env[name] = str(value)
    for name in definition.command.env_allowlist:
        value = source_value(name)
        if value is not None:
            env[name] = str(value)
    env.update({str(key): str(value) for key, value in definition.command.env.items()})
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "MYAGENT_PROJECT_ROOT": str(project_root),
            "MYAGENT_HOOK_EVENT": definition.event,
            "MYAGENT_HOOK_ID": definition.id,
            "MYAGENT_HOOK_SOURCE": definition.source_id,
            "MYAGENT_PLUGIN_ROOT": str(definition.source_root),
            # Compatibility aliases let imported declarative hook packages use
            # their existing root-relative command strings without inheriting
            # any additional host environment.
            "CLAUDE_PLUGIN_ROOT": str(definition.source_root),
            "CODEX_PLUGIN_ROOT": str(definition.source_root),
        }
    )
    if definition.plugin_id:
        env["MYAGENT_PLUGIN_ID"] = definition.plugin_id
    return env


def _nested_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _parse_hook_output(parsed: Mapping[str, Any]) -> Dict[str, Any]:
    specific = _nested_mapping(parsed.get("hookSpecificOutput"))
    decision = parsed.get("decision", specific.get("permissionDecision"))
    if decision is None and parsed.get("continue") is False:
        decision = "deny"
    decision = str(decision or "continue").strip().lower()
    if decision not in HOOK_DECISIONS:
        raise HookExecutionError(
            f"Hook returned unsupported decision {decision!r}; expected one of {sorted(HOOK_DECISIONS)}."
        )
    updated = parsed.get("updated_input", parsed.get("updatedInput", specific.get("updatedInput")))
    if updated is not None and not isinstance(updated, Mapping):
        raise HookExecutionError("updated_input must be a JSON object.")
    additional_context = parsed.get(
        "additional_context",
        parsed.get("additionalContext", specific.get("additionalContext", "")),
    )
    user_message = parsed.get("user_message", parsed.get("userMessage", parsed.get("systemMessage", "")))
    reason = parsed.get(
        "reason",
        specific.get("permissionDecisionReason", parsed.get("stopReason", "")),
    )
    return {
        "decision": decision,
        "updated_input": dict(updated) if isinstance(updated, Mapping) else None,
        "additional_context": str(additional_context or ""),
        "user_message": str(user_message or ""),
        "reason": str(reason or ""),
    }


class CommandHookExecutor:
    """Execute command hooks with JSON stdin/stdout and bounded runtime."""

    def __init__(
        self,
        project_root: Any,
        *,
        source_environment: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.source_environment = source_environment

    def _cwd(self, definition: HookDefinition) -> Path:
        raw_cwd = definition.command.cwd
        if not raw_cwd:
            return definition.source_root
        expanded = _replace_roots(raw_cwd, definition, self.project_root)
        path = Path(expanded).expanduser()
        if not path.is_absolute():
            path = definition.source_root / path
        path = path.resolve()
        if not path.is_dir():
            raise HookExecutionError(f"Hook working directory does not exist: {path}")
        return path

    @staticmethod
    async def _terminate_process(process: asyncio.subprocess.Process) -> None:
        """Terminate the shell and its child tree without an unbounded wait."""

        if process.returncode is not None:
            return
        try:
            if os.name == "nt":
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                await asyncio.wait_for(killer.wait(), timeout=2.0)
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except Exception:
            try:
                process.kill()
            except ProcessLookupError:
                pass

    async def execute(
        self,
        definition: HookDefinition,
        payload: Mapping[str, Any],
    ) -> HookExecutionResult:
        started = time.perf_counter()
        command = definition.command.platform_command()
        if not command:
            return self._failure(definition, started, "No command is configured for this platform.")
        command = _replace_roots(command, definition, self.project_root)
        try:
            workspace_root = str(payload.get("workspace_root") or "").strip()
            worktree_isolated = bool(payload.get("worktree_isolated"))
            if workspace_root and worktree_isolated:
                cwd = Path(workspace_root).expanduser().resolve()
                if not cwd.is_dir():
                    raise HookExecutionError(
                        f"Hook worktree directory does not exist: {cwd}"
                    )
            else:
                cwd = self._cwd(definition)
            stdin_data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
            env = build_hook_environment(
                definition,
                self.project_root,
                source_environment=self.source_environment,
            )
            if workspace_root:
                env["MYAGENT_WORKSPACE_ROOT"] = workspace_root
                env["MYAGENT_WORKTREE_ISOLATED"] = "1" if worktree_isolated else "0"
            kwargs: Dict[str, Any] = {}
            if os.name == "nt":
                kwargs["creationflags"] = (
                    getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                )
            else:
                kwargs["start_new_session"] = True
            if os.name == "nt":
                shell_argv = [
                    os.environ.get("COMSPEC", "cmd.exe"),
                    "/d",
                    "/s",
                    "/c",
                    command,
                ]
            else:
                shell_argv = ["/bin/sh", "-c", command]
            if os.name == "nt":
                process = await asyncio.create_subprocess_shell(
                    command,
                    executable=os.environ.get("COMSPEC", "cmd.exe"),
                    cwd=str(cwd),
                    env=env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **kwargs,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *shell_argv,
                    cwd=str(cwd),
                    env=env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **kwargs,
                )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(stdin_data),
                    timeout=definition.command.timeout_seconds,
                )
            except asyncio.TimeoutError:
                await self._terminate_process(process)
                return self._failure(
                    definition,
                    started,
                    f"Hook timed out after {definition.command.timeout_seconds:g} seconds.",
                    outcome="timed_out",
                )
            except asyncio.CancelledError:
                await self._terminate_process(process)
                raise

            stderr_text = stderr.decode("utf-8", errors="replace")[-16384:]
            if process.returncode:
                return self._failure(
                    definition,
                    started,
                    f"Hook command exited with code {process.returncode}.",
                    exit_code=process.returncode,
                    stderr=stderr_text,
                )
            if len(stdout) > definition.command.max_output_bytes:
                return self._failure(
                    definition,
                    started,
                    f"Hook stdout exceeded {definition.command.max_output_bytes} bytes.",
                    exit_code=process.returncode,
                    stderr=stderr_text,
                )
            output = stdout.decode("utf-8-sig", errors="replace").strip()
            if output:
                try:
                    parsed = json.loads(output)
                except json.JSONDecodeError as exc:
                    return self._failure(
                        definition,
                        started,
                        f"Hook stdout is not valid JSON: {exc.msg}.",
                        exit_code=process.returncode,
                        stderr=stderr_text,
                    )
                if not isinstance(parsed, Mapping):
                    return self._failure(
                        definition,
                        started,
                        "Hook stdout JSON must be an object.",
                        exit_code=process.returncode,
                        stderr=stderr_text,
                    )
            else:
                parsed = {}
            try:
                values = _parse_hook_output(parsed)
            except HookExecutionError as exc:
                return self._failure(
                    definition,
                    started,
                    str(exc),
                    exit_code=process.returncode,
                    stderr=stderr_text,
                )
            return HookExecutionResult(
                hook_id=definition.id,
                event=definition.event,
                source_id=definition.source_id,
                plugin_id=definition.plugin_id,
                success=True,
                outcome="success",
                duration_ms=int((time.perf_counter() - started) * 1000),
                exit_code=process.returncode,
                stderr=stderr_text,
                failure_policy=definition.failure_policy,
                **values,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return self._failure(definition, started, str(exc))

    @staticmethod
    def _failure(
        definition: HookDefinition,
        started: float,
        error: str,
        *,
        outcome: str = "failed",
        exit_code: Optional[int] = None,
        stderr: str = "",
    ) -> HookExecutionResult:
        return HookExecutionResult(
            hook_id=definition.id,
            event=definition.event,
            source_id=definition.source_id,
            plugin_id=definition.plugin_id,
            success=False,
            outcome=outcome,
            decision="continue",
            duration_ms=int((time.perf_counter() - started) * 1000),
            exit_code=exit_code,
            stderr=stderr,
            error=error,
            failure_policy=definition.failure_policy,
        )
