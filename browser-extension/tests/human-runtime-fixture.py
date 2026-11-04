"""Isolated backend using real ask/approval waiters and application handlers."""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'app'),str(ROOT)]
os.environ['MYAGENT_UI_CLOSED_NOTIFY']='0'
import pytest
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from tests.test_session_control import composed
from tests.test_browser_human import human_runtime
from plugins import load_plugin
from plugins.host import _module
import session_control.integration
import runtime_lifecycle
import model_profiles

work=Path(sys.argv[1]);work.mkdir(parents=True,exist_ok=True)
patch=pytest.MonkeyPatch()
patch.setattr(runtime_lifecycle,'state_path',lambda:work/'lifecycle.sqlite3')
patch.setattr(model_profiles,'load_store',lambda _:{'profiles':[],'default_profile':''})
c=composed.__wrapped__(work,patch)
patch.setattr(session_control.integration,'_application',c.control)
human=human_runtime(c,patch)
# Presence is orthogonal to this test's real ask/approval handlers. Keep the
# sidebar heartbeat inside the isolated app rather than failing its socket.
sys.modules['webui'].update_ui_attention_surface=lambda *_args:None
host=_module(load_plugin(ROOT/'plugins/browser-use'))
async def call(function,*args):return await function(*args)
async def ensure(_):return SimpleNamespace(relay_url=lambda:'ws://127.0.0.1:1/extension?token=fixture')
host._manager=host.BrowserManager(SimpleNamespace(call=call));host._manager.enabled=lambda:True;host._manager.ensure=ensure
host.install(c.app,{'session_manager':c.manager},load_plugin(ROOT/'plugins/browser-use'))
sid,*_=c.manager.get_or_create_session();c.manager.set_session_name(sid,'人机交互回归')

@c.app.middleware('http')
async def failures(request,call_next):
    if request.url.path in {'/api/browser/v1/questions/resolve','/api/browser/v1/approvals/resolve'}:
        if human.fail_next:
            human.fail_next=False
            return JSONResponse({'error':'测试：暂时无法提交，请重试'},status_code=503)
        if human.delay:await asyncio.sleep(human.delay)
    return await call_next(request)

@c.app.post('/__human')
async def fixture(request:Request):
    data=await request.json()
    if data.get('create'):
        return await human.create(sid,data.get('kind','question'),questions=data.get('questions'),forced=data.get('forced',False),persistent=data.get('persistent',False),workspace=data.get('workspace',False),stale=data.get('stale',False))
    if 'fail_next' in data:human.fail_next=data['fail_next']
    if 'delay' in data:human.delay=data['delay']
    if data.get('external_cancel'):
        from session_event_bus import publish_session_event
        record=human.service.cancel(sid,data['external_cancel'],kind=data.get('kind','question'))
        await publish_session_event(sid,{'type':'interaction_cancelled' if data.get('kind','question')=='question' else 'approval_cancelled',**record})
    return {'records':human.service.list(sid)+human.service.list(sid,kind='approval'),'grants':human.grants,'results':human.results}

@c.app.on_event('shutdown')
async def close():
    for task in human.tasks:
        if not task.done():task.cancel()
    await asyncio.gather(*human.tasks,return_exceptions=True)
    await c.control.close()

listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
print(json.dumps({'baseUrl':'http://127.0.0.1:'+str(listener.getsockname()[1]),'session_id':sid}),flush=True)
try:uvicorn.Server(uvicorn.Config(c.app,log_level='error')).run(sockets=[listener])
finally:listener.close();patch.undo()
