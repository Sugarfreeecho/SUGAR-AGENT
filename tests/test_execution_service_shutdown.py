"""A restart must survive an interrupted execution-service teardown.

The 2026-11 restarts failed with "保存运行状态失败：execution service is shutting
down" because the first teardown was cancelled by its 15s budget, leaving the
admission gate closed while the loop kept running; the duplicate shutdown that
prepare_runtime issued then raised. These tests pin the recovery path.
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from execution_services.jobs import ExecutionService


def test_duplicate_shutdown_is_idempotent():
    async def scenario():
        service = ExecutionService()
        await service.call(asyncio.sleep, 0)
        await service.shutdown()
        await service.shutdown()  # a second owner must not raise
        assert await service.call(asyncio.sleep, 0, result="ok") == "ok"
        await service.shutdown()

    asyncio.run(scenario())


def test_interrupted_teardown_can_still_stop_the_loop():
    async def scenario():
        service = ExecutionService()
        await service.call(asyncio.sleep, 0)
        # State left behind by a teardown that was cancelled mid-flight.
        service._teardown = True
        service._closing = True
        await service.shutdown()
        assert service._thread is None and service._loop is None
        assert not service._closing and not service._teardown
        assert await service.call(asyncio.sleep, 0, result=7) == 7
        await service.shutdown()

    asyncio.run(scenario())


def test_cancelled_teardown_is_finished_by_the_next_shutdown():
    """Regression: a timeout-cancelled teardown used to fail the next restart."""

    async def scenario():
        service = ExecutionService()
        await service.call(asyncio.sleep, 0)

        async def blocking():
            await asyncio.sleep(30)

        service.register_shutdown_callback(blocking)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(service.shutdown(), timeout=0.2)
        service.unregister_shutdown_callback(blocking)
        # This used to raise RuntimeError("execution service is shutting down").
        await service.shutdown()
        assert await service.call(asyncio.sleep, 0, result="ok") == "ok"
        await service.shutdown()

    asyncio.run(scenario())


def test_calls_still_rejected_while_the_service_is_closing():
    async def scenario():
        service = ExecutionService()
        await service.call(asyncio.sleep, 0)
        service._closing = True
        with pytest.raises(RuntimeError, match="shutting down"):
            await service.call(asyncio.sleep, 0)
        service._closing = False
        await service.shutdown()

    asyncio.run(scenario())
