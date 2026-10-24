import ast
import asyncio
from pathlib import Path
import subprocess
import threading
import re
from types import SimpleNamespace

import pytest

from starlette.concurrency import run_in_threadpool


ROOT = Path(__file__).resolve().parents[1]


def test_startup_catalog_warmup_does_not_open_or_rebuild_session_history(monkeypatch):
    import sys
    calls = []
    tree = ast.parse((ROOT/'app/webui.py').read_text(encoding='utf-8'))
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_warm_ui_caches')
    def forbidden(*_args, **_kwargs):
        raise AssertionError('startup speculation must not hold the first-open history index lock')
    monkeypatch.setitem(sys.modules, 'agent_tools', SimpleNamespace(discover_skills=lambda **_: calls.append('skills')))
    monkeypatch.setitem(sys.modules, 'agent_extensions', SimpleNamespace(extensions_snapshot=lambda: calls.append('extensions')))
    # Run the actual worker synchronously, including its imports. Its initial
    # delay is simulated, and any history/catalog ordering regression is visible.
    monkeypatch.setattr('time.sleep', lambda seconds: calls.append(('delay', seconds)))
    class Worker:
        def __init__(self, target, **_):
            self.target = target
        def start(self):
            calls.append('thread-start')
            self.target()
    errors = []
    namespace = {'threading': SimpleNamespace(Thread=Worker),
                 'session_manager': SimpleNamespace(list_sessions=forbidden),
                 'logger': SimpleNamespace(debug=lambda *args, **kwargs: errors.append(args))}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/webui.py', 'exec'), namespace)
    namespace['_warm_ui_caches']()
    assert calls == ['thread-start', ('delay', 2.0), 'skills', 'extensions']
    assert not errors, 'a swallowed history-access assertion must also fail the regression'


def test_frontend_startup_failure_recovery():
    result = subprocess.run(['node', '--test', str(ROOT/'tests/js/startup_failure_recovery_runtime.cjs')],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_workspace_root_lookup_cannot_suspend_other_http_coroutines(tmp_path):
    tree = ast.parse((ROOT/'app/webui.py').read_text(encoding='utf-8'))
    node = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'list_workspace_files')
    node.decorator_list = []
    event_loop_thread = threading.get_ident()
    entered, release = threading.Event(), threading.Event()

    def root(sid, directory):
        assert threading.get_ident() != event_loop_thread, 'workspace metadata/path I/O is blocking the HTTP loop'
        assert sid == 's' and directory == ''
        entered.set()
        assert release.wait(2)
        return tmp_path

    namespace = {'Query': lambda value, **_: value, '_workspace_request_root': root,
                 'run_in_threadpool': run_in_threadpool, '_list_workspace_dir': lambda *_: [],
                 'JSONResponse': lambda data, **_: data}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/webui.py', 'exec'), namespace)

    async def scenario():
        request = asyncio.create_task(namespace['list_workspace_files'](q='', dir='', session_id='s', work_dir=''))
        try:
            await asyncio.sleep(0)
            if request.done():
                await request
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait), timeout=1)
            await asyncio.wait_for(asyncio.sleep(0), timeout=.1)
            assert not request.done()
            release.set()
            assert (await request)['ok'] is True
        finally:
            release.set()
            await asyncio.gather(request, return_exceptions=True)
    asyncio.run(scenario())


def test_clear_unread_disk_write_cannot_block_other_http_coroutines():
    tree = ast.parse((ROOT/'app/webui.py').read_text(encoding='utf8'))
    node = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'clear_session_unread_result')
    node.decorator_list = []
    event_loop_thread = threading.get_ident()
    entered, release = threading.Event(), threading.Event()

    def clear(sid, expected_run_id):
        assert threading.get_ident() != event_loop_thread, 'opening a chat is writing the index on the HTTP loop'
        assert (sid, expected_run_id) == ('s', 'run')
        entered.set()
        assert release.wait(2)
        return True

    namespace = {'Query': lambda value: value, 'session_manager': SimpleNamespace(clear_session_unread_result=clear),
                 'run_in_threadpool': run_in_threadpool, 'JSONResponse': lambda content: content}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/webui.py', 'exec'), namespace)

    async def scenario():
        request = asyncio.create_task(namespace['clear_session_unread_result']('s', 'run'))
        try:
            await asyncio.sleep(0)
            if request.done():
                await request
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait), timeout=1)
            await asyncio.wait_for(asyncio.sleep(0), timeout=.1)
            assert not request.done()
            release.set()
            assert (await request)['cleared'] is True
        finally:
            release.set()
            await asyncio.gather(request, return_exceptions=True)
    asyncio.run(scenario())


