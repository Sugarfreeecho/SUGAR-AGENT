"""UI index rebuilds must avoid work on hidden execution stream payloads."""
import json
from contextlib import contextmanager

import pytest

from runtime_v2 import attachment_migration
from runtime_v2.event_log import RuntimeEventLogCorruptionError, SessionEventLog
from runtime_v2.ui_projection import RuntimeUiProjection
from runtime_v2.ui_row_store import UiRowStore
from runtime_v2.versions import EVENT_SCHEMA_VERSION, UI_PROJECTION_INDEX_VERSION, UI_ROW_PROJECTION_VERSION


def write_facts(root, rows):
    folder = root / 's'
    folder.mkdir(exist_ok=True)
    records = [dict(schema_version=EVENT_SCHEMA_VERSION, seq=i, type=kind, session_id='s',
                    timestamp='2026-10-23T00:00:00Z', run_id='r', payload=payload)
               for i, (kind, payload) in enumerate(rows, 1)]
    (folder / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in records), encoding='utf-8')
    return records


def test_cold_projection_skips_hidden_migration_but_keeps_visible_content_and_cursor(tmp_path, monkeypatch):
    write_facts(tmp_path, [
        ('user_turn_committed', {'content': 'question'}),
        ('execution_recorded', {'execution_id': 'e', 'text_delta': 'nested history'}),
        ('tool_finished', {'content': 'tool image', 'tool': 'read_file'}),
        ('context_tokens', {'estimated': 123}),
        ('assistant_final_committed', {'content': 'answer'}),
        ('execution_recorded', {'execution_id': 'e', 'status': 'completed'}),
    ])
    calls = []
    def migrate(kind, payload):
        calls.append(kind)
        return dict(payload, content='migrated:' + payload['content']) if 'content' in payload else payload
    monkeypatch.setattr(attachment_migration, 'migrate_payload', migrate)
    projection = RuntimeUiProjection(tmp_path)
    original = projection.event_log.iter_events
    # Compare against the complete repository compatibility path used before
    # this optimization, without changing actual facts or their order.
    with monkeypatch.context() as patch:
        def unfiltered(sid, **options):
            options.pop('_skip_attachment_types', None)
            return original(sid, **options)
        patch.setattr(projection.event_log, 'iter_events', unfiltered)
        baseline, _, _ = projection._project_visible_ui_entries('s', hydrate=False)
    assert calls.count('execution_recorded') == 2
    calls.clear()
    page = projection.read_ui_page('s', limit=200)
    assert page['events'] == baseline
    assert page['last_runtime_seq'] == 6, 'hidden tail facts still advance the reconnect boundary'
    assert 'execution_recorded' not in calls
    assert calls == ['user_turn_committed', 'tool_finished', 'context_tokens', 'assistant_final_committed']
    assert page['events'][0]['content'] == 'migrated:question'
    assert page['events'][1]['content'] == 'migrated:tool image'
    calls.clear()
    SessionEventLog(tmp_path).read_all('s')
    assert calls.count('execution_recorded') == 2, 'normal/model/execution readers still migrate every payload'


