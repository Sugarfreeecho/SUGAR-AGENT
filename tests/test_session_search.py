import json
from pathlib import Path
import threading
import uuid
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from session_search import SessionSearch, SearchError, install_session_search


class Manager:
    def __init__(self, root, v2=True):
        self.sessions_dir = root
        self.rows = []
        self.v2 = v2

    def _runtime_v2_primary(self):
        return self.v2

    def _resolve_session_path(self, sid):
        return self.sessions_dir / str(uuid.UUID(sid))

    def list_sessions(self, include_archived=False):
        return [dict(s) for s in self.rows if include_archived or not s.get('archived')]

    def get_session_summary(self, sid):
        return next((s for s in self.rows if s['id'] == sid), None)

    def get_ui_events_for_display(self, sid):
        return json.loads((self._resolve_session_path(sid) / 'ui_events.json').read_text(encoding='utf8'))

    def add(self, name='Example', archived=False, messages=(), **fields):
        sid = str(uuid.uuid4())
        root = self._resolve_session_path(sid)
        root.mkdir()
        self.rows.append(dict(id=sid, name=name, archived=archived, last_activity_at='2026-10-25T08:00:00Z', **fields))
        if self.v2:
            self.events(sid, messages)
        else:
            (root / 'ui_events.json').write_text(json.dumps(list(messages), ensure_ascii=False), encoding='utf8')
        return sid

    def events(self, sid, messages):
        rows = [dict(schema_version=1, seq=i + 1, type=typ, session_id=sid, timestamp='2026-10-25T08:00:00Z', payload=payload)
                for i, (typ, payload) in enumerate(messages)]
        (self._resolve_session_path(sid) / 'events.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')

    def archive(self, sid, rows):
        root = self._resolve_session_path(sid) / 'history_context_archives'
        root.mkdir(exist_ok=True)
        (root / 'saved.jsonl').write_text(''.join(json.dumps(dict(kind='message', item_id=f'm{i}', **r), ensure_ascii=False) + '\n'
                                               for i, r in enumerate(rows)), encoding='utf8')


def run(service, **payload):
    return list(service.search(service.prepare(dict(q='needle') | payload), threading.Event()))


def upserts(events):
    return [v for k, v in events if k == 'upsert']


@pytest.mark.parametrize('fts', [True, False])
def test_stages_full_history_tools_short_chinese_and_location(tmp_path, fts):
    manager = Manager(tmp_path)
    active = manager.add(messages=[('user_turn_committed', {'content': '早期问题 needle 中文'}),
                                   ('run_heartbeat', {}),
                                   ('assistant_final_committed', {'content': '<think>secret reasoning</think>public needle reply'}),
                                   ('tool_finished', {'tool': 'shell', 'output': 'tool-only evidence'})])
    archived = manager.add('Needle archive', True, messages=[('assistant_final_committed', {'content': 'archived needle'})])
    manager.archive(active, [dict(role='assistant', content='public needle reply'),
                             dict(role='user', content='compressed-only needle'),
                             dict(role='assistant', content='visible', reasoning='hidden-archive-thought')])
    service = SessionSearch(manager, use_fts=fts)
    events = run(service)
    assert [v['phase'] for k, v in events if k == 'phase_done'] == ['metadata', 'active_content', 'archived_content']
    assert [(r['phase'], r['session']['id']) for r in upserts(events)] == [('metadata', archived), ('active_content', active), ('archived_content', archived)]
    active_result = next(r for r in upserts(events) if r['phase'] == 'active_content')
    assert len(active_result['hits']) == 3  # archive copy of reply deduplicated
    hit = active_result['hits'][1]
    location = service.resolve(active, hit['ref'], hit['source_version'])
    assert location['ui_index'] == 1  # Runtime seq=3 is not UI index=3
    assert location['turn_index'] == 0
    assert location['content'] == 'public needle reply'
    assert upserts(run(service, q='中文'))
    assert not upserts(run(service, q='secret'))
    assert not upserts(run(service, q='hidden-archive-thought'))
    assert not upserts(run(service, q='tool-only'))
    assert upserts(run(service, q='tool-only', include_tools=True))
    assert not upserts(run(service, q='早期 reply'))  # AND applies within one message
    assert len(upserts(run(service, q='compressed-only'))) == 1
    service.close()


