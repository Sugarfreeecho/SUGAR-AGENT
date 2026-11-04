"""Persistent user pairing survives plugin leases and transient transport faults."""
import asyncio
import dataclasses
from types import SimpleNamespace

import httpx
import pytest

from tests.test_browser_use import browser_host
from tests.test_session_control import composed


async def pair(host, client):
    code = (await client.post('/api/browser/v1/pairings', headers={'Origin':'http://127.0.0.1'}, json={})).json()['code']
    return (await client.post('/api/browser/v1/claim', headers={'Origin':host.extension_origin()}, json={'code':code})).json()


def test_pairing_survives_plugin_disable_enable_and_operation_leases_still_expire(browser_host):
    host, c = browser_host
    from session_control.public import source_state
    from session_control.errors import ControlError
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            issued = await pair(host, client)
            principal = c.control.identities.authenticate(issued['token'])
            assert principal.source_ancestors[0]['kind'] == 'browser-pairing'
            headers = {'Authorization':'Bearer '+issued['token']}
            assert (await client.get('/api/browser/v1/connection', headers=headers)).json() == {'paired':True,'browser_id':issued['browser_id']}
            original = c.store.get('host_sources', 'browser-use')
            source_state('browser-use', False, app=c.control)
            assert (await client.get('/api/browser/v1/connection', headers=headers)).status_code == 403
            renewed = source_state('browser-use', True, app=c.control)
            assert renewed['epoch'] > original['epoch']
            assert (await client.get('/api/browser/v1/connection', headers=headers)).status_code == 200
            with pytest.raises(ControlError, match='revoked'):
                c.service.authorize(principal, 'system.health', {'_source':{'id':'browser-use','epoch':original['epoch']}})
            c.control.identities.remote.revoke_device(issued['browser_id'])
            assert (await client.get('/api/browser/v1/connection', headers=headers)).status_code == 401
    asyncio.run(scenario())


def test_restore_only_live_original_paired_browser_grants(browser_host):
    host, c = browser_host
    from session_control.public import source_state
    from session_control.errors import ControlError
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            issued = await pair(host, client)
            principal = c.control.identities.authenticate(issued['token'])
            legacy = dataclasses.replace(principal, source_ancestors=[{**principal.source_ancestors[0],'kind':'plugin'}])
            token = c.control.identities.issue(legacy, ttl=86400)
            revoked = c.control.identities.issue(legacy)
            c.control.identities.revoke(revoked)
            expired = c.control.identities.issue(legacy, ttl=-1)
            child = c.control.identities.issue(dataclasses.replace(legacy, parent_id=legacy.id))
            unpaired = c.control.identities.issue(dataclasses.replace(legacy, id='unpaired'))
            source_state('browser-use', False, app=c.control)
            source_state('browser-use', True, app=c.control)
            assert (await client.get('/api/browser/v1/connection', headers={'Authorization':'Bearer '+token})).status_code == 403
            host.restore_pairing_grants(c.control)
            restored = c.control.identities.authenticate(token)
            assert restored.policy == legacy.policy
            assert restored.source_ancestors[0]['kind'] == 'browser-pairing'
            assert (await client.get('/api/browser/v1/connection', headers={'Authorization':'Bearer '+token})).status_code == 200
            for old in (revoked, expired):
                with pytest.raises(ControlError):c.control.identities.authenticate(old)
            assert c.control.identities.authenticate(child).source_ancestors[0]['kind'] == 'plugin'
            assert c.control.identities.authenticate(unpaired).source_ancestors[0]['kind'] == 'plugin'
            host.restore_pairing_grants(c.control)
            assert c.control.identities.authenticate(token).source_ancestors == restored.source_ancestors
    asyncio.run(scenario())


@pytest.mark.parametrize('failure,close_code', [('temporary',1011),('disabled',4403),('revoked',4401)])
def test_websocket_auth_failures_are_distinguished_from_runtime_failures(browser_host, monkeypatch, failure, close_code):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from session_control.errors import ControlError
    host, c = browser_host
    async def issue():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            return await pair(host, client)
    issued = asyncio.run(issue())
    class LocalService:
        async def call(self, fn, *args):return await fn(*args)
    async def ensure(_record):
        if failure == 'temporary':raise ControlError('control_unavailable','Temporary host failure',status=503)
        return SimpleNamespace(relay_url=lambda:'ws://127.0.0.1:1/extension')
    monkeypatch.setattr(host, '_manager', SimpleNamespace(enabled=lambda:True, ensure=ensure, service=LocalService(), bindings={}))
    if failure == 'revoked':c.control.identities.remote.revoke_device(issued['browser_id'])
    if failure == 'disabled':
        from session_control.public import source_state
        source_state('browser-use',False,app=c.control)
    async def loopback(scope, receive, send):await c.app({**scope,'client':('127.0.0.1',1234)},receive,send)
    with TestClient(loopback) as client:
        with client.websocket_connect('/api/browser/v1/ws',headers={'Origin':host.extension_origin()}) as ws:
            ws.send_json({'type':'hello','token':issued['token'],'browser_id':issued['browser_id']})
            if failure == 'temporary':assert ws.receive_json()['code'] == 'browser_runtime_unavailable'
            with pytest.raises(WebSocketDisconnect) as closed:ws.receive_json()
            assert closed.value.code == close_code
