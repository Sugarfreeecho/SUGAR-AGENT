import asyncio

from tests.test_subagent_performance_paths import child_runtime,done,tool_rows


def test_result_delivery_uses_registered_shared_heartbeat_without_metadata_barrier(child_runtime,monkeypatch):
    import runtime_observability as obs
    child,manager,metrics,published,parent,execute=child_runtime
    original=manager.patch_subagent_metadata
    def metadata(sid,fields):
        assert set(fields)!={'subagent_run_heartbeat_at','subagent_run_status'}, 'duplicate metadata heartbeat on delivery'
        return original(sid,fields)
    monkeypatch.setattr(manager,'patch_subagent_metadata',metadata)

    async def react(state,emit):
        rid=state['_runtime_v2_run_id']
        assert ('child',rid) in metrics._heartbeat_controls
        await emit.tool_batch(tool_rows())
        assert len(published)==4
        before=obs.snapshot('child')['runs'][-1]['heartbeat_at']
        metrics.heartbeat_run('child',rid,'working')
        observed=obs.snapshot('child')['runs'][-1]
        assert observed['status']=='running' and observed['heartbeat_at']>=before
        return done(state)

    result=asyncio.run(execute(react))
    assert 'done' in result
    run=obs.snapshot('child')['runs'][-1]
    assert run['status']=='finished' and run['finished_at']
    assert ('child',run['run_id']) not in metrics._heartbeat_controls
    metrics.heartbeat_run('child',run['run_id'],'late')
    assert obs.snapshot('child')['runs'][-1]==run
    lifecycle=[m for m in manager.metadata if 'subagent_run_status' in m]
    assert lifecycle[-1]['subagent_run_status']=='completed'


def test_cancelled_child_cannot_be_revived_by_late_shared_heartbeat(child_runtime):
    import runtime_observability as obs
    child,manager,metrics,published,parent,execute=child_runtime
    ready=asyncio.Event()

    async def react(state,emit):
        await emit({'type':'status','content':'working'})
        ready.set()
        await asyncio.Future()

    async def scenario():
        task=asyncio.create_task(execute(react))
        await asyncio.wait_for(ready.wait(),3)
        await child.subagent_registry.cancel('child')
        await task

    asyncio.run(scenario())
    run=obs.snapshot('child')['runs'][-1]
    assert run['status']=='interrupted'
    metrics.heartbeat_run('child',run['run_id'],'late')
    assert obs.snapshot('child')['runs'][-1]==run
    assert not metrics._heartbeat_controls
    assert [m['subagent_run_status'] for m in manager.metadata if 'subagent_run_status' in m][-1]=='interrupted'
