import asyncio
import threading
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('cancel',[False,True])
def test_catalog_waits_for_disclosure_without_blocking_owner_loop(monkeypatch,cancel):
    import agent_loop as agent
    import agent_extensions as ext
    import agent_subagent as child
    import tool_search
    from tool_registry import ToolInvocationKind

    definition={'type':'function','function':{'name':'read_file','description':'Read',
                'parameters':{'type':'object','properties':{}}}}
    monkeypatch.setattr(agent,'_build_host_tool_catalog',lambda *_:([definition],{'read_file':(ToolInvocationKind.HOST,'core.tools')}))
    monkeypatch.setattr(ext,'load_plugins',lambda **_:SimpleNamespace(plugins=()))
    async def empty():return []
    async def contracts():return {}
    monkeypatch.setattr(ext,'plugin_tool_definitions',empty)
    monkeypatch.setattr(ext,'plugin_tool_contracts',contracts)
    monkeypatch.setattr(child,'inject_task_model_profiles',lambda rows:rows)
    monkeypatch.setattr(agent,'resolve_executor_config_for_session',lambda _:('model',None,None,128000))
    monkeypatch.setattr(agent.agent_mcp,'get_pinned_tool_names',lambda:frozenset())
    entered,release,finished=threading.Event(),threading.Event(),threading.Event()
    original=tool_search.assemble
    owner=threading.get_ident()
    def assemble(*args,**kwargs):
        assert threading.get_ident()!=owner
        entered.set()
        assert release.wait(3)
        try:return original(*args,**kwargs)
        finally:finished.set()
    monkeypatch.setattr(tool_search,'assemble',assemble)

    async def scenario():
        task=asyncio.create_task(agent.build_combined_tool_registry_for_session(
            'disclosure-fixture',session_meta={},include_mcp=False))
        try:
            async def started():
                while not entered.is_set():
                    if task.done():await task
                    await asyncio.sleep(.001)
            await asyncio.wait_for(started(),3)
            assert not task.done()
            pulse=asyncio.Event()
            asyncio.get_running_loop().call_soon(pulse.set)
            await asyncio.wait_for(pulse.wait(),1)
            if cancel:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):await task
            release.set()
            if not cancel:
                registry=await task
                assert registry.names()=={'read_file'}
        finally:
            release.set()
            await asyncio.to_thread(finished.wait,3)
    asyncio.run(scenario())
