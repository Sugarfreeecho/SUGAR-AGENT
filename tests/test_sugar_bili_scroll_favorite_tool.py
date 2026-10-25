"""Exercise the model-facing favorite tool with temporary data and no B站 writes."""
import asyncio
import json

import pytest

from tests.test_sugar_bili_scroll_tasks import host
from tests.test_sugar_bili_scroll_workflows import BV1, runtime, tool_context


@pytest.fixture
def favorite(runtime, monkeypatch):
    rt = runtime
    async def folders(home, uid=0):
        rt.calls.append(('folders',uid))
        return {'uid':999,'folders':[{'id':42,'title':'测试收藏夹'},{'id':43,'title':'其他收藏夹'}]}
    async def add(home, bvid, fid):
        rt.calls.append(('favorite',bvid,fid))
        return {'ok':True,'bvid':bvid,'fid':fid,'aid':123}
    monkeypatch.setattr(rt.h.bili_client,'favorite_folders',folders,raising=False)
    monkeypatch.setattr(rt.h.bili_client,'favorite_add',add,raising=False)
    return rt


@pytest.mark.parametrize('mode',['manual','dm','reply'])
def test_favorite_uses_current_accounts_folder_and_returns_receipt(favorite, mode):
    rt = favorite
    run_id = 'manual' if mode=='manual' else 'bili-'+mode+'-favorite'
    if mode!='manual':
        rt.flow.store.start_run(run_id,'s',{'mode':mode,'uid':'100'})
    result = asyncio.run(rt.h._invoke(tool_context(run_id,'bili_favorite_add'),{'bvid':BV1,'fid':42}))
    assert result.kind.value=='completed'
    assert json.loads(result.content)['fid']==42
    assert rt.calls==[('folders',0),('favorite',BV1,42)]


def test_favorite_falls_back_to_config_and_explicit_folder_wins(favorite):
    rt = favorite
    rt.cfg['fav_folder_id']=42
    context = tool_context('manual','bili_favorite_add')
    result = asyncio.run(rt.h._invoke(context,{'bvid':BV1}))
    assert result.kind.value=='completed'
    result = asyncio.run(rt.h._invoke(context,{'bvid':BV1,'fid':43}))
    assert result.kind.value=='completed'
    assert [call[2] for call in rt.calls if call[0]=='favorite']==[42,43]


@pytest.mark.parametrize('args',[{'bvid':'bad','fid':42},{'bvid':BV1},{'bvid':BV1,'fid':-1},{'bvid':BV1,'fid':True},{'bvid':BV1,'fid':1.5}])
def test_invalid_favorite_is_rejected_before_network(favorite,args):
    rt = favorite
    result = asyncio.run(rt.h._invoke(tool_context('manual','bili_favorite_add'),args))
    assert result.kind.value=='failed' and not rt.calls


def test_foreign_folder_and_remote_error_are_not_reported_as_success(favorite,monkeypatch):
    rt = favorite
    context=tool_context('manual','bili_favorite_add')
    result=asyncio.run(rt.h._invoke(context,{'bvid':BV1,'fid':99}))
    assert result.kind.value=='failed' and rt.calls==[('folders',0)]
    async def failed(*args):
        return {'ok':False,'error':'收藏失败'}
    monkeypatch.setattr(rt.h.bili_client,'favorite_add',failed)
    result=asyncio.run(rt.h._invoke(context,{'bvid':BV1,'fid':42}))
    assert result.kind.value=='failed' and '收藏失败' in result.content


@pytest.mark.parametrize('revocation',['stranger','revoked','during_lookup','switch'])
def test_collection_obeys_whitelist_and_account_changes(favorite,monkeypatch,revocation):
    rt=favorite
    rt.flow.store.start_run('bili-dm-fav','s',{'mode':'dm','uid':'200' if revocation=='stranger' else '100'})
    if revocation=='revoked':rt.cfg['inbound_whitelist']=''
    if revocation in {'during_lookup','switch'}:
        async def folders(*args):
            if revocation=='during_lookup':rt.cfg['inbound_whitelist']=''
            else:(rt.h._home()/'bili_credential.json').write_text('changed-test-cookie',encoding='utf-8')
            return {'uid':999,'folders':[{'id':42}]}
        monkeypatch.setattr(rt.h.bili_client,'favorite_folders',folders)
    result=asyncio.run(rt.h._invoke(tool_context('bili-dm-fav','bili_favorite_add'),{'bvid':BV1,'fid':42}))
    assert result.kind.value=='failed'
    assert not any(call[0]=='favorite' for call in rt.calls)


def test_favorite_catalog_declares_external_write_and_respects_session_scope(favorite):
    rt=favorite
    context={'is_enabled':lambda pid:True}
    assert rt.h.tool_definitions(context,rt.h._runtime['plugin']) == []
    row=next(row for row in rt.h.mcp_tool_rows() if row[0]['function']['name']=='bili_favorite_add')
    definition=row[0]['function']
    assert definition['parameters']['required']==['bvid']
    assert row[2]=='external_write'
    context['session_meta']={'_plugin_run_policy':{'allowed':[]}}
    assert not rt.h.tool_definitions(context,rt.h._runtime['plugin'])
    row=rt.h.tasks_mod.new_row()
    rt.h.tasks_mod.save(rt.h._home(),[row])
    assert 'bili_favorite_add' not in rt.flow.allowed({'mode':'duty','task_id':row['id']})
