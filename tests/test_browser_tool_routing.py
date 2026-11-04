"""Paired browser tools must not be confused with a second MCP browser."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import host_tool_contracts
from tool_registry import ToolRegistry, ToolInvocationKind
from tests.test_browser_use import browser_host
from tests.test_session_control import composed


def definition(name):
    return {'type':'function','function':{'name':name,'parameters':{'type':'object','properties':{}}}}


def registry_with_browser(owner='browser-use', include_host=True):
    registry=ToolRegistry()
    if include_host:
        registry.register_definition(definition('browser_snapshot'),invocation_kind='host_service',owner=owner)
    for name in ['mcp_old_snapshot','mcp_old_run_code','mcp_docs_search']:
        registry.register_definition(definition(name),invocation_kind='mcp',owner='mcp:arbitrary-alias')
    registry.rename_tools({'mcp_old_snapshot':'old__browser_snapshot','mcp_old_run_code':'old__browser_run_code','mcp_docs_search':'search_docs'})
    return registry


def identity(name):
    return {'mcp_old_snapshot':('arbitrary-alias','browser_snapshot'),
            'mcp_old_run_code':('arbitrary-alias','browser_run_code'),
            'mcp_docs_search':('docs','search')} .get(name)


def contract(name):
    return {'managed_by':'browser-use','preferred_mcp_families':('browser_',)} if name=='browser_snapshot' else {}


def test_paired_transport_excludes_alternative_browser_family_including_run_code(monkeypatch):
    monkeypatch.setattr(host_tool_contracts,'_PROVIDERS',[contract])
    registry=registry_with_browser()
    removed=host_tool_contracts.filter_preferred_mcp_tools(registry,identity)
    assert set(removed)=={'old__browser_snapshot','old__browser_run_code'}
    assert registry.names()=={'browser_snapshot','search_docs'}
    assert registry.require('browser_snapshot').invocation_kind is ToolInvocationKind.HOST_SERVICE
    assert registry.resolve('old__browser_run_code') is None


def test_disabled_unavailable_or_different_owner_cannot_hide_mcp_tools(monkeypatch):
    monkeypatch.setattr(host_tool_contracts,'_PROVIDERS',[contract])
    for registry in [registry_with_browser(include_host=False),registry_with_browser(owner='different-provider')]:
        assert host_tool_contracts.filter_preferred_mcp_tools(registry,identity)==[]
        assert registry.resolve('old__browser_snapshot')
    monkeypatch.setattr(host_tool_contracts,'_PROVIDERS',[])
    registry=registry_with_browser()
    assert host_tool_contracts.filter_preferred_mcp_tools(registry,identity)==[]
    assert registry.resolve('old__browser_run_code')


def test_live_agent_catalog_prefers_extension_and_keeps_unrelated_mcp(monkeypatch):
    import agent_extensions,agent_loop,agent_mcp,agent_subagent
    from host_tool_registry import HostToolInvokerRegistry
    from tool_execution_policy import ToolExecutionPolicy
    from plugins import load_plugin
    from plugins.host import _module
    root=Path(__file__).resolve().parents[1]
    manager=_module(load_plugin(root/'plugins/browser-use')).BrowserManager(None)
    manager.enabled=lambda:True
    manager.catalog=[definition('browser_snapshot')]
    host=HostToolInvokerRegistry()
    host.register('browser_snapshot',manager.invoke,owner='browser-use',policy=ToolExecutionPolicy(effect='read'))
    monkeypatch.setattr(agent_loop,'host_tool_invokers',host)
    monkeypatch.setattr(host_tool_contracts,'_PROVIDERS',[manager.tool_contract])
    monkeypatch.setenv('MYAGENT_TOOL_SEARCH','off')
    monkeypatch.setattr(agent_loop,'OPENAI_TOOL_DEFINITIONS',[])
    monkeypatch.setattr(agent_loop,'tools_dict',{})
    monkeypatch.setattr(agent_extensions,'bundled_host_tool_definitions',lambda **_:manager.catalog)
    async def mcp():return [definition(name) for name in ['mcp_old_snapshot','mcp_old_run_code','mcp_docs_search']]
    async def none():return []
    async def contracts():return {}
    monkeypatch.setattr(agent_mcp,'get_published_tool_definitions',mcp)
    monkeypatch.setattr(agent_mcp,'get_tool_identity',identity)
    monkeypatch.setattr(agent_mcp,'get_pinned_tool_names',lambda:[])
    monkeypatch.setattr(agent_extensions,'plugin_tool_definitions',none)
    monkeypatch.setattr(agent_extensions,'plugin_tool_contracts',contracts)
    monkeypatch.setattr(agent_subagent,'filter_tools_for_session',lambda rows,_:rows)
    monkeypatch.setattr(agent_subagent,'inject_task_model_profiles',lambda rows:rows)
    registry=asyncio.run(agent_loop.build_combined_tool_registry_for_session('routing-test',session_meta={}))
    assert registry.require('browser_snapshot').owner=='browser-use'
    assert not any(d.invocation_kind is ToolInvocationKind.MCP and identity(d.execution_name)[1].startswith('browser_') for d in registry.descriptors())
    assert any(d.execution_name=='mcp_docs_search' for d in registry.descriptors())


def test_revoking_default_cleans_future_bindings_and_persists_online_replacement(browser_host,monkeypatch,tmp_path):
    import security.runtime
    host,c=browser_host
    manager=host._manager
    monkeypatch.setattr(security.runtime,'session_permission_mode',lambda _:'full_access')
    async def call(function,*args):return await function(*args)
    manager.service=SimpleNamespace(call=call)
    called=[]
    class Runtime:
        def __init__(self,name):
            self.name,self.state,self.tool_gate=name,{'connected':True,'initialized':True},asyncio.Lock()
            self.closed=False
        async def close(self):self.closed=True
        async def request(self,*_):called.append(self.name);return {'content':[]}
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=c.app),base_url='http://127.0.0.1') as client:
            ids=[]
            for _ in range(2):
                code=(await client.post('/api/browser/v1/pairings',headers={'Origin':'http://127.0.0.1'},json={})).json()['code']
                issued=(await client.post('/api/browser/v1/claim',headers={'Origin':host.extension_origin()},json={'code':code})).json()
                ids.append(issued['browser_id'])
            first,second=ids
            old=Runtime(first)
            manager.runtimes={first:old,second:Runtime(second)}
            manager.default_browser=first
            manager.bindings['main-session']=first
            manager.run_bindings['in-flight']=first
            c.control.store.put('browser_preferences','default',{'browser_id':first})
            response=await client.post('/api/browser/v1/devices/'+first+'/revoke',headers={'Origin':'http://127.0.0.1'},json={})
            assert response.status_code==200,response.text
            assert old.closed and first not in manager.runtimes
            assert manager.default_browser==second
            assert 'main-session' not in manager.bindings
            assert c.control.store.get('browser_preferences','default')['browser_id']==second
            def context(run):return SimpleNamespace(session_id='main-session',run_id=run,state={},services={'security_workspace':tmp_path},service=lambda _:'browser_snapshot')
            with pytest.raises(RuntimeError,match='bound to this run'):
                await manager._call(context('in-flight'),{},'full_access')
            await manager._call(context('next-run'),{},'full_access')
            assert called==[second]
    asyncio.run(scenario())


def test_new_connection_replaces_missing_stale_default(monkeypatch,tmp_path):
    import security.store
    from plugins import load_plugin
    from plugins.host import _module
    root=Path(__file__).resolve().parents[1]
    manager=_module(load_plugin(root/'plugins/browser-use')).BrowserManager(None)
    class Runtime:
        def __init__(self,*args,**kwargs):pass
        async def start(self):pass
    monkeypatch.setitem(manager.ensure.__globals__,'BrowserRuntime',Runtime)
    monkeypatch.setattr(security.store,'security_state_dir',lambda:tmp_path/'security')
    manager.default_browser='already-revoked'
    asyncio.run(manager.ensure({'id':'current','origin':'chrome-extension://test'}))
    assert manager.default_browser=='current'
