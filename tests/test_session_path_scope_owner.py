import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextvars
import threading


def manager_for_scope_test(tmp_path):
    from agent_harness import SessionManager
    manager = SessionManager.__new__(SessionManager)
    manager.sessions_dir = tmp_path
    (tmp_path/'s').mkdir()
    calls=[]
    def uncached(sid, **kwargs):
        calls.append(threading.get_ident())
        return tmp_path/sid
    manager._resolve_session_path_uncached=uncached
    manager._session_subagent_index_identity=lambda:('unchanged-index',)
    return manager,calls


def test_copied_thread_context_cannot_borrow_or_clear_parent_path_scope(tmp_path):
    manager,calls=manager_for_scope_test(tmp_path)
    with manager._session_path_resolution_scope():
        manager._resolve_session_path('s')
        parent=manager._session_path_scope.get()
        assert len(parent['paths'])==1
        def worker():
            before=len(calls)
            manager._resolve_session_path('s')
            assert len(calls)==before+1
            with manager._session_path_resolution_scope():
                child=manager._session_path_scope.get()
                assert child is not parent and child['owner']!=parent['owner']
                manager._resolve_session_path('s')
                warm=len(calls)
                manager._resolve_session_path('s')
                assert len(calls)==warm
            assert not child['active'] and not child['paths']
        with ThreadPoolExecutor(1) as pool:
            pool.submit(contextvars.copy_context().run,worker).result(5)
        assert parent['active'] and len(parent['paths'])==1
        count=len(calls)
        manager._resolve_session_path('s')
        assert len(calls)==count
    assert not parent['active'] and not parent['paths']


def test_copied_async_task_context_gets_its_own_path_scope(tmp_path):
    manager,calls=manager_for_scope_test(tmp_path)
    async def run():
        with manager._session_path_resolution_scope():
            manager._resolve_session_path('s')
            parent=manager._session_path_scope.get()
            async def child_task():
                before=len(calls)
                manager._resolve_session_path('s')
                assert len(calls)==before+1
                with manager._session_path_resolution_scope():
                    child=manager._session_path_scope.get()
                    assert child is not parent and child['owner']!=parent['owner']
                    manager._resolve_session_path('s')
                    warm=len(calls)
                    manager._resolve_session_path('s')
                    assert len(calls)==warm
            await asyncio.create_task(child_task())
            assert parent['active'] and len(parent['paths'])==1
    asyncio.run(run())
