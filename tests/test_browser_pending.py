"""Real browser queue persistence, ownership and scheduler/steer boundaries."""
import asyncio
import base64
import dataclasses

import httpx

from tests.test_browser_use import browser_host
from tests.test_session_control import composed


async def pair(client, host):
    code=(await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()['code']
    issued=(await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':code})).json()
    return {'Origin':host.extension_origin(),'Authorization':'Bearer '+issued['token']},issued


def test_pending_edit_cancel_owner_and_fifo_execution(browser_host, monkeypatch):
    import agent_loop
    from session_control.store import ControlStore
    host,c=browser_host
    monkeypatch.setattr(agent_loop,'session_manager',c.manager)
    sid,*_=c.manager.get_or_create_session()
    c.active[sid]='held-run'
    async def scenario():
        await c.control.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
                headers,issued=await pair(client,host)
                other,_=await pair(client,host)
                async def post(path,body,auth=headers):return await client.post('/api/browser/v1/'+path,headers=auth,json=body)
                async def send(text,key,**extra):
                    response=await post('messages',{'session_id':sid,'message':text,'ui_message':text,'mode':'pending','automatic':False,'composer':{'text':text,'contexts':[]},'idempotency_key':key,**extra})
                    assert response.status_code==200,response.text
                    return response.json()['data']
                first=await send('第一条','first')
                second=await send('第二条','second')
                removed=await send('不应执行','removed')
                oid=first['operation_id'];original=c.store.get_operation(oid)
                # A different store instance sees the durable draft immediately.
                assert ControlStore(c.store.path).get_operation(oid)['request']['_browser_draft']['text']=='第一条'
                listing=(await post('steers',{'session_id':sid})).json()['pending']
                assert [row['operationId'] for row in listing]==[oid,second['operation_id'],removed['operation_id']]
                assert (await post('steers',{'session_id':sid},other)).json()['pending']==[]
                for action in ('cancel','edit'):
                    if action=='cancel':response=await post('pending/cancel',{'session_id':sid,'operation_id':oid},other)
                    else:response=await post('messages',{'session_id':sid,'message':'attack','mode':'pending','automatic':False,'edit_operation_id':oid,'idempotency_key':'attack'},other)
                    assert response.status_code==404,response.text
                edited=await send('第一条已修改','edit-first',edit_operation_id=oid)
                assert edited['operation_id']==oid
                revised=c.store.get_operation(oid)
                assert revised['created']==original['created'] and revised['request']['message']=='第一条已修改'
                assert not c.store.update_operation(oid,expected='queued',expected_updated=original['updated'],status='running')
                # Empty/invalid edit identities must never admit a new message.
                for invalid in ('',None,False):
                    bad=await post('messages',{'session_id':sid,'message':'must not send','mode':'pending','automatic':False,'edit_operation_id':invalid,'idempotency_key':'bad-edit'})
                    assert bad.status_code==400,bad.text
                for _ in range(2):
                    response=await post('pending/cancel',{'session_id':sid,'operation_id':removed['operation_id']})
                    assert response.status_code==200,response.text
                assert c.active[sid]=='held-run' and not c.calls
                listing=(await post('steers',{'session_id':sid})).json()['pending']
                assert [row['draft']['text'] for row in listing]==['第一条已修改','第二条']
                c.active.clear()
                for receipt in (first,second):
                    done,_=await c.service.execute(c.admin,'operation.wait',{'id':receipt['operation_id'],'timeout':10})
                    assert done['status']=='succeeded',done
                assert [row[1] for row in c.calls]==['第一条已修改','第二条']
                late=await post('pending/cancel',{'session_id':sid,'operation_id':oid})
                assert late.status_code==409
                assert c.store.get_operation(oid)['status']=='succeeded'
                assert not (await post('steers',{'session_id':sid})).json()['pending']
                assert not c.manager.is_interrupt_requested(sid,first['run_id'])
        finally:
            c.active.clear()
            await c.control.close()
    asyncio.run(scenario())


def test_interrupt_aborts_real_control_and_preserves_image_in_live_and_history(browser_host,monkeypatch):
    import agent_loop
    import webui
    import session_control.integration
    host,c=browser_host
    monkeypatch.setattr(session_control.integration,'_application',c.control)
    monkeypatch.setattr(webui,'WORK_DIR',c.root)
    monkeypatch.setattr(agent_loop,'session_manager',c.manager)
    sid,*_=c.manager.get_or_create_session()
    c.active[sid]='held-interrupt-run'
    control=agent_loop._register_steer_run_control(sid,'held-interrupt-run')
    async def scenario():
        await c.control.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
                headers,issued=await pair(client,host)
                image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1cAAAAASUVORK5CYII=')
                upload=await client.post('/api/browser/v1/uploads?session_id='+sid,headers=headers,files={'files':('steer.png',image,'image/png')})
                assert upload.status_code==200,upload.text
                identity=upload.json()['files'][0]['id']
                body={'session_id':sid,'message':'按图片调整','ui_message':'按图片调整','mode':'interrupt','automatic':False,'idempotency_key':'interrupt-image','attachments':[{'id':identity}]}
                principal=c.control.identities.authenticate(issued['token'])
                restricted=dataclasses.replace(principal,policy={'scope':'all','capabilities':['system.health','session.send','session.steer','session.history']})
                token=c.control.identities.issue(restricted)
                denied=await client.post('/api/browser/v1/messages',headers={**headers,'Authorization':'Bearer '+token},json=body)
                assert denied.status_code==403,denied.text
                assert not control.is_aborted()
                response=await client.post('/api/browser/v1/messages',headers=headers,json=body)
                assert response.status_code==200,response.text
                receipt=response.json()['data']
                assert receipt['aborted'] and control.is_aborted()
                assert receipt['item']['mode']=='interrupt' and receipt['item']['state']=='interrupting'
                assert receipt['item']['ui_attachments'][0]['attachmentId']
                model={'session_id':sid,'_runtime_v2_run_id':'held-interrupt-run','work_messages':[],'llm_history':[],'stream_events':[]}
                assert await agent_loop._consume_steer_messages(model,modes={'interrupt'})
                assert model['work_messages'][0].content==receipt['item']['user_content']
                event=model['stream_events'][0]
                assert event['steer_mode']=='interrupt' and event['attachments']==receipt['item']['ui_attachments']
                history,_=await c.service.execute(c.admin,'session.history',{'session_id':sid})
                consumed=[event for event in history['events'] if event['type']=='user_steer']
                assert len(consumed)==1 and consumed[0]['attachments']==event['attachments']
                listing=(await client.post('/api/browser/v1/steers',headers=headers,json={'session_id':sid})).json()
                assert listing['items'][0]['ui_attachments']==event['attachments']
                replay=await client.post('/api/browser/v1/messages',headers=headers,json=body)
                assert replay.status_code==200 and replay.json()['data']['operation_id']==receipt['operation_id']
                assert not c.calls
        finally:
            agent_loop._clear_steer_run_control(sid,control)
            c.active.clear()
            await c.control.close()
    asyncio.run(scenario())
