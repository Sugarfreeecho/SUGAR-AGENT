"""Alternating A/B review measurements; never mutate a real session/workspace.

The baseline is a saved pre-change store.py. Real-session mode copies index
bytes only and exercises metadata I/O/migration (never reads original files).
Synthetic capture mode fixes inventory to isolate store cost from Git startup.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def summary(values):
    ordered = sorted(values)
    return {'n': len(values), 'p50_ms': statistics.median(values),
            'p95_ms': ordered[min(len(ordered) - 1, math.ceil(len(ordered) * .95) - 1)],
            'max_ms': max(values)}


def timed(call):
    start = time.perf_counter()
    result = call()
    return result, (time.perf_counter() - start) * 1000


def legacy_snapshot(path, module):
    """Rebuild a v1 fixture if the running app already migrated this session.

    Retired/GC'd text is not resurrected. Both variants receive identical
    retained content, and the report marks reconstructed inputs explicitly.
    """
    raw = path.read_bytes()
    data = json.loads(raw)
    version = data.get('version')
    if version == 1:
        return raw, False, version, len(raw)
    source = module.FileChangeReviewStore(path.parent.parent)
    for record in data['records'].values():
        value = (record.get('diff') if record.get('dropped') or record.get('neutralized')
                 else source.public_record(record)['diff'])
        record.pop('diff_blob', None)
        record.pop('diff_empty', None)
        record['diff'] = value
    for baseline in data['baselines'].values():
        baseline['entries'] = source._baseline_entries(baseline)
        for key in ('entries_blob', 'entries_archive', 'entries_sha256'):
            baseline.pop(key, None)
    for key, event in list(data['review_events'].items()):
        data['review_events'][key] = source._public_result(event)
    for operation in data['operations'].values():
        if isinstance(operation.get('result'), dict):
            operation['result'] = source._public_result(operation['result'])
    data['version'] = 1
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), True, version, len(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-store', type=Path, required=True)
    parser.add_argument('--sessions', nargs='*', default=[])
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--files', type=int, default=30)
    parser.add_argument('--modes', nargs='+', choices=('unchanged_shell', 'native_edit', 'batch_three'),
                        default=['unchanged_shell', 'native_edit', 'batch_three'])
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 4 or args.files < 1:
        parser.error('at least four samples and one file are required')
    logging.disable(logging.CRITICAL)
    modules = {'previous': load(args.baseline_store.resolve(), 'review_storage_before'),
               'current': load(ROOT / 'plugins/change-review/store.py', 'review_storage_after')}
    report = {'scope': 'alternating warm A/B, includes fsync; excludes model/tool work; isolated copies',
              'samples': args.samples, 'sessions': {}, 'synthetic': {}}
    with tempfile.TemporaryDirectory(prefix='review-storage-benchmark-') as temporary:
        sandbox = Path(temporary)
        for prefix in args.sessions:
            matches = [path for path in (ROOT / 'workspace/sessions').glob('*/change_reviews/index.json')
                       if path.parent.parent.name.startswith(prefix)]
            if len(matches) != 1:
                parser.error(f'expected one session for {prefix}, found {len(matches)}')
            raw, reconstructed, version, source_bytes = legacy_snapshot(matches[0], modules['current'])
            stores = {}
            details = {'source_bytes': source_bytes, 'source_version': version,
                       'legacy_fixture_bytes': len(raw), 'baseline_reconstructed': reconstructed,
                       'first_access_ms': {}}
            for name, module in modules.items():
                store = module.FileChangeReviewStore(sandbox / prefix / name)
                store.root.mkdir(parents=True)
                store.index_path.write_bytes(raw)
                _, elapsed = timed(store._load)
                stores[name] = store
                details['first_access_ms'][name] = elapsed
            values = {name: {'load': [], 'save': []} for name in modules}
            for sample in range(args.samples):
                order = list(modules) if sample % 2 == 0 else list(reversed(modules))
                for name in order:
                    index, elapsed = timed(stores[name]._load)
                    values[name]['load'].append(elapsed)
                    _, elapsed = timed(lambda: stores[name]._save(index))
                    values[name]['save'].append(elapsed)
            for name in modules:
                details[name] = {key: summary(vals) for key, vals in values[name].items()}
                details[name]['index_bytes'] = stores[name].index_path.stat().st_size
            report['sessions'][prefix] = details

        import agent_tools
        workspace = sandbox / 'workspace'
        workspace.mkdir()
        inventory = [workspace / f'{index}.txt' for index in range(args.files)]
        for path in inventory:
            path.write_text('initial\n', encoding='utf-8')
        for mode in args.modes:
            roots = {name: sandbox / mode / name for name in modules}
            for name, module in modules.items():
                module.FileChangeReviewStore._git_inventory = staticmethod(lambda _root: inventory)
                store = module.FileChangeReviewStore(roots[name])
                token = store.begin_capture('run_shell', {}, run_id='turn', tool_call_id='warmup', work_root=workspace)
                store.finish_capture(token)
            values = {name: [] for name in modules}
            with agent_tools.tool_work_dir_override(workspace):
                for sample in range(args.samples + 2):
                    order = list(modules) if sample % 2 == 0 else list(reversed(modules))
                    for name in order:
                        module = modules[name]
                        elapsed = 0.0
                        count = 3 if mode == 'batch_three' else 1
                        for position in range(count):
                            store = module.FileChangeReviewStore(roots[name])
                            target = inventory[position]
                            tool = 'run_shell' if mode == 'unchanged_shell' else 'write_file'
                            token, cost = timed(lambda: store.begin_capture(tool, {'path': str(target)},
                                run_id='turn', tool_call_id=f'{sample}-{position}', work_root=workspace))
                            elapsed += cost
                            if mode != 'unchanged_shell':
                                target.write_text(f'sample {sample}\n', encoding='utf-8')
                            _, cost = timed(lambda: store.finish_capture(token, defer_workspace_sweep=count > 1))
                            elapsed += cost
                        if count > 1:
                            def flush():
                                for event in store.flush_deferred_sweeps():
                                    store.acknowledge_review_event(event['operation_id'])
                            _, cost = timed(flush)
                            elapsed += cost
                        if sample >= 2:
                            values[name].append(elapsed)
            report['synthetic'][mode] = {name: summary(values[name]) for name in modules}
            report['synthetic'][mode]['paired_samples_ms'] = values
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
