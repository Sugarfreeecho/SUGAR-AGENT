"""Concurrent metadata panels must not parse the same large snapshot N times."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from app.runtime_v2.snapshot_store import SnapshotStore


def test_cold_read_is_shared_and_other_sessions_and_writers_can_progress(tmp_path, monkeypatch):
    monkeypatch.setenv('RUNTIME_V2_ASYNC_SNAPSHOT_CHECKPOINTS', 'true')
    store = SnapshotStore(tmp_path)
    monkeypatch.setattr(store, '_schedule_checkpoint', lambda *_args: None)
    for sid in ('slow', 'other'):
        path = store.path(sid)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'last_seq': 1, 'messages': [sid]}), encoding='utf-8')
    entered, release = threading.Event(), threading.Event()
    original = json.load
    calls = []

    def blocked_load(stream, *args, **kwargs):
        if str(stream.name) == str(store.path('slow')):
            calls.append(True)
            entered.set()
            assert release.wait(5)
        return original(stream, *args, **kwargs)

    monkeypatch.setattr(json, 'load', blocked_load)
    with ThreadPoolExecutor(max_workers=12) as pool:
        first = pool.submit(store._read_published, 'slow')
        try:
            assert entered.wait(2)
            readers = [pool.submit(store._read_published, 'slow') for _ in range(8)]
            assert pool.submit(store._read_published, 'other').result(timeout=1)['messages'] == ['other']
            # Publication uses a separate lock; it must not wait for the cold
            # reader or let that older disk result replace a newer generation.
            newer = {'last_seq': 2, 'messages': ['newer']}
            pool.submit(store.write_checkpointed, 'slow', newer).result(timeout=1)
        finally:
            release.set()
        results = [first.result(timeout=2)] + [item.result(timeout=2) for item in readers]
    assert calls == [True]
    assert all(item is newer for item in results)
    assert store._read_published('slow') is newer


def test_external_checkpoint_change_is_not_hidden_by_coalescing(tmp_path):
    store = SnapshotStore(tmp_path)
    path = store.path('s')
    path.parent.mkdir(parents=True)
    path.write_text('{"last_seq":1}', encoding='utf-8')
    assert store._read_published('s')['last_seq'] == 1
    path.write_text('{"last_seq":22}', encoding='utf-8')
    assert store._read_published('s')['last_seq'] == 22
