"""Sequence cache keys must describe the same file as their stat."""
import json
import os


def test_cache_key_uses_the_same_resolved_file_as_its_stat(tmp_path, monkeypatch):
    from app.runtime_v2.event_log import SessionEventLog
    from app.runtime_v2.event_schema import RuntimeEvent
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    for directory, seq in [(a, 10), (b, 20)]:
        event = RuntimeEvent(seq=seq, type='model_user', session_id='s', payload={'content': 'x'})
        (directory / 'events.jsonl').write_text(json.dumps(event.to_dict()) + '\n', encoding='utf8')
    pa, pb = a / 'events.jsonl', b / 'events.jsonl'
    assert pa.stat().st_size == pb.stat().st_size
    stamp = pb.stat()
    os.utime(pa, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    monkeypatch.setattr(SessionEventLog, '_seq_cache', {})
    calls = []
    def resolver(sid):
        calls.append(sid)
        return a if len(calls) == 1 else b
    log = SessionEventLog(tmp_path, path_resolver=resolver)
    log._update_seq_cache('s', 10)
    # A namespace switch must not install a's cursor under b's cache key.
    assert log.next_seq('s') == 21


def test_cached_read_does_not_resolve_a_second_namespace_for_its_key(tmp_path, monkeypatch):
    from app.runtime_v2.event_log import SessionEventLog
    log = SessionEventLog(tmp_path)
    log.append('s', 'model_user', {'content': 'x'})
    calls = []
    tracked = SessionEventLog(tmp_path, path_resolver=lambda sid: calls.append(sid) or tmp_path / sid)
    assert tracked._cached_last_seq('s') == 1
    assert calls == ['s']


def test_append_stat_invalidation_and_distinct_roots_remain_independent(tmp_path, monkeypatch):
    from app.runtime_v2.event_log import SessionEventLog
    monkeypatch.setattr(SessionEventLog, '_seq_cache', {})
    a, b = SessionEventLog(tmp_path / 'a'), SessionEventLog(tmp_path / 'b')
    a.append('s', 'model_user', {'content': 'one'})
    b.append('s', 'model_user', {'content': 'one'})
    b.append('s', 'model_assistant', {'content': 'two'})
    assert a.next_seq('s') == 2 and b.next_seq('s') == 3
    record = a.read_all('s')[-1].to_dict()
    record['seq'] = 7
    with a.event_path('s').open('ab') as file:
        file.write((json.dumps(record) + '\n').encode())
    assert a.next_seq('s') == 8 and b.next_seq('s') == 3
