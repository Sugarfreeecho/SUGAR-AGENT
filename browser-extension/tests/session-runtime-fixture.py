"""Isolated real control API for sidebar session/model regression tests.

Only browser automation and LLM output are fixtures. Pairing, authorization,
WebSocket subscription, session persistence and model updates use production code.
"""
import ast
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT)]
os.environ['MYAGENT_UI_CLOSED_NOTIFY'] = '0'

import pytest
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from tests.test_session_control import composed
from plugins import load_plugin
from plugins.host import _module
from runtime_v2 import RuntimeHistoryOps
import model_profiles
import runtime_lifecycle
import session_control.integration

work = Path(sys.argv[1])
work.mkdir(parents=True, exist_ok=True)
patch = pytest.MonkeyPatch()
patch.setattr(runtime_lifecycle, 'state_path', lambda: work / 'lifecycle.sqlite3')
profiles = [dict(id='model-' + name, name='测试模型 ' + name.upper(), model='fixture-' + name,
                 base_url='http://127.0.0.1:1', llm_type='openai', api_key='fixture-only',
                 context_window=128000, max_output_tokens=8192) for name in ('a', 'b')]
patch.setattr(model_profiles, 'load_store', lambda _root: {'profiles': profiles, 'default_profile': 'model-a'})
patch.setattr(model_profiles, 'register_legacy_env_model_profile', lambda *_args: {'action': 'fixture'})
c = composed.__wrapped__(work, patch)
import agent_loop
patch.setattr(agent_loop, 'session_manager', c.manager)
patch.setattr(session_control.integration, '_application', c.control)
original_stream = c.service.deps.astream_events
async def stream(message, **kwargs):
    if state.get('native_stream'):
        async for event in agent_loop.astream_events(message, **kwargs):
            yield event
        return
    from session_event_bus import publish_session_event, close_session_stream
    await publish_session_event(kwargs['session_id'], {'type':'run_started','run_id':kwargs['run_id'],'ephemeral':True})
    async for event in original_stream(message, **kwargs):
        if event.get('type') == 'user' and kwargs.get('user_operation_id'):
            event={**event,'operation_id':kwargs['user_operation_id']}
        if event.get('type') == 'user' and state.get('steer_test'):
            await publish_session_event(kwargs['session_id'], {**event, 'run_id':kwargs['run_id']})
            yield event
            model_state={'session_id':kwargs['session_id'],'_runtime_v2_run_id':kwargs['run_id'],
                         'work_messages':[],'llm_history':[],'stream_events':[]}
            control=agent_loop._register_steer_run_control(kwargs['session_id'],kwargs['run_id'])
            async def emit(value):
                await publish_session_event(kwargs['session_id'],{**value,'run_id':kwargs['run_id']})
            deadline=time.monotonic()+120
            try:
                while not state.get('steer_finish') and time.monotonic()<deadline and not kwargs['should_stop'](kwargs['session_id']):
                    if control.is_aborted():
                        state['steer_interrupts']+=1
                        await agent_loop._consume_steer_messages(model_state,emit,modes={'interrupt'})
                        control.reset()
                    if state.get('steer_consume'):
                        await agent_loop._consume_steer_messages(model_state,emit,modes={'append'})
                    state['steer_inputs']=[agent_loop._message_to_dict(row) for row in model_state['work_messages']]
                    await asyncio.sleep(.05)
            finally:agent_loop._clear_steer_run_control(kwargs['session_id'],control)
            continue
        if event.get('type') == 'final' and state.get('stream_deltas'):
            for chunk in ('正在输出：', str(message), '…'):
                await publish_session_event(kwargs['session_id'], {'type':'llm_response_delta','delta':chunk,'run_id':kwargs['run_id'],'ephemeral':True})
                await asyncio.sleep(.08)
        if event.get('type') == 'final' and state.get('shared_run_followups'):
            # The main UI consumes Pending turns inside the existing run. Use
            # its real queue and consumer, rather than emitting invented users.
            await publish_session_event(kwargs['session_id'], {**event, 'run_id':kwargs['run_id']})
            yield event
            texts=state['shared_run_followups'];state['shared_run_followups']=[]
            agent_loop.sync_session_followup_queue(kwargs['session_id'],[
                {'client_id':'shared-'+str(index),'content':text,'ui_content':text,'mode':'append'} for index,text in enumerate(texts)])
            model_state={'session_id':kwargs['session_id'],'_runtime_v2_run_id':kwargs['run_id'],
                         'work_messages':[],'llm_history':[],'stream_events':[]}
            async def shared_emit(value):
                await publish_session_event(kwargs['session_id'],{**value,'run_id':kwargs['run_id']})
            index=1
            while await agent_loop._consume_steer_messages(model_state,emit=shared_emit,after_turn=True):
                index+=1
                reply='answer:'+model_state['user_input']
                await shared_emit({'type':'llm_response_delta','react_iter':index,'delta':reply,'ephemeral':True,
                                   'process_group_id':'turn:'+str(model_state['_runtime_v2_user_turn_seq'])})
                ops.commit_assistant_final(kwargs['session_id'],reply,operation_id='shared-final:'+model_state['_runtime_v2_turn_id'],run_id=kwargs['run_id'])
                await shared_emit({'type':'final','content':reply,'runtime_seq':model_state['_runtime_v2_user_turn_seq']})
            continue
        await publish_session_event(kwargs['session_id'], {**event, 'run_id': kwargs['run_id']})
        yield event
    await publish_session_event(kwargs['session_id'], {'type': 'run_finished', 'run_id': kwargs['run_id'], 'result_status': 'succeeded', 'ephemeral': True})
    # Production closes each /chat stream after a turn. A sidebar must keep
    # following this session through that boundary and subsequent messages.
    await close_session_stream(kwargs['session_id'])
    if state.get('auto_name'):
        # The control worker owns a short-lived asyncio.run loop. Keep this
        # delayed post-terminal notification inside it rather than scheduling
        # a task that its loop shutdown would immediately cancel.
        await asyncio.sleep(.15)
        await asyncio.to_thread(c.manager.set_session_name, kwargs['session_id'], '自动命名：'+str(message)[:12])
