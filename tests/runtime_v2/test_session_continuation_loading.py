"""Summary continuation checks must not replay message payloads."""
from runtime_v2.mirror import RuntimeMirror
from runtime_v2.ui_projection import RuntimeUiProjection
from runtime_v2.ui_row_store import UiRowStore
import pytest


def test_continuation_uses_visible_rows_without_blobs_or_fact_replay(tmp_path, monkeypatch):
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event('s', {'type': 'user', 'content': 'work'})
    for i in range(200):
        mirror.mirror_ui_event('s', {'type': 'status', 'content': str(i)})
    projection = RuntimeUiProjection(tmp_path)
    projection.read_ui_page('s', limit=1)
    monkeypatch.setattr(projection, 'read_ui_events', lambda *_: (_ for _ in ()).throw(AssertionError('full replay')))
    monkeypatch.setattr(projection, '_hydrate_blob_refs', lambda *_: (_ for _ in ()).throw(AssertionError('blob load')))
    assert projection.has_unanswered_user('s') is True
    mirror.mirror_ui_event('s', {'type': 'final', 'content': 'done'})
    assert projection.has_unanswered_user('s') is False
    mirror.mirror_ui_event('s', {'type': 'user', 'content': 'again'})
    assert projection.has_unanswered_user('s') is True


def test_completed_turn_check_reads_only_a_small_tail(tmp_path, monkeypatch):
    projection = RuntimeUiProjection(tmp_path)
    events = [{'type': 'user', 'content': 'long turn'}]
    events += [{'type': 'status', 'content': str(i)} for i in range(2000)]
    events += [{'type': 'final', 'content': 'done'}, {'type': 'status', 'content': 'metrics'}]
    # A compacted baseline has the same visible boundaries as uncompressed facts.
    from runtime_v2.event_log import SessionEventLog
    SessionEventLog(tmp_path).append('s', 'runtime_snapshot_compacted', {'ui_events': events})
    projection.read_ui_page('s', limit=1)
    original = UiRowStore.read
    sizes = []
    def read(store, files, locations):
        sizes.append(len(locations))
        return original(store, files, locations)
    monkeypatch.setattr(UiRowStore, 'read', read)
    assert projection.has_unanswered_user('s') is False
    assert sizes == [64], 'the final near the tail avoids reading thousands of earlier rows'


def test_no_user_is_not_continuable(tmp_path):
    mirror = RuntimeMirror(tmp_path)
    mirror.mirror_ui_event('s', {'type': 'status', 'content': 'no question'})
    assert RuntimeUiProjection(tmp_path).has_unanswered_user('s') is False


def test_unavailable_history_does_not_grant_a_new_queue_run(tmp_path, monkeypatch):
    projection = RuntimeUiProjection(tmp_path)
    monkeypatch.setattr(projection, '_read_or_build_ui_index', lambda _: {})
    with pytest.raises(RuntimeError, match='unavailable'):
        projection.has_unanswered_user('s')
