"""Real paired adapters, durable cards, Web UI handlers and live tool waiters."""
import ast
import asyncio
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

import httpx
import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from tests.test_browser_use import browser_host
from tests.test_session_control import composed

ROOT = Path(__file__).resolve().parents[1]


def human_runtime(c, patch):
    patch.setenv('ASK_USER_ENABLED', '1')
    import attachments
    import human_interaction.service as human
    import security
    import security.reviewer
    import tool_approval_gate as gate
    from runtime_v2 import RuntimeHistoryOps
    from session_event_bus import publish_session_event
    from security.models import CapabilityRequest
    service = human.HumanInteractionService(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
    patch.setattr(human, '_shared_human_interaction_service', service)
    patch.setattr(gate, 'session_manager', c.manager)
    store_factory = attachments.get_attachment_store
    patch.setattr(attachments, 'get_attachment_store', lambda _root=None: store_factory(c.root))
    state = SimpleNamespace(service=service, tasks=[], grants=[], recoveries=[], results={}, fail_next=False, delay=0)
    patch.setattr(security, 'add_approval_grant', lambda *args: state.grants.append(('grant', args)))
    patch.setattr(security, 'add_permission_rule', lambda **kwargs: state.grants.append(('rule', kwargs)))
    async def review(*args, **kwargs):
        return SimpleNamespace(approved=True, risk='low', reason='仅检查隔离测试文件', available=True,
                               intercept_reason='请求需要确认', risk_analysis='只读操作', command_purpose='验证浏览器审批')
    patch.setattr(security.reviewer, 'review_request', review)
    def recovered(record, *args):
        state.recoveries.append(record)
        return True
    source = ast.parse((ROOT / 'app/webui.py').read_text(encoding='utf-8-sig'))
    names = {'resolve_session_interaction', 'cancel_session_interaction', 'resolve_session_approval',
             'analyze_session_approval', '_human_interaction_error_response', '_interaction_resolver_metadata'}
    callbacks = [node for node in source.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    for callback in callbacks:
        callback.decorator_list = []
    namespace = dict(Request=Request, JSONResponse=JSONResponse, asyncio=asyncio, logger=logging.getLogger(__name__),
                     publish_session_event=publish_session_event, session_manager=c.manager,
                     _has_local_worker_activity=lambda sid: sid in c.active,
                     _append_recovered_question_tool_result=recovered, _append_recovered_approval_result=recovered,
                     _schedule_human_interaction_recovery=lambda sid: True)
    exec(compile(ast.Module(body=callbacks, type_ignores=[]), 'app/webui.py', 'exec'), namespace)
    async def tokens(_sid): return JSONResponse({'ok': True, 'estimated': 10000, 'threshold': 128000})
    patch.setitem(sys.modules, 'webui', SimpleNamespace(**{name: namespace[name] for name in names}, get_session_context_tokens=tokens))
    patch.setattr(security, 'security_status_for_session', lambda _sid: {'mode':'ask_for_approval', 'security_enabled':True,
        'available_modes':{'ask_for_approval':True, 'approve_for_me':True, 'full_access':True}})
    ops = RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)

    async def create(sid, kind='question', *, questions=None, forced=False, persistent=False, workspace=False, stale=False):
        run, identity = uuid.uuid4().hex, uuid.uuid4().hex
        ops.commit_user_turn(sid, '人机交互验证', operation_id='user-'+run, run_id=run)
        async def emit(event): await publish_session_event(sid, event)
        metadata = dict(_durable=True, run_id=run, tool_call_id='call-'+identity, tool='run_shell', title='检查工作区文件',
                        message='运行 `git status`，检查文件变更。', subtitle='请确认本次操作', security_request_digest='security-'+identity,
                        force_approval=forced, allow_session_available=not forced, allow_always_available=persistent,
                        rule_action='process.exec' if persistent else '', rule_pattern='git status' if persistent else '',
                        external_workspace_grantable=workspace, approval_level='danger' if forced else 'warning')
        if stale:
            return service.create_approval(sid, approval_id=identity, metadata={key:value for key,value in metadata.items() if not key.startswith('_')}, run_id=run)
        c.active[sid]=run
        async def worker():
            try:
                await emit({'type':'run_started','run_id':run,'ephemeral':True})
                if kind=='question':
                    result=await human.wait_for_user_answers(sid, {'questions':questions or [{'header':'范围','question':'选择实现范围？',
                        'options':[{'label':'完整实现','description':'包含前后端'},{'label':'先做界面','description':'只做前端'}]}]}, run_id=run, tool_call_id='call-'+identity, emit=emit)
                else:
                    async def approval_emit(): await emit({'type':'approval_requested', **service.get(sid,identity,kind='approval')})
                    result=await gate.wait_tool_ui_approval_after_emit(sid,identity,approval_emit,metadata=metadata,return_resolution=True,
                        review_context={'request':CapabilityRequest.create(action='process.exec',resource='git status',effect='read'), 'user_intent':'检查测试工作区'})
                state.results[identity]=result
                text='交互完成，Agent 已继续。'
                ops.commit_assistant_final(sid,text,operation_id='final-'+run,run_id=run)
                await emit({'type':'final','run_id':run,'content':text})
                await emit({'type':'run_finished','run_id':run,'result_status':'succeeded','ephemeral':True})
            finally:
                c.active.pop(sid,None)
        task=asyncio.create_task(worker());state.tasks.append(task)
        for _ in range(500):
            rows=service.list(sid,kind=kind,status='pending')
            row=next((row for row in rows if row.get('run_id')==run),None)
            if row:return row
            if task.done():await task
            await asyncio.sleep(.01)
        raise RuntimeError('Human waiter did not start')
    state.create=create
    return state


def test_browser_human_answers_wake_real_waiter_and_persist(browser_host, monkeypatch):
    host,c=browser_host
    state=human_runtime(c,monkeypatch)
    sid,*_=c.manager.get_or_create_session()
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
            pairing=(await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()
            claim=(await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':pairing['code']})).json()
            headers={'Origin':host.extension_origin(),'Authorization':'Bearer '+claim['token']}
            ask=await state.create(sid)
            listed=await client.post('/api/browser/v1/human/list',headers=headers,json={'session_id':sid})
            assert listed.json()['records'][0]['interaction_id']==ask['interaction_id']
            payload={'session_id':sid,'interaction_id':ask['interaction_id'],'request_digest':ask['request_digest'],
                     'answers':[{'question_id':'q1','selected_option_ids':['q1o1']}]}
            bad=await client.post('/api/browser/v1/questions/resolve',headers=headers,json={**payload,'request_digest':'stale'})
            assert bad.status_code==409 and not state.tasks[-1].done()
            result=await client.post('/api/browser/v1/questions/resolve',headers=headers,json=payload)
            assert result.status_code==200,result.text
            await asyncio.wait_for(state.tasks[-1],5)
            assert state.service.get(sid,ask['interaction_id'])['answers'][0]['selected_labels']==['完整实现']
            assert len(state.results)==1
            # The same answer is a terminal replay, not another tool execution.
            replay=await client.post('/api/browser/v1/questions/resolve',headers=headers,json=payload)
            assert replay.json()['interaction']['status']=='resolved'
            assert result.json()['interaction']['resolver']['client'].startswith('browser-use:')
            ask=await state.create(sid)
            cancelled=await client.post('/api/browser/v1/questions/cancel',headers=headers,json={'session_id':sid,'interaction_id':ask['interaction_id'],'request_digest':ask['request_digest']})
            assert cancelled.json()['interaction']['status']=='cancelled'
            await asyncio.wait_for(state.tasks[-1],5)
    asyncio.run(scenario())


@pytest.mark.parametrize('removed_during_read', [False, True])
def test_human_list_ignores_removed_descendants_but_preserves_parent_cards(browser_host, monkeypatch, removed_during_read):
    from dataclasses import replace
    host,c=browser_host
    state=human_runtime(c,monkeypatch)
    sid,*_=c.manager.get_or_create_session()
    child=str(uuid.uuid4());missing=str(uuid.uuid4())
    c.manager.create_session_with_id(child,work_dir=str(c.root))
    question={'questions':[{'header':'范围','question':'保留哪个方案？','options':[{'label':'方案 A','description':'完整保留'},{'label':'方案 B','description':'精简保留'}]}]}
    parent_card=state.service.create_question(sid,question)
    child_card=state.service.create_question(child,question)
    monkeypatch.setattr(c.manager,'list_subagent_descendants',lambda _: [missing,child])
    original=c.control.service.authorize
    if removed_during_read:
        def authorize(principal,method,params):
            if params.get('session_id')==child and method=='approval.list' and c.manager.get_session_summary(child):
                c.manager.delete_session(child)
            return original(principal,method,params)
        monkeypatch.setattr(c.control.service,'authorize',authorize)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
            pairing=(await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()
            claim=(await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':pairing['code']})).json()
            headers={'Origin':host.extension_origin(),'Authorization':'Bearer '+claim['token']}
            listed=await client.post('/api/browser/v1/human/list',headers=headers,json={'session_id':sid,'include_descendants':True})
            assert listed.status_code==200,listed.text
            identities={row['interaction_id'] for row in listed.json()['records']}
            assert parent_card['interaction_id'] in identities
            assert (child_card['interaction_id'] in identities) is not removed_during_read
            principal=c.control.identities.authenticate(claim['token'])
            restricted=c.control.identities.issue(replace(principal,policy={**principal.policy,'scope':'sessions','session_ids':[sid]}))
            scoped=await client.post('/api/browser/v1/human/list',headers={**headers,'Authorization':'Bearer '+restricted},json={'session_id':sid})
            assert scoped.status_code==200
            assert {row['session_id'] for row in scoped.json()['records']}=={sid}
            absent=await client.post('/api/browser/v1/human/list',headers=headers,json={'session_id':missing})
            assert absent.status_code==404
            assert '重新选择' in absent.json()['detail']
    asyncio.run(scenario())


def test_browser_approval_uses_full_resolution_and_rejects_scope_escalation(browser_host, monkeypatch):
    from dataclasses import replace
    host,c=browser_host
    state=human_runtime(c,monkeypatch)
    sid,*_=c.manager.get_or_create_session()
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
            pairing=(await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()
            claim=(await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':pairing['code']})).json()
            headers={'Origin':host.extension_origin(),'Authorization':'Bearer '+claim['token']}
            approval=await state.create(sid,'approval',forced=True)
            payload={'session_id':sid,'approval_id':approval['approval_id'],'request_digest':approval['request_digest'],'decision':'allow_always'}
            denied=await client.post('/api/browser/v1/approvals/resolve',headers=headers,json=payload)
            assert denied.status_code==422 and state.grants==[]
            response=await client.post('/api/browser/v1/approvals/resolve',headers=headers,json={**payload,'decision':'deny','rejection_reason':'先检查路径'})
            assert response.status_code==200,response.text
            await asyncio.wait_for(state.tasks[-1],5)
            assert state.results[approval['approval_id']]['rejection_reason']=='先检查路径'
            approval=await state.create(sid,'approval',persistent=True)
            payload={**payload,'approval_id':approval['approval_id'],'request_digest':approval['request_digest']}
            response=await client.post('/api/browser/v1/approvals/resolve',headers=headers,json=payload)
            assert response.status_code==200,response.text
            await asyncio.wait_for(state.tasks[-1],5)
            assert state.grants[-1][0]=='rule' and state.grants[-1][1]['pattern']=='git status'
            principal=c.control.identities.authenticate(claim['token'])
            restricted=c.control.identities.issue(replace(principal,policy={**principal.policy,'scope':'sessions','session_ids':[]}))
            assert (await client.post('/api/browser/v1/human/list',headers={**headers,'Authorization':'Bearer '+restricted},json={'session_id':sid})).status_code==403
            stale=await state.create(sid,'approval',stale=True)
            response=await client.post('/api/browser/v1/approvals/resolve',headers=headers,json={'session_id':sid,'approval_id':stale['approval_id'],'request_digest':stale['request_digest'],'decision':'allow_once'})
            assert response.status_code==409 and state.service.get(sid,stale['approval_id'],kind='approval')['status']=='cancelled'
    asyncio.run(scenario())