@pytest.mark.parametrize('handler', ['get_session_model_profile', 'get_session_steer_status', 'list_session_steer_status'])
def test_startup_auxiliary_metadata_and_steer_lock_do_not_block_http_loop(handler):
    tree = ast.parse((ROOT/'app/webui.py').read_text(encoding='utf8'))
    node = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == handler)
    node.decorator_list = []
    main_thread = threading.get_ident()
    entered, release = threading.Event(), threading.Event()

    def blocked(*_args, **_kwargs):
        assert threading.get_ident() != main_thread, 'startup auxiliary I/O/locks must not suspend the HTTP loop'
        entered.set()
        assert release.wait(2)
        return {'ok': True, 'model_profile_id': 'profile'}

    namespace = {'session_manager': SimpleNamespace(_load_metadata=blocked),
                 'model_profiles': SimpleNamespace(is_usable_profile=lambda *_: True, get_profile=lambda *_: {}),
                 'PROJECT_ROOT': ROOT, 'get_session_steer': blocked, 'list_session_steers': blocked,
                 'run_in_threadpool': run_in_threadpool, 'JSONResponse': lambda content, **_: content}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app/webui.py', 'exec'), namespace)

    async def scenario():
        args = ('s', 'steer') if handler == 'get_session_steer_status' else ('s',)
        request = asyncio.create_task(namespace[handler](*args))
        try:
            await asyncio.sleep(0)
            if request.done():
                await request
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait), timeout=1)
            await asyncio.wait_for(asyncio.sleep(0), timeout=.1)
            assert not request.done()
            release.set()
            assert (await request)['ok'] is True
        finally:
            release.set()
            await asyncio.gather(request, return_exceptions=True)
    asyncio.run(scenario())


@pytest.fixture
def browser_page():
    import os
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, **({'channel': 'msedge'} if os.name == 'nt' else {}))
        yield browser.new_page()
        browser.close()


def workspace_functions(page, *names):
    source = (ROOT/'frontend/src/app/modules/dock/embedder/right-column.js').read_text(encoding='utf8')
    page.add_script_tag(content='''
        window.dockRightText=x=>x;
        window.workspaceApiUrl=x=>x;
        window.getWorkspaceRequestContext=()=>({sessionId:'s'});
        window.dockRightTrackScroll=()=>{};
        window.DOCK_ICON_REFRESH='refresh';
        window.dockRightFileRow=()=>document.createElement('div');
    ''' + '\n'.join(re.search(r'^(?:async )?function '+name+r'\([\s\S]*?^}', source, re.M)[0]
                     for name in names))


def test_workspace_failure_stays_visible_and_can_be_retried(browser_page):
    page = browser_page
    page.set_content('<div id="tree"></div>')
    workspace_functions(page, 'dockRightFetchJSON', 'dockRightLoadDir')
    page.evaluate('''async () => {
        let calls=0;
        window.fetch=async()=>++calls===1
            ? {ok:false,status:503,json:async()=>({error:'temporarily unavailable'})}
            : {ok:true,status:200,json:async()=>({ok:true,files:[]})};
        await dockRightLoadDir(document.getElementById('tree'),'',0,{});
    }''')
    assert 'loadFailed' in page.locator('#tree').inner_text()
    page.locator('#tree button').click()
    page.wait_for_function("document.getElementById('tree').textContent==='emptyDir'")


def test_workspace_refresh_cancels_obsolete_request(browser_page):
    page = browser_page
    page.set_content('<div id="host"></div>')
    workspace_functions(page, 'dockRightFetchJSON', 'dockRightLoadDir', 'dockRightFilesBody')
    page.evaluate('''() => {
        let calls=0;window.aborted=0;
        window.fetch=async(_url,options)=>++calls===1
            ? new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>{
                aborted++;reject(new DOMException('cancelled','AbortError'));
              },{once:true}))
            : {ok:true,status:200,json:async()=>({ok:true,root:'current',files:[]})};
        document.getElementById('host').appendChild(dockRightFilesBody({id:'files'}));
    }''')
    page.locator('[data-dock-files-refresh]').click()
    page.wait_for_function("document.querySelector('.dock-files-tree').textContent==='emptyDir'")
    assert page.evaluate('aborted') == 1
    assert page.locator('[data-dock-files-path]').inner_text() == 'current'
