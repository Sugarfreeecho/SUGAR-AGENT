"""Read-only Goal handoff timing report; never exports conversation payloads.

Usage: python scripts/diagnose_goal_handoff.py SESSION_ID --output REPORT.json
Add --events to read durable run start/terminal anchors from events.jsonl.
Wall-clock timestamps and monotonic duration metrics remain separate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import statistics


ROOT = Path(__file__).resolve().parents[1]


def epoch(value):
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (TypeError, ValueError, AttributeError):
        return None


def seconds(start, end):
    a, b = epoch(start), epoch(end)
    return round(b - a, 3) if a is not None and b is not None else None


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def first_request(run):
    requests = sorted(run.get('requests', []), key=lambda q: q.get('react_iter', 0))
    if not requests:
        return None
    request = requests[0]
    phases = request.get('phases', {})
    local = request.get('local_request_timing') or {}
    stream = phases.get('llm_stream', {}).get('events', [])
    # These are nested spans, not additive stages. Preserve their names.
    pre_api = phases.get('pre_api', {})
    return {
        'metrics_recorded_at': request.get('started_at'),
        'run_start_to_request_metrics_s': seconds(run.get('started_at'), request.get('started_at')),
        'pre_api_total_ms': pre_api.get('total_ms'),
        'pre_api_nested_spans_ms': pre_api.get('events', {}),
        'pre_api_tail_ms': request.get('pre_api_tail_ms'),
        'preparation_to_http_send_ms': local.get('preparation_to_http_send_ms'),
        'request_worker_queue_ms': local.get('worker_queue_ms'),
        'first_token_ms': request.get('first_token_ms'),
        'stream_anchors': [{k: e[k] for k in (
            'step', 'ms_since_api_start', 'delta_type', 'body_handed_off_ms',
            'server_wait_ms', 'response_headers_ms', 'http11_send_request_body_ms') if k in e}
            for e in stream if e.get('step') in {'first_chunk', 'first_delta', 'transport_breakdown'}],
    }


def diagnose(session_dir, database, *, events=False, limit=10):
    metrics = {r['run_id']: r for r in load(session_dir / 'execution_metrics.json').get('runs', [])}
    observed = {r['run_id']: r for r in load(session_dir / 'runtime_observability.json').get('runs', [])}
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        operations = {r['run_id']: dict(r) for r in db.execute(
            "SELECT id,run_id,method,status,created,updated,"
            "json_extract(request,'$._continuation_source') AS continuation_source,"
            "json_extract(request,'$._recovery_reason') AS recovery_reason "
            "FROM operations WHERE session_id=? AND method IN ('session.send','session.continue','session.recover')",
            (session_dir.name,))}
    # Keep interrupted runs in sequence: filtering them out creates false handoffs.
    runs = sorted(set(metrics) | set(observed), key=lambda rid: epoch(
        metrics.get(rid, {}).get('started_at') or observed.get(rid, {}).get('started_at')) or 0)
    facts = {}
    if events:
        selected = {rid.encode() for rid in runs[-limit - 1:]}
        with (session_dir / 'events.jsonl').open('rb') as file:
            for line in file:
                if not any(rid in line for rid in selected):
                    continue
                event = json.loads(line)
                if event.get('type') in {'run_started', 'run_finished', 'run_failed', 'run_interrupted', 'assistant_final_committed'}:
                    row = facts.setdefault(event.get('run_id'), {})
                    row.setdefault(event['type'], event.get('timestamp'))
    handoffs = []
    for previous, current in zip(runs, runs[1:]):
        pm, po, op = metrics.get(previous, {}), observed.get(previous, {}), operations.get(previous, {})
        cm, co, next_op = metrics.get(current, {}), observed.get(current, {}), operations.get(current, {})
        if next_op.get('continuation_source') != 'agent-goal':
            continue
        if po.get('status', pm.get('status')) != 'finished' or op.get('status') != 'succeeded':
            continue
        anchors = {
            'previous_durable_final': facts.get(previous, {}).get('assistant_final_committed'),
            'previous_durable_terminal': facts.get(previous, {}).get('run_finished'),
            'previous_metrics_finished': pm.get('finished_at'),
            'previous_observability_finished': po.get('finished_at'),
            'previous_control_updated': op.get('updated'),
            'next_admitted': next_op.get('created'),
            'next_metrics_started': cm.get('started_at'),
            'next_durable_started': facts.get(current, {}).get('run_started'),
        }
        def gap(a, b):
            return seconds(anchors[a], anchors[b])
        durations = {
            'final_commit_to_durable_terminal_s': gap('previous_durable_final', 'previous_durable_terminal'),
            'final_commit_to_next_start_s': gap('previous_durable_final', 'next_metrics_started'),
            'metrics_finish_to_control_terminal_s': gap('previous_metrics_finished', 'previous_control_updated'),
            'control_terminal_to_admission_s': gap('previous_control_updated', 'next_admitted'),
            'admission_to_run_start_s': gap('next_admitted', 'next_metrics_started'),
            'metrics_finish_to_next_start_s': gap('previous_metrics_finished', 'next_metrics_started'),
            'observability_finish_to_next_start_s': gap('previous_observability_finished', 'next_metrics_started'),
            'durable_terminal_to_next_start_s': gap('previous_durable_terminal', 'next_metrics_started'),
        }
        total = durations['metrics_finish_to_next_start_s']
        handoffs.append({'previous_run_id': previous, 'next_run_id': current,
            'next_status': co.get('status', cm.get('status')), 'anchors': anchors, 'durations': durations,
            'long_gap_needs_review': total is not None and total > 300,
            'first_request': first_request(cm)})
    sample = [h['durations']['metrics_finish_to_next_start_s'] for h in handoffs
              if not h['long_gap_needs_review'] and h['durations']['metrics_finish_to_next_start_s'] is not None]
    meta = load(session_dir / 'metadata.json')
    return {
        'session_id': session_dir.name, 'captured_at': datetime.now(timezone.utc).isoformat(),
        'current_interrupt': {k: meta.get(k) for k in ('interrupt_requested', 'interrupt_reason')},
        'notes': [
            'Read-only snapshots; completed run adjacency is preserved across interruptions.',
            'started_at of request metrics is a recording anchor, not an exact HTTP-send or browser-paint timestamp.',
            'pre_api spans overlap and must not be summed; preparation_to_http_send overlaps pre_api.',
            'No historical scheduler substages or browser-paint times are inferred from missing data.',
            'Long gaps (>300 s) require manual review and are excluded from summary, not labelled as scheduler latency.',
        ],
        'summary': {'count': len(sample), 'median_s': round(statistics.median(sample), 3) if sample else None,
                    'p95_s': sorted(sample)[min(len(sample)-1, int(len(sample)*.95))] if sample else None,
                    'max_s': max(sample) if sample else None},
        'handoffs': handoffs[-limit:],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session_id')
    parser.add_argument('--sessions-dir', type=Path, default=ROOT / 'workspace/sessions')
    parser.add_argument('--database', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'SugarAgent/session-control/control.sqlite3')
    parser.add_argument('--events', action='store_true')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if Path(args.session_id).name != args.session_id or not 1 <= args.limit <= 100:
        parser.error('Expected a session ID and a limit between 1 and 100')
    report = diagnose(args.sessions_dir / args.session_id, args.database, events=args.events, limit=args.limit)
    result = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + '\n', encoding='utf-8')
        print(json.dumps({'output': str(args.output.resolve()), 'summary': report['summary']}, ensure_ascii=False))
    else:
        print(result)
