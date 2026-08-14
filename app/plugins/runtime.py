"""Persistent host runtime for executable Plugin API v1 capabilities."""
from __future__ import annotations

import atexit
import copy
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .models import PluginDefinition


_FUNCTION_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")
_MAX_FUNCTION_NAME = 64


class PluginRuntimeError(RuntimeError):
    """Raised when a plugin worker cannot describe or invoke a capability."""


@dataclass(frozen=True)
class RuntimeToolBinding:
    function_name: str
    plugin_id: str
    local_name: str
    plugin_signature: str
    contract: Mapping[str, Any]


def runtime_tool_name(plugin_id: str, local_name: str) -> str:
    """Return a stable OpenAI-compatible function name."""

    plugin_part = _FUNCTION_SAFE_RE.sub("_", str(plugin_id or "")).strip("_") or "plugin"
    local_part = _FUNCTION_SAFE_RE.sub("_", str(local_name or "")).strip("_") or "tool"
    candidate = f"plugin_{plugin_part}__{local_part}"
    if len(candidate) <= _MAX_FUNCTION_NAME:
        return candidate
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:10]
    return f"{candidate[:_MAX_FUNCTION_NAME - 11]}_{digest}"


class _PersistentPluginWorker:
    """One line-delimited JSON-RPC process owned by one plugin signature."""

    def __init__(self, plugin: PluginDefinition) -> None:
        self.plugin = plugin
        self._process: Optional[subprocess.Popen[str]] = None
        self._responses: "queue.Queue[Any]" = queue.Queue()
        self._request_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._stderr_tail: "deque[str]" = deque(maxlen=100)
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

    @staticmethod
    def _worker_path(runtime_type: str) -> Path:
        filename = "worker.py" if runtime_type == "python" else "worker_node.cjs"
        return Path(__file__).resolve().with_name(filename)

    def _command_and_environment(self) -> tuple[list[str], Dict[str, str]]:
        runtime = self.plugin.runtime
        if runtime is None:
            raise PluginRuntimeError(
                f"Plugin {self.plugin.plugin_id!r} has no executable runtime"
            )
        from security.extensions import minimal_extension_environment

        permissions = dict(self.plugin.permissions or {})
        raw_allow = permissions.get("env_allowlist") or permissions.get("environment_allowlist") or []
        allow_names = (
            [str(item) for item in raw_allow]
            if isinstance(raw_allow, (list, tuple))
            else []
        )
        raw_explicit = permissions.get("env") or permissions.get("environment") or {}
        explicit = raw_explicit if isinstance(raw_explicit, Mapping) else {}
        env = minimal_extension_environment(
            allow_names=allow_names,
            explicit=explicit,
        )
        app_dir = str(Path(__file__).resolve().parent.parent)
        existing_pythonpath = str(env.get("PYTHONPATH") or "")
        env["PYTHONPATH"] = (
            app_dir + os.pathsep + existing_pythonpath
            if existing_pythonpath
            else app_dir
        )
        env.setdefault("PYTHONUTF8", "1")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if runtime.runtime_type == "python":
            runtime_root = self.plugin.root / ".myagent-runtime" / "python"
            venv_python = (
                runtime_root / "Scripts" / "python.exe"
                if os.name == "nt"
                else runtime_root / "bin" / "python"
            )
            python_command = str(venv_python) if venv_python.is_file() else sys.executable
            command = [
                python_command,
                "-B",
                "-u",
                str(self._worker_path(runtime.runtime_type)),
            ]
        elif runtime.runtime_type == "node":
            bun_command = (
                shutil.which("bun") if runtime.adapter == "opencode" else None
            )
            node_command = bun_command or shutil.which("node")
            if not node_command:
                raise PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} requires Node.js but `node` was not found"
                )
            if runtime.entrypoint.suffix.lower() in {".ts", ".tsx"} and not bun_command:
                raise PluginRuntimeError(
                    f"OpenCode TypeScript plugin {self.plugin.plugin_id!r} requires Bun"
                )
            command = [node_command, str(self._worker_path(runtime.runtime_type))]
        else:
            raise PluginRuntimeError(
                f"Plugin {self.plugin.plugin_id!r} runtime "
                f"{runtime.runtime_type!r} is unsupported"
            )
        command.extend(
            [
                "--plugin-root",
                str(self.plugin.root),
                "--entrypoint",
                str(runtime.entrypoint),
                "--adapter",
                runtime.adapter,
            ]
        )
        return command, env

    def _stdout_reader(self, process: subprocess.Popen[str]) -> None:
        stream = process.stdout
        if stream is None:
            self._responses.put(
                PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker has no stdout channel"
                )
            )
            return
        try:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    self._responses.put(
                        PluginRuntimeError(
                            f"Plugin {self.plugin.plugin_id!r} worker returned invalid JSON"
                        )
                    )
                    continue
                self._responses.put(response)
        finally:
            self._responses.put(
                PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker exited unexpectedly"
                )
            )

    def _stderr_reader(self, process: subprocess.Popen[str]) -> None:
        stream = process.stderr
        if stream is None:
            return
        for line in stream:
            text = line.rstrip()
            if text:
                self._stderr_tail.append(text)

    def start(self) -> None:
        with self._state_lock:
            if self._process is not None and self._process.poll() is None:
                return
            # A previous worker may have exited after placing its terminal
            # sentinel in the queue. Never let that stale response poison a
            # newly started process.
            while True:
                try:
                    self._responses.get_nowait()
                except queue.Empty:
                    break
            command, env = self._command_and_environment()
            kwargs: Dict[str, Any] = {}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    cwd=str(self.plugin.root),
                    env=env,
                    **kwargs,
                )
            except OSError as exc:
                raise PluginRuntimeError(
                    f"Cannot start plugin {self.plugin.plugin_id!r} worker: {exc}"
                ) from exc
            self._process = process
            self._stdout_thread = threading.Thread(
                target=self._stdout_reader,
                args=(process,),
                name=f"plugin-{self.plugin.plugin_id}-stdout",
                daemon=True,
            )
            self._stderr_thread = threading.Thread(
                target=self._stderr_reader,
                args=(process,),
                name=f"plugin-{self.plugin.plugin_id}-stderr",
                daemon=True,
            )
            self._stdout_thread.start()
            self._stderr_thread.start()

    def request(self, method: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        runtime = self.plugin.runtime
        if runtime is None:
            raise PluginRuntimeError(
                f"Plugin {self.plugin.plugin_id!r} has no executable runtime"
            )
        with self._request_lock:
            self.start()
            process = self._process
            if process is None or process.stdin is None or process.poll() is not None:
                raise PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker is not running"
                )
            request_id = uuid.uuid4().hex
            payload = {
                "id": request_id,
                "method": str(method),
                "params": dict(params or {}),
            }
            try:
                process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self.terminate()
                raise PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker pipe failed"
                ) from exc
            try:
                response = self._responses.get(timeout=runtime.timeout_seconds)
            except queue.Empty as exc:
                self.terminate()
                raise PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker timed out after "
                    f"{runtime.timeout_seconds:g}s"
                ) from exc
            if isinstance(response, Exception):
                detail = "\n".join(self._stderr_tail)[-4096:]
                self.terminate()
                raise PluginRuntimeError(
                    f"{response}{': ' + detail if detail else ''}"
                )
            if not isinstance(response, dict):
                self.terminate()
                raise PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker response must be an object"
                )
            if not response.get("ok"):
                error = response.get("error")
                message = (
                    str(error.get("message") or error.get("type") or "unknown error")
                    if isinstance(error, dict)
                    else str(error or "unknown error")
                )
                raise PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker failed: {message}"
                )
            if response.get("id") != request_id:
                self.terminate()
                raise PluginRuntimeError(
                    f"Plugin {self.plugin.plugin_id!r} worker response id mismatch"
                )
            return response.get("result")

    @property
    def pid(self) -> Optional[int]:
        process = self._process
        return process.pid if process is not None and process.poll() is None else None

    def terminate(self) -> None:
        with self._state_lock:
            process = self._process
            self._process = None
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=2)
                except Exception:
                    pass
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass
        current = threading.current_thread()
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None and thread is not current and thread.is_alive():
                thread.join(timeout=1)
        while True:
            try:
                self._responses.get_nowait()
            except queue.Empty:
                break

    def close(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            try:
                self.request("plugin.shutdown", {})
                process.wait(timeout=2)
            except Exception:
                pass
        self.terminate()


class PluginRuntimeRegistry:
    """Discover and invoke tools, hooks, and commands in persistent workers."""

    def __init__(self, *, enforce_trust: bool = False) -> None:
        self._lock = threading.RLock()
        # Keep the registry reusable as a low-level runtime component for
        # compatibility tooling and tests. The application-owned singleton is
        # trust-gated below, before any plugin worker can execute describe().
        self._enforce_trust = bool(enforce_trust)
        self._describe_cache: Dict[Tuple[str, str], Mapping[str, Any]] = {}
        self._workers: Dict[Tuple[str, str], _PersistentPluginWorker] = {}
        self._tool_bindings: Dict[str, RuntimeToolBinding] = {}
        self._errors_by_plugin: Dict[str, str] = {}

    @property
    def errors(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(self._errors_by_plugin[key] for key in sorted(self._errors_by_plugin))

    def _close_workers(self, workers: Iterable[_PersistentPluginWorker]) -> None:
        for worker in workers:
            worker.close()

    def invalidate(self) -> None:
        with self._lock:
            workers = tuple(self._workers.values())
            self._describe_cache.clear()
            self._workers.clear()
            self._tool_bindings.clear()
            self._errors_by_plugin.clear()
        self._close_workers(workers)

    close = invalidate

    def _synchronise_workers(
        self, plugins: Sequence[PluginDefinition]
    ) -> Dict[Tuple[str, str], _PersistentPluginWorker]:
        active = {
            (plugin.plugin_id, plugin.content_signature): plugin
            for plugin in plugins
            if plugin.runtime is not None
        }
        stale_keys = [key for key in self._workers if key not in active]
        stale_workers = [self._workers.pop(key) for key in stale_keys]
        for key in stale_keys:
            self._describe_cache.pop(key, None)
        for plugin_id in set(self._errors_by_plugin) - {key[0] for key in active}:
            self._errors_by_plugin.pop(plugin_id, None)
        for key, plugin in active.items():
            self._workers.setdefault(key, _PersistentPluginWorker(plugin))
        self._close_workers(stale_workers)
        return {key: self._workers[key] for key in active}

    @staticmethod
    def _validate_description(
        plugin: PluginDefinition, result: Any
    ) -> Mapping[str, Any]:
        if not isinstance(result, dict) or str(result.get("api_version") or "") != "1":
            raise PluginRuntimeError(
                f"Plugin {plugin.plugin_id!r} returned an incompatible API description"
            )
        for field in ("tools", "hooks", "commands"):
            if not isinstance(result.get(field), list):
                raise PluginRuntimeError(
                    f"Plugin {plugin.plugin_id!r} description has no {field} array"
                )
        return copy.deepcopy(result)

    def _capabilities(
        self, plugins: Sequence[PluginDefinition]
    ) -> Dict[str, tuple[PluginDefinition, Mapping[str, Any]]]:
        workers = self._synchronise_workers(plugins)
        result: Dict[str, tuple[PluginDefinition, Mapping[str, Any]]] = {}
        for plugin in sorted(plugins, key=lambda item: item.plugin_id):
            if plugin.runtime is None:
                continue
            key = (plugin.plugin_id, plugin.content_signature)
            try:
                if self._enforce_trust:
                    from security.extensions import (
                        extension_registration_is_approved,
                        plugin_descriptor,
                    )

                    if not extension_registration_is_approved(plugin_descriptor(plugin)):
                        self._errors_by_plugin[plugin.plugin_id] = (
                            "Plugin registration is not approved, or its content changed; "
                            "approve the current digest in Security settings before it can start."
                        )
                        continue
                description = self._describe_cache.get(key)
                if description is None:
                    description = self._validate_description(
                        plugin,
                        workers[key].request("plugin.describe", {}),
                    )
                    self._describe_cache[key] = description
                result[plugin.plugin_id] = (plugin, description)
                self._errors_by_plugin.pop(plugin.plugin_id, None)
            except PluginRuntimeError as exc:
                self._errors_by_plugin[plugin.plugin_id] = str(exc)
        return result

    def tool_definitions(
        self, plugins: Iterable[PluginDefinition]
    ) -> list[Dict[str, Any]]:
        plugin_rows = tuple(plugins)
        with self._lock:
            definitions: list[Dict[str, Any]] = []
            bindings: Dict[str, RuntimeToolBinding] = {}
            for plugin_id, (plugin, description) in self._capabilities(plugin_rows).items():
                seen: set[str] = set()
                try:
                    for raw in description["tools"]:
                        if not isinstance(raw, dict):
                            raise PluginRuntimeError(
                                f"Plugin {plugin_id!r} returned an invalid tool description"
                            )
                        local_name = str(raw.get("name") or "").strip()
                        if not local_name or local_name in seen:
                            raise PluginRuntimeError(
                                f"Plugin {plugin_id!r} returned an empty or duplicate tool name"
                            )
                        schema = raw.get("input_schema")
                        if not isinstance(schema, dict) or schema.get("type", "object") != "object":
                            raise PluginRuntimeError(
                                f"Plugin tool {plugin_id}:{local_name} has an invalid input schema"
                            )
                        seen.add(local_name)
                        function_name = runtime_tool_name(plugin_id, local_name)
                        if function_name in bindings:
                            raise PluginRuntimeError(
                                f"Runtime tool name collision: {function_name}"
                            )
                        effect = str(raw.get("effect") or "").strip().lower()
                        if effect not in {
                            "",
                            "read",
                            "workspace_write",
                            "external_write",
                        }:
                            raise PluginRuntimeError(
                                f"Plugin tool {plugin_id}:{local_name} has an invalid effect"
                            )
                        resource_arguments = raw.get("resource_arguments") or []
                        path_arguments = raw.get("path_arguments") or []
                        if isinstance(resource_arguments, str):
                            resource_arguments = [resource_arguments]
                        if isinstance(path_arguments, str):
                            path_arguments = [path_arguments]
                        root_argument = str(
                            raw.get("workspace_root_argument") or ""
                        ).strip()
                        contract = {
                            "declared": bool(effect),
                            "effect": effect,
                            "permissions": dict(plugin.permissions),
                            "network": bool(plugin.permissions.get("network")),
                            "resource_arguments": [
                                str(item)
                                for item in resource_arguments
                                if str(item).strip()
                            ],
                            "path_arguments": [
                                str(item)
                                for item in path_arguments
                                if str(item).strip()
                            ],
                            "workspace_root_argument": root_argument,
                            "worktree_compatible": bool(
                                raw.get("worktree_compatible") or root_argument
                            ),
                        }
                        bindings[function_name] = RuntimeToolBinding(
                            function_name=function_name,
                            plugin_id=plugin_id,
                            local_name=local_name,
                            plugin_signature=plugin.content_signature,
                            contract=contract,
                        )
                        definitions.append(
                            {
                                "type": "function",
                                "function": {
                                    "name": function_name,
                                    "description": str(raw.get("description") or "").strip()
                                    or f"Tool {local_name} provided by plugin {plugin_id}.",
                                    "parameters": copy.deepcopy(schema),
                                },
                            }
                        )
                except PluginRuntimeError as exc:
                    self._errors_by_plugin[plugin_id] = str(exc)
                    definitions = [
                        item
                        for item in definitions
                        if not str(item["function"]["name"]).startswith(
                            f"plugin_{_FUNCTION_SAFE_RE.sub('_', plugin_id)}__"
                        )
                    ]
                    bindings = {
                        key: value
                        for key, value in bindings.items()
                        if value.plugin_id != plugin_id
                    }
            self._tool_bindings = bindings
            return definitions

    def tool_contract(
        self,
        function_name: str,
        plugins: Iterable[PluginDefinition],
    ) -> Dict[str, Any]:
        plugin_rows = tuple(plugins)
        with self._lock:
            self.tool_definitions(plugin_rows)
            binding = self._tool_bindings.get(str(function_name or ""))
            return copy.deepcopy(dict(binding.contract)) if binding else {}

    def hook_descriptions(
        self, plugins: Iterable[PluginDefinition]
    ) -> list[Dict[str, Any]]:
        plugin_rows = tuple(plugins)
        with self._lock:
            rows = []
            for plugin_id, (plugin, description) in self._capabilities(plugin_rows).items():
                seen: set[tuple[str, str]] = set()
                try:
                    for raw in description["hooks"]:
                        if not isinstance(raw, dict):
                            raise PluginRuntimeError(
                                f"Plugin {plugin_id!r} returned an invalid hook description"
                            )
                        event = str(raw.get("event") or "").strip()
                        hook_id = str(raw.get("id") or "").strip()
                        key = (event, hook_id)
                        if not event or not hook_id or key in seen:
                            raise PluginRuntimeError(
                                f"Plugin {plugin_id!r} returned an empty or duplicate hook"
                            )
                        seen.add(key)
                        rows.append(
                            {
                                "plugin_id": plugin_id,
                                "plugin_signature": plugin.content_signature,
                                "id": hook_id,
                                "event": event,
                                "matcher": str(raw.get("matcher") or ""),
                                "priority": int(raw.get("priority", 100)),
                                "failure_policy": str(
                                    raw.get("failure_policy") or "warn"
                                ).lower(),
                                "timeout_seconds": float(
                                    plugin.runtime.timeout_seconds
                                    if plugin.runtime
                                    else 30
                                ),
                            }
                        )
                except (PluginRuntimeError, TypeError, ValueError) as exc:
                    self._errors_by_plugin[plugin_id] = str(exc)
                    rows = [row for row in rows if row["plugin_id"] != plugin_id]
            return rows

    def command_descriptions(
        self, plugins: Iterable[PluginDefinition]
    ) -> list[Dict[str, Any]]:
        plugin_rows = tuple(plugins)
        with self._lock:
            rows = []
            for plugin_id, (plugin, description) in self._capabilities(plugin_rows).items():
                seen: set[str] = set()
                try:
                    for raw in description["commands"]:
                        if not isinstance(raw, dict):
                            raise PluginRuntimeError(
                                f"Plugin {plugin_id!r} returned an invalid command description"
                            )
                        name = str(raw.get("name") or "").strip()
                        if not name or name in seen:
                            raise PluginRuntimeError(
                                f"Plugin {plugin_id!r} returned an empty or duplicate command"
                            )
                        seen.add(name)
                        rows.append(
                            {
                                "plugin_id": plugin_id,
                                "plugin_signature": plugin.content_signature,
                                "name": name,
                                "qualified_name": f"{plugin_id}:{name}",
                                "description": str(raw.get("description") or ""),
                                "usage": str(raw.get("usage") or ""),
                            }
                        )
                except PluginRuntimeError as exc:
                    self._errors_by_plugin[plugin_id] = str(exc)
                    rows = [row for row in rows if row["plugin_id"] != plugin_id]
            return rows

    def _plugin_and_worker(
        self,
        plugin_id: str,
        signature: str,
        plugins: Sequence[PluginDefinition],
    ) -> tuple[PluginDefinition, _PersistentPluginWorker]:
        self._capabilities(plugins)
        plugin = next(
            (
                item
                for item in plugins
                if item.plugin_id == plugin_id
                and item.content_signature == signature
                and item.runtime is not None
            ),
            None,
        )
        if plugin is None:
            raise PluginRuntimeError(
                f"Plugin {plugin_id!r} changed or was disabled before invocation"
            )
        worker = self._workers.get((plugin_id, signature))
        if worker is None:
            raise PluginRuntimeError(f"Plugin {plugin_id!r} worker is unavailable")
        return plugin, worker

    def invoke(
        self,
        function_name: str,
        arguments: Mapping[str, Any],
        plugins: Sequence[PluginDefinition],
    ) -> Any:
        with self._lock:
            self.tool_definitions(plugins)
            binding = self._tool_bindings.get(str(function_name or ""))
            if binding is None:
                raise PluginRuntimeError(f"Unknown or disabled plugin tool: {function_name}")
            _plugin, worker = self._plugin_and_worker(
                binding.plugin_id, binding.plugin_signature, plugins
            )
        return worker.request(
            "tool.call",
            {"name": binding.local_name, "arguments": dict(arguments or {})},
        )

    def invoke_hook(
        self,
        plugin_id: str,
        plugin_signature: str,
        event: str,
        hook_id: str,
        payload: Mapping[str, Any],
        plugins: Sequence[PluginDefinition],
    ) -> Any:
        with self._lock:
            _plugin, worker = self._plugin_and_worker(
                plugin_id, plugin_signature, plugins
            )
        return worker.request(
            "hook.call",
            {
                "event": event,
                "hook_id": hook_id,
                "payload": dict(payload or {}),
            },
        )

    def invoke_command(
        self,
        plugin_id: str,
        plugin_signature: str,
        name: str,
        arguments: str,
        context: Mapping[str, Any],
        plugins: Sequence[PluginDefinition],
    ) -> Any:
        with self._lock:
            _plugin, worker = self._plugin_and_worker(
                plugin_id, plugin_signature, plugins
            )
        return worker.request(
            "command.call",
            {
                "name": name,
                "arguments": str(arguments or ""),
                "context": dict(context or {}),
            },
        )

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "workers": [
                    {
                        "plugin_id": plugin_id,
                        "content_signature": signature,
                        "pid": worker.pid,
                        "running": worker.pid is not None,
                    }
                    for (plugin_id, signature), worker in sorted(self._workers.items())
                ],
                "errors": list(self.errors),
                "tool_count": len(self._tool_bindings),
            }


_default_registry = PluginRuntimeRegistry(enforce_trust=True)
atexit.register(_default_registry.close)


def get_plugin_runtime_registry() -> PluginRuntimeRegistry:
    return _default_registry


__all__ = [
    "PluginRuntimeError",
    "PluginRuntimeRegistry",
    "RuntimeToolBinding",
    "get_plugin_runtime_registry",
    "runtime_tool_name",
]
