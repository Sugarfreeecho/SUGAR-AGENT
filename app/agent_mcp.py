"""
MCP（Model Context Protocol）桥：支持 stdio / SSE / Streamable HTTP，配置变更热重载，
默认免注册确认（EXTENSION_REGISTRATION_APPROVAL_ENABLED=1 时启用摘要绑定的统一扩展注册审批），
工具调用走中央权限策略，结构化日志。

配置：`PROJECT_ROOT/mcp_servers.json` 或 `MCP_SERVERS_JSON`；路径可用 `MCP_SERVERS_PATH`。
禁用：`MCP_ENABLED=0`；未安装 `mcp` 包时跳过。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple, TypeVar

import httpx

from agent_harness import PROJECT_ROOT

logger = logging.getLogger(__name__)

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client
    from mcp.shared._httpx_utils import create_mcp_http_client

    _MCP_IMPORT_OK = True
except ImportError:
    ClientSession = None  # type: ignore
    StdioServerParameters = None  # type: ignore
    stdio_client = None  # type: ignore
    sse_client = None  # type: ignore
    streamable_http_client = None  # type: ignore
    create_mcp_http_client = None  # type: ignore
    _MCP_IMPORT_OK = False

_TOOL_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")
_ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_STOP = object()

_fname_to_tool: Dict[str, Tuple[str, str]] = {}
_servers: Dict[str, Any] = {}
_defs_snapshot: List[Dict[str, Any]] = []
_tool_contracts: Dict[str, Dict[str, Any]] = {}
_server_start_errors: Dict[str, str] = {}
_start_lock = asyncio.Lock()
_loaded_signature: Optional[str] = None
_signature_cache: Optional[Tuple[float, str]] = None
_SIGNATURE_CACHE_TTL_SEC = 1.0
_last_config_error: Optional[str] = None

_MCP_TOOLS_STATE_PATH = PROJECT_ROOT / "mcp_tools_state.json"
_mcp_tool_state_lock = threading.RLock()
_disabled_mcp_tools: set[str] = set()
_disabled_mcp_tools_loaded = False

_T = TypeVar("_T")
_mcp_loop: Optional[asyncio.AbstractEventLoop] = None
_mcp_loop_thread: Optional[threading.Thread] = None
_mcp_loop_init_lock = threading.Lock()


def _expand_env_references(value: str, *, field: str) -> str:
    """Resolve ${NAME} at connection time without persisting secret values."""
    missing = sorted(
        {
            match.group(1)
            for match in _ENV_REFERENCE.finditer(value)
            if match.group(1) not in os.environ
        }
    )
    if missing:
        raise ValueError(
            f"{field} references missing environment variable(s): {', '.join(missing)}"
        )
    return _ENV_REFERENCE.sub(lambda match: os.environ[match.group(1)], value)


def _headers_from_config(cfg: dict) -> Optional[Dict[str, str]]:
    headers_raw = cfg.get("headers")
    if not isinstance(headers_raw, dict):
        return None
    return {
        str(key): _expand_env_references(str(value), field=f"MCP header {key!s}")
        for key, value in headers_raw.items()
    }


def _get_mcp_loop() -> asyncio.AbstractEventLoop:
    """Return the one long-lived event loop that owns all MCP async state."""
    global _mcp_loop, _mcp_loop_thread

    loop = _mcp_loop
    thread = _mcp_loop_thread
    if loop is not None and loop.is_running() and thread is not None and thread.is_alive():
        return loop

    with _mcp_loop_init_lock:
        loop = _mcp_loop
        thread = _mcp_loop_thread
        if loop is not None and loop.is_running() and thread is not None and thread.is_alive():
            return loop

        ready = threading.Event()
        startup_error: List[BaseException] = []

        def _loop_worker() -> None:
            global _mcp_loop
            worker_loop: Optional[asyncio.AbstractEventLoop] = None
            try:
                worker_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(worker_loop)
                _mcp_loop = worker_loop
                # Signal only after run_forever has started processing callbacks.
                worker_loop.call_soon(ready.set)
                worker_loop.run_forever()
            except BaseException as exc:
                startup_error.append(exc)
                ready.set()
                logger.exception("MCP background event loop exited unexpectedly")
            finally:
                if worker_loop is not None:
                    pending = asyncio.all_tasks(worker_loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        worker_loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )
                    worker_loop.close()
                if _mcp_loop is worker_loop:
                    _mcp_loop = None

        thread = threading.Thread(
            target=_loop_worker,
            name="mcp-event-loop",
            daemon=True,
        )
        _mcp_loop_thread = thread
        thread.start()
        if not ready.wait(timeout=10.0):
            raise RuntimeError("MCP background event loop startup timed out")
        loop = _mcp_loop
        if startup_error or loop is None or not loop.is_running():
            detail = f": {startup_error[0]}" if startup_error else ""
            raise RuntimeError(f"MCP background event loop failed to start{detail}")
        return loop


async def _run_on_mcp_loop(awaitable: Awaitable[_T]) -> _T:
    """Await an MCP coroutine on the dedicated loop from any caller loop."""
    target_loop = _get_mcp_loop()
    try:
        caller_loop = asyncio.get_running_loop()
    except RuntimeError:
        caller_loop = None
    if caller_loop is target_loop:
        return await awaitable

    try:
        submitted = asyncio.run_coroutine_threadsafe(awaitable, target_loop)
    except BaseException:
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise
    try:
        return await asyncio.wrap_future(submitted)
    except asyncio.CancelledError:
        submitted.cancel()
        raise


def _load_disabled_mcp_tools() -> set[str]:
    """Load persisted per-tool disabled state (enabled is the default)."""
    global _disabled_mcp_tools, _disabled_mcp_tools_loaded
    if _disabled_mcp_tools_loaded:
        return _disabled_mcp_tools
    with _mcp_tool_state_lock:
        if _disabled_mcp_tools_loaded:
            return _disabled_mcp_tools
        _disabled_mcp_tools = set()
        try:
            data = json.loads(_MCP_TOOLS_STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = None
        raw = data.get("tools") if isinstance(data, dict) else None
        if isinstance(raw, dict):
            for fname, value in raw.items():
                name = str(fname or "").strip()
                if name and isinstance(value, dict) and value.get("enabled") is False:
                    _disabled_mcp_tools.add(name)
        _disabled_mcp_tools_loaded = True
    return _disabled_mcp_tools


def is_mcp_tool_enabled(function_name: str) -> bool:
    return str(function_name or "") not in _load_disabled_mcp_tools()


def set_mcp_tool_enabled(function_name: str, enabled: bool) -> bool:
    """Persist whether a registered MCP tool is visible and callable."""
    global _disabled_mcp_tools
    name = str(function_name or "").strip()
    if not name or name not in _fname_to_tool:
        return False
    with _mcp_tool_state_lock:
        disabled = set(_load_disabled_mcp_tools())
        if enabled:
            disabled.discard(name)
        else:
            disabled.add(name)
        out = {
            "version": 1,
            "tools": {key: {"enabled": False} for key in sorted(disabled)},
        }
        _MCP_TOOLS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _MCP_TOOLS_STATE_PATH.with_suffix(_MCP_TOOLS_STATE_PATH.suffix + ".tmp")
        tmp.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(_MCP_TOOLS_STATE_PATH)
        _disabled_mcp_tools = disabled
    return True


def _register_tools_globally(alias: str, tools: List[Any]) -> int:
    """Register a server's latest tools in the global OpenAI tool snapshots."""
    global _defs_snapshot
    seen_fname: set[str] = set()
    registered = 0
    for t in tools or []:
        orig_name = getattr(t, "name", "") or ""
        if not orig_name:
            continue
        desc = getattr(t, "description", "") or ""
        schema = getattr(t, "inputSchema", None)
        od = _openai_tool_def(alias, orig_name, desc, schema)
        fname = od["function"]["name"]
        if fname in seen_fname:
            continue
        seen_fname.add(fname)
        existing = _fname_to_tool.get(fname)
        if existing and existing != (alias, orig_name):
            logger.warning("MCP: duplicate tool key `%s`, skip `%s.%s`", fname, alias, orig_name)
            continue
        _fname_to_tool[fname] = (alias, orig_name)
        _defs_snapshot = [
            d
            for d in _defs_snapshot
            if d.get("function", {}).get("name") != fname
        ]
        _defs_snapshot.append(od)
        registered += 1
    return registered


