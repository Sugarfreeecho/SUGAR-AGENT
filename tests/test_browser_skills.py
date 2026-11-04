import ast
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

from tests.test_browser_use import browser_host
from tests.test_session_control import composed


def test_skill_catalog_and_message_use_main_selection_with_live_enabled_validation(browser_host,monkeypatch):
    import agent_tools
    host,c=browser_host
    catalog=[{'name':'repo-engineering','description':'工程规程','enabled':True,'path':'private/path','body':'private body'},
             {'name':'disabled','description':'停用规程','enabled':False}]
    def discover(include_disabled=False):return list(catalog) if include_disabled else [row for row in catalog if row['enabled']]
    monkeypatch.setattr(agent_tools,'discover_skills',discover)
    source=ast.parse((Path(__file__).resolve().parents[1]/'app/webui.py').read_text(encoding='utf-8-sig'))
    names={'_valid_selected_skill_names','_build_agent_message_with_selected_skills','_build_ui_message_with_selected_skills'}
    namespace={'Any':Any,'json':json,'discover_skills':discover}
    exec(compile(ast.Module(body=[node for node in source.body if isinstance(node,ast.FunctionDef) and node.name in names],type_ignores=[]),'app/webui.py','exec'),namespace)
    monkeypatch.setitem(sys.modules,'webui',SimpleNamespace(**{name:namespace[name] for name in names}))
    sid,*_=c.manager.get_or_create_session()
    async def scenario():
        await c.control.start()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
                code=(await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()['code']
                issued=(await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':code})).json()
                auth={'Authorization':'Bearer '+issued['token'],'Origin':host.extension_origin()}
                assert (await client.get('/api/browser/v1/skills')).status_code==401
                assert (await client.get('/api/browser/v1/skills',headers={**auth,'Origin':'https://foreign.test'})).status_code==403
                result=await client.get('/api/browser/v1/skills',headers=auth)
                assert result.status_code==200
                assert result.json()['skills']==[{key:row[key] for key in ('name','description','enabled')} for row in catalog]
                body={'session_id':sid,'message':'检查项目','ui_message':'检查项目','automatic':False,
                      'selected_skills':['repo-engineering','repo-engineering'],'idempotency_key':'selected-skill'}
                result=await client.post('/api/browser/v1/messages',headers=auth,json=body)
                assert result.status_code==200,result.text
                receipt=result.json()['data']
                operation,_=await c.service.execute(c.admin,'operation.wait',{'id':receipt['operation_id'],'timeout':10},idempotency_key='wait-skill')
                assert operation['status']=='succeeded'
                assert c.calls and '<selected_skills_for_this_conversation>' in c.calls[0][1]
                assert c.calls[0][1].count('- repo-engineering')==1 and 'activate_skill' in c.calls[0][1]
                saved=c.store.get_operation(receipt['operation_id'])
                assert saved['request']['ui_message']=='检查项目\n\nActivated Skill: repo-engineering'
                count=len(c.calls)
                for index,selected in enumerate((['disabled'],['unknown'],'repo-engineering',[None],['repo-engineering']*33)):
                    denied=await client.post('/api/browser/v1/messages',headers=auth,json={**body,'selected_skills':selected,'idempotency_key':'invalid-'+str(index)})
                    assert denied.status_code in {400,409},denied.text
                catalog[0]['enabled']=False
                stale=await client.post('/api/browser/v1/messages',headers=auth,json={**body,'idempotency_key':'stale'})
                assert stale.status_code==409 and len(c.calls)==count
                assert (await client.get('/api/browser/v1/skills',headers=auth)).json()['skills'][0]['enabled'] is False
        finally:await c.control.close()
    asyncio.run(scenario())
