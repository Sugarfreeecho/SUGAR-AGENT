import json
import threading
import time

from runtime_v2.event_log import SessionEventLog
from runtime_v2.ui_projection import RuntimeUiProjection
from runtime_v2 import ui_projection


def drain(projection, sid):
    key = str(projection._ui_index_path(sid).resolve())
    deadline = time.monotonic() + 5
    with projection._checkpoint_condition:
        while key in projection._checkpoint_pending or key in projection._checkpoint_active:
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'checkpoint worker did not drain'
            projection._checkpoint_condition.wait(remaining)


def test_slow_prefix_hash_does_not_hold_foreground_index_lock(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append('s', 'message_user', {'content': 'first'})
    projection = RuntimeUiProjection(tmp_path)
    projection.read_ui_page('s')
    monkeypatch.setattr(RuntimeUiProjection, '_ASYNC_INDEX_MIN_BYTES', 0)
    monkeypatch.setattr(RuntimeUiProjection, '_INDEX_CHECKPOINT_SECONDS', 0)
    entered, release = threading.Event(), threading.Event()
    original = ui_projection.seal_source

    def blocked(*args, **kwargs):
        assert threading.current_thread().name == 'ui-index-checkpoint', 'full hashing is still in the foreground'
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(ui_projection, 'seal_source', blocked)
    try:
        log.append('s', 'message_user', {'content': 'second'})
        page = projection.read_ui_page('s', include_user_turns=True)
        assert entered.wait(1)
        assert page['events'][-1]['content'] == 'second'
        assert page['user_turns'][-1]['event_index'] == 1
        log.append('s', 'message_user', {'content': 'third'})
        latest = projection.read_ui_page('s', include_user_turns=True)
        assert latest['events'][-1]['content'] == 'third'
        assert len(latest['user_turns']) == 3
    finally:
        release.set()
        drain(projection, 's')
    persisted = json.loads(projection._ui_index_path('s').read_text(encoding='utf-8'))
    assert persisted['last_runtime_seq'] == 3
    assert persisted['source']['sha256']
    # A new process cache still verifies the persisted prefix independently.
    with projection._cache_lock:
        projection._index_cache.pop(str(projection._ui_index_path('s').resolve()), None)
    assert projection.read_ui_page('s')['events'][-1]['content'] == 'third'


def test_page_and_toc_use_one_captured_index_even_if_a_user_turn_arrives(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append('s', 'message_user', {'content': 'first'})
    projection = RuntimeUiProjection(tmp_path)
    original = projection._read_or_build_ui_index
    reads = []

    def capture(*args, **kwargs):
        index = original(*args, **kwargs)
        reads.append(index['last_runtime_seq'])
        if len(reads) == 1:
            log.append('s', 'message_user', {'content': 'later'})
        return index

    monkeypatch.setattr(projection, '_read_or_build_ui_index', capture)
    page = projection.read_ui_page('s', include_user_turns=True)
    assert reads == [1]
    assert page['total'] == len(page['events']) == len(page['user_turns']) == 1
    assert page['last_runtime_seq'] == 1
    assert projection.read_ui_page('s', include_user_turns=True)['total'] == 2


def test_sidebar_hint_does_not_build_indexes_or_full_ui_history(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append('s', 'message_user', {'content': 'bounded preview'})
    projection = RuntimeUiProjection(tmp_path)
    def forbidden(*_args, **_kwargs):
        raise AssertionError('sidebar hint must not rebuild or replay history')
    monkeypatch.setattr(projection, '_read_or_build_ui_index', forbidden)
    monkeypatch.setattr(projection, 'read_ui_events', forbidden)
    assert projection.read_user_preview_hint('s') == 'bounded preview'
    log.append('s', 'message_deleted', {'target_seq': 1})
    assert projection.read_user_preview_hint('s') == ''


def test_checkpoint_failure_does_not_stop_future_publication(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    log.append('s', 'message_user', {'content': 'one'})
    projection = RuntimeUiProjection(tmp_path)
    projection.read_ui_page('s')
    monkeypatch.setattr(RuntimeUiProjection, '_ASYNC_INDEX_MIN_BYTES', 0)
    monkeypatch.setattr(RuntimeUiProjection, '_INDEX_CHECKPOINT_SECONDS', 0)
    original = ui_projection.seal_source
    calls = []
    def fail_once(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError('checkpoint unavailable')
        return original(*args, **kwargs)
    monkeypatch.setattr(ui_projection, 'seal_source', fail_once)
    log.append('s', 'message_user', {'content': 'two'})
    assert projection.read_ui_page('s')['total'] == 2
    drain(projection, 's')
    log.append('s', 'message_user', {'content': 'three'})
    assert projection.read_ui_page('s')['total'] == 3
    drain(projection, 's')
    saved = json.loads(projection._ui_index_path('s').read_text(encoding='utf-8'))
    assert saved['last_runtime_seq'] == 3
