"""Isolated, model-free measurement of review work between tool invocations.

Example: python scripts/benchmark_change_review.py --files 1000 --steps 20
The report separates first-capture initialization from steady-state work.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor


def load_store(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def measure(module, root: Path, workspace: Path, steps: int):
    rows = []
    store = module.FileChangeReviewStore(root)
    for index in range(steps + 1):
        started = time.perf_counter()
        pending = store.begin_capture("run_shell", {}, run_id="benchmark", tool_call_id=str(index), work_root=workspace)
        ready = time.perf_counter()
        before_details = dict(store.timings) if index == 0 else None
        # Exercise a real edit as well as unchanged scans, without executing a
        # shell or including its work in the review latency measurement.
        if index % 3 == 1:
            (workspace / "edited.txt").write_text(f"step {index}\n", encoding="utf-8")
        finished = time.perf_counter()
        store.finish_capture(pending)
        ended = time.perf_counter()
        rows.append({"before_ms": (ready - started) * 1000, "after_ms": (ended - finished) * 1000,
                     "before_details": before_details,
                     "after_details": dict(store.timings) if index == 0 else None})
    # Actual boundary: post-tool audit of step N plus pre-tool audit of N+1.
    gaps = [rows[i]["after_ms"] + rows[i + 1]["before_ms"] for i in range(steps)]
    gaps.sort()
    return {"initial_before_ms": rows[0]["before_ms"],
            "initial_before_details": rows[0]['before_details'],
            "initial_after_details": rows[0]['after_details'], "p50_ms": statistics.median(gaps),
            "p95_ms": gaps[min(len(gaps) - 1, int(len(gaps) * .95))], "max_ms": max(gaps), "samples": rows}


def measure_batches(module, root: Path, workspace: Path, steps: int, batch_size: int):
    """Measure store work only; writes, model calls and host UI delivery excluded."""
    import agent_tools

    store = module.FileChangeReviewStore(root)
    inventory_calls = 0
    original_inventory = store._git_inventory

    def inventory(path):
        nonlocal inventory_calls
        inventory_calls += 1
        return original_inventory(path)

    store._git_inventory = inventory
    deferred = hasattr(store, 'flush_deferred_sweeps')
    samples = []
    with agent_tools.tool_work_dir_override(workspace):
        for batch in range(steps + 1):
            elapsed_ms = 0.0
            calls_before = inventory_calls
            for position in range(batch_size):
                name = f'batch-{position}.txt'
                started = time.perf_counter()
                pending = store.begin_capture('write_file', {'path': name}, run_id='batch-benchmark',
                                              tool_call_id=f'{batch}-{position}', work_root=workspace)
                elapsed_ms += (time.perf_counter() - started) * 1000
                (workspace / name).write_text(f'batch {batch}\n', encoding='utf-8')
                started = time.perf_counter()
                kwargs = {'defer_workspace_sweep': True} if deferred else {}
                changes = store.finish_capture(pending, **kwargs)
                elapsed_ms += (time.perf_counter() - started) * 1000
                assert any(row['path'] == name for row in changes)
            started = time.perf_counter()
            if deferred:
                for event in store.flush_deferred_sweeps():
                    store.acknowledge_review_event(event['operation_id'])
            elapsed_ms += (time.perf_counter() - started) * 1000
            samples.append({'elapsed_ms': elapsed_ms, 'inventory_calls': inventory_calls - calls_before,
                            'last_scan': dict(getattr(store, 'timings', {}))})
    warm = sorted(row['elapsed_ms'] for row in samples[1:])
    return {'initial_batch_ms': samples[0]['elapsed_ms'], 'p50_ms': statistics.median(warm),
            'p95_ms': warm[min(len(warm) - 1, int(len(warm) * .95))], 'max_ms': max(warm),
            'inventory_calls_per_warm_batch': [row['inventory_calls'] for row in samples[1:]],
            'samples': samples}


def measure_signatures(module, workspace: Path, samples: int):
    """Rotate serial/4/8 worker scans; include pool startup and ordered merging."""
    inventory = module.FileChangeReviewStore._git_inventory(workspace)
    expected = [module._file_signature(path) for path in inventory]
    rows = {str(workers): [] for workers in (1, 4, 8)}
    for sample in range(samples):
        order = [1, 4, 8]
        order = order[sample % 3:] + order[:sample % 3]
        for workers in order:
            started = time.perf_counter()
            if workers == 1:
                actual = [module._file_signature(path) for path in inventory]
            else:
                actual = []
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for position in range(0, len(inventory), 128):
                        actual.extend(pool.map(module._file_signature, inventory[position:position + 128]))
            rows[str(workers)].append((time.perf_counter() - started) * 1000)
            assert actual == expected
    return {'files': len(inventory), 'batch_size': 128, 'samples_per_variant': samples,
            'p50_ms': {workers: statistics.median(values) for workers, values in rows.items()},
            'samples': rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=300)
    parser.add_argument("--file-kib", type=int, default=64)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--target-ms", type=float, default=500)
    parser.add_argument("--baseline-store", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument('--batch-size', type=int, default=0,
                        help='Also compare batches of declared native writes (0 disables).')
    parser.add_argument('--current-first', action='store_true', help='Reverse A/B order to check warm-cache bias.')
    parser.add_argument('--signature-samples', type=int, default=0, help='Also rotate serial/4/8 worker metadata scans.')
    args = parser.parse_args()
    if args.files < 1 or args.steps < 1 or args.file_kib < 1 or args.batch_size < 0 or args.signature_samples < 0:
        parser.error("files, steps and file-kib must be positive")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'app'))
    with tempfile.TemporaryDirectory(prefix="myagent-review-benchmark-") as temporary:
        sandbox = Path(temporary)
        if sandbox.resolve().parent != Path(tempfile.gettempdir()).resolve() or not sandbox.name.startswith('myagent-review-benchmark-'):
            raise RuntimeError('benchmark cleanup target is outside its temporary root')
        workspace = sandbox / "repo"
        workspace.mkdir()
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        for index in range(args.files):
            (workspace / f"{index:05}.bin").write_bytes(os.urandom(args.file_kib * 1024))
        (workspace / "edited.txt").write_text("initial\n", encoding="utf-8")
        report = {"files": args.files + 1, "payload_mib": args.files * args.file_kib / 1024,
                  "scope": "review after tool N + review before tool N+1; excludes model, tools and other ReAct work"}
        current = load_store(root / "plugins/change-review/store.py", "benchmark_review_current")
        variants = [('current', current)]
        if args.baseline_store:
            previous = load_store(args.baseline_store, 'benchmark_review_previous')
            variants.insert(0, ('previous', previous))
        if args.current_first:
            variants.reverse()
        report['order'] = [name for name, _module in variants]
        for name, module in variants:
            (workspace / 'edited.txt').write_text('initial\n', encoding='utf-8')
            report[name] = measure(module, sandbox / name, workspace, args.steps)
        if args.batch_size:
            report['batch_size'] = args.batch_size
            report['batch_scope'] = 'sum of native before/after capture plus batch flush; excludes writes, model and host UI delivery'
            def reset_batch():
                for position in range(args.batch_size):
                    (workspace / f'batch-{position}.txt').write_text('initial\n', encoding='utf-8')
            for name, module in variants:
                reset_batch()
                report[name + '_batch'] = measure_batches(module, sandbox / (name + '-batch'), workspace, args.steps, args.batch_size)
        if args.signature_samples:
            report['signatures'] = measure_signatures(current, workspace, args.signature_samples)
        report["target_ms"] = args.target_ms
        report["target_met"] = report["current"]["max_ms"] < args.target_ms
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        def compact(value):
            if not isinstance(value, dict):
                return value
            return {key: (compact(item) if isinstance(item, dict) else item)
                    for key, item in value.items() if key != 'samples'}
        print(json.dumps({key: compact(value) for key, value in report.items()}, indent=2))
        return 0 if report["target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
