import asyncio

import pytest

from history_operation_requests import HistoryOperationRequests


def test_concurrent_retry_and_disconnect_keep_one_branch():
    async def exercise():
        requests = HistoryOperationRequests()
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def create():
            calls.append(1)
            entered.set()
            await release.wait()
            return {'ok': True, 'session_id': 'branch'}
        first = asyncio.create_task(requests.run(('source', 'nonce'), (2, 4), create))
        await entered.wait()
        retry = asyncio.create_task(requests.run(('source', 'nonce'), (2, 4), create))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert (await retry)['session_id'] == 'branch'
        assert await requests.run(('source', 'nonce'), (2, 4), create) == await retry
        assert calls == [1]
        assert (await requests.run(('source', 'nonce'), (3, 5), create))['error'] == 'branch_request_conflict'
    asyncio.run(exercise())


def test_failures_can_retry_and_receipts_are_bounded():
    async def exercise():
        requests = HistoryOperationRequests(limit=2, ttl=600)
        outcomes = iter([{'ok': False}, {'ok': True, 'session_id': 'b'}])
        async def create():
            return next(outcomes)
        assert (await requests.run('one', (), create))['ok'] is False
        assert (await requests.run('one', (), create))['ok'] is True
        async def success():
            return {'ok': True}
        await requests.run('two', (), success)
        await requests.run('three', (), success)
        assert len(requests.entries) == 2
        requests.ttl = 0
        await requests.run('four', (), success)
        assert list(requests.entries) == ['four']
    asyncio.run(exercise())


def test_full_pending_table_does_not_evict_inflight_branch():
    async def exercise():
        requests = HistoryOperationRequests(limit=1)
        entered, release = asyncio.Event(), asyncio.Event()
        async def create():
            entered.set()
            await release.wait()
            return {'ok': True}
        first = asyncio.create_task(requests.run('one', (), create))
        await entered.wait()
        assert (await requests.run('two', (), create))['error'] == 'branch_requests_busy'
        release.set()
        await first
    asyncio.run(exercise())