def test_metadata_scope_alias_order_and_paging(tmp_path):
    manager = Manager(tmp_path, v2=False)
    for i in range(26):
        manager.add(f'needle {i:02d}', i % 2 == 0, work_dir='D:/project', work_dir_label='project')
    exact = manager.add('needle')
    manager.add('hidden needle', draft=True)
    service = SessionSearch(manager)
    first = run(service, phase='metadata')
    assert len(upserts(first)) == 20
    assert upserts(first)[0]['session']['id'] == exact
    cursor = next(v['cursor'] for k, v in first if k == 'phase_done')
    second = upserts(run(service, phase='metadata', cursor=cursor))
    assert len(second) == 7
    assert not ({r['session']['id'] for r in second} & {r['session']['id'] for r in upserts(first)})
    assert len(upserts(run(service, phase='metadata', scope='archived'))) == 13
    assert upserts(run(service, q='自定义', phase='metadata', workdir_aliases={'workdir:d:/project': '自定义工作区'}))
    manager.rows[0]['name'] = 'Changed'
    with pytest.raises(SearchError, match='已变化'):
        service.prepare(dict(q='needle', phase='metadata', cursor=cursor))
    service.close()


def test_hit_paging_stale_refs_archive_context_and_cancel(tmp_path):
    manager = Manager(tmp_path)
    sid = manager.add(messages=[('user_turn_committed', {'content': f'needle item {i}'}) for i in range(7)])
    manager.archive(sid, [dict(role='assistant', content='archive needle')])
    service = SessionSearch(manager)
    first = upserts(run(service, phase='active_content'))[0]
    second = upserts(run(service, phase='active_content', session_id=sid, cursor=first['hit_cursor']))[0]
    assert len(second['hits']) == 3
    assert not ({h['ref'] for h in first['hits']} & {h['ref'] for h in second['hits']})
    last = upserts(run(service, phase='active_content', session_id=sid, cursor=second['hit_cursor']))[0]
    assert len(last['hits']) == 2
    archive_hit = last['hits'][-1]
    assert service.resolve(sid, archive_hit['ref'], archive_hit['source_version'])['archive']
    old = first['hits'][0]
    manager.events(sid, [('user_turn_committed', {'content': 'replaced'})])
    with pytest.raises(SearchError, match='已变化'):
        service.resolve(sid, old['ref'], old['source_version'])
    stop = threading.Event(); stop.set()
    assert list(service.search(service.prepare({'q': 'needle'}), stop)) == []
    assert not upserts(run(service, phase='active_content', q='item'))
    manager.rows.clear()
    with pytest.raises(SearchError) as deleted:
        service.resolve(sid, old['ref'], old['source_version'])
    assert deleted.value.status == 404
    service.close()


@pytest.mark.parametrize('operation,payload', [('message_deleted', {'target_seq': 1}),
    ('message_rewritten', {'target_seq': 1, 'content': 'replacement'}), ('visible_range_changed', {'to_seq': 0})])
def test_removed_text_is_not_resurrected_from_archive(tmp_path, operation, payload):
    manager = Manager(tmp_path)
    sid = manager.add(messages=[('user_turn_committed', {'content': 'obsolete needle'}), (operation, payload)])
    manager.archive(sid, [dict(role='user', content='obsolete needle')])
    service = SessionSearch(manager)
    assert not upserts(run(service, phase='active_content'))
    service.close()


def test_execution_journal_and_derived_cache_corruption(tmp_path):
    manager = Manager(tmp_path)
    sid = manager.add(messages=[('user_turn_committed', {'content': 'hello'}),
        ('execution_recorded', {'execution_id': 'call-1', 'kind': 'tool', 'turn_id': '1', 'tool': 'shell',
                                'result': 'execution needle', 'status': 'completed'}),
        ('execution_recorded', {'execution_id': 'think', 'kind': 'llm_reasoning', 'content': 'secret needle'})])
    service = SessionSearch(manager)
    service.path.write_bytes(b'broken derived database')
    assert not upserts(run(service))
    result = upserts(run(service, include_tools=True))[0]
    assert len(result['hits']) == 1
    hit = result['hits'][0]
    assert service.resolve(sid, hit['ref'], hit['source_version'])['turn_index'] == 0
    assert not upserts(run(service, q='secret', include_tools=True))
    service.close()