c.service.deps.astream_events = stream

# Load the actual webui callback without starting the personal web application.
source = ast.parse((ROOT / 'app/webui.py').read_text(encoding='utf-8-sig'))
callbacks = [node for node in source.body if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name in ('_control_update_model', '_control_update_effort', '_persist_session_reasoning_effort', '_apply_session_permission_mode')]
namespace = {'model_profiles': model_profiles, 'PROJECT_ROOT': work, 'session_manager': c.manager, 'asyncio': asyncio,
             '_invalidate_executor_config_cache': lambda _sid: None, 'reset_executor_failure_state_for_session': lambda _sid: None}
exec(compile(ast.Module(body=callbacks, type_ignores=[]), 'app/webui.py', 'exec'), namespace)
import threading
from typing import Optional
from starlette.concurrency import run_in_threadpool
notifications=[]
async def notify_fixture(title='',message='',session_id=''):
    notifications.append({'message':message,'session_id':session_id})
    return []
namespace.update(time=time,Optional=Optional,run_in_threadpool=run_in_threadpool,
    _ui_presence_lock=threading.Lock(),_ui_attention_notify_lock=threading.Lock(),
    _ui_presence_tokens={},_ui_attention_surfaces={},_ui_attention_notify_reasons={},
    _UI_ATTENTION_SURFACE_TTL_SEC=30,_UI_PRESENCE_TOKEN_TTL_SEC=300,_desktop_ui_hidden=None,
    _UI_CLOSED_NOTIFY_ENABLED=True,_UI_CLOSED_NOTIFY_GRACE_SEC=0,
    _ui_attention_notify_task=None,_ui_closed_notify_task=None,_last_ui_attention_notify_at=0,
    _notification_context=lambda sid,status,count:('Fixture',status),
    _session_pending_human_count=lambda sid:1,_ui_attention_terminal_is_obsolete=lambda *args:False,
    notify_user=notify_fixture,logger=SimpleNamespace(warning=lambda *args:None))
presence_callbacks=[node for node in source.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in (
    '_ui_presence_prune','_ui_presence_page_is_open','_ui_presence_has_active','update_ui_attention_surface',
    '_cancel_pending_ui_closed_notify','_cancel_pending_ui_attention_notify','_schedule_ui_attention_notify','_delayed_ui_attention_notify')]
