"""Offline self-check for the bundled thread-monitor plugin.

Runs in a plain Python process (the Agent runtime is not required) and asserts
that the sampler really sees OS threads, folds pool thread names into groups,
tracks history, and never raises.

Usage:
    python scripts/selfcheck_thread_monitor.py          # thread metrics only
    python scripts/selfcheck_thread_monitor.py --full   # also probe host registries
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins" / "thread-monitor"
APP_DIR = ROOT / "app"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def load_monitor():
    path = PLUGIN_DIR / "monitor.py"
    spec = importlib.util.spec_from_file_location("thread_monitor_under_test", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    full = "--full" in sys.argv[1:]
    if not full:
        os.environ.setdefault("THREAD_MONITOR_SKIP_CONCURRENCY", "1")
    os.environ.setdefault("THREAD_MONITOR_INTERVAL_SEC", "0.25")

    monitor_module = load_monitor()
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        if ok:
            print(f"[ok]   {name}")
        else:
            print(f"[FAIL] {name} {detail}")
            failures.append(name)

    # Name folding is the grouping contract.
    check(
        "pool names fold to one group key",
        monitor_module.group_thread_name("myagent-llm-request_3") == "myagent-llm-request_*",
        monitor_module.group_thread_name("myagent-llm-request_3"),
    )
    check(
        "dashed worker names fold too",
        monitor_module.group_thread_name("selftest-worker-11") == "selftest-worker-*",
        monitor_module.group_thread_name("selftest-worker-11"),
    )
    check(
        "digit-free names survive",
        monitor_module.group_thread_name("pending-counts") == "pending-counts",
        monitor_module.group_thread_name("pending-counts"),
    )
    check(
        "empty names get a placeholder",
        monitor_module.group_thread_name("") == "unnamed",
        monitor_module.group_thread_name(""),
    )

    stop = threading.Event()

    def worker() -> None:
        while not stop.is_set():
            time.sleep(0.02)

    workers = [
        threading.Thread(target=worker, name=f"selftest-worker-{i}", daemon=True) for i in range(3)
    ]
    for thread in workers:
        thread.start()

    monitor = monitor_module.ThreadMonitor()
    try:
        first = monitor.sample()
        time.sleep(0.4)
        second = monitor.sample()

        check("sample reports OS threads", first["thread_total"] > 0, f"got {first['thread_total']}")
        names = [row["name"] for row in first["threads"]]
        check(
            "python threads are named",
            any("selftest-worker" in name for name in names),
            str(names[:8]),
        )
        groups = {row["group"] for row in first["thread_groups"]}
        check("worker threads collapse into one group", "selftest-worker-*" in groups, str(sorted(groups)[:12]))
        check(
            "group counts add up",
            sum(int(row["count"]) for row in first["thread_groups"]) == first["thread_total"],
        )
        check("peak tracks the maximum", second["peak_threads"] >= second["thread_total"])
        check("baseline is recorded", second["baseline_threads"] > 0)
        check("no sampler errors", not second["errors"], str(second["errors"]))

        snapshot = monitor.snapshot(history=10)
        for key in (
            "thread_total",
            "thread_groups",
            "concurrency",
            "history",
            "suspected_leaks",
            "process",
            "interval_seconds",
            "leak_suspect_seconds",
        ):
            check(f"snapshot exposes {key}", key in snapshot)
        check("history grows", len(snapshot["history"]) >= 2, str(len(snapshot["history"])))
        check(
            "concurrency block is numeric",
            isinstance(snapshot["concurrency"].get("total"), int),
            str(snapshot["concurrency"].get("total")),
        )
        json.dumps(snapshot)
        check("snapshot is JSON serializable", True)
        check(
            "process block reports this pid",
            int(snapshot["process"].get("pid") or 0) == os.getpid(),
        )

        monitor.start()
        time.sleep(0.9)
        live = monitor.snapshot(history=4)
        check("background ticker runs", live.get("running") is True)
        check("background ticker appends history", len(live["history"]) >= 2)

        monitor.reset_baseline()
        cleared = monitor.snapshot(history=4)
        check("reset clears history", len(cleared["history"]) == 1, str(len(cleared["history"])))
    finally:
        monitor.stop()
        stop.set()
        for thread in workers:
            thread.join(timeout=1.0)

    check("ticker stops cleanly", monitor.running is False)

    if failures:
        print(f"\n{len(failures)} check(s) failed: {failures}")
        return 1
    print("\nAll thread-monitor self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
