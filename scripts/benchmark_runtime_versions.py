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


def measure(fn: Callable[[], Any], repeats: int) -> Dict[str, float]:
    values: List[float] = []
    for _ in range(max(1, int(repeats))):
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000.0)
    return {
        "min_ms": min(values),
        "median_ms": statistics.median(values),
        "p95_ms": percentile(values, 95),
        "max_ms": max(values),
    }


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

    return {
        "session_id": session_id,
        "legacy_ui_count": len(legacy_ui),
        "legacy_model_count": len(legacy_model),
        "runtime_v2_ui_count": len(read_v2_ui_full()),
        "runtime_v2_model_count": len(read_v2_model()),
        "benchmarks": {
            "v1_ui_full": measure(read_v1_ui_full, repeats),
            "v1_ui_page": measure(read_v1_ui_page, repeats),
            "v1_model": measure(read_v1_model, repeats),
            "v2_ui_full": measure(read_v2_ui_full, repeats),
            "v2_ui_page": measure(read_v2_ui_page, repeats),
            "v2_model": measure(read_v2_model, repeats),
        },
    }


def select_sessions(sessions_dir: Path, limit: int, session_id: str = "") -> List[str]:
    if session_id.strip():
        return [session_id.strip()]
    rows = []
    for path in sessions_dir.iterdir() if sessions_dir.exists() else []:
        if not path.is_dir():
            continue
        ui_path = path / "ui_events.json"
        size = ui_path.stat().st_size if ui_path.exists() else 0
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
