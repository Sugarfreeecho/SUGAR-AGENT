import json
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.mark.parametrize("data", [
    {"version": 1, "session_id": "empty", "runs": []},
    {"version": 1, "runs": [{"run_id": "empty", "requests": []},
                            {"run_id": "legacy"}, None]},
    {"version": 1, "extra": {"precision": 2 ** 100, "missing": float("nan")},
     "runs": [{"requests": [{"iteration": i, "model": "中文模型", "values": (i, None)}
                             for i in range(1300)],
               "user_preview": "引用\"、反斜杠\\、换行\n", "finished": True}]},
])
def test_metrics_file_preserves_all_records_and_json_values(tmp_path, monkeypatch, data):
    import execution_metrics

    expected = json.dumps(json.loads(json.dumps(data)), ensure_ascii=False, sort_keys=True)
    if data.get("runs") and isinstance(data["runs"][0], dict):
        run = data["runs"][0]
        if run.get("requests"):
            # Real captured request roots are copy-on-write dict subclasses.
            run["requests"] = [execution_metrics._RequestMetrics(row) for row in run["requests"]]
    target = tmp_path / "execution_metrics.json"
    target.write_text('{"previous":true}', encoding="utf-8")
    monkeypatch.setattr(execution_metrics, "_path", lambda _sid: target)

    execution_metrics._write_now("s1", data)

    actual = json.loads(target.read_text(encoding="utf-8"))
    assert json.dumps(actual, ensure_ascii=False, sort_keys=True) == expected
    assert not target.with_suffix(".json.tmp").exists()