def _enabled_flag() -> bool:
    v = (os.getenv("MCP_ENABLED") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _config_path() -> Path:
    custom = (os.getenv("MCP_SERVERS_PATH") or "").strip()
    if custom:
        return Path(custom).expanduser()
    return (PROJECT_ROOT / "mcp_servers.json").resolve()


def get_config_path() -> Path:
    """配置文件路径（供 Web UI 展示与保存）。"""
    return _config_path()


def _compute_config_signature() -> str:
    """配置签名：变更则触发关闭并重连。"""
    if not _enabled_flag():
        return "disabled"
    inline = (os.getenv("MCP_SERVERS_JSON") or "").strip()
    if inline:
        base = "inline:" + hashlib.sha256(inline.encode("utf-8")).hexdigest()
    else:
        path = _config_path()
        try:
            st = path.stat()
            base = f"file:{path.resolve()}:{st.st_mtime_ns}:{st.st_size}"
        except OSError:
            base = f"missing:{path.resolve()}"
    try:
        from agent_extensions import plugin_registry_signature

        plugin_sig = hashlib.sha256(
            plugin_registry_signature().encode("utf-8")
        ).hexdigest()
    except Exception as exc:
        logger.debug("MCP plugin signature unavailable: %s", exc)
        plugin_sig = "unavailable"
    return f"{base}|plugins:{plugin_sig}"


def _compute_config_signature_cached() -> str:
    global _signature_cache
    now = time.monotonic()
    cached = _signature_cache
    if cached and now - cached[0] <= _SIGNATURE_CACHE_TTL_SEC:
        return cached[1]
    sig = _compute_config_signature()
    _signature_cache = (now, sig)
    return sig


def _load_servers_dict_from_config() -> Tuple[Optional[dict], Optional[str]]:
    """返回 (servers dict | None, error reason | None)。"""
    global _last_config_error
    _last_config_error = None
    if not _enabled_flag():
        return None, None
    try:
        from agent_extensions import plugin_mcp_servers

        plugin_servers = dict(plugin_mcp_servers())
    except Exception as exc:
        logger.debug("MCP plugin resources unavailable: %s", exc)
        plugin_servers = {}

    inline = (os.getenv("MCP_SERVERS_JSON") or "").strip()
    raw_obj: Any = None
    if inline:
        try:
            raw_obj = json.loads(inline)
        except json.JSONDecodeError as e:
            _last_config_error = f"MCP_SERVERS_JSON parse error: {e}"
            logger.warning(_last_config_error)
            return (plugin_servers or None), _last_config_error
    else:
        path = _config_path()
        if not path.is_file():
            raw_obj = None
        else:
            try:
                raw_obj = json.loads(path.read_text(encoding="utf-8"))
            except OSError as e:
                _last_config_error = f"read {path}: {e}"
                logger.warning(_last_config_error)
                return (plugin_servers or None), _last_config_error
            except json.JSONDecodeError as e:
                _last_config_error = f"{path}: {e}"
                logger.warning(_last_config_error)
                return (plugin_servers or None), _last_config_error

    if raw_obj is not None and not isinstance(raw_obj, dict):
        _last_config_error = "MCP config root must be an object"
        logger.warning(_last_config_error)
        return (plugin_servers or None), _last_config_error

    project_servers: Dict[str, Any] = {}
    if isinstance(raw_obj, dict) and raw_obj.get("enabled") is not False:
        servers = raw_obj.get("servers")
        if servers is None:
            servers = raw_obj.get("mcpServers")
        if isinstance(servers, dict):
            project_servers.update(servers)

    merged = dict(project_servers)
    for alias, config in plugin_servers.items():
        if alias in merged:
            logger.warning("MCP: plugin server `%s` conflicts with project config and was ignored", alias)
            continue
        merged[alias] = config
    return (merged or None), _last_config_error


def _resolve_transport(cfg: dict) -> str:
    t = (cfg.get("transport") or "").strip().lower()
    url = str(cfg.get("url") or "").strip()
    cmd = str(cfg.get("command") or "").strip()
    if t in ("stdio", "sse", "streamable-http", "streamable_http", "http"):
        if t in ("http", "streamable_http"):
            return "streamable-http"
        return t
    if cmd:
        return "stdio"
    if url:
        return "streamable-http"
    return ""


def _safe_function_key(alias: str, tool_name: str) -> str:
    a = _TOOL_NAME_SAFE.sub("_", alias).strip("_").lower() or "srv"
    t = _TOOL_NAME_SAFE.sub("_", tool_name).strip("_").lower() or "tool"
    base = f"mcp_{a}_{t}"
    if len(base) > 120:
        base = base[:120].rstrip("_")
    return base


def _schema_to_parameters(schema: Any) -> Dict[str, Any]:
    if isinstance(schema, dict):
        return schema
    return {"type": "object", "properties": {}}


def _openai_tool_def(alias: str, name: str, description: str, input_schema: Any) -> Dict[str, Any]:
    fname = _safe_function_key(alias, name)
    desc = (description or "").strip() or name
    full_desc = f"[MCP server `{alias}`] {desc}"
    return {
        "type": "function",
        "function": {
            "name": fname,
            "description": full_desc[:4096],
            "parameters": _schema_to_parameters(input_schema),
        },
    }


def _tool_contract_from_config(cfg: dict, tool_name: str) -> Dict[str, Any]:
    contracts = cfg.get("tool_contracts", cfg.get("tools", {}))
    raw = contracts.get(tool_name) if isinstance(contracts, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    effect = str(
        raw.get("effect")
        or raw.get("write_semantics")
        or cfg.get("default_tool_effect")
        or ""
    ).strip().lower()
    aliases = {
        "readonly": "read",
        "read_only": "read",
        "filesystem_write": "workspace_write",
        "write": "workspace_write",
        "external": "external_write",
    }
    effect = aliases.get(effect, effect)
    path_arguments = raw.get("path_arguments") or []
    if isinstance(path_arguments, str):
        path_arguments = [path_arguments]
    resource_arguments = raw.get("resource_arguments") or []
    if isinstance(resource_arguments, str):
        resource_arguments = [resource_arguments]
    return {
        "declared": bool(raw or cfg.get("default_tool_effect")),
        "effect": effect,
        "network": _resolve_transport(cfg) in {"sse", "streamable-http"},
        "server_source": str(cfg.get("url") or "").strip(),
        "resource_arguments": [
            str(item) for item in resource_arguments if str(item).strip()
        ],
        "path_arguments": [
            str(item) for item in path_arguments if str(item).strip()
        ],
        "workspace_root_argument": str(
            raw.get("workspace_root_argument")
            or raw.get("worktree_root_argument")
            or ""
        ).strip(),
        "worktree_compatible": bool(
            raw.get("worktree_compatible")
            or raw.get("workspace_root_argument")
            or raw.get("worktree_root_argument")
        ),
    }


def get_tool_contract(function_name: str) -> Dict[str, Any]:
    return dict(_tool_contracts.get(str(function_name or ""), {}))


def _serialize_call_tool_result_for_log(result: Any, max_len: int = 12000) -> str:
    try:
        if hasattr(result, "model_dump"):
            dumped = result.model_dump(mode="json")
            s = json.dumps(dumped, ensure_ascii=False, default=str)
            return s if len(s) <= max_len else s[:max_len] + "…[truncated]"
    except Exception:
        pass
    try:
        s = json.dumps(result, ensure_ascii=False, default=str)
        return s if len(s) <= max_len else s[:max_len] + "…[truncated]"
    except Exception:
        pass
    r = repr(result)
    return r if len(r) <= max_len else r[:max_len] + "…[truncated]"


class _PersistentMcpServer:
    """通用持久会话：由 connect_cm 提供 (read, write) 流。"""

    def __init__(
        self,
        alias: str,
        transport_label: str,
        connect_cm: Callable[[], Any],
        call_timeout_sec: float = 120.0,
    ):
        self.alias = alias
        self.transport_label = transport_label
        self._connect_cm = connect_cm
        self.call_timeout_sec = max(1.0, float(call_timeout_sec or 120.0))
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._ready = asyncio.Event()
        self._tools: List[Any] = []
        self._fatal: Optional[str] = None
        self._restart_lock = asyncio.Lock()

    async def start(self, timeout_sec: float = 60.0) -> None:
        self._ready.clear()
        self._fatal = None
        self._task = asyncio.create_task(self._runner())
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            self._fatal = f"MCP `{self.alias}` ({self.transport_label}) startup timed out after {timeout_sec}s"
            raise RuntimeError(self._fatal) from None
        if self._fatal:
            raise RuntimeError(self._fatal)

    async def _runner(self) -> None:
        if not _MCP_IMPORT_OK or ClientSession is None:
            self._fatal = "Python package `mcp` is not installed"
            if not self._ready.is_set():
                self._ready.set()
            return
        try:
            async with self._connect_cm() as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    self._tools = list(listed.tools)
                    mapped = _register_tools_globally(self.alias, self._tools)
                    if not self._ready.is_set():
                        self._ready.set()
                    logger.info(
                        "MCP server ready alias=%s transport=%s tools=%s mapped_tools=%s",
                        self.alias,
                        self.transport_label,
                        len(self._tools),
                        mapped,
                    )
                    while True:
                        req = await self._queue.get()
                        if req is _STOP:
                            break
                        fut: asyncio.Future = req[0]
                        tname: str = req[1]
                        targs: Dict[str, Any] = req[2]
                        try:
                            result = await asyncio.wait_for(
                                session.call_tool(tname, targs),
                                timeout=self.call_timeout_sec,
                            )
                            if not fut.done():
                                fut.set_result(result)
                        except asyncio.TimeoutError:
                            if not fut.done():
                                fut.set_exception(
                                    TimeoutError(
                                        f"MCP tool `{self.alias}.{tname}` timed out after "
                                        f"{self.call_timeout_sec:g}s"
                                    )
                                )
                        except BaseException as e:
                            if not fut.done():
                                fut.set_exception(e)
        except asyncio.CancelledError:
            logger.info("MCP server `%s` (%s) runner cancelled", self.alias, self.transport_label)
        except BaseException as e:
            self._fatal = str(e)
            logger.exception("MCP server `%s` (%s) exited", self.alias, self.transport_label)
        finally:
            self._fail_queued_requests()
            if not self._ready.is_set():
                self._ready.set()

    def _fail_queued_requests(self) -> None:
        err = self._fatal or f"MCP server `{self.alias}` is not connected"
        while True:
            try:
                req = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if req is _STOP:
                continue
            try:
                fut = req[0]
                if not fut.done():
                    fut.set_exception(RuntimeError(err))
            except Exception:
                pass

    async def _restart(self, retries: int = 3) -> None:
        async with self._restart_lock:
            if self._task is not None and not self._task.done() and not self._fatal:
                return
            last_err: Optional[BaseException] = None
            for attempt in range(1, max(1, retries) + 1):
                self._fatal = None
                self._ready.clear()
                self._task = asyncio.create_task(self._runner())
                try:
                    await asyncio.wait_for(self._ready.wait(), timeout=60.0)
                    if not self._fatal:
                        logger.info(
                            "MCP server `%s` restarted attempt=%s",
                            self.alias,
                            attempt,
                        )
                        return
                    last_err = RuntimeError(self._fatal)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    last_err = e
                if self._task and not self._task.done():
                    self._task.cancel()
                await asyncio.sleep(min(0.5 * attempt, 2.0))
            if last_err:
                raise RuntimeError(f"MCP server `{self.alias}` restart failed: {last_err}") from last_err
            raise RuntimeError(f"MCP server `{self.alias}` restart failed")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if self._task is None or self._task.done():
            await self._restart()
        if self._fatal:
            raise RuntimeError(self._fatal)
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        await self._queue.put((fut, tool_name, dict(arguments or {})))
        return await fut

    async def stop(self) -> None:
        if self._task is None:
            return
        await self._queue.put(_STOP)
        try:
            await asyncio.wait_for(self._task, timeout=20.0)
        except asyncio.TimeoutError:
            self._task.cancel()


def _make_stdio_connector(alias: str, cfg: dict) -> _PersistentMcpServer:
    cmd = str(cfg.get("command") or "").strip()
    args = cfg.get("args") or []
    if not isinstance(args, list):
        args = []
    args = [str(a) for a in args]
    from security.extensions import minimal_extension_environment

    env = cfg.get("env")
    explicit_env = (
        {str(k): str(v) for k, v in env.items()}
        if isinstance(env, dict)
        else {}
    )
    raw_allow = cfg.get("env_allowlist") or cfg.get("environmentAllowlist") or []
    allow_names = (
        [str(item) for item in raw_allow]
        if isinstance(raw_allow, (list, tuple))
        else []
    )
    env_d: Dict[str, str] = minimal_extension_environment(
        allow_names=allow_names,
        explicit=explicit_env,
    )
    cwd = cfg.get("cwd") or cfg.get("workingDirectory")
    cwd_s = str(cwd).strip() if cwd else None
    params = StdioServerParameters(command=cmd, args=args, env=env_d, cwd=cwd_s or None)

    @asynccontextmanager
    async def _cm() -> AsyncIterator[Tuple[Any, Any]]:
        async with stdio_client(params) as rw:
            yield rw

    call_timeout = float(cfg.get("tool_timeout", cfg.get("call_timeout", cfg.get("callTimeout", 120))))
    return _PersistentMcpServer(alias, "stdio", _cm, call_timeout_sec=call_timeout)


def _make_sse_connector(alias: str, cfg: dict) -> _PersistentMcpServer:
    url = str(cfg.get("url") or "").strip()
    headers = _headers_from_config(cfg)
    timeout = float(cfg.get("timeout", 30))
    sse_read = float(cfg.get("sse_read_timeout", cfg.get("sseReadTimeout", 300)))
    call_timeout = float(cfg.get("tool_timeout", cfg.get("call_timeout", cfg.get("callTimeout", 120))))
    verify = cfg.get("verify", True)
    skip_verify = verify is False

    @asynccontextmanager
    async def _cm() -> AsyncIterator[Tuple[Any, Any]]:
        httpx_client_factory = create_mcp_http_client
        if skip_verify:
            def _insecure_httpx_client_factory(
                headers: Optional[Dict[str, str]] = None,
                timeout: Optional[httpx.Timeout] = None,
                auth: Optional[httpx.Auth] = None,
            ) -> httpx.AsyncClient:
                return httpx.AsyncClient(
                    headers=headers,
                    timeout=timeout,
                    auth=auth,
                    verify=False,
                )

            httpx_client_factory = _insecure_httpx_client_factory
            logger.warning("MCP SSE `%s`: SSL certificate verification disabled by config", alias)
        async with sse_client(
            url,
            headers=headers if headers else None,
            timeout=timeout,
            sse_read_timeout=sse_read,
            httpx_client_factory=httpx_client_factory,
        ) as rw:
            yield rw

    return _PersistentMcpServer(alias, "sse", _cm, call_timeout_sec=call_timeout)


def _make_streamable_connector(alias: str, cfg: dict) -> _PersistentMcpServer:
    url = str(cfg.get("url") or "").strip()
    headers = _headers_from_config(cfg)
    timeout_sec = float(cfg.get("timeout", 30))
    read_sec = float(cfg.get("sse_read_timeout", cfg.get("read_timeout", 300)))
    call_timeout = float(cfg.get("tool_timeout", cfg.get("call_timeout", cfg.get("callTimeout", 120))))
    terminate = bool(cfg.get("terminate_on_close", True))

    @asynccontextmanager
    async def _cm() -> AsyncIterator[Tuple[Any, Any]]:
        to = httpx.Timeout(timeout_sec, read=read_sec)
        hc = create_mcp_http_client(headers=headers if headers else None, timeout=to)
        async with hc:
            async with streamable_http_client(url, http_client=hc, terminate_on_close=terminate) as streams:
                read, write, _ = streams
                yield (read, write)

    return _PersistentMcpServer(alias, "streamable-http", _cm, call_timeout_sec=call_timeout)


async def _shutdown_servers_unlocked() -> None:
    global _fname_to_tool, _servers, _defs_snapshot, _tool_contracts
    for srv in list(_servers.values()):
        try:
            await srv.stop()
        except Exception:
            logger.exception("MCP stop failed for %s", getattr(srv, "alias", "?"))
    _servers.clear()
    _fname_to_tool.clear()
    _defs_snapshot.clear()
    _tool_contracts.clear()


def _remove_server_tools_unlocked(alias: str) -> None:
    """Remove one server's tool mappings without disturbing other servers."""
    global _defs_snapshot
    names = {
        function_name
        for function_name, pair in _fname_to_tool.items()
        if pair[0] == alias
    }
    for function_name in names:
        _fname_to_tool.pop(function_name, None)
        _tool_contracts.pop(function_name, None)
    if names:
        _defs_snapshot = [
            item
            for item in _defs_snapshot
            if str((item.get("function") or {}).get("name") or "") not in names
        ]


async def _start_configured_server_unlocked(alias: str, cfg: dict) -> None:
    """Start one approved server and register its discovered tool contracts."""
    from security.extensions import mcp_descriptor, mcp_registration_is_approved

    if not mcp_registration_is_approved(mcp_descriptor(alias, cfg)):
        raise PermissionError("registration approval is required")

    transport = _resolve_transport(cfg)
    if transport == "stdio":
        if not str(cfg.get("command") or "").strip():
            raise ValueError("stdio transport requires command")
        srv = _make_stdio_connector(alias, cfg)
    elif transport == "sse":
        if not str(cfg.get("url") or "").strip():
            raise ValueError("SSE transport requires url")
        srv = _make_sse_connector(alias, cfg)
    elif transport == "streamable-http":
        if not str(cfg.get("url") or "").strip():
            raise ValueError("Streamable HTTP transport requires url")
        srv = _make_streamable_connector(alias, cfg)
    else:
        raise ValueError("unknown transport")

    try:
        await srv.start()
    except BaseException:
        await srv.stop()
        raise

    _servers[alias] = srv
    for function_name, pair in list(_fname_to_tool.items()):
        if pair[0] == alias:
            _tool_contracts[function_name] = _tool_contract_from_config(cfg, pair[1])
    logger.info(
        "MCP: server `%s` OK transport=%s mapped_tools=%s",
        alias,
        getattr(srv, "transport_label", "?"),
        sum(1 for pair in _fname_to_tool.values() if pair[0] == alias),
    )


async def _force_reload_impl() -> None:
    """写入新配置后调用：关闭连接并于下次 ensure_started 重建。"""
    global _loaded_signature, _signature_cache
    async with _start_lock:
        await _shutdown_servers_unlocked()
        _loaded_signature = None
        _signature_cache = None


async def force_reload() -> None:
    await _run_on_mcp_loop(_force_reload_impl())


async def _ensure_started_impl() -> None:
    global _loaded_signature
    if not _MCP_IMPORT_OK:
        return
    async with _start_lock:
        sig = _compute_config_signature_cached()
        if sig == _loaded_signature:
            return

        await _shutdown_servers_unlocked()
        _server_start_errors.clear()

        servers_cfg, err = _load_servers_dict_from_config()
        if not servers_cfg:
            _loaded_signature = sig
            if err:
                logger.info("MCP: skipped (%s)", err)
            elif _last_config_error:
                logger.info("MCP: skipped (%s)", _last_config_error)
            else:
                logger.info("MCP: no config (`mcp_servers.json` / MCP_SERVERS_JSON)")
            return

        for alias, cfg in servers_cfg.items():
            if not isinstance(cfg, dict):
                error = "server configuration must be an object"
                _server_start_errors[str(alias)] = error
                logger.warning("MCP: skip server `%s` (%s)", alias, error)
                continue
            try:
                await _start_configured_server_unlocked(str(alias), cfg)
            except Exception as e:
                _server_start_errors[str(alias)] = str(e)
                logger.warning("MCP: failed to start `%s`: %s", alias, e)
                continue

        _loaded_signature = sig


async def ensure_started() -> None:
    await _run_on_mcp_loop(_ensure_started_impl())


async def _register_server_impl(alias: str) -> Dict[str, Any]:
    if not _MCP_IMPORT_OK:
        raise RuntimeError("Python package `mcp` is not installed")
    async with _start_lock:
        servers_cfg, _ = _load_servers_dict_from_config()
        cfg = (servers_cfg or {}).get(alias) if isinstance(servers_cfg, dict) else None
        if not isinstance(cfg, dict):
            raise KeyError(alias)

        previous = _servers.pop(alias, None)
        if previous is not None:
            await previous.stop()
        _remove_server_tools_unlocked(alias)
        _server_start_errors.pop(alias, None)
        try:
            await _start_configured_server_unlocked(alias, cfg)
        except Exception as exc:
            _server_start_errors[alias] = str(exc)
            logger.warning("MCP: manual registration failed `%s`: %s", alias, exc)

        rows = [row for row in list_configured_servers() if row["server"] == alias]
        return rows[0] if rows else {"server": alias, "connected": False, "discovered": False, "tool_count": 0}


async def register_server(alias: str) -> Dict[str, Any]:
    """Retry connection and tool registration for one configured MCP server."""
    name = str(alias or "").strip()
    if not name:
        raise ValueError("MCP server name is required")
    return await _run_on_mcp_loop(_register_server_impl(name))


async def get_tool_definitions() -> List[Dict[str, Any]]:
    await ensure_started()
    disabled = _load_disabled_mcp_tools()
    return [
        d
        for d in _defs_snapshot
        if str((d.get("function") or {}).get("name") or "") not in disabled
    ]


def list_registered_tools() -> List[Dict[str, Any]]:
    """Return the currently registered MCP tools for UI display."""
    disabled = _load_disabled_mcp_tools()
    descriptions = {
        str(d.get("function", {}).get("name") or ""): str(
            d.get("function", {}).get("description") or ""
        )
        for d in _defs_snapshot
    }
    tools = [
        {
            "function_name": fname,
            "server": alias,
            "tool_name": orig_name,
            "description": descriptions.get(fname, ""),
            "enabled": fname not in disabled,
        }
        for fname, (alias, orig_name) in _fname_to_tool.items()
    ]
    tools.sort(key=lambda item: (str(item["server"]).lower(), str(item["tool_name"]).lower()))
    return tools


def list_configured_servers() -> List[Dict[str, Any]]:
    """Return every configured MCP server, including ones with no discovered tools."""
    servers_cfg, _ = _load_servers_dict_from_config()
    configured = servers_cfg if isinstance(servers_cfg, dict) else {}
    tool_counts: Dict[str, int] = {}
    for alias, _tool_name in _fname_to_tool.values():
        tool_counts[alias] = tool_counts.get(alias, 0) + 1

    aliases = set(str(alias) for alias in configured)
    aliases.update(str(alias) for alias in _servers)
    aliases.update(tool_counts)
    servers = []
    for alias in sorted(aliases, key=str.lower):
        cfg = configured.get(alias)
        tool_count = int(tool_counts.get(alias, 0))
        servers.append(
            {
                "server": alias,
                "transport": _resolve_transport(cfg) if isinstance(cfg, dict) else "",
                "connected": alias in _servers,
                "discovered": tool_count > 0,
                "tool_count": tool_count,
                "error": str(_server_start_errors.get(alias) or ""),
            }
        )
    return servers


def format_call_tool_result(result: Any) -> str:
    if result is None:
        return ""
    err = getattr(result, "isError", False)
    parts: List[str] = []
    for block in getattr(result, "content", None) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            parts.append(str(getattr(block, "text", "") or ""))
        elif btype == "image":
            parts.append("[image content omitted]")
        elif btype == "resource":
            res = getattr(block, "resource", None)
            txt = getattr(res, "text", None) if res is not None else None
            if txt:
                parts.append(str(txt))
            else:
                parts.append(f"[resource: {getattr(res, 'uri', res)!s}]")
        else:
            parts.append(str(block))
    body = "\n".join(parts).strip()
    if err:
        prefix = "MCP tool returned an error."
        return f"{prefix}\n{body}" if body else prefix
    return body if body else repr(result)


async def invoke_tool_by_fname(
    function_name: str,
    arguments: Dict[str, Any],
    *,
    work_dir: str = "",
    require_worktree_isolation: bool = False,
) -> str:
    await ensure_started()
    return await _run_on_mcp_loop(
        _invoke_tool_by_fname_impl(
            function_name,
            arguments,
            work_dir=work_dir,
            require_worktree_isolation=require_worktree_isolation,
        )
    )


async def _invoke_tool_by_fname_impl(
    function_name: str,
    arguments: Dict[str, Any],
    *,
    work_dir: str = "",
    require_worktree_isolation: bool = False,
) -> str:
    pair = _fname_to_tool.get(function_name)
    if not pair:
        return f"Error: unknown MCP tool `{function_name}`."
    if function_name in _load_disabled_mcp_tools():
        return f"Error: MCP tool `{function_name}` is disabled."
    alias, orig = pair
    contract = get_tool_contract(function_name)
    call_arguments = dict(arguments or {})
    if require_worktree_isolation:
        if not contract.get("declared") or not contract.get("effect"):
            return (
                f"Error: MCP tool `{function_name}` is blocked in a managed worktree "
                "because it does not declare an effect/resource isolation contract."
            )
        effect = str(contract.get("effect") or "")
        if effect == "workspace_write":
            if not contract.get("worktree_compatible"):
                return (
                    f"Error: MCP tool `{function_name}` declares workspace writes but "
                    "does not declare worktree compatibility."
                )
            root_argument = str(contract.get("workspace_root_argument") or "")
            if not root_argument:
                return (
                    f"Error: MCP tool `{function_name}` requires a "
                    "workspace_root_argument for worktree isolation."
                )
            call_arguments[root_argument] = str(Path(work_dir).resolve())
        elif effect not in {"read", "external_write"}:
            return (
                f"Error: MCP tool `{function_name}` has unsupported effect "
                f"{effect!r} for worktree isolation."
            )
        root = Path(work_dir).resolve()
        for argument_name in contract.get("path_arguments") or []:
            raw_path = str(call_arguments.get(argument_name) or "").strip()
            if not raw_path:
                continue
            candidate = Path(raw_path)
            candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                return (
                    f"Error: MCP argument `{argument_name}` escapes the managed "
                    "worktree."
                )
            call_arguments[argument_name] = str(candidate)
    srv = _servers.get(alias)
    if srv is None:
        return f"Error: MCP server `{alias}` is not running."
    if getattr(srv, "_task", None) is None or srv._task.done():
        try:
            await srv._restart()
        except Exception as e:
            return f"Error: MCP server `{alias}` reconnect failed: {e}"
    t0 = time.perf_counter()
    try:
        raw = await srv.call_tool(orig, call_arguments)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        raw_dump = _serialize_call_tool_result_for_log(raw)
        logger.info(
            "MCP call_ok server=%s transport=%s tool=%s fname=%s elapsed_ms=%.2f raw=%s",
            alias,
            getattr(srv, "transport_label", "?"),
            orig,
            function_name,
            elapsed_ms,
            raw_dump,
        )
        return format_call_tool_result(raw)
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logger.warning(
            "MCP call_fail server=%s tool=%s fname=%s elapsed_ms=%.2f err=%s",
            alias,
            orig,
            function_name,
            elapsed_ms,
            e,
        )
        return f"MCP tool error ({function_name}): {e}"