exec(compile(ast.Module(body=presence_callbacks,type_ignores=[]),'app/webui.py','exec'),namespace)
real_update = namespace['_control_update_model']
state = {'models_fail': True, 'model_write_fail': False, 'model_write_noop': False,
         'history_fail': '', 'history_delay': '', 'create_delay': False, 'send_fail': False, 'effort_write_fail': False, 'picker_cancelled': False, 'picker_delay': 0,
         'auto_name':False,'stream_deltas':False,'state_delay':0,'permission_delay':0,
         'steer_test':False,'steer_consume':False,'steer_finish':False,'steer_inputs':[],'steer_interrupts':0,'message_delay':0,
         'connection_enabled':True,'latency_history':False,'shared_run_followups':[],
         'native_stream':False,'native_hold':False,'native_phase':0,'forwarder_fail_once':False,
         'native_add_chunk':False,'native_response_hold':False,'native_failure':'','drop_terminal':False,'hide_terminal_history':False,
         'subscriptions':0,'drop_stream_frames':False,'drop_generation':0}
requests = []

async def update_model(sid, value):
    from session_control.errors import ControlError
    if state['model_write_fail']:
        raise ControlError('fixture_model_rejected', '测试：模型保存被拒绝', status=409)
    if not state['model_write_noop']:
        await real_update(sid, value)
c.service.callbacks['model_profile_id'] = update_model
async def update_effort(sid, value):
    from session_control.errors import ControlError
    if state['effort_write_fail']:
        raise ControlError('fixture_effort_rejected', '测试：思考强度保存被拒绝', status=409)
    await namespace['_control_update_effort'](sid, value)
c.service.callbacks['reasoning_effort'] = update_effort
picked_workspace = work / 'picked-workspace'
picked_workspace.mkdir(exist_ok=True)
import path_picker_util
import agent_extensions
def pick_workspace(*_args):
    time.sleep(state['picker_delay'])
    return None if state['picker_cancelled'] else str(picked_workspace)
patch.setattr(path_picker_util, 'pick_native_path', pick_workspace)
patch.setattr(agent_extensions, 'plugin_catalog_snapshot', lambda: {'plugins': [
    {'id': 'browser-use', 'name': '浏览器连接', 'enabled': True, 'loaded': True, 'description': '使用当前浏览器'},
    {'id': 'fixture-files', 'name': '测试文件插件', 'enabled': False, 'loaded': False, 'description': '文件检索'}],
    'ui_contributions': [{'slot': 'settings.section', 'plugin_id': 'fixture-files', 'id': 'main'}]})

host = _module(load_plugin(ROOT / 'plugins/browser-use'))
async def call(function, *args): return await function(*args)
async def ensure(_record): return SimpleNamespace(relay_url=lambda: 'ws://127.0.0.1:1/extension?token=fixture')
host._manager = host.BrowserManager(SimpleNamespace(call=call))
host._manager.enabled = lambda: state['connection_enabled']
host._manager.ensure = ensure
# Keep sidebar metadata deterministic and inside the isolated fixture. This
# process never imports the user's running web application or security store.
import security
sidebar_permissions = {'mode': 'ask_for_approval', 'mode_scope': 'global', 'security_enabled': True, 'updated_at':time.time(),
                       'available_modes': {'ask_for_approval': True, 'approve_for_me': True, 'full_access': True}}
patch.setattr(security, 'security_status_for_session', lambda _sid: dict(sidebar_permissions))
patch.setattr(security, 'set_session_permission_mode', lambda _sid,mode: sidebar_permissions.update(mode=mode,updated_at=time.time()))
import execution_services.integration
async def permissions_changed(_mode): pass
patch.setattr(execution_services.integration,'permissions_changed',permissions_changed)
from session_event_bus import publish_session_event
namespace['publish_session_event']=publish_session_event
async def context_tokens(_sid):
    return JSONResponse({'ok': True, 'estimated': 32000, 'threshold': 128000})
