"""Synthetic 1,000-session / 100,000-message search benchmark; never reads user history."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from session_search import SessionSearch


class FixtureManager:
    def __init__(self, root, count, messages):
        self.sessions_dir = root
        self.rows = []
        for i in range(count):
            sid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'myagent-search-benchmark-{i}'))
            folder = self._resolve_session_path(sid)
            folder.mkdir()
            self.rows.append(dict(id=sid, name=f'needle benchmark {i}', archived=bool(i % 2),
                                 last_activity_at='2026-10-25T08:00:00Z'))
            with (folder / 'events.jsonl').open('w', encoding='utf8') as f:
                for m in range(messages):
                    event = dict(schema_version=1, session_id=sid, seq=m + 1,
                        type='user_turn_committed' if m % 2 == 0 else 'assistant_final_committed',
                        timestamp='2026-10-25T08:00:00Z',
                        payload={'content': f'检索基准 needle session-{i:05d} message-{m:03d} 中文内容'})
                    f.write(json.dumps(event, ensure_ascii=False) + '\n')

    def _resolve_session_path(self, sid):
        return self.sessions_dir / sid

    def list_sessions(self, include_archived=False):
        return [dict(row) for row in self.rows if include_archived or not row['archived']]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sessions', type=int, default=1000)
    parser.add_argument('--messages', type=int, default=100)
    parser.add_argument('--runs', type=int, default=15)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = dict(sessions=args.sessions, messages=args.sessions * args.messages, runs=args.runs)
    with tempfile.TemporaryDirectory(prefix='myagent-search-benchmark-') as temporary:
        manager = FixtureManager(Path(temporary), args.sessions, args.messages)
        service = SessionSearch(manager)
        stop = threading.Event()
        started = time.perf_counter()
        for row in manager.rows:
            service.ensure(row['id'], stop)
        result['cold_index_ms'] = round((time.perf_counter() - started) * 1000, 2)
        result['fts5_trigram'] = service.fts
        timings = {}
        for phase in ('metadata', 'active_content', 'archived_content'):
            samples = []
            for _ in range(args.runs):
                started = time.perf_counter()
                events = service.search(service.prepare({'q': 'needle', 'phase': phase}), stop)
                try:
                    batch = []
                    for name, value in events:
                        if name == 'upsert':
                            batch.append(value)
                        if len(batch) >= 20 or name == 'phase_done':
                            break
                    assert len(batch) == min(20, len(manager.rows) if phase == 'metadata' else len(manager.rows) // 2)
                    samples.append((time.perf_counter() - started) * 1000)
                finally:
                    events.close()
            timings[phase] = dict(median_ms=round(statistics.median(samples), 2),
                                  p95_ms=round(sorted(samples)[max(0, int(len(samples) * .95 + .999) - 1)], 2))
        started = time.perf_counter()
        absent = list(service.search(service.prepare({'q': 'not-present-anywhere'}), stop))
        assert not any(name == 'upsert' for name, _ in absent)
        result['complete_absent_query_ms'] = round((time.perf_counter() - started) * 1000, 2)
        result['warm_first_batch'] = timings
        service.close()
    encoded = json.dumps(result, indent=2, ensure_ascii=False)
    print(encoded)
    if args.output:
        args.output.write_text(encoded + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
