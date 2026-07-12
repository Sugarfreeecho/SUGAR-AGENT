from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_runtime_versions import load_json_list  # noqa: E402
from app.runtime_v2 import RuntimeModelProjection, RuntimeUiProjection  # noqa: E402


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[index]


def measure(
    fn: Callable[[], Any],
    repeats: int,
    *,
    before_each: Optional[Callable[[], None]] = None,
) -> Dict[str, float]:
    values: List[float] = []
    for _ in range(max(1, int(repeats))):
        if before_each is not None:
            before_each()
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000.0)
    return {
        "min_ms": min(values),
        "median_ms": statistics.median(values),
        "p95_ms": percentile(values, 95),
        "max_ms": max(values),
    }


def measure_cache_states(
    fn: Callable[[], Any],
    repeats: int,
    *,
    reset_application_cache: Optional[Callable[[], None]] = None,
) -> Dict[str, Dict[str, float]]:
    """Measure application-cache misses separately from warm reads.

    The cold measurement clears only caches owned by this process. It does not
    try to evict the operating-system page cache, which would make this script
    destructive, privileged, and difficult to reproduce.
    """

    cold = measure(fn, repeats, before_each=reset_application_cache)
    if reset_application_cache is not None:
        reset_application_cache()
    fn()  # Excluded warm-up read.
    warm = measure(fn, repeats)
    return {"cold": cold, "warm": warm}


def page_events(events: List[dict], *, limit: int = 200, turns: Optional[int] = None) -> dict:
    total = len(events)
    if turns is not None:
        user_indices = [
            index for index, event in enumerate(events)
            if isinstance(event, dict) and event.get("type") == "user"
        ]
        turn_count = max(1, int(turns))
        if len(user_indices) <= turn_count:
            start = 0
        else:
            start = user_indices[len(user_indices) - turn_count]
        return {"events": events[start:], "total": total}
    lim = max(1, int(limit))
    return {"events": events[max(0, total - lim):], "total": total}


def benchmark_session(sessions_dir: Path, session_id: str, repeats: int, turns: int) -> Dict[str, Any]:
    session_dir = sessions_dir / session_id
    ui_projection = RuntimeUiProjection(sessions_dir)
    model_projection = RuntimeModelProjection(sessions_dir)

    legacy_ui = load_json_list(session_dir / "ui_events.json")
    legacy_model = load_json_list(session_dir / "llm_history.json")

    def read_v1_ui_full() -> List[dict]:
        return load_json_list(session_dir / "ui_events.json")

    def read_v1_ui_page() -> dict:
        return page_events(load_json_list(session_dir / "ui_events.json"), turns=turns)

    def read_v1_model() -> List[dict]:
        return load_json_list(session_dir / "llm_history.json")

    def read_v2_ui_full() -> List[dict]:
        return ui_projection.read_ui_events_fast(session_id)

    def read_v2_ui_page() -> dict:
        return ui_projection.read_ui_page(session_id, turns=turns)

    def read_v2_model() -> List[dict]:
        return model_projection.read_message_dicts(session_id)

    def reset_v2_ui_application_cache() -> None:
        # RuntimeUiProjection caches are process-wide. Do not call
        # invalidate_cache() here because that also deletes the on-disk UI
        # index; a benchmark must not mutate the session being measured.
        key = ui_projection._cache_key(session_id)
        with RuntimeUiProjection._cache_lock:
            RuntimeUiProjection._events_cache.pop(key, None)
            try:
                RuntimeUiProjection._events_cache_order.remove(key)
            except ValueError:
                pass

    storage = session_storage_bytes(session_dir)

    return {
        "session_id": session_id,
        "selection_bytes": storage["selection_bytes"],
        "storage_bytes": storage,
        "legacy_ui_count": len(legacy_ui),
        "legacy_model_count": len(legacy_model),
        "runtime_v2_ui_count": len(read_v2_ui_full()),
        "runtime_v2_model_count": len(read_v2_model()),
        "benchmarks": {
            "v1_ui_full": measure_cache_states(read_v1_ui_full, repeats),
            "v1_ui_page": measure_cache_states(read_v1_ui_page, repeats),
            "v1_model": measure_cache_states(read_v1_model, repeats),
            "v2_ui_full": measure_cache_states(
                read_v2_ui_full,
                repeats,
                reset_application_cache=reset_v2_ui_application_cache,
            ),
            "v2_ui_page": measure_cache_states(
                read_v2_ui_page,
                repeats,
                reset_application_cache=reset_v2_ui_application_cache,
            ),
            "v2_model": measure_cache_states(read_v2_model, repeats),
        },
    }


def _file_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def session_storage_bytes(session_dir: Path) -> Dict[str, int]:
    """Return comparable V1/V2 main-session storage used for selection.

    A pure V2 session may not have ``ui_events.json`` at all. Ranking only by
    that legacy file silently excluded the sessions for which the V2 open path
    matters most. We score each session by its larger active representation.
    """

    legacy_bytes = (
        _file_size(session_dir / "ui_events.json")
        + _file_size(session_dir / "llm_history.json")
    )
    runtime_v2_bytes = (
        _file_size(session_dir / "events.jsonl")
        + _file_size(session_dir / "snapshots" / "latest.json")
    )
    return {
        "legacy_bytes": legacy_bytes,
        "runtime_v2_bytes": runtime_v2_bytes,
        "selection_bytes": max(legacy_bytes, runtime_v2_bytes),
    }


def select_sessions(sessions_dir: Path, limit: int, session_id: str = "") -> List[str]:
    if session_id.strip():
        return [session_id.strip()]
    rows = []
    for path in sessions_dir.iterdir() if sessions_dir.exists() else []:
        if not path.is_dir():
            continue
        size = session_storage_bytes(path)["selection_bytes"]
        rows.append((size, path.name))
    rows.sort(reverse=True)
    return [session_id for _size, session_id in rows[:max(1, int(limit))]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark V1 legacy reads against Runtime V2 projections.")
    parser.add_argument("--sessions-dir", default=str(ROOT / "workspace" / "sessions"))
    parser.add_argument("--session-id", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir)
    sessions = select_sessions(sessions_dir, args.limit, args.session_id)
    results = [benchmark_session(sessions_dir, session_id, args.repeats, args.turns) for session_id in sessions]
    payload = {
        "sessions_dir": str(sessions_dir),
        "repeats": int(args.repeats),
        "turns": int(args.turns),
        "methodology": {
            "selection": "max(legacy_ui_plus_model_bytes, runtime_v2_events_plus_snapshot_bytes)",
            "cold": "application cache cleared where one exists; operating-system page cache retained",
            "warm": "one excluded warm-up read followed by measured reads",
        },
        "sessions": results,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