patch.setitem(sys.modules, 'webui', SimpleNamespace(get_session_context_tokens=context_tokens,_apply_session_permission_mode=namespace['_apply_session_permission_mode'],update_ui_attention_surface=namespace['update_ui_attention_surface']))
async def upload_files(files,request=None):
    # Use the real bounded image store; avoid importing the personal web app.
    from attachments import get_attachment_store
    from attachments.types import SaveImageAttachment
    store=get_attachment_store(work);rows=[]
    for file in files:
        data=await file.read();name=Path(file.filename).name
        if file.content_type.startswith('image/'):
            ref=(await store.save_images([SaveImageAttachment(data,file.content_type,name)]))[0]
            rows.append({'name':name,'size':len(data),'path':str(store.image_host_path(ref)),'attachment':ref})
        else:
            dest=work/('upload-'+uuid.uuid4().hex+'-'+name);dest.write_bytes(data)
            rows.append({'name':name,'size':len(data),'path':str(dest)})
    return JSONResponse({'files':rows})
sys.modules['webui'].upload_chat_files=upload_files
import human_interaction.service as human_service
patch.setattr(human_service, '_shared_human_interaction_service', human_service.HumanInteractionService(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path))
host.install(c.app, {'session_manager': c.manager}, load_plugin(ROOT / 'plugins/browser-use'))
live_sockets=set()
for route in c.app.routes:
    if getattr(route,'path','')=='/api/browser/v1/ws':
        original_socket=route.dependant.call
        async def tracked_socket(socket):
            live_sockets.add(socket)
            try:await original_socket(socket)
            finally:live_sockets.discard(socket)
        route.dependant.call=tracked_socket
from session_control.public import source_state
source_state('browser-use',True,app=c.control)
host.restore_pairing_grants(c.control)

sessions = []
child_sessions = []
ops = RuntimeHistoryOps(c.manager.sessions_dir, path_resolver=c.manager._resolve_session_path)
for number, name in enumerate(('已有会话一', '已有会话二')):
    sid = str(uuid.uuid4())
    c.manager.create_session_with_id(sid, work_dir=str(work), model_profile_id='model-a' if number == 0 else 'model-b')
    c.manager.set_session_name(sid, name)
    run = str(uuid.uuid4())
    ops.commit_user_turn(sid, name + '的问题', operation_id='user-' + run, run_id=run)
    ops.commit_assistant_final(sid, name + '的历史回答', operation_id='final-' + run, run_id=run)
    sessions.append(sid)

read_without_latency_history=c.service._read
async def read_with_latency_history(principal,method,params):
    if state['hide_terminal_history'] and method=='session.history':
        result=await read_without_latency_history(principal,method,params)
        return {**result,'events':[event for event in result.get('events',[]) if event.get('type') not in {'run_failed','run_interrupted','run_finished'}]}
    if state['latency_history'] and method=='session.history' and params.get('session_id')==sessions[0]:
        events=[]
        for turn in range(15):
            run='latency-history-'+str(turn)
            events.append({'type':'user','run_id':run,'content':'历史任务 '+str(turn),'runtime_seq':len(events)+1})
            for tool in range(12):
                events.append({'type':'tool_call','run_id':run,'tool':'run_shell','tool_call_id':run+'-'+str(tool),
                               'result':('long tool output with structured details '+str(tool)+'\n')*45,
                               'execution_status':'completed','runtime_seq':len(events)+1})
            events.append({'type':'final','run_id':run,'content':'历史回答\n\n'+('段落内容 **重要细节** 与 `source.py`。\n\n'*12),'runtime_seq':len(events)+1})
        return {'events':events,'range_start':0,'has_older':False}
    return await read_without_latency_history(principal,method,params)
c.service._read=read_with_latency_history

@c.app.get('/__latency/reference')
async def latency_reference():
    return HTMLResponse('''<meta charset="utf-8"><div id="output"></div><script>
      window.samples=[];window.ready=false;
      const source=new EventSource('/__latency/events');source.onopen=()=>window.ready=true;
      source.onmessage=event=>{const value=JSON.parse(event.data);if(!value.type?.endsWith('_delta'))return;
        samples.push({type:value.type,run:value.run_id,received:Date.now(),emitted:value.fixture_emitted_ms});
        output.append(document.createTextNode(value.delta));};
    </script>''')