@pytest.mark.parametrize('invalid', ['schema_version', 'payload'])
def test_hidden_records_are_still_validated_and_corruption_is_not_skipped(tmp_path, invalid):
    records = write_facts(tmp_path, [('message_user', {'content': 'visible'}), ('execution_recorded', {})])
    records[-1][invalid] = EVENT_SCHEMA_VERSION + 1 if invalid == 'schema_version' else []
    (tmp_path / 's/events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in records), encoding='utf-8')
    with pytest.raises(RuntimeEventLogCorruptionError):
        RuntimeUiProjection(tmp_path)._build_ui_index('s')


@pytest.mark.parametrize('from_second', [False, True])
@pytest.mark.parametrize('partial_tail', [False, True])
def test_streaming_replay_tracks_exact_byte_boundaries_without_per_row_file_position_calls(tmp_path, monkeypatch, from_second, partial_tail):
    write_facts(tmp_path, [('message_user', {'content': '中文 first'}),
                           ('ui_event', {'type': 'status', 'content': 'second'}),
                           ('assistant_final_committed', {'content': 'last'})])
    log = SessionEventLog(tmp_path)
    path = log.event_path('s')
    lines = path.read_bytes().splitlines(keepends=True)
    # Blank lines and a nonzero starting offset still count toward the next
    # complete boundary. A partial final fact must never be acknowledged.
    path.write_bytes(lines[0] + b'\n' + lines[1] + lines[2])
    start = len(lines[0]) if from_second else 0
    end = path.stat().st_size - (4 if partial_tail else 0)
    original = log._event_read_stream
    @contextmanager
    def no_tell(*args, **kwargs):
        with original(*args, **kwargs) as (stream, base, stat):
            class Reader:
                def readline(self, *args):
                    return stream.readline(*args)
                def tell(self):
                    raise AssertionError('per-row file position queries cause startup scheduling stalls')
            yield Reader(), base, stat
    monkeypatch.setattr(log, '_event_read_stream', no_tell)
    metadata = {}
    events = list(log.iter_from_offset('s', start, end_offset=end, read_metadata=metadata))
    assert [e.seq for e in events] == ([2] if from_second else [1, 2]) + ([] if partial_tail else [3])
    assert metadata['byte_offset'] == len(lines[0]) + 1 + len(lines[1]) + (0 if partial_tail else len(lines[2]))
    assert metadata['last_runtime_seq'] == (2 if partial_tail else 3)


def test_ui_row_segments_keep_byte_locations_and_integrity_without_tell(tmp_path, monkeypatch):
    from pathlib import Path
    original_open = Path.open
    def no_tell(path, mode='r', *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if mode != 'xb':
            return stream
        class Writer:
            def __enter__(self):
                stream.__enter__()
                return self
            def __exit__(self, *exc):
                return stream.__exit__(*exc)
            def write(self, data):
                return stream.write(data)
            def tell(self):
                raise AssertionError('row offsets must not query the raw file position')
        return Writer()
    monkeypatch.setattr(Path, 'open', no_tell)
    store = UiRowStore(tmp_path)
    # Include multibyte text, escaped newlines and a row larger than the write
    # buffer. Read out of order, as pagination may address any row independently.
    rows = [{'content': '中文\n🙂'}, {'content': 'x' * (300 * 1024)}, {'content': 'last'}]
    name, locations = store.write(rows)
    assert store.read([name], [locations[2], locations[0], locations[1]]) == [rows[2], rows[0], rows[1]]
    with original_open(tmp_path / name, 'r+b') as stream:
        stream.seek(locations[1][1])
        stream.write(b'!')
    with pytest.raises(ValueError, match='corrupt'):
        store.read([name], locations)


@pytest.mark.parametrize(('field', 'value', 'reason'), [
    ('row_version', UI_ROW_PROJECTION_VERSION - 1, 'row_version'),
    ('index_version', UI_PROJECTION_INDEX_VERSION - 1, 'index_version'),
    ('total', 999, 'row_count'),
])
def test_stale_disk_index_reports_why_it_rebuilt_and_does_not_serve_old_rows(tmp_path, field, value, reason):
    write_facts(tmp_path, [('message_user', {'content': 'current'})])
    projection = RuntimeUiProjection(tmp_path)
    projection.read_ui_page('s')
    path = projection._ui_index_path('s')
    index = json.loads(path.read_text(encoding='utf-8'))
    index[field] = value
    path.write_text(json.dumps(index), encoding='utf-8')
    # Drop only the process cache; invalidate_cache also deletes the disk
    # index and would accidentally test "missing", not an upgrade on restart.
    with projection._cache_lock:
        key = str(path.resolve())
        projection._index_cache.pop(key, None)
        projection._index_cache_sizes.pop(key, None)
    diagnostics = {}
    page = projection.read_ui_page('s', diagnostics=diagnostics)
    assert page['events'][0]['content'] == 'current'
    assert page['total'] == 1
    assert diagnostics['index'] == 'rebuilt'
    assert diagnostics['index_rebuild_reason'] == reason
    assert diagnostics['index_rebuild_ms'] >= 0
    assert diagnostics['index_rebuild_cpu_ms'] >= 0
    rebuilt = json.loads(path.read_text(encoding='utf-8'))
    assert rebuilt['row_version'] == UI_ROW_PROJECTION_VERSION
    assert rebuilt['index_version'] == UI_PROJECTION_INDEX_VERSION
