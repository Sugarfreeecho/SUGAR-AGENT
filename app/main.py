"""Web UI 启动入口。依赖自检请运行 check_requirements.bat / check_requirements.py。"""

from __future__ import annotations

import ssl_bypass  # SSL certificate bypass

import asyncio
import os
import socket
import threading
import time
import webbrowser
from contextlib import asynccontextmanager

import uvicorn

from python_runtime import configure_agent_python_environment


# Establish one Python runtime policy for the whole agent and all inherited subprocesses.
configure_agent_python_environment()


def _env_wants_browser() -> bool:
    v = os.getenv("OPEN_BROWSER", "True").strip().lower()
    return v not in ("0", "false", "no", "off")


def _open_browser_when_listening(host: str, port: int) -> None:
    url = f"http://{host}:{port}/"
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                pass
        except OSError:
            time.sleep(0.15)
            continue
        try:
            webbrowser.open(url, new=0, autoraise=True)
        except TypeError:
            webbrowser.open(url, new=0)
        return


def _schedule_browser_open(host: str, port: int) -> None:
    if not _env_wants_browser():
        return
    threading.Thread(
        target=_open_browser_when_listening,
        args=(host, port),
        daemon=True,
    ).start()


if __name__ == "__main__":
    from webui import (
        fastapi_app,
        schedule_runtime_auto_migration,
        start_feishu_adapter,
        start_goal_runner,
        stop_feishu_adapter,
        stop_goal_runner,
    )
    from agent_harness import refresh_executor_client_from_env
    from agent_subagent import reconcile_orphaned_subagent_runs, subagent_registry
    
    # 确保配置正确加载，避免重启后400/401错误
    refresh_executor_client_from_env()

    _listen_host = "127.0.0.1"
    _listen_port = 8192

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        import cpu_pressure

        cpu_pressure.start()
        # 启动时打开浏览器
        _schedule_browser_open("127.0.0.1", _listen_port)
        await asyncio.to_thread(reconcile_orphaned_subagent_runs)
        import runtime_observability
        from agent_harness import session_manager
        from session_lifecycle import cancel_run_tasks, is_run_active

        runtime_observability.configure(
            session_manager.sessions_dir,
            path_resolver=session_manager._resolve_session_path,
        )

        def runtime_run_is_locally_active(session_id: str, _run_id: str) -> bool:
            """Keep stale heartbeat records alive while their local task still exists."""
            return is_run_active(session_id) or subagent_registry.is_running(session_id)

        await asyncio.to_thread(
            runtime_observability.reconcile_orphaned_runs,
            live_checker=runtime_run_is_locally_active,
        )

        watchdog_stop = asyncio.Event()

        async def runtime_watchdog() -> None:
            stale_seconds = max(
                30.0,
                float(os.getenv("AGENT_RUN_STALE_SECONDS", "90")),
            )
            interval = max(
                5.0,
                min(60.0, float(os.getenv("AGENT_RUN_WATCHDOG_INTERVAL_SECONDS", "15"))),
            )
            while not watchdog_stop.is_set():
                await asyncio.sleep(interval)
                stale = await asyncio.to_thread(
                    runtime_observability.scan_stale_runs,
                    stale_seconds,
                    live_checker=runtime_run_is_locally_active,
                )
                targets = {
                    str(item.get("session_id") or "")
                    for item in stale
                    if str(item.get("session_id") or "")
                }
                for sid in targets:
                    try:
                        session_manager.request_interrupt(
                            sid,
                            reason="runtime_watchdog",
                        )
                    except Exception:
                        pass
                if targets:
                    await cancel_run_tasks(targets)

        watchdog_task = asyncio.create_task(runtime_watchdog())
        schedule_runtime_auto_migration()
        from agent_team.tools import start_auto_scheduler, stop_auto_scheduler

        await start_auto_scheduler()
        await start_goal_runner()
        try:
            await start_feishu_adapter()
            yield
        finally:
            cpu_pressure.stop()
            watchdog_stop.set()
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass
            await stop_auto_scheduler()
            await stop_feishu_adapter()
            await stop_goal_runner()
        
    fastapi_app.router.lifespan_context = lifespan

    uvicorn.run(fastapi_app, host=_listen_host, port=_listen_port)
