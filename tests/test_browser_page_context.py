"""Page references travel with durable inputs; browser focus is never authority."""
import asyncio
import threading

import httpx

from tests.test_browser_use import browser_host
from tests.test_session_control import composed


def test_browser_message_context_is_scoped_durable_queued_and_optional(browser_host):
    host, c = browser_host
    manager = host._manager
    snapshots = []
    gate = threading.Event()
    begin = manager.begin_input

    def before(session_id, run_id, params):
        begin(session_id, run_id, params)
        snapshots.append((run_id, manager.run_contexts[run_id]))
    manager.begin_input = before
    original = c.service.deps.astream_events

    async def stream(message, **kwargs):
        if message.startswith('总结这页'):
            await asyncio.to_thread(gate.wait, 10)
        async for event in original(message, **kwargs):
            yield event
    c.service.deps.astream_events = stream

    async def scenario():
        await c.control.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
                pairing = (await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()
                issued = (await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':pairing['code']})).json()
                headers={'Origin':host.extension_origin(),'Authorization':'Bearer '+issued['token']}
                async def rpc(method, params, key):
                    response=await client.post('/api/control/v1/rpc',headers=headers,json={'method':method,'params':params,'idempotency_key':key})
                    assert response.status_code==200,response.text
                    return response.json()['data']
                sid=(await rpc('session.create',{'name':'页面引用回归'},'create'))['session_id']
                page={'tab_id':11,'window_id':1,'target_id':'target-A','url':'https://example.test/a','title':'页面 A',
                      'captured_at':'2026-10-30T10:00:00+08:00','selection':{'text':'用户选择的段落','frame_id':0,'frame_url':'https://example.test/a','truncated':False},
                      'text':'不得自动附加的整页正文'}
                first={'session_id':sid,'message':'总结这页','ui_message':'总结这页','mode':'queue','automatic':True,
                       'browser_context':{'browser_id':'forged-other-browser','page':page},'idempotency_key':'page-A'}
                async def send(body, request_headers=headers):
                    return await client.post('/api/browser/v1/messages',headers=request_headers,json=body)
                assert (await send(first,{'Origin':host.extension_origin()})).status_code==401
                assert (await send(first,{**headers,'Origin':'https://foreign.test'})).status_code==403
                response=await send(first);assert response.status_code==200,response.text
                receipt=response.json()['data']
                for _ in range(100):
                    if snapshots:break
                    await asyncio.sleep(.02)
                assert snapshots and snapshots[0][0]==receipt['run_id']
                assert snapshots[0][1]['browser_id']==issued['browser_id']
                assert manager.run_bindings[receipt['run_id']]==issued['browser_id']
                assert 'text' not in snapshots[0][1]['page']
                replay=await send(first);assert replay.json()['data']['operation_id']==receipt['operation_id']
                second={**first,'message':'解释这段','ui_message':'解释这段','idempotency_key':'page-B',
                        'browser_context':{'page':{**page,'tab_id':22,'target_id':'target-B','url':'https://example.test/b','title':'页面 B'}}}
                queued=await send(second);assert queued.status_code==200,queued.text
                assert manager.run_contexts[receipt['run_id']]['page']['target_id']=='target-A'
                assert len(snapshots)==1
                gate.set()
                for operation in (receipt,queued.json()['data']):
                    finished=await rpc('operation.wait',{'id':operation['operation_id'],'timeout':10},'wait-'+operation['operation_id'])
                    assert finished['status']=='succeeded',finished
                assert [entry[1]['page']['target_id'] for entry in snapshots]==['target-A','target-B']
                assert '用户选择的段落' in c.calls[0][1]
                assert '不得自动附加的整页正文' not in c.calls[0][1]
                assert '页面 B' in c.calls[1][1]
                assert receipt['run_id'] not in manager.run_contexts
                disabled={**first,'message':'一般问题','ui_message':'一般问题','automatic':False,'idempotency_key':'disabled'}
                response=await send(disabled);assert response.status_code==200,response.text
                await rpc('operation.wait',{'id':response.json()['data']['operation_id'],'timeout':10},'wait-disabled')
                assert c.calls[-1][1]=='一般问题'
                assert snapshots[-1][1]['automatic'] is False
                for invalid in ({**first,'_browser_context':{}}, {**first,'browser_context':{'page':{**page,'url':'chrome://settings'}}},
                                {**first,'browser_context':{'page':{**page,'selection':{'text':'x'*8001}}}}):
                    assert (await send(invalid)).status_code==400
        finally:
            gate.set()
            await c.control.close()
    asyncio.run(scenario())