def test_sse_api_validation_and_resolution(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    manager = Manager(tmp_path)
    manager.add(messages=[('user_turn_committed', {'content': 'api needle'})])
    app = FastAPI()
    service = install_session_search(app, manager)
    # No background thread in this isolated API test; warmup is tested separately.
    service.warm = lambda _: None
    with TestClient(app) as client:
        assert client.post('/sessions/search', json={'q': ''}).status_code == 400
        response = client.post('/sessions/search', json={'q': 'needle'})
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/event-stream')
        assert 'event: done' in response.text
        frames = [json.loads(frame.split('data: ', 1)[1]) for frame in response.text.split('\n\n') if frame.startswith('event: upsert')]
        hit = frames[0]['hits'][0]
        sid = frames[0]['session']['id']
        assert client.get(f'/sessions/{sid}/search-hit', params={'ref': hit['ref'], 'source_version': hit['source_version']}).json()['ui_index'] == 0
        assert client.get(f'/sessions/{sid}/search-hit', params={'ref': hit['ref'], 'source_version': 'stale'}).status_code == 409
    service.close()


def test_archive_excerpt_centers_on_unicode_match_after_large_prefix(tmp_path):
    manager = Manager(tmp_path)
    sid = manager.add()
    manager.archive(sid, [dict(role='assistant', content='ß' * 60000 + ' UnicodeNeedle tail')])
    service = SessionSearch(manager)
    result = upserts(run(service, q='unicodeneedle', phase='active_content'))[0]['hits'][0]
    assert 'UnicodeNeedle' in result['snippet']
    resolved = service.resolve(sid, result['ref'], result['source_version'], result['match_offset'])
    assert 'UnicodeNeedle' in resolved['content']
    assert resolved['content_offset'] > 0
    service.close()


def test_one_unreadable_session_does_not_hide_other_matches(tmp_path):
    manager = Manager(tmp_path, v2=False)
    bad = manager.add()
    (manager._resolve_session_path(bad) / 'ui_events.json').unlink()
    good = manager.add(messages=[dict(type='user', content='needle visible')])
    service = SessionSearch(manager)
    events = run(service, phase='active_content')
    assert [r['session']['id'] for r in upserts(events)] == [good]
    assert any(k == 'error' for k, _ in events)
    assert not any(k == 'phase_done' for k, _ in events)
    service.close()


def test_background_warmup_keeps_cursor_and_changes_invalidate_it(tmp_path):
    manager = Manager(tmp_path, v2=False)
    for i in range(25):
        manager.add(f'needle {i}')
    service = SessionSearch(manager)
    first = run(service, phase='metadata')
    cursor = next(v['cursor'] for k, v in first if k == 'phase_done')
    service.warm(manager.rows)
    service.work.join()
    assert len(upserts(run(service, phase='metadata', cursor=cursor))) == 5
    service.invalidate(manager.rows[0]['id'])
    with pytest.raises(SearchError, match='已变化'):
        service.prepare(dict(q='needle', phase='metadata', cursor=cursor))
    service.close()


def test_visible_intermediate_response_and_archived_tool_calls(tmp_path):
    manager = Manager(tmp_path)
    sid = manager.add(messages=[('user_turn_committed', {'content': 'hello'}),
        ('execution_recorded', dict(execution_id='response', kind='llm_response', turn_id='1', content='<think>hidden-reasoning</think>intermediate needle'))])
    manager.archive(sid, [dict(role='assistant', content='answer', tool_calls=[dict(name='shell', args={'cmd': 'archived-tool-needle'})])])
    service = SessionSearch(manager)
    assert upserts(run(service, q='intermediate'))
    assert not upserts(run(service, q='hidden-reasoning', include_tools=True))
    assert not upserts(run(service, q='archived-tool-needle'))
    assert upserts(run(service, q='archived-tool-needle', include_tools=True))
    service.close()


def test_snapshot_compaction_keeps_archive_original_searchable(tmp_path):
    manager = Manager(tmp_path)
    sid = manager.add(messages=[('user_turn_committed', {'content': 'compressed needle'}),
                               ('runtime_snapshot_compacted', {'ui_events': [], 'snapshot': {}})])
    manager.archive(sid, [dict(role='user', content='compressed needle')])
    service = SessionSearch(manager)
    result = upserts(run(service, phase='active_content'))
    assert len(result) == 1
    assert ':archive:' in result[0]['hits'][0]['ref']
    service.close()
