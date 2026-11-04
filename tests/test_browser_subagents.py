"""Sidebar subagent navigation uses real nested storage and caller authorization."""
import asyncio
import dataclasses
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pytest

from runtime_v2 import RuntimeHistoryOps
from tests.test_browser_use import browser_host
from tests.test_browser_pending import pair
from tests.test_session_control import composed as composed_base, rpc


@pytest.fixture
def composed(monkeypatch):
    # Three UUID directory levels exceed Windows MAX_PATH under pytest's long
    # default test-name directory. Keep the isolated real store path short.
    with TemporaryDirectory(prefix='sa31-') as directory:
        yield composed_base.__wrapped__(Path(directory), monkeypatch)


def seed(c):
    parent, *_ = c.manager.get_or_create_session()
    c.manager.set_session_name(parent, '主任务')
    child = c.manager.create_subagent_session(parent, '检查接口', 'generalPurpose', 1)
    grandchild = c.manager.create_subagent_session(child, '检查边界', 'generalPurpose', 2)
    c.manager.upsert_subagent_task(parent, child, {'description': '检查接口', 'status': 'completed'})
    c.manager.upsert_subagent_task(child, grandchild, {'description': '检查边界', 'status': 'running'})
    ops = RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
    ops.commit_user_turn(child, '子任务内容', operation_id='child-user', run_id='child-run')
    ops.commit_assistant_final(child, '子任务回答', operation_id='child-final', run_id='child-run')
    return parent, child, grandchild


def test_nested_child_detail_history_attach_and_send_use_real_storage(composed):
    c = composed
    parent, child, grandchild = seed(c)
    assert c.manager.get_session_summary(child) is None  # Deliberately absent from root index.
    async def scenario():
        try:
            for method in ('session.get', 'session.attach', 'session.history'):
                response = await rpc(c, method, {'session_id': child, 'include_runtime': True})
                assert response.status_code == 200, response.text
                data = response.json()['data']
                if method == 'session.get':
                    assert data['session']['id'] == child
                    assert data['session']['parent_session_id'] == parent
                else:
                    history = data.get('history', data)
                    assert any(row.get('content') == '子任务回答' for row in history['events'])
            listing = (await rpc(c, 'session.list')).json()['data']['sessions']
            assert [row['id'] for row in listing] == [parent]
            sent = (await rpc(c, 'session.send', {'session_id': child, 'message': '子会话继续'})).json()['data']
            done = (await rpc(c, 'operation.wait', {'id': sent['operation_id'], 'timeout': 10})).json()['data']
            assert done['status'] == 'succeeded', done
            assert c.calls[0][0:2] == (child, '子会话继续')
        finally:
            await c.control.close()
    asyncio.run(scenario())


def test_catalog_reads_nested_task_metadata_without_scanning_chat_history(browser_host, monkeypatch):
    host, c = browser_host
    parent, child, grandchild = seed(c)
    virtual = str(uuid.uuid4())
    c.manager.upsert_subagent_task(parent, virtual, {'description': '汇总任务', 'status': 'completed', 'virtual_task': True})
    c.active[grandchild] = 'nested-run'
    c.service.callbacks['pending_human'] = lambda sid: int(sid == grandchild)
    monkeypatch.setattr(c.manager, '_load_ui_events_for_active_runtime', lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('must not scan history')))
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            headers, _ = await pair(client, host)
            async def catalog(sid):
                response = await client.post('/api/browser/v1/subagents', headers=headers, json={'session_id': sid})
                assert response.status_code == 200, response.text
                return response.json()
            root = await catalog(parent)
            assert root['root']['id'] == parent and root['parent'] is None
            rows = {row['id']: row for row in root['entries']}
            assert rows[child]['depth'] == 1 and rows[grandchild]['depth'] == 2
            assert rows[grandchild]['running'] and rows[grandchild]['pending_human_count'] == 1
            assert not rows[virtual]['selectable'] and rows[virtual]['virtual_task']
            nested = await catalog(grandchild)
            assert nested['parent']['id'] == child
            assert [row['id'] for row in nested['breadcrumbs']] == [parent, child, grandchild]
            assert nested['parent_available']
    asyncio.run(scenario())


def test_catalog_filters_unauthorized_children_and_does_not_leak_parent_metadata(browser_host):
    host, c = browser_host
    parent, child, grandchild = seed(c)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app), base_url='http://127.0.0.1') as client:
            headers, issued = await pair(client, host)
            principal = c.control.identities.authenticate(issued['token'])
            def scoped(ids):
                token = c.control.identities.issue(dataclasses.replace(principal, policy={'scope': 'sessions', 'session_ids': ids, 'capabilities': ['read']}))
                return {**headers, 'Authorization': 'Bearer ' + token}
            root = await client.post('/api/browser/v1/subagents', headers=scoped([parent]), json={'session_id': parent})
            assert root.status_code == 200, root.text
            assert root.json()['entries'] == []
            only_child = scoped([child])
            detail = await client.post('/api/browser/v1/subagents', headers=only_child, json={'session_id': child})
            assert detail.status_code == 200, detail.text
            data = detail.json()
            assert not data['parent_available'] and data['parent'] is None
            assert data['root']['id'] == child and data['entries'] == []
            assert parent not in detail.text and '主任务' not in detail.text
            denied = await rpc(c, 'session.history', {'session_id': parent}, token=only_child['Authorization'][7:])
            assert denied.status_code == 403
            for value in ('invalid', str(uuid.uuid4())):
                missing = await client.post('/api/browser/v1/subagents', headers=headers, json={'session_id': value})
                assert missing.status_code == 404, missing.text
    asyncio.run(scenario())
