from runtime_v2.event_log import SessionEventLog
from runtime_v2.history_ops import RuntimeHistoryOps
from runtime_v2.projector import RuntimeProjector


def test_source_checkpoint_reads_once_and_applies_later_semantic_edits(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    user = log.append('s', 'message_user', {'content': 'original'})
    final = log.append('s', 'message_assistant_final', {'content': 'answer'})
    log.append('s', 'message_user', {'content': 'future turn'})
    edit = log.append('s', 'message_rewritten', {'target_seq': user.seq, 'content': 'edited'})
    ops = RuntimeHistoryOps(tmp_path)
    calls = []
    original = ops.event_log.iter_events
    def counted(*args, **kwargs):
        calls.append(args[0])
        yield from original(*args, **kwargs)
    monkeypatch.setattr(ops.event_log, 'iter_events', counted)
    snapshot = ops._source_snapshot_at_seq('s', final.seq)
    expected = RuntimeProjector().project([user, final])
    RuntimeProjector().apply(expected, edit)
    RuntimeProjector().finalize(expected)
    assert snapshot == expected
    assert calls == ['s']


def test_early_anchor_retains_only_provenance_from_future_model_seed(tmp_path, monkeypatch):
    log = SessionEventLog(tmp_path)
    final = log.append('s', 'message_assistant_final', {'content': 'answer'})
    log.append('s', 'execution_recorded', {'content': 'x' * 50000})
    seed = log.append('s', 'model_history_replaced', {'reason': 'branch_model_seed', 'messages': [{'role': 'user', 'content': 'x' * 50000}]})
    ops = RuntimeHistoryOps(tmp_path)
    captured = []
    def origin(*args, _source_events):
        captured.extend(_source_events)
        return None
    monkeypatch.setattr(ops, '_branch_origin_at_seq', origin)
    ops._source_snapshot_at_seq('s', final.seq)
    assert [event.seq for event in captured] == [final.seq, seed.seq]
    assert captured[-1].payload == {'reason': 'branch_model_seed'}