@c.app.get('/__latency/events')
async def latency_events():
    from session_event_bus import subscribe_session_events
    async def events():
        yield ': ready\n\n'
        async for event in subscribe_session_events(sessions[0],replay_recent=False,persistent=True):
            if event:yield 'data: '+json.dumps(event)+'\n\n'
    return StreamingResponse(events(),media_type='text/event-stream')

@c.app.post('/__latency/publish')
async def latency_publish(request:Request):
    data=await request.json();run=data['run']
    async def emit(event):
        await publish_session_event(sessions[0],{**event,'run_id':run,'ephemeral':True,'fixture_emitted_ms':time.time()*1000})
    await emit({'type':'run_started'})
    await asyncio.sleep(.12)
    await emit({'type':'llm_reasoning_delta','react_iter':1,'delta':run+'-思考首段'})
    await asyncio.sleep(.25)
    await emit({'type':'llm_response_delta','react_iter':1,'delta':run+'-正文首段'})
    await asyncio.sleep(.25)
    await emit({'type':'final','content':run+'-完成'})
    await emit({'type':'run_finished','result_status':'succeeded'})
    return {'ok':True}

@c.app.middleware('http')
async def failures(request: Request, call_next):
    if request.url.path == '/api/browser/v1/models':
        requests.append({'method': 'models', 'origin': request.headers.get('origin', '')})
        if state['models_fail']:
            return JSONResponse({'detail': '测试：模型列表暂时不可用'}, status_code=503)
    if request.url.path == '/api/control/v1/rpc':
        data = await request.json()
        method, params = data.get('method'), data.get('params', {})
        requests.append({'method': method, 'params': params})
        if method == 'session.history' and params.get('session_id') == state['history_delay']:
            await asyncio.sleep(.5)
        if method == 'session.create' and state['create_delay']:
            await asyncio.sleep(.3)
        if method == 'session.history' and params.get('session_id') == state['history_fail']:
            return JSONResponse({'error': {'message': '测试：请求被拒绝'}}, status_code=409)
    if request.url.path == '/api/browser/v1/messages':
        requests.append({'method':'browser.message','params':await request.json()})
        if state['message_delay']:await asyncio.sleep(state['message_delay'])
        if state['send_fail']:
            return JSONResponse({'error': {'message': '测试：请求被拒绝'}}, status_code=409)
    response = await call_next(request)
    if request.url.path == '/api/browser/v1/steers':
        requests.append({'method':'steer.snapshot.served'})
    if request.url.path == '/api/browser/v1/session-state' and state['state_delay']:
        requests.append({'method':'state_response_held'})
        await asyncio.sleep(state['state_delay'])
    if request.url.path == '/api/browser/v1/permissions' and state['permission_delay']:
        requests.append({'method':'permission_response_held'})
        await asyncio.sleep(state['permission_delay'])
    return response

