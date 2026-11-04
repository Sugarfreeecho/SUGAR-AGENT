"""Browser append admission, durable consumption and run-boundary retries."""
import asyncio
import dataclasses
import json

import httpx

from tests.test_browser_use import browser_host
from tests.test_session_control import composed


def test_browser_append_uses_real_steer_queue_and_attachment_admission(browser_host, monkeypatch):
    import agent_loop
    host, c = browser_host
    monkeypatch.setattr(agent_loop, 'session_manager', c.manager)
    sid, *_ = c.manager.get_or_create_session()
    c.active[sid] = 'existing-run'
    uploaded = c.root / 'reference.txt'
    uploaded.write_text('附加的测试资料', encoding='utf-8')

    async def scenario():
        await c.control.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
                pairing = (await client.post('/api/browser/v1/pairings', headers={'Origin':'http://127.0.0.1'}, json={})).json()
                issued = (await client.post('/api/browser/v1/claim', headers={'Origin':host.extension_origin()}, json={'code':pairing['code']})).json()
                headers = {'Origin':host.extension_origin(), 'Authorization':'Bearer '+issued['token']}
                c.store.put('message_uploads', 'owned-file', {'owner':issued['browser_id'], 'path':str(uploaded), 'name':uploaded.name})
                body = {'session_id':sid, 'message':'改用简短回答', 'ui_message':'改用简短回答', 'mode':'append',
                        'automatic':False, 'idempotency_key':'append-one', 'attachments':[{'id':'owned-file'}]}
                async def send(value=body, auth=headers):
                    return await client.post('/api/browser/v1/messages', headers=auth, json=value)
                response = await send()
                assert response.status_code == 200, response.text
                receipt = response.json()['data']
                assert receipt['accepted'] and receipt['item']['state'] == 'queued'
                assert receipt['aborted'] is False and receipt['restart'] is False
                assert c.store.get_operation(receipt['operation_id'])['method'] == 'session.steer'
                assert c.calls == [] and c.active[sid] == 'existing-run'
                canonical = receipt['item']['user_content']
                assert uploaded.name in json.dumps(canonical) and '改用简短回答' in json.dumps(canonical, ensure_ascii=False)
                replay = await send()
                assert replay.json()['data']['operation_id'] == receipt['operation_id']
                changed = await send({**body, 'message':'different'})
                assert changed.status_code == 409
                listing = await client.post('/api/browser/v1/steers', headers=headers, json={'session_id':sid})
                assert listing.status_code == 200
                row = listing.json()['items'][0]
                assert row['state'] == 'queued' and 'user_content' not in row and 'content' not in row
                assert str(uploaded) not in listing.text
                model = {'session_id':sid, '_runtime_v2_run_id':'existing-run', 'work_messages':[], 'llm_history':[], 'stream_events':[]}
                assert await agent_loop._consume_steer_messages(model, modes={'append'})
                assert model['work_messages'][0].content == canonical
                assert model['stream_events'][0]['type'] == 'user_steer'
                assert model['stream_events'][0]['steer_id'] == row['id']
                assert not await agent_loop._consume_steer_messages(model, modes={'append'})
                listing = await client.post('/api/browser/v1/steers', headers=headers, json={'session_id':sid})
                assert listing.json()['items'][0]['state'] == 'consumed'
                assert listing.json()['items'][0]['consumed_by'] == 'existing-run'
                history, _ = await c.service.execute(c.admin, 'session.history', {'session_id':sid})
                assert len([event for event in history['events'] if event['type'] == 'user_steer']) == 1
                c.active.pop(sid)
                # Replaying after the run ended must return the same steer, not
                # route it to a fresh queued turn or reject its idempotency key.
                replay = await send()
                assert replay.status_code == 200, replay.text
                assert replay.json()['data']['operation_id'] == receipt['operation_id'] and c.calls == []
                for mode in ('invented',):
                    assert (await send({**body, 'mode':mode, 'idempotency_key':mode})).status_code == 400
                for attachments in ([{'path':str(uploaded)}], [{'id':'missing'}]):
                    assert (await send({**body, 'attachments':attachments, 'idempotency_key':'bad-attachments'})).status_code >= 400
                principal = c.control.identities.authenticate(issued['token'])
                restricted = dataclasses.replace(principal, policy={'scope':'all', 'capabilities':['system.health','session.send','session.history']})
                restricted_token = c.control.identities.issue(restricted)
                denied = await send({**body, 'idempotency_key':'no-steer'}, {**headers,'Authorization':'Bearer '+restricted_token})
                assert denied.status_code == 403, denied.text
                missing = await client.post('/api/browser/v1/steers', headers=headers, json={'session_id':'deleted-session'})
                assert missing.status_code == 404
                assert (await client.post('/api/browser/v1/steers', headers={'Origin':host.extension_origin()}, json={'session_id':sid})).status_code == 401
        finally:
            c.active.clear()
            await c.control.close()
    asyncio.run(scenario())


def test_append_after_completion_becomes_one_normal_turn(browser_host, monkeypatch):
    import agent_loop
    host, c = browser_host
    monkeypatch.setattr(agent_loop, 'session_manager', c.manager)
    sid, *_ = c.manager.get_or_create_session()
    async def scenario():
        await c.control.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
                code = (await client.post('/api/browser/v1/pairings', headers={'Origin':'http://127.0.0.1'}, json={})).json()['code']
                issued = (await client.post('/api/browser/v1/claim', headers={'Origin':host.extension_origin()}, json={'code':code})).json()
                headers = {'Origin':host.extension_origin(), 'Authorization':'Bearer '+issued['token']}
                body = {'session_id':sid, 'message':'刚结束时发送', 'mode':'append', 'automatic':False, 'idempotency_key':'at-boundary'}
                receipt = (await client.post('/api/browser/v1/messages', headers=headers, json=body)).json()['data']
                assert 'item' not in receipt
                done, _ = await c.service.execute(c.admin, 'operation.wait', {'id':receipt['operation_id'], 'timeout':10})
                assert done['status'] == 'succeeded'
                replay = await client.post('/api/browser/v1/messages', headers=headers, json=body)
                assert replay.status_code == 200 and replay.json()['data']['operation_id'] == receipt['operation_id']
                assert len(c.calls) == 1 and len(c.manager.list_sessions()) == 1
        finally:
            await c.control.close()
    asyncio.run(scenario())
