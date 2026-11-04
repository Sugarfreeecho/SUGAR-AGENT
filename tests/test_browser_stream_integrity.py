import asyncio
from types import SimpleNamespace

import pytest
from tests.test_browser_use import browser_host
from tests.test_session_control import composed


def test_lossless_subscriber_reports_overflow_and_can_resubscribe():
    import session_event_bus as bus
    async def scenario():
        sid='browser-overflow-contract'
        stream=bus.subscribe_session_events(sid,replay_recent=False,persistent=True,fail_on_overflow=True)
        first=asyncio.create_task(anext(stream));await asyncio.sleep(0)
        await bus.publish_session_event(sid,{'type':'run_started','run_id':'r'})
        await first
        for index in range(1100):
            await bus.publish_session_event(sid,{'type':'llm_response_delta','run_id':'r','delta':'x','ephemeral':True})
        with pytest.raises(bus.SessionStreamOverflow):await anext(stream)
        assert not bus._subscribers.get(sid)
        recovered=bus.subscribe_session_events(sid,replay_recent=True,persistent=True,fail_on_overflow=True)
        snapshot=await anext(recovered)
        assert snapshot['replayed_recent'] and snapshot['delta']=='x'*1100
        await recovered.aclose()
    asyncio.run(scenario())


def test_existing_non_lossless_subscriber_contract_stays_unchanged():
    import session_event_bus as bus
    async def scenario():
        stream=bus.subscribe_session_events('legacy-overflow-contract',replay_recent=False)
        first=asyncio.create_task(anext(stream));await asyncio.sleep(0)
        await bus.publish_session_event('legacy-overflow-contract',{'type':'status','content':'first'})
        await first
        for index in range(1100):await bus.publish_session_event('legacy-overflow-contract',{'type':'status','content':str(index)})
        assert (await anext(stream))['content']=='0'
        await stream.aclose()
    asyncio.run(scenario())


def test_large_initial_replay_does_not_fail_before_subscriber_registration():
    import session_event_bus as bus
    async def scenario():
        sid='large-browser-bootstrap'
        for index in range(1100):
            await bus.publish_session_event(sid,{'type':'llm_reasoning_delta','run_id':'run','react_iter':index,'ephemeral':True,'delta':'x'})
        stream=bus.subscribe_session_events(sid,persistent=True,fail_on_overflow=True)
        assert (await anext(stream))['replayed_recent']
        assert bus._subscribers.get(sid)
        await stream.aclose();await bus.close_session_stream(sid)
    asyncio.run(scenario())


@pytest.mark.parametrize('fault,code',[('exception',1011),('overflow',4429),('ended',1012),('typed',None)])
def test_broken_forwarder_closes_transport_and_typed_results_do_not_kill_sender(browser_host,monkeypatch,fault,code):
    import session_event_bus as bus
    from pathlib import Path
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from tests.test_browser_pending import pair
    import httpx
    host,c=browser_host
    async def issued():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
            return (await pair(client,host))[1]
    credentials=asyncio.run(issued());sid,*_=c.manager.get_or_create_session()
    class Service:
        async def call(self,fn,*args):return await fn(*args)
    async def ensure(_):return SimpleNamespace(relay_url=lambda:'ws://127.0.0.1:1/extension?token=fixture')
    monkeypatch.setattr(host,'_manager',SimpleNamespace(enabled=lambda:True,ensure=ensure,service=Service(),bindings={}))
    if fault!='typed':
        async def broken(*_a,**_k):
            if fault=='exception':raise RuntimeError('fixture failure')
            if fault=='overflow':raise bus.SessionStreamOverflow('fixture overflow')
            if False:yield
        monkeypatch.setattr(bus,'subscribe_session_events',broken)
    async def loopback(scope,receive,send):await c.app({**scope,'client':('127.0.0.1',1234)},receive,send)
    with TestClient(loopback) as client:
        with client.websocket_connect('/api/browser/v1/ws',headers={'Origin':host.extension_origin()}) as ws:
            ws.send_json({'type':'hello',**credentials})
            assert ws.receive_json()['type']=='ready'
            ws.send_json({'type':'subscribe','session_id':sid})
            if code:
                with pytest.raises(WebSocketDisconnect) as closed:
                    while True:ws.receive_json()
                assert closed.value.code==code
            else:
                while ws.receive_json()['type']!='session.metadata':pass
                client.portal.call(bus.publish_session_event,sid,{'type':'tool_call','result':{'path':Path('fixture-file')}})
                assert ws.receive_json()['event']['result']['path']=='fixture-file'
                ws.send_json({'type':'ping'});assert ws.receive_json()['type']=='pong'
