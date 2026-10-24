"""Saved B站 identities use temporary credentials and no real network calls."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from tests.test_sugar_bili_scroll_tasks import host
from tests.test_sugar_bili_scroll_workflows import api, runtime


@pytest.fixture
def accounts_api(api, monkeypatch):
    rt, app = api
    client = rt.h._load_sibling('bili_client')
    monkeypatch.setattr(rt.h, 'bili_client', client)
    monkeypatch.setattr(client, '_login_session', None)
    monkeypatch.setattr(client, '_login_key', '')
    monkeypatch.setattr(client, '_login_generation', 0)
    async def self_info(*, credential):
        return {'mid':int(credential.dedeuserid), 'name':'测试账号'}
    monkeypatch.setattr(client.user, 'get_self_info', self_info)
    return rt, app, client


def credential(uid, suffix='a'):
    from bilibili_api import Credential
    return Credential(sessdata='test-cookie-'+suffix, bili_jct='test-jct-'+suffix, dedeuserid=str(uid))


def http(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver', headers={'origin':'http://testserver'})


def test_legacy_login_is_imported_and_logout_retains_it(accounts_api):
    rt, app, client = accounts_api
    path = client.credential_path(rt.h._home())
    legacy = {'sessdata':'legacy-secret','bili_jct':'legacy-jct','dedeuserid':'999','buvid3':'','ac_time_value':''}
    path.write_text(json.dumps(legacy), encoding='utf-8')
    async def scenario():
        async with http(app) as request:
            listed = (await request.get('/api/sugar-bili-scroll/accounts')).json()
            assert len(listed['items']) == 1 and listed['items'][0]['active']
            assert listed['items'][0]['uid'] == '999'
            assert 'legacy-secret' not in json.dumps(listed) and 'credential' not in json.dumps(listed)
            assert json.loads(path.read_text(encoding='utf-8')) == legacy
            await request.post('/api/sugar-bili-scroll/logout')
            assert client.load_credential(rt.h._home()) is None
            saved = (await request.get('/api/sugar-bili-scroll/accounts')).json()['items']
            assert len(saved) == 1 and not saved[0]['active']
            assert rt.h.store_mod.Store(rt.h._home()).account('999')['sessdata'] == 'legacy-secret'
            assert (await request.post('/api/sugar-bili-scroll/accounts/999/activate')).status_code == 200
            assert client.load_credential(rt.h._home()).dedeuserid == '999'
    asyncio.run(scenario())


def test_saved_logins_can_be_switched_without_qr_and_refresh_does_not_duplicate(accounts_api):
    rt, app, client = accounts_api
    home = rt.h._home()
    client.save_credential(home, credential('999'))
    client.save_credential(home, credential('888', 'b'))
    async def scenario():
        async with http(app) as request:
            for uid in ['999','888','999']:
                result = await request.post('/api/sugar-bili-scroll/accounts/'+uid+'/activate')
                assert result.status_code == 200
                assert client.load_credential(home).dedeuserid == uid
                rows = (await request.get('/api/sugar-bili-scroll/accounts')).json()['items']
                assert len(rows) == 2 and sum(row['active'] for row in rows) == 1
                assert next(row['uid'] for row in rows if row['active']) == uid
            client.save_credential(home, credential('999','renewed'))
            assert len(client.saved_accounts(home)) == 2
            assert rt.flow.store.account('999')['sessdata'] == 'test-cookie-renewed'
            assert rt.flow.store.account('888')['sessdata'] == 'test-cookie-b'
    asyncio.run(scenario())


@pytest.mark.parametrize('failure', ['expired','network','identity'])
def test_validation_failure_preserves_current_identity(accounts_api, monkeypatch, failure):
    from bilibili_api.exceptions import ResponseCodeException
    rt, app, client = accounts_api
    home = rt.h._home()
    client.save_credential(home, credential('888','b'))
    client.save_credential(home, credential('999'))
    async def fail(**kwargs):
        if failure == 'expired':
            raise ResponseCodeException(-101,'账号未登录')
        if failure == 'network':
            raise OSError('private diagnostic not for API')
        return {'mid':777}
    monkeypatch.setattr(client.user,'get_self_info',fail)
    async def scenario():
        async with http(app) as request:
            result = await request.post('/api/sugar-bili-scroll/accounts/888/activate')
            assert result.status_code == (502 if failure == 'network' else 409)
            assert client.load_credential(home).dedeuserid == '999'
            assert not rt.h._runtime['account_changing']
            assert len(client.saved_accounts(home)) == 2
            assert 'private diagnostic' not in result.text
            if failure == 'expired':
                assert next(row for row in client.saved_accounts(home) if row['uid']=='888')['error']
    asyncio.run(scenario())


def test_account_writes_enforce_origin_ids_and_running_work(accounts_api):
    rt, app, client = accounts_api
    client.save_credential(rt.h._home(),credential('999'))
    async def scenario():
        async with http(app) as request:
            activate = '/api/sugar-bili-scroll/accounts/999/activate'
            remove = '/api/sugar-bili-scroll/accounts/999'
            assert (await request.post(activate,headers={'origin':'http://foreign.example'})).status_code == 403
            assert (await request.delete(remove,headers={'origin':'http://foreign.example'})).status_code == 403
            assert (await request.post('/api/sugar-bili-scroll/accounts/bad/activate')).status_code == 400
            assert (await request.delete('/api/sugar-bili-scroll/accounts/-1')).status_code == 400
            assert (await request.post('/api/sugar-bili-scroll/accounts/777/activate')).status_code == 404
            rt.flow.workers['dm:100'] = SimpleNamespace(done=lambda:False)
            assert (await request.post(activate)).status_code == 409
            assert (await request.delete(remove)).status_code == 409
            rt.flow.workers.clear()
            assert client.load_credential(rt.h._home()).dedeuserid == '999'
    asyncio.run(scenario())


def test_switch_validation_blocks_new_work_and_can_be_cancelled(accounts_api, monkeypatch):
    rt, app, client = accounts_api
    home = rt.h._home()
    client.save_credential(home,credential('888','b'))
    client.save_credential(home,credential('999'))
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def check(**kwargs):
            entered.set()
            await release.wait()
            return {'mid':888}
        monkeypatch.setattr(client.user,'get_self_info',check)
        async with http(app) as request:
            pending = asyncio.create_task(request.post('/api/sugar-bili-scroll/accounts/888/activate'))
            await entered.wait()
            status = (await request.get('/api/sugar-bili-scroll/status')).json()
            assert status['account_changing'] and status['account_uid'] == '999'
            for route in ['/run-now','/logout','/login/start?force=true','/favorite-now']:
                assert (await request.post('/api/sugar-bili-scroll'+route)).status_code == 409
            await rt.flow.dispatch()
            assert not rt.flow.workers
            await request.post('/api/sugar-bili-scroll/login/cancel')
            release.set()
            assert (await pending).status_code == 409
            assert client.load_credential(home).dedeuserid == '999'
            assert not rt.h._runtime['account_changing']
    asyncio.run(scenario())


def test_remove_saved_identity_is_explicit_and_does_not_choose_another(accounts_api):
    rt, app, client = accounts_api
    home = rt.h._home()
    client.save_credential(home,credential('888','b'))
    client.save_credential(home,credential('999'))
    async def scenario():
        async with http(app) as request:
            assert (await request.delete('/api/sugar-bili-scroll/accounts/888')).status_code == 200
            assert client.load_credential(home).dedeuserid == '999'
            client.save_credential(home,credential('888','b'))
            assert (await request.delete('/api/sugar-bili-scroll/accounts/888')).status_code == 200
            assert client.load_credential(home) is None
            rows = (await request.get('/api/sugar-bili-scroll/accounts')).json()['items']
            assert len(rows) == 1 and rows[0]['uid'] == '999' and not rows[0]['active']
            assert (await request.delete('/api/sugar-bili-scroll/accounts/888')).status_code == 404
            assert rt.cfg['inbound_whitelist'] == '100 好友'
    asyncio.run(scenario())


def test_cancel_adding_an_account_keeps_previous_login_available(accounts_api, monkeypatch):
    rt, app, client = accounts_api
    home = rt.h._home()
    client.save_credential(home,credential('999'))
    class QR:
        _QrCodeLogin__qr_key = 'test-key'
        async def generate_qrcode(self):
            pass
        def get_qrcode_picture(self):
            return SimpleNamespace(content=b'test-image')
    monkeypatch.setattr(client,'QrCodeLogin',QR)
    async def scenario():
        async with http(app) as request:
            result = await request.post('/api/sugar-bili-scroll/login/start?force=true')
            assert result.json()['status']=='qrcode_ready'
            assert client.load_credential(home) is None
            await request.post('/api/sugar-bili-scroll/login/cancel')
            rows = (await request.get('/api/sugar-bili-scroll/accounts')).json()['items']
            assert len(rows)==1 and rows[0]['uid']=='999' and not rows[0]['active']
            assert (await request.post('/api/sugar-bili-scroll/accounts/999/activate')).status_code==200
            assert client.load_credential(home).dedeuserid=='999'
    asyncio.run(scenario())