@c.app.post('/__fixture')
async def fixture(request: Request):
    data = await request.json()
    if data.get('native_stream') and not state['native_stream']:
        patch.setattr(agent_loop,'setup_logging',lambda *a,**k:None)
        patch.setattr(agent_loop,'schedule_session_title_generation',lambda *a,**k:None)
        patch.setattr(agent_loop,'_load_key_context_for_run',lambda *a,**k:'')
        patch.setattr(agent_loop,'_load_model_history_dicts_v2_primary',lambda *a,**k:[])
        patch.setattr(agent_loop,'_load_work_history_dicts_for_run',lambda *a,**k:[])
        async def native_react(model_state, emit):
            state['native_phase']+=1
            phase=state['native_phase'];iteration=int(model_state.get('_queued_react_iter_offset') or 0)+1
            reasoning_seq=1
            model_state['_current_react_iter']=iteration+1
            await agent_loop._push_stream_event(model_state,{'type':'llm_reasoning_delta','delta':'native thinking '+str(phase),'delta_seq':1,'react_iter':iteration,'ephemeral':True},emit)
            while state['native_hold'] and not c.manager.is_interrupt_requested(model_state['session_id'],model_state['_runtime_v2_run_id']):
                if state['native_add_chunk']:
                    state['native_add_chunk']=False
                    reasoning_seq+=1
                    await agent_loop._push_stream_event(model_state,{'type':'llm_reasoning_delta','delta':' plus','delta_seq':reasoning_seq,'react_iter':iteration,'ephemeral':True},emit)
                await asyncio.sleep(.03)
            if state['native_failure']=='exception':
                raise RuntimeError('fixture provider connection lost')
            if state['native_failure']=='structured':
                await agent_loop._push_stream_event(model_state,{'type':'error','content':'__ERR_CARD__'+json.dumps({'t':'模型请求失败','m':'连接已断开','s':'检查模型服务','d':'fixture socket reset'},ensure_ascii=False)},emit)
                model_state['_run_error']='fixture socket reset'
                model_state['final_response']='模型请求未完成'
                return model_state
            call='native-tool-'+str(phase)
            await emit({'type':'tool_pending','tool':'run_shell','tool_call_id':call,'args':{'command':'fixture only'},'react_iter':iteration,'ephemeral':True})
            await emit({'type':'tool_call','tool':'run_shell','tool_call_id':call,'args':{'command':'fixture only'},'result':'native result '+str(phase),'status':{'ok':True},'react_iter':iteration})
            await emit({'type':'llm_response_delta','delta':'native answer:'+model_state['user_input'],'delta_seq':1,'react_iter':iteration+1,'ephemeral':True})
            while state['native_response_hold']:
                await asyncio.sleep(.03)
            await emit({'type':'llm_response_delta','delta':' · done','delta_seq':2,'react_iter':iteration+1,'ephemeral':True})
            model_state['final_response']='native answer:'+model_state['user_input']+' · done';model_state['_queue_can_continue']=True
            return model_state
        patch.setattr(agent_loop,'_run_react_node_off_loop',native_react)
        import session_event_bus as event_bus
        original_subscribe=event_bus.subscribe_session_events
        async def faultable_subscribe(*args,**kwargs):
            state['subscriptions']+=1
            generation=state['subscriptions']
            async for event in original_subscribe(*args,**kwargs):
                if state['drop_stream_frames'] and generation<=state['drop_generation'] and event and event.get('type') not in {'context_tokens','process_metrics','lifecycle_changed','sse_keepalive'}:
                    continue
                if state['drop_terminal'] and event and event.get('type') in {'run_failed','run_interrupted','run_finished'}:
                    continue
                if state['forwarder_fail_once'] and event and event.get('type')=='llm_reasoning_delta':
                    state['forwarder_fail_once']=False
                    raise RuntimeError('fixture: subscription failed')
                yield event
        patch.setattr(event_bus,'subscribe_session_events',faultable_subscribe)
    if data.get('main_queue'):
        agent_loop.sync_session_followup_queue(sessions[0],[{'client_id':'native-main-'+str(index),'content':text,'ui_content':text,'mode':'append'} for index,text in enumerate(data['main_queue'])])
    if data.get('create_subagents') and not child_sessions:
        child = c.manager.create_subagent_session(sessions[0], '接口审查', 'generalPurpose', 1)
        sibling = c.manager.create_subagent_session(sessions[0], '界面审查', 'generalPurpose', 1)
        grandchild = c.manager.create_subagent_session(child, '嵌套检查', 'generalPurpose', 2)
        child_sessions.extend([child, sibling, grandchild])
        for number, sid in enumerate(child_sessions):
            run = 'fixture-child-' + str(number)
            ops.commit_user_turn(sid, '子任务问题' + str(number), operation_id='user-' + run, run_id=run)
            ops.commit_assistant_final(sid, '子任务回答' + str(number), operation_id='final-' + run, run_id=run)
        c.manager.upsert_subagent_task(sessions[0], child, {'status':'completed','description':'接口审查'})
        c.manager.upsert_subagent_task(sessions[0], sibling, {'status':'completed','description':'界面审查'})
        c.manager.upsert_subagent_task(child, grandchild, {'status':'completed','description':'嵌套检查'})
    if data.get('emit_events'):
        for row in data['emit_events']:
            await publish_session_event(row['target'], row['event'])
    if data.get('child_question'):
        patch.setenv('ASK_USER_ENABLED', '1')
        service = human_service._shared_human_interaction_service
        c.service.callbacks['pending_human'] = lambda sid: sum(service.pending_counts(sid).get(key, 0) for key in ('questions', 'approvals'))
        question = service.create_question(child_sessions[0], {'questions':[{'header':'子任务','question':'只在子会话显示的提问？','options':[{'label':'继续','description':'继续审查'},{'label':'暂停','description':'暂停审查'}]}]}, run_id='fixture-child-0')
        await publish_session_event(sessions[0], {'type':'interaction_requested','session_id':child_sessions[0],'agent_id':child_sessions[0],'_subagent_forward':True,**question})
    cancelled_steers=0
    if data.get('seed_cancelled_steers'):
        for number,text in enumerate(('请改为1.5.1吧','和上次迁移包相比是不是只有packing文件夹改了')):
            row=agent_loop.enqueue_session_steer(sessions[0],text,client_id='cancelled-history-'+str(number),mode='append')['item']
            agent_loop.remove_session_steer(sessions[0],steer_id=row['id'])
    if data.get('cancel_steer_text'):
        for row in agent_loop.list_session_steers(sessions[0]).get('items',[]):
            if row.get('ui_content')==data['cancel_steer_text']:
                removed=agent_loop.remove_session_steer(sessions[0],steer_id=row['id'])
                cancelled_steers+=int(removed.get('ok',False))
    if 'plugin_lease' in data:
        source_state('browser-use',data['plugin_lease'],app=c.control)
    if data.get('close_sockets'):
        for connection in list(live_sockets):
            try:await connection.close(code=int(data['close_sockets']))
            except RuntimeError:pass  # The production revocation watcher may win.
    if data.get('notify_reason') in {'completed','failed','pending'}:
        namespace['_schedule_ui_attention_notify'](sessions[0],data['notify_reason'])
        pending=namespace['_ui_attention_notify_task']
        if pending:
            await pending
    if data.get('clear'):
        for row in c.manager.list_sessions(): c.manager.delete_session(row['id'])
    state.update({key: value for key, value in data.items() if key in state})
    if data.get('drop_stream_frames'):
        state['drop_generation']=state['subscriptions']
    if data.get('main_message'):
        await c.service.execute(c.admin,'session.send',{'session_id':sessions[0],'message':data['main_message']},idempotency_key='native-main-'+uuid.uuid4().hex)
    if data.get('main_interrupt'):
        await c.service.execute(c.admin,'session.interrupt',{'session_id':sessions[0]},idempotency_key='native-stop-'+uuid.uuid4().hex)
    if data.get('rename'):
        await asyncio.to_thread(c.manager.set_session_name,data['rename']['session_id'],data['rename']['name'])
    if data.get('permission_mode'):
        await namespace['_apply_session_permission_mode'](data.get('session_id') or sessions[0],data['permission_mode'])
    with c.store.transaction() as db:
        operations=[{'status':row[0],'method':row[1],'error':row[2]} for row in db.execute('SELECT status,method,error FROM operations ORDER BY created DESC LIMIT 8')]
    inspection = await c.service._read(c.admin,'session.history',{'session_id':data['inspect_session']}) if data.get('inspect_session') else None
    return {'child_sessions':child_sessions,'cancelled_steers':cancelled_steers,'history':inspection,'operations':operations,
            'subscriptions':state['subscriptions'],
            'paired_browsers':len(c.store.list('browser_connections')),'socket_count':len(live_sockets),'steer_inputs':state['steer_inputs'],'steer_interrupts':state['steer_interrupts'],'attention_active':namespace['_ui_presence_has_active'](),'attention_surfaces':len(namespace['_ui_attention_surfaces']),'notifications':notifications,
            'sessions': c.manager.list_sessions(), 'requests': requests, 'workspace': str(picked_workspace.resolve()),
            'calls': [{'session_id': row[0], 'message': row[1]} for row in c.calls]}

@c.app.on_event('shutdown')
async def close(): await c.control.close()

listener = socket.socket()
listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
listener.bind(('127.0.0.1', int(sys.argv[2]) if len(sys.argv)>2 else 0))
listener.listen()
print(json.dumps({'baseUrl': 'http://127.0.0.1:' + str(listener.getsockname()[1]), 'sessions': sessions}), flush=True)
try:
    uvicorn.Server(uvicorn.Config(c.app, log_level='error')).run(sockets=[listener])
finally:
    listener.close()
    patch.undo()
