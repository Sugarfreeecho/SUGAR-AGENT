"""Sidebar identity/permission locks must not block unrelated HTTP traffic."""
import asyncio
import importlib
import threading

import httpx
import pytest

from session_control.policy import Principal
from tests.test_browser_use import browser_host
from tests.test_session_control import composed


@pytest.mark.parametrize('blocked', ['authenticate', 'authorize'])
def test_sidebar_security_reads_leave_http_loop_responsive(browser_host, monkeypatch, blocked):
    import agent_loop
    host, c = browser_host
    entered, release = threading.Event(), threading.Event()
    calls = []
    principal = Principal('test-browser', admin=True)
    def gate(stage):
        calls.append(stage)
        if stage == blocked:
            entered.set()
            assert release.wait(4)
    def authenticate(request):
        gate('authenticate')
        return principal, {}
    def authorize(*args):
        gate('authorize')
    monkeypatch.setattr(host, 'authenticate', authenticate)
    monkeypatch.setattr(host, 'authorize_session', authorize)
    monkeypatch.setattr(agent_loop, 'list_session_steers', lambda *args, **kw: {'items': []})
    pending = importlib.import_module(host.__package__ + '.pending')
    monkeypatch.setattr(pending, 'pending_messages', lambda *args: [])
    monkeypatch.setattr(pending, 'started_pending_turns', lambda *args: [])
    @c.app.get('/fixture-readiness')
    async def readiness():
        return {'ok': True}
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            request = asyncio.create_task(client.post('/api/browser/v1/steers', json={'session_id': 's'}))
            watchdog = threading.Timer(3, release.set)
            watchdog.start()
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                response = await client.get('/fixture-readiness')
                assert response.json() == {'ok': True}
                assert not release.is_set(), 'security lock stalled unrelated HTTP requests until watchdog release'
            finally:
                release.set()
                watchdog.cancel()
            result = await request
            assert result.status_code == 200, result.text
            assert calls.count('authenticate') == 1
            assert calls.count('authorize') == 3, 'all pre/post-read permission checks must be preserved'
    asyncio.run(exercise())
